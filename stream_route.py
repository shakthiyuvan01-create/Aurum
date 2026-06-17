# Temporary file — content to inject as /stream route
STREAM_ROUTE = r'''

@app.route("/stream", methods=["POST"])
def stream_ask():
    if not session.get("auth"):
        return jsonify({"error": "login"}), 401
    body  = request.json or {}
    msg   = body.get("message", "").strip()
    cid   = (body.get("chat_id") or "").strip() or uuid.uuid4().hex[:12]
    uname = _current_user() or "default"
    if not msg:
        return jsonify({"error": "empty"}), 400

    import datetime as _dt2, requests as _rq, json as _jj

    chat = _db.get_chat(cid) or {"id": cid, "title": "", "messages": []}
    if not chat["title"]:
        try:
            title = (assistant.ask_ai_brain(
                "Give a 3-word max title for: '" + msg[:80] + "'. Reply ONLY the title.",
                with_context=False) or msg[:40]).strip()[:40]
        except Exception:
            title = msg[:40]
    else:
        title = chat["title"]

    chat["messages"].append({"role": "user", "text": msg})
    assistant._recent_turns.clear()
    for m in chat["messages"][-14:]:
        assistant._recent_turns.append(
            ("you" if m["role"] == "user" else "assistant", m["text"]))

    mem_facts = _db.get_memories(uname)
    mem_ctx = ("\n\nThings you remember about the user:\n" +
               "\n".join("- " + f for f in mem_facts)) if mem_facts else ""
    system_prompt = (
        "You are " + assistant.ASSISTANT_NAME + ", an AI assistant made by Yuvan Industries.\n"
        "Today is " + _dt2.datetime.now().strftime('%A, %d %B %Y') + ". "
        "Time: " + _dt2.datetime.now().strftime('%I:%M %p') + ".\n\n"
        "Be direct and genuinely helpful. Match length to complexity. "
        "No filler, no sycophancy, no trailing questions. "
        "Use markdown: **bold**, `code`, code blocks with language tags, LaTeX for math ($...$).\n"
        + mem_ctx
    )
    history = "\n".join(
        ("User" if r == "you" else "Assistant") + ": " + t
        for r, t in assistant._recent_turns[-14:]
    )

    def generate():
        full_reply = []
        try:
            resp = _rq.post(
                "https://models.inference.ai.azure.com/chat/completions",
                headers={"Authorization": "Bearer " + (assistant.GITHUB_TOKEN or ""),
                         "Content-Type": "application/json"},
                json={
                    "model": assistant.GITHUB_MODEL,
                    "temperature": 0.7,
                    "max_tokens": 1500,
                    "stream": True,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": history + "\nUser: " + msg}
                    ]
                },
                stream=True, timeout=60
            )
            for line in resp.iter_lines():
                if not line:
                    continue
                decoded = line.decode("utf-8")
                if not decoded.startswith("data: "):
                    continue
                data = decoded[6:]
                if data == "[DONE]":
                    break
                try:
                    chunk = _jj.loads(data)
                    delta = chunk["choices"][0]["delta"].get("content", "")
                    if delta:
                        full_reply.append(delta)
                        yield "data: " + _jj.dumps({"delta": delta}) + "\n\n"
                except Exception:
                    pass
        except Exception as e:
            log.error("Stream error: %s", e)
            yield "data: " + _jj.dumps({"error": str(e)}) + "\n\n"
            return

        reply_text = "".join(full_reply)
        chat["messages"].append({"role": "assistant", "text": reply_text})
        save_chat(cid, title, chat["messages"])
        assistant._recent_turns.append(("assistant", reply_text))
        yield "data: " + _jj.dumps({"done": True, "chat_id": cid, "title": title}) + "\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
'''
