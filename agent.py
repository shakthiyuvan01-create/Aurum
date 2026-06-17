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

GITHUB_API = "https://models.inference.ai.azure.com/chat/completions"

# Tools excluded from the auto-schema (too dangerous / not suited for chat)
_EXCLUDE_FROM_AGENT = {"code_runner", "git"}

# Max tool-call rounds per turn (prevents infinite loops)
MAX_ROUNDS = 4


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _chat(messages: list, model: str, token: str,
          tools_schema: list | None = None,
          stream: bool = False, temperature: float = 0.7,
          max_tokens: int = 1800) -> _rq.Response:
    payload: dict = {
        "model":       model,
        "messages":    messages,
        "temperature": temperature,
        "max_tokens":  max_tokens,
        "stream":      stream,
    }
    if tools_schema:
        payload["tools"]       = tools_schema
        payload["tool_choice"] = "auto"
    return _rq.post(GITHUB_API, headers=_headers(token),
                    json=payload, stream=stream, timeout=90)


# ── Public entry point ────────────────────────────────────────────────────────

def run_stream(
    msg: str,
    system_prompt: str,
    history_messages: list,          # list of {"role":…, "content":…}
    model: str,
    token: str,
    username: str = "default",
    enable_tools: bool = True,
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
    messages.append({"role": "user", "content": msg})

    tools_used: list[str] = []

    # ── Phase 1 & 2: Plan + Execute (non-streaming, repeating) ───────────────
    for _round in range(MAX_ROUNDS):
        try:
            resp = _chat(messages, model, token,
                         tools_schema=all_tools if all_tools else None,
                         stream=False)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.error("Agent plan call failed (round %d): %s", _round, e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        choice  = data["choices"][0]
        message = choice["message"]
        finish  = choice.get("finish_reason", "stop")

        # ── No tool calls → done planning, go stream ──────────────────────
        if finish != "tool_calls" or not message.get("tool_calls"):
            break

        # ── Execute each tool call ────────────────────────────────────────
        messages.append(message)   # assistant message with tool_calls

        for tc in message["tool_calls"]:
            tname  = tc["function"]["name"]
            tc_id  = tc.get("id", tname)
            log.info("Agent executing tool: %s", tname)
            result = _tools.call_from_openai(tc, username=username)
            tools_used.append(tname)

            # Notify UI so it can show a "🔧 Used weather" chip
            yield f"data: {json.dumps({'tool_used': tname, 'result': result[:300]})}\n\n"

            messages.append({
                "role":         "tool",
                "tool_call_id": tc_id,
                "content":      result,
            })

    # ── Phase 3: Stream final answer ─────────────────────────────────────────
    try:
        stream_resp = _chat(messages, model, token,
                            tools_schema=None,   # no more tool calls in answer phase
                            stream=True)
        stream_resp.raise_for_status()
    except Exception as e:
        log.error("Agent stream call failed: %s", e)
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        return

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
                yield f"data: {json.dumps({'delta': delta})}\n\n"
        except Exception:
            pass

    reply_text = "".join(full_reply)
    yield f"data: {json.dumps({'done': True, 'reply': reply_text, 'model': model, 'tools_used': tools_used})}\n\n"
