"""
routes/chat.py — /ask (non-stream), /chats CRUD, /greet, /project, /memory
"""
import os, uuid, logging, re
from flask import Blueprint, request, session, jsonify, render_template, redirect
from services.auth_service import login_required, current_user, no_guests, current_nick

chat_bp = Blueprint("chat", __name__)
log = logging.getLogger("routes.chat")

_deps: dict = {}

def _init(deps: dict) -> None:
    _deps.update(deps)

def _db():       return _deps["db"]
def _vmem():     return _deps["vmem"]
def _asst():     return _deps["assistant"]
def _brain():    return _deps["brain"]   # project-aware brain function


# ── home ─────────────────────────────────────────────────────────────────────

@chat_bp.route("/")
def home():
    return render_template("index.html",
                           ANAME=_asst().ASSISTANT_NAME,
                           UNAME=current_nick() or "there",
                           IS_GUEST=session.get("is_guest", False))


@chat_bp.route("/greet")
def greet():
    from services.auth_service import current_nick as _nick
    proj_name = _deps.get("current_project", lambda: "General")()
    uname = _nick() or "there"
    hello = _asst().time_greeting()
    proj  = (" You're in %s mode." % proj_name) if proj_name != "General" else ""
    return jsonify({"reply": "%s, %s!%s How can I help you today?" % (hello, uname, proj)})


@chat_bp.route("/project", methods=["POST"])
def project():
    set_proj = _deps.get("set_project")
    name = (request.json or {}).get("name", "General")
    if set_proj:
        set_proj(name)
    try:
        _asst()._recent_turns.clear()
    except Exception as e:
        log.warning("Could not clear turns: %s", e)
    return jsonify({"ok": True})


# ── /ask  (non-streaming) ─────────────────────────────────────────────────────

@chat_bp.route("/ask", methods=["POST"])
def ask():
    log.info("ask: user=%s", current_user())
    body  = request.json or {}
    msg   = body.get("message", "").strip()
    cid   = (body.get("chat_id") or "").strip() or uuid.uuid4().hex[:12]
    uname = current_user() or "default"
    asst  = _asst()
    db    = _db()
    brain = _brain()

    if not msg:
        return jsonify({"reply": ""})

    chat = db.get_chat(cid) or {"id": cid, "title": "", "messages": []}

    # title
    if not chat["title"]:
        try:
            title = (asst.ask_ai_brain(
                "Give a 3-word max title for this chat topic: '%s'. Reply ONLY the short title." % msg,
                with_context=False) or msg[:40]).strip()[:40]
        except Exception as _e:
            log.debug("title gen failed: %s", _e)
            title = msg[:40]
    else:
        title = chat["title"]

    chat["messages"].append({"role": "user", "text": msg})

    # load history
    asst._recent_turns.clear()
    for m in chat["messages"][-14:]:
        role = "you" if m["role"] == "user" else "assistant"
        asst._recent_turns.append((role, m["text"]))

    # short-reply continuation
    short_replies = {"yes", "ok", "okay", "yeah", "sure", "continue", "go on"}
    if msg.lower() in short_replies and len(chat["messages"]) > 1:
        for m in reversed(chat["messages"][:-1]):
            if m["role"] == "user":
                msg = "The user replied '%s'. Continue the previous discussion naturally. Previous topic:\n%s" % (
                    msg, m["text"])
                break

    capture = []

    # image generation
    _IMG_TRIGGERS = [
        "create an image", "generate an image", "make an image", "draw an image",
        "generate image of", "create image of", "make image of", "draw a picture",
        "create a picture", "generate a picture", "make a picture", "create a photo",
        "generate a photo", "paint a", "draw a", "render an image",
        "image of ", "picture of ", "illustration of ",
    ]
    if any(t in msg.lower() for t in _IMG_TRIGGERS):
        try:
            UPLOAD_DIR = _deps.get("upload_dir", "uploads")
            img_path = asst.create_image(msg)
            if img_path and os.path.exists(img_path):
                import shutil
                fname = os.path.basename(img_path)
                dest  = os.path.join(UPLOAD_DIR, fname)
                if not os.path.exists(dest):
                    shutil.copy2(img_path, dest)
                capture.append("[IMAGE]/uploads/" + fname)
            else:
                capture.append("Image generation failed.")
        except Exception as ie:
            log.error("Image generation: %s", ie)
            capture.append("Image generation error: %s" % ie)
    else:
        try:
            reply = brain(msg, with_context=True)
            if reply:
                reply = re.sub(r"^(let me search.*?\.)\s*", "", reply, flags=re.IGNORECASE).strip()
            capture.append(reply or "I couldn't answer that.")
        except Exception as e:
            log.exception("Ask error")
            capture.append("(Error: %s)" % e)

    reply = "\n\n".join(capture) or "..."
    reply = re.sub(r"^(let me search.*?\.)\s*", "", reply, flags=re.IGNORECASE).strip() or "..."

    # image reply formatting
    if reply.startswith("[IMAGE]"):
        img_path = reply.replace("[IMAGE]", "").strip()
        fname    = os.path.basename(img_path)
        UPLOAD_DIR = _deps.get("upload_dir", "uploads")
        import shutil
        dest = os.path.join(UPLOAD_DIR, fname)
        try:
            if not os.path.exists(dest):
                shutil.copy2(img_path, dest)
        except Exception as e:
            log.warning("Image copy: %s", e)
        reply = "[IMAGE]/uploads/" + fname

    chat["messages"].append({"role": "smith", "text": reply})
    db.save_chat(cid, uname, title, chat["messages"])
    return jsonify({"reply": reply, "chat_id": cid})


# ── chat CRUD ─────────────────────────────────────────────────────────────────

@chat_bp.route("/chats")
def chats():
    log.debug("list chats: user=%s", current_user())
    uname = current_user() or "default"
    return jsonify(_db().list_chats(uname))


@chat_bp.route("/chat/<cid>")
def get_chat_route(cid):
    chat = _db().get_chat(cid)
    if not chat:
        return jsonify({"error": "not found"}), 404
    return jsonify(chat)


@chat_bp.route("/chats/<cid>", methods=["DELETE"])
@login_required
def delete_chat_route(cid):
    _db().delete_chat(cid, current_user())
    return jsonify({"ok": True})


@chat_bp.route("/chats/<cid>/rename", methods=["POST"])
@login_required
def rename_chat_route(cid):
    title = (request.json or {}).get("title", "").strip()
    if title:
        _db().rename_chat(cid, current_user(), title)
    return jsonify({"ok": True})


# ── memory routes ─────────────────────────────────────────────────────────────

@chat_bp.route("/memory", methods=["GET", "POST"])
def memory_route():
    uname = current_user()
    if not uname:
        return jsonify({"error": "login"}), 401
    db = _db()
    if request.method == "GET":
        return jsonify({"memories": db.get_memories(uname)})
    body   = request.json or {}
    action = body.get("action", "")
    if action == "save":
        fact = body.get("fact", "").strip()
        if fact:
            db.add_memory(uname, fact)
        return jsonify({"ok": True, "memories": db.get_memories(uname)})
    if action == "clear":
        db.clear_memories(uname)
        return jsonify({"ok": True, "memories": []})
    return jsonify({"error": "unknown action"})


@chat_bp.route("/memory/vector_clear", methods=["POST"])
@login_required
@no_guests
def vector_clear_route():
    _vmem().clear_user_memory(current_user())
    return jsonify({"ok": True})
