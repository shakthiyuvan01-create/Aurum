"""
routes/stream_routes.py — SSE streaming endpoint for Assist Neo
================================================================
Registered as a Flask Blueprint in smith_web.py.

Flow:
    POST /stream  →  agent.run_stream()
                        ↓
                    Plan (function-calling)
                        ↓
                    Execute tools (weather, calc, news, …)
                        ↓
                    Stream final answer (SSE)
"""

from __future__ import annotations
import os, uuid, json, logging
import datetime as _dt

from flask import Blueprint, request, session, jsonify, Response, stream_with_context

stream_bp = Blueprint("stream", __name__)
log = logging.getLogger("routes.stream")


# ── helpers injected by smith_web.py at register time ────────────────────────
#   (avoids circular imports)
_deps: dict = {}

def _init(deps: dict) -> None:
    """Call this from smith_web.py after creating the blueprint to inject deps."""
    _deps.update(deps)


def _db():    return _deps["db"]
def _vmem():  return _deps["vmem"]
def _asst():  return _deps["assistant"]
def _agent(): return _deps["agent"]

def _current_user() -> str:
    return session.get("username", "default")

def _route_model(msg: str, settings: dict) -> str:
    return _deps["route_model"](msg, settings)

def _save_chat(cid, uname, title, messages):
    """Pass uname explicitly — don't rely on session inside a generator."""
    save_fn = _deps["save_chat"]
    import inspect
    # smith_web.save_chat(cid, title, messages) injects username via _current_user()
    # If it accepts username as 4th arg, pass it; otherwise call as-is.
    try:
        sig = inspect.signature(save_fn)
        if len(sig.parameters) >= 4:
            return save_fn(cid, uname, title, messages)
    except Exception:
        pass
    return save_fn(cid, title, messages)


# ── /stream ───────────────────────────────────────────────────────────────────

@stream_bp.route("/stream", methods=["POST"])
def stream_ask():
    if not session.get("auth"):
        return jsonify({"error": "login"}), 401

    body       = request.json or {}
    msg        = body.get("message", "").strip()
    cid        = (body.get("chat_id") or "").strip() or uuid.uuid4().hex[:12]
    uname      = _current_user()
    image_b64  = body.get("image_b64")    # base64 image string (optional)
    image_mime = body.get("image_mime", "image/jpeg")

    if not msg and not image_b64:
        return jsonify({"error": "empty"}), 400
    if not msg and image_b64:
        msg = "What is in this image? Describe it in detail."

    db   = _db()
    vmem = _vmem()
    asst = _asst()
    ag   = _agent()

    # ── chat record ──────────────────────────────────────────────────────
    chat = db.get_chat(cid) or {"id": cid, "title": "", "messages": []}
    if not chat["title"]:
        try:
            title = (asst.ask_ai_brain(
                "Give a 3-word max title for: '" + msg[:80] + "'. Reply ONLY the title.",
                with_context=False) or msg[:40]).strip()[:40]
        except Exception as _e:
            log.debug("title gen failed: %s", _e)
            title = msg[:40]
    else:
        title = chat["title"]

    # ── model routing ────────────────────────────────────────────────────
    settings   = db.get_settings(uname)
    model_key  = _route_model(msg, settings)
    model_name = {
        "code": os.getenv("CODE_MODEL", "gpt-4o"),
        "fast": os.getenv("FAST_MODEL", "gpt-4o-mini"),
        "main": os.getenv("MAIN_MODEL", asst.GITHUB_MODEL),
    }[model_key]
    log.info("stream: user=%s model=%s (%s)", uname, model_name, model_key)

    # ── build history for the agent ──────────────────────────────────────
    chat["messages"].append({"role": "user", "text": msg})
    history_messages = [
        {"role": "user" if m["role"] == "user" else "assistant", "content": m["text"]}
        for m in chat["messages"][-8:-1]    # last N turns, excluding current
    ]

    # ── memory + persona ─────────────────────────────────────────────────
    mem_facts = db.get_memories(uname)
    # Only do vector search for messages long enough to benefit (avoids ChromaDB lag on short msgs)
    sem_mems  = vmem.retrieve_relevant(uname, msg, n=3) if len(msg) > 20 else []
    persona     = settings.get("persona_name", "").strip()
    custom_inst = settings.get("custom_instructions", "").strip()
    asst_name   = persona or asst.ASSISTANT_NAME

    mem_ctx = ""
    if mem_facts:
        mem_ctx += "\n\nThings you remember about the user:\n" + \
                   "\n".join("- " + f for f in mem_facts)
    if sem_mems:
        mem_ctx += "\n\nRelevant past conversations:\n" + "\n---\n".join(sem_mems)

    system_prompt = (
        f"You are {asst_name}, an AI assistant made by Yuvan Industries.\n"
        f"Today is {_dt.datetime.now().strftime('%A, %d %B %Y')}. "
        f"Time: {_dt.datetime.now().strftime('%I:%M %p')}.\n\n"
        "Be direct and genuinely helpful. Match length to complexity. "
        "No filler, no sycophancy, no trailing questions. "
        "Use markdown: **bold**, `code`, code blocks with language tags, "
        "LaTeX for math ($...$).\n"
        + (f"\n\nCustom instructions from user:\n{custom_inst}" if custom_inst else "")
        + mem_ctx
    )

    # ── generator ────────────────────────────────────────────────────────
    def generate():
        reply_text = ""
        try:
            for chunk in ag.run_stream(
                msg             = msg,
                system_prompt   = system_prompt,
                history_messages= history_messages,
                model           = model_name,
                token           = asst.GITHUB_TOKEN or "",
                username        = uname,
                enable_tools    = bool(settings.get("model_routing", 1)),
                image_b64       = image_b64,
                image_mime      = image_mime,
            ):
                # Accumulate delta; suppress agent's raw done (we emit enriched one)
                try:
                    data = json.loads(chunk[len("data: "):].rstrip())
                    if data.get("done"):
                        continue          # skip — we emit enriched done below
                    if data.get("delta"):
                        reply_text += data["delta"]
                except Exception:
                    pass
                yield chunk

        except Exception as e:
            log.error("Stream generator error: %s", e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        # ── persist after streaming + emit enriched done ─────────────
        if reply_text:
            chat["messages"].append({"role": "assistant", "text": reply_text})
            _save_chat(cid, uname, title, chat["messages"])
            try:
                vmem.store_conversation(uname, msg, reply_text, cid)
            except Exception as ve:
                log.warning("vector store failed: %s", ve)
        yield f"data: {json.dumps({'done': True, 'chat_id': cid, 'title': title, 'model': model_key})}\n\n"


    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"X-Accel-Buffering": "no",
                 "Cache-Control": "no-cache"}
    )
