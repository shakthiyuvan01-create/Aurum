"""
smith_web.py — backward-compatible entry point
===============================================
The app has been refactored into app.py + routes/ + services/.
This file exists so existing scripts that run  `python smith_web.py`
continue to work unchanged.

New structure:
    app.py                  <- Flask app factory + blueprint registration
    services/
        auth_service.py     <- password hashing, login_required decorator
        ai_service.py       <- model routing keywords
        speech_service.py   <- Windows TTS / edge-tts
        chat_service.py     <- chat CRUD helpers
    routes/
        auth.py             <- /login  /register  /logout
        chat.py             <- /  /ask  /greet  /project  /chats  /memory
        upload.py           <- /upload/image  /uploads/<f>  /screenshot  /logo
        tools_routes.py     <- /tools  /tools/run  /tts  /docs  /reminders
        files.py            <- /files/*  /code/run  /git/push
        settings.py         <- /settings/personality
        stream_routes.py    <- /stream  (SSE)
        research_routes.py  <- /research  /analyze
"""
from app import app   # noqa: F401  -- re-export so `flask run` picks it up

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
