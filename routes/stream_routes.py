"""
routes/stream_routes.py -- SSE streaming endpoint for AI Aurum
"""
from __future__ import annotations
import os, uuid, json, logging
import datetime as _dt

from flask import Blueprint, request, session, jsonify, Response, stream_with_context
from services.auth_service import login_required

stream_bp = Blueprint("stream", __name__)
log = logging.getLogger("routes.stream")

_deps: dict = {}

def _init(deps: dict) -> None:
    _deps.update(deps)

def _db():    return _deps["db"]
def _vmem():  return _deps["vmem"]
def _asst():  return _deps["assistant"]
def _agent(): return _deps["agent"]

def _current_user() -> str:
    return session.get("username", "default")

def _route_model(msg: str, settings: dict) -> str:
    return _deps["route_model"](msg, settings)

_RULE_RE = None

def _maybe_learn_rule(uname: str, msg: str, db) -> bool:
    """Detect standing instructions ("always...", "never...", "from now on...",
    "remember that...") and store them as rules. Stored rules are auto-injected
    into every future prompt via the existing memory step."""
    global _RULE_RE
    import re as _re
    if _RULE_RE is None:
        _RULE_RE = _re.compile(
            r"^(always|never|from now on|remember (that|to)|rule\s*:|going forward)\b",
            _re.I)
    m = (msg or "").strip()
    if len(m) < 12 or len(m) > 400 or not _RULE_RE.search(m):
        return False
    try:
        db.add_memory(uname, "STANDING RULE: " + m)
        log.info("learned rule for %s: %s", uname, m[:80])
        return True
    except Exception as e:
        log.debug("rule store failed: %s", e)
        return False


def _extract_knowledge(uname: str, msg: str, reply: str) -> None:
    """Background: update the live knowledge graph from this conversation."""
    try:
        from services.permission_manager import perms
        if not perms.check("background_ai"):
            return
        from providers import AI
        import json as _json, re as _re
        raw = AI.generate(
            "Extract factual entity relationships from this exchange as JSON:\n"
            '{"relations": [["source", "relation", "target"], ...]}\n'
            "Max 4 relations, only real facts about people/projects/companies/"
            "technologies. Reply ONLY JSON, or {\"relations\": []} if none.\n\n"
            "User: %s\nAssistant: %s" % (msg[:500], reply[:800]),
            model="gpt-4o-mini", max_tokens=150, temperature=0.1)
        m = _re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return
        rels = _json.loads(m.group(0)).get("relations", [])[:4]
        if rels:
            from services.memory_layers import mem
            for r in rels:
                if isinstance(r, list) and len(r) == 3 and all(isinstance(x, str) for x in r):
                    mem.knowledge.add_relation(uname, r[0][:60], r[1][:40], r[2][:60])
            log.debug("kg: +%d relations for %s", len(rels), uname)
    except Exception as e:
        log.debug("kg extraction skipped: %s", e)


def _smart_title(msg: str, reply: str) -> str:
    """AI-generated descriptive chat title: 'hi' -> 'Greeting exchange',
    'what is coding' -> 'Coding basics'. Falls back to the raw message."""
    try:
        from providers import AI
        t = AI.generate(
            "Create a short descriptive title (2-4 words) for a chat that starts "
            "with this exchange. Examples: 'hi' -> Greeting exchange; "
            "'what is coding' -> Coding basics; 'fix my python error' -> Python debugging.\n"
            "Reply with ONLY the title, no quotes, no punctuation at the end.\n\n"
            "User: %s\nAssistant: %s" % (msg[:300], reply[:300]),
            model=os.getenv("FAST_MODEL", "gpt-4o-mini"),
            max_tokens=12, temperature=0.2)
        t = t.strip().strip('"').strip("'").rstrip(".")
        if t and not t.startswith("[AI error") and 1 <= len(t) <= 60:
            return t[:40]
    except Exception as e:
        log.debug("smart title failed: %s", e)
    return (msg[:40] if msg else "Chat")


def _save_chat(cid, uname, title, messages):
    _deps["db"].save_chat(cid, uname, title, messages)


@stream_bp.route("/stream", methods=["POST"])
@login_required
def stream():
    db   = _db()
    vmem = _vmem()
    asst = _asst()
    ag   = _agent()

    data       = request.get_json(force=True) or {}
    msg        = (data.get("message") or "").strip()
    cid        = data.get("chat_id") or uuid.uuid4().hex
    image_b64  = data.get("image_b64")
    image_mime = data.get("image_mime", "image/jpeg")
    uname      = _current_user()

    if not msg and not image_b64:
        return jsonify({"error": "No message"}), 400

    # -- Observability: start a trace for this request -----------------------
    _trace_id = ""
    try:
        from services.tracer import tracer as _tracer
        _trace_id = _tracer.start_trace(
            username=uname,
            description=(msg or "image")[:80],
        )
    except Exception:
        pass

    # Guest sessions: no persistent chat load/save
    is_guest = session.get("is_guest", False)

    if is_guest:
        chat = {"id": cid, "title": msg[:40] if msg else "Chat", "messages": []}
        is_new_chat = True
    else:
        _existing = db.get_chat(cid)
        is_new_chat = _existing is None
        chat = _existing or {"id": cid, "title": msg[:40] if msg else "Chat", "messages": []}

    settings = db.get_settings(uname) if not is_guest else {}
    rule_learned = False if is_guest else _maybe_learn_rule(uname, msg, db)
    title    = chat.get("title") or (msg[:40] if msg else "Chat")

    model_key  = _route_model(msg, settings)
    model_name = {
        "code":   os.getenv("CODE_MODEL",   "gpt-4o"),
        "fast":   os.getenv("FAST_MODEL",   "gpt-4o-mini"),
        "main":   os.getenv("MAIN_MODEL",   asst.GITHUB_MODEL),
        "vision": os.getenv("VISION_MODEL", "gpt-4o"),
        "reason": os.getenv("REASON_MODEL", "o1-mini"),
    }.get(model_key, os.getenv("MAIN_MODEL", asst.GITHUB_MODEL))
    log.info("stream: user=%s model=%s (%s)", uname, model_name, model_key)

    chat["messages"].append({"role": "user", "text": msg})
    history_messages = [
        {"role": "user" if m["role"] == "user" else "assistant", "content": m["text"]}
        for m in chat["messages"][-6:-1]
    ]

    mem_facts = db.get_memories(uname) if not is_guest else []
    sem_mems  = vmem.retrieve_relevant(uname, msg, n=2) if (not is_guest and len(msg) >= 40) else []
    persona     = settings.get("persona_name", "").strip()
    custom_inst = settings.get("custom_instructions", "").strip()
    asst_name   = persona or asst.ASSISTANT_NAME

    mem_ctx = ""
    if mem_facts:
        mem_ctx += "\n\nThings you remember about the user:\n" + \
                   "\n".join("- " + f for f in mem_facts)
    if sem_mems:
        mem_ctx += "\n\nRelevant past conversations:\n" + "\n---\n".join(sem_mems)

    # MemorySystem (5-tier): working + knowledge-graph + archive layers
    if not is_guest and len(msg) >= 20:
        try:
            from services.memory_layers import mem as _mem_sys
            extra = _mem_sys.context_string(uname, msg)
            if extra:
                mem_ctx += "\n\n" + extra
        except Exception as _mle:
            log.debug("memory_layers context skipped: %s", _mle)

    # -- Project context (persistent across sessions) ------------------------
    proj_ctx = ""
    if not is_guest:
        try:
            pc = db.get_project_context(uname)
            if pc.get("name"):
                proj_ctx = f"\n\nActive project: **{pc['name']}**"
                if pc.get("description"):
                    proj_ctx += f"\nDescription: {pc['description']}"
                stack = pc.get("tech_stack") or []
                if isinstance(stack, list) and stack:
                    proj_ctx += f"\nStack: {', '.join(stack)}"
                if pc.get("goals"):
                    proj_ctx += f"\nGoals: {pc['goals']}"
        except Exception as _pe:
            log.debug("project context fetch failed: %s", _pe)

    # -- Relevant skills -----------------------------------------------------
    skills_ctx = ""
    if not is_guest and len(msg) >= 30:
        try:
            relevant_skills = db.search_skills(uname, msg, limit=2)
            if relevant_skills:
                skill_lines = [f"### {s['name']}\n{s['content'][:400]}" for s in relevant_skills]
                skills_ctx = ("\n\nRelevant saved skills (proven solutions -- prefer these):\n"
                              + "\n---\n".join(skill_lines))
        except Exception as _se:
            log.debug("skills context fetch failed: %s", _se)

    # Pick up self-eval hint from the previous turn (if any)
    eval_hint_ctx = ""
    if not is_guest:
        eval_hint_ctx = session.pop("_eval_hint", "") or ""

    system_prompt = (
        f"You are {asst_name}, an AI assistant made by Yuvan Industries.\n"
        f"Today is {_dt.datetime.now().strftime('%A, %d %B %Y')}. "
        f"Time: {_dt.datetime.now().strftime('%I:%M %p')}.\n\n"
        "Be direct and genuinely helpful. Match length to complexity. "
        "No filler, no sycophancy, no trailing questions. "
        "Use markdown: **bold**, `code`, code blocks with language tags, "
        "LaTeX for math ($...$).\n"
        + (f"\n\nCustom instructions from user:\n{custom_inst}" if custom_inst else "")
        + proj_ctx
        + mem_ctx
        + skills_ctx
        + eval_hint_ctx
    )

    def generate():
        reply_text = ""
        try:
            for chunk in ag.run_stream(
                msg              = msg,
                system_prompt    = system_prompt,
                history_messages = history_messages,
                model            = model_name,
                token            = asst.GITHUB_TOKEN or "",
                username         = uname,
                enable_tools     = bool(settings.get("model_routing", 1)),
                image_b64        = image_b64,
                image_mime       = image_mime,
            ):
                parsed = json.loads(chunk[len("data: "):].strip()) if chunk.startswith("data: ") else {}
                if parsed.get("done"):
                    reply_text = parsed.get("reply", reply_text)
                    continue
                yield chunk
        except Exception as e:
            log.error("stream generate error: %s", e)
            yield "data: " + json.dumps({"error": str(e)}) + "\n\n"
            return

        chat["messages"].append({"role": "assistant", "text": reply_text})
        if is_new_chat and msg:
            title = _smart_title(msg, reply_text)
        if not is_guest:
            _save_chat(cid, uname, title, chat["messages"])
            try:
                vmem.store_conversation(uname, msg, reply_text, cid)
            except Exception as ve:
                log.warning("vector store failed: %s", ve)
            # live knowledge graph update (background thread, zero latency)
            try:
                import threading as _th
                _th.Thread(target=_extract_knowledge,
                           args=(uname, msg, reply_text), daemon=True).start()
            except Exception:
                pass

        # self-evaluation -- async, best-effort
        eval_hint = ""
        _confidence = None
        try:
            import self_eval as _se
            _eval = _se.evaluate(msg, reply_text)
            if not _eval.get("skipped"):
                _confidence = round(100 * float(_eval.get("overall", 0)))
            eval_hint = _se.hint_for_next_turn(_eval)
            if eval_hint and not is_guest:
                try:
                    session["_eval_hint"] = eval_hint
                except Exception:
                    pass
        except Exception as _ee:
            log.debug("self_eval skipped: %s", _ee)

        # close trace
        try:
            from services.tracer import tracer as _tracer
            if _trace_id:
                _tracer.add_event(_trace_id, "response_sent",
                                  {"chars": len(reply_text), "model": model_name})
                _tracer.end_trace(_trace_id, status="ok")
        except Exception:
            pass

        done_payload: dict = {
            "done":     True,
            "confidence": _confidence,
            "rule_learned": rule_learned,
            "chat_id":  cid,
            "title":    title,
            "model":    model_name,
            "trace_id": _trace_id,
        }
        if eval_hint:
            done_payload["eval_warning"] = True
        yield "data: " + json.dumps(done_payload) + "\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
