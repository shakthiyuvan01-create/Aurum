"""
agent.py — Planner + ReAct tool-calling agent for Assist Neo
=============================================================
Architecture:
    User question
        ↓
    [Phase 1 – Plan]  one non-streaming call with all tools attached
        → LLM either replies directly OR emits one or more tool_calls
        ↓
    [Phase 2 – Execute]  run each tool, collect results
        ↓
    [Phase 3 – Answer]  streaming call with tool results injected
        → yields SSE chunks: {"delta": "..."} … {"done": True, ...}

This module is intentionally stateless — all context is passed in per call.
"""

from __future__ import annotations
import json, logging, os
import requests as _rq
import tools as _tools

log = logging.getLogger("agent")

GITHUB_API   = "https://models.inference.ai.azure.com/chat/completions"
OLLAMA_API   = os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/v1/chat/completions"
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")

# Tools excluded from the auto-schema (too dangerous / not suited for chat)
_EXCLUDE_FROM_AGENT = {"code_runner", "git"}

# Max tool-call rounds per turn (2 is enough for 99% of queries)
MAX_ROUNDS = 2

_SSE_END = "\n\n"


def _is_token_valid(token: str) -> bool:
    """Return True if a non-empty, non-placeholder token exists."""
    return bool(token and token.strip() and token != "your_github_token_here")


def _is_ollama_up() -> bool:
    """Quick 2-second ping — returns True if Ollama is reachable."""
    try:
        base = OLLAMA_API.replace("/v1/chat/completions", "/")
        r = _rq.get(base, timeout=2)
        return r.status_code < 500
    except Exception as _e:
        log.debug("Ollama health check failed: %s", _e)
        return False


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _chat(messages: list, model: str, token: str,
          tools_schema: list | None = None,
          stream: bool = False, temperature: float = 0.6,
          max_tokens: int = 1200,
          use_ollama: bool = False,
          ollama_model: str | None = None) -> _rq.Response:
    payload: dict = {
        "model":       (ollama_model or OLLAMA_MODEL) if use_ollama else model,
        "messages":    messages,
        "temperature": temperature,
        "max_tokens":  max_tokens,
        "stream":      stream,
    }
    if tools_schema and not use_ollama:
        # Ollama tool-calling support varies by model; skip tools to be safe
        payload["tools"]       = tools_schema
        payload["tool_choice"] = "auto"
    if use_ollama:
        return _rq.post(OLLAMA_API,
                        headers={"Content-Type": "application/json"},
                        json=payload, stream=stream, timeout=60)
    return _rq.post(GITHUB_API, headers=_headers(token),
                    json=payload, stream=stream, timeout=45)


def _should_fallback(err: Exception) -> bool:
    """Return True when the error looks like an auth failure."""
    s = str(err)
    return "401" in s or "403" in s or "invalid" in s.lower()


def _sse(payload: dict) -> str:
    return "data: " + json.dumps(payload) + "\n\n"


# ── Public entry point ────────────────────────────────────────────────────────

def _provider_rescue(messages: list, model: str):
    """Last-resort: answer through the provider chain (Nara/Gemini/OpenAI/
    Ollama) without tools. Returns (reply, provider_name) or (None, None)."""
    try:
        from providers import AI
        # If the last user message contains an image, try Gemini vision first
        try:
            last = messages[-1] if messages else {}
            if isinstance(last.get("content"), list):
                img = next((x["image_url"]["url"] for x in last["content"]
                            if isinstance(x, dict) and x.get("type") == "image_url"), None)
                txt = next((x.get("text", "") for x in last["content"]
                            if isinstance(x, dict) and x.get("type") == "text"), "")
                if img and img.startswith("data:"):
                    header, b64 = img.split(",", 1)
                    mime = header.split(":")[1].split(";")[0]
                    from providers.gemini import GeminiProvider
                    g = GeminiProvider()
                    if g.available():
                        return g.vision(txt, b64, mime=mime), "gemini-vision"
        except Exception as ve:
            log.debug("vision rescue failed: %s", ve)
        plain = []
        for m in messages:
            c = m.get("content")
            if isinstance(c, list):  # multimodal -> keep only the text parts
                c = " ".join(x.get("text", "") for x in c if isinstance(x, dict))
            if c and m.get("role") in ("system", "user", "assistant"):
                plain.append({"role": m["role"], "content": str(c)})
        reply = AI.chat(plain, model=model, max_tokens=1600, temperature=0.4)
        if reply and not reply.startswith("[AI error"):
            return reply, (AI.last_used or "fallback")
    except Exception as e:
        log.error("provider rescue failed: %s", e)
    return None, None


def run_stream(
    msg: str,
    system_prompt: str,
    history_messages: list,          # list of {"role":…, "content":…}
    model: str,
    token: str,
    username: str = "default",
    enable_tools: bool = True,
    image_b64: str | None = None,    # base64 image for vision queries
    image_mime: str = "image/jpeg",  # mime type of the image
) -> "Generator[str, None, None]":   # yields raw SSE strings
    """Main agent entry.

    Yields SSE strings:
        data: {"delta": "…"}\\n\\n
        data: {"tool_used": "weather", "result": "…"}\\n\\n   (optional, for UI)
        data: {"done": true, "model": "…", "tools_used": […]}\\n\\n
    """
    all_tools = _tools.to_openai_tools(exclude=_EXCLUDE_FROM_AGENT) if enable_tools else []

    # Build initial message list
    messages: list = [{"role": "system", "content": system_prompt}]
    messages.extend(history_messages)

    # ── Multimodal user message (image + text) ────────────────────────────────
    if image_b64:
        data_url   = f"data:{image_mime};base64,{image_b64}"
        user_content = [
            {"type": "text",      "text": msg or "What is in this image?"},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]
        messages.append({"role": "user", "content": user_content})
    else:
        messages.append({"role": "user", "content": msg})

    tools_used: list[str] = []

    # ── Decide upfront: GitHub Models or Ollama? ──────────────────────────────
    use_ollama   = not _is_token_valid(token)
    # When image is attached and using Ollama, switch to llava vision model
    ollama_model = ("llava" if image_b64 else OLLAMA_MODEL)
    if use_ollama:
        if not _is_ollama_up():
            yield _sse({"error": "⚠️ No GitHub token set and Ollama is not running. "
                                  "Add GITHUB_TOKEN to .env or start Ollama."})
            return
        note = "*(using local Ollama — " + OLLAMA_MODEL + ")*\n\n"
        yield _sse({"delta": note})

    # ── Phase 1 & 2: Plan + Execute (non-streaming, up to MAX_ROUNDS) ─────────
    # Plan phase uses fewer tokens — we only need tool_call decisions or a
    # short direct answer, not a full streamed response.
    _PLAN_MAX_TOKENS = 600
    for _round in range(MAX_ROUNDS):
        try:
            resp = _chat(messages, model, token,
                         tools_schema=all_tools if (all_tools and not use_ollama) else None,
                         stream=False, temperature=0.3,
                         max_tokens=_PLAN_MAX_TOKENS,
                         use_ollama=use_ollama, ollama_model=ollama_model)
            resp.raise_for_status()
            data = resp.json()

        except Exception as e:
            log.error("Agent plan call failed (round %d): %s", _round, e)
            # UNIVERSAL FALLBACK: on ANY failure (429/401/403/500/503/timeout),
            # try the full provider chain (Nara -> GitHub -> BluesMinds ->
            # Gemini -> OpenAI -> Ollama). Works on phone, Render and PC.
            reply, used = _provider_rescue(messages, model)
            if reply and not reply.startswith("[AI error"):
                yield _sse({"delta": reply})
                yield _sse({"done": True, "reply": reply,
                            "model": used, "tools_used": tools_used})
                return
            if True:
                err_str = str(e)
                try:
                    from providers import AI as _AIe
                    if _AIe.last_errors:
                        err_str += " | fallbacks: " + "; ".join(_AIe.last_errors[-4:])
                except Exception:
                    pass
                if "429" in err_str.split(" | ")[0]:
                    err_msg = ("⚠️ Rate limit on the primary AI, and every fallback "
                               "also failed. Details: " + err_str[:400] +
                               " -- open /providers/test to diagnose keys.")
                elif "503" in err_str:
                    err_msg = "⚠️ The AI service is temporarily unavailable (503) and no fallback provider answered. Check your API keys in .env."
                elif "timeout" in err_str.lower():
                    err_msg = "⚠️ Request timed out. Please try again."
                else:
                    err_msg = "⚠️ " + err_str
                yield _sse({"error": err_msg})
                return

        choice  = data["choices"][0]
        message = choice["message"]
        finish  = choice.get("finish_reason", "stop")

        # ── No tool calls → done planning, proceed to stream answer ───────
        if finish != "tool_calls" or not message.get("tool_calls"):
            break

        # ── Ollama: no tool execution, treat response as final ────────────
        if use_ollama:
            break

        # ── Execute tool calls concurrently ─────────────────────────────
        messages.append(message)
        tool_calls_list = message["tool_calls"]

        if len(tool_calls_list) > 1:
            log.info("Agent running %d tools concurrently: %s",
                     len(tool_calls_list),
                     [tc["function"]["name"] for tc in tool_calls_list])
            results = _tools.call_multiple_concurrent(tool_calls_list, username=username)
        else:
            results = [_tools.call_from_openai(tool_calls_list[0], username=username)]

        for tc, result in zip(tool_calls_list, results):
            tname = tc["function"]["name"]
            tc_id = tc.get("id", tname)
            tools_used.append(tname)
            yield _sse({"tool_used": tname, "result": result[:300]})
            messages.append({
                "role":         "tool",
                "tool_call_id": tc_id,
                "content":      result,
            })

    # ── Phase 3: Stream final answer ─────────────────────────────────────────
    try:
        stream_resp = _chat(messages, model, token,
                            tools_schema=None,
                            stream=True, use_ollama=use_ollama, ollama_model=ollama_model)
        stream_resp.raise_for_status()

    except Exception as e:
        # UNIVERSAL FALLBACK at stream phase: full provider chain on ANY error.
        reply, used = _provider_rescue(messages, model)
        if reply and not reply.startswith("[AI error"):
            yield _sse({"delta": reply})
            yield _sse({"done": True, "reply": reply,
                        "model": used, "tools_used": tools_used})
            return
        if True:
            err_str = str(e)
            if "401" in err_str or "403" in err_str:
                err_msg = "⚠️ GitHub token expired or invalid. Update GITHUB_TOKEN in your .env and restart."
            elif "429" in err_str:
                err_msg = "⚠️ API rate limit hit. Please wait a moment and try again."
            elif "timeout" in err_str.lower():
                err_msg = "⚠️ Request timed out. Please try again."
            else:
                err_msg = "⚠️ " + err_str
            yield _sse({"error": err_msg})
            return

    active_model = ("ollama/" + OLLAMA_MODEL) if use_ollama else model
    full_reply: list[str] = []

    for line in stream_resp.iter_lines():
        if not line:
            continue
        decoded = line.decode("utf-8") if isinstance(line, bytes) else line
        if not decoded.startswith("data: "):
            continue
        raw = decoded[6:]
        if raw == "[DONE]":
            break
        try:
            chunk = json.loads(raw)
            delta = chunk["choices"][0]["delta"].get("content", "")
            if delta:
                full_reply.append(delta)
                yield _sse({"delta": delta})
        except Exception as _chunk_err:
            log.debug("SSE chunk parse skip: %s", _chunk_err)

    reply_text = "".join(full_reply)
    yield _sse({"done": True, "reply": reply_text,
                "model": active_model, "tools_used": tools_used})
