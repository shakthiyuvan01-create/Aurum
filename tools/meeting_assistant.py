"""
tools/meeting_assistant.py - AI Meeting Assistant.
"""
import json, logging, os

log = logging.getLogger(__name__)

NAME        = "meeting_assistant"
DESCRIPTION = (
    "AI meeting assistant: transcribe audio, summarize meetings, extract action items, "
    "generate formal minutes, draft participant emails. "
    "Actions: transcribe, summarize, action_items, minutes, email_draft, full_pipeline."
)
CATEGORY = "productivity"
ICON     = "📋"
INPUTS = [
    {"name": "action",        "label": "Action",  "type": "select",
     "options": ["transcribe","summarize","action_items","minutes","email_draft","full_pipeline"],
     "required": True},
    {"name": "audio_path",    "label": "Audio file path",               "type": "text"},
    {"name": "transcript",    "label": "Existing transcript",           "type": "textarea"},
    {"name": "meeting_title", "label": "Meeting title",                 "type": "text"},
    {"name": "participants",  "label": "Participants (comma-separated)", "type": "text"},
    {"name": "date",          "label": "Meeting date",                  "type": "text"},
    {"name": "language",      "label": "Language",  "type": "select",
     "options": ["en","hi","te","ta","kn","mr"], "default": "en"},
    {"name": "username",      "label": "Username",                      "type": "text"},
]


def _ai(prompt: str, max_tokens: int = 1200) -> str:
    from providers import AI
    return AI.generate(prompt, model="gpt-4o", max_tokens=max_tokens, temperature=0.3)


def _transcribe(audio_path: str, language: str = "en") -> str:
    try:
        from services.voice_service import transcribe
        result = transcribe(audio_path, language)
        return result.get("text", result.get("error", "Transcription failed"))
    except Exception as e:
        return f"[Transcription error: {e}]"


def _summarize(transcript: str, title: str = "") -> str:
    title_part = f" - {title}" if title else ""
    return _ai(
        f"Summarize this meeting transcript{title_part}\n\n"
        "Include: Key topics discussed, decisions made, important points.\n\n"
        + transcript[:6000]
    )


def _action_items(transcript: str) -> str:
    return _ai(
        "Extract ALL action items from this meeting transcript.\n"
        "Format: - [ ] **Action**: Description | **Owner**: Name | **Due**: Date\n\n"
        + transcript[:6000]
    )


def _minutes(transcript: str, title: str, participants: list, date: str) -> str:
    plist = ", ".join(participants) if participants else "See transcript"
    return _ai(
        "Generate formal meeting minutes.\n\n"
        f"Meeting: {title or 'Team Meeting'}\n"
        f"Date: {date or '(not provided)'}\n"
        f"Participants: {plist}\n\n"
        f"Transcript:\n{transcript[:5000]}\n\n"
        "Format:\n"
        "1. Meeting Details\n2. Agenda Items\n3. Key Decisions\n"
        "4. Action Items (owners + deadlines)\n5. Next Meeting\n6. AOB",
        max_tokens=1500,
    )


def _email_draft(summary: str, action_items: str, participants: list, title: str) -> str:
    to_list  = ", ".join(participants) if participants else "Team"
    fallback = "Today's Meeting"
    subject  = f"Meeting Follow-up - {title or fallback}"
    return _ai(
        f"Draft a professional follow-up email.\n\n"
        f"To: {to_list}\n"
        f"Subject: {subject}\n\n"
        f"Meeting Summary:\n{summary[:600]}\n\n"
        f"Action Items:\n{action_items[:600]}\n\n"
        "Write concise, professional email with all action items.",
        max_tokens=600,
    )


def run(
    action:        str = "full_pipeline",
    audio_path:    str = "",
    transcript:    str = "",
    meeting_title: str = "",
    participants:  str = "",
    date:          str = "",
    language:      str = "en",
    username:      str = "",
) -> dict:
    action = (action or "full_pipeline").lower().strip()
    parts_list = [p.strip() for p in participants.split(",") if p.strip()] if participants else []

    if action == "transcribe":
        if not audio_path or not os.path.exists(audio_path):
            return {"error": "audio_path required and must exist"}
        text = _transcribe(audio_path, language)
        return {"result": text, "transcript": text}

    if not transcript and audio_path and os.path.exists(audio_path):
        transcript = _transcribe(audio_path, language)

    if not transcript:
        return {"error": "transcript or audio_path required"}

    if action == "summarize":
        return {"result": _summarize(transcript, meeting_title)}

    if action == "action_items":
        return {"result": _action_items(transcript)}

    if action == "minutes":
        return {"result": _minutes(transcript, meeting_title, parts_list, date)}

    if action == "email_draft":
        summary = _summarize(transcript, meeting_title)
        items   = _action_items(transcript)
        return {"result": _email_draft(summary, items, parts_list, meeting_title)}

    # full_pipeline
    summary = _summarize(transcript, meeting_title)
    items   = _action_items(transcript)
    minutes = _minutes(transcript, meeting_title, parts_list, date)
    email   = _email_draft(summary, items, parts_list, meeting_title)
    full    = (
        f"## Meeting Summary\n{summary}\n\n"
        f"## Action Items\n{items}\n\n"
        f"## Meeting Minutes\n{minutes}\n\n"
        f"## Follow-up Email\n{email}"
    )
    return {"result": full, "summary": summary, "action_items": items, "minutes": minutes, "email": email}
