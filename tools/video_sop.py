"""
tools/video_sop.py -- multimodal: video/audio walkthrough -> SOP or minutes.

Pipeline: video -> extract audio (ffmpeg) -> transcribe (voice_service:
Whisper API / local whisper / vosk) -> chunked AI synthesis ->
Standard Operating Procedure, meeting minutes, or summary.

Heavy: run via /tools/run_async.
"""
import os
import subprocess
import shutil
import tempfile
import logging

log = logging.getLogger("tools.video_sop")

NAME        = "video_sop"
DESCRIPTION = (
    "Turn a video or audio walkthrough into a Standard Operating Procedure, "
    "meeting minutes, or summary. Handles long recordings by chunking. "
    "Inputs: file_path (video/audio), output: sop | minutes | summary."
)
CATEGORY = "builtin"
ICON     = "film"
INPUTS = [
    {"name": "file_path", "label": "Video/audio file path", "type": "text", "required": True},
    {"name": "output",    "label": "Output type", "type": "select",
     "options": [{"value": "sop", "label": "SOP"},
                 {"value": "minutes", "label": "Meeting minutes"},
                 {"value": "summary", "label": "Summary"}], "required": True},
    {"name": "username",  "label": "Username", "type": "text"},
]

VIDEO_EXT = (".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".wmv")
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac", ".webm")

PROMPTS = {
    "sop": (
        "Convert this walkthrough transcript into a professional Standard "
        "Operating Procedure. Structure: Title, Purpose, Prerequisites, "
        "numbered Step-by-step Procedure (with sub-steps), Warnings/Notes, "
        "and a Verification checklist. Be precise and complete."),
    "minutes": (
        "Convert this meeting transcript into detailed meeting minutes. "
        "Structure: Title/Date, Attendees (if mentioned), Agenda, Discussion "
        "points, Decisions made, Action items (owner + deadline if stated), "
        "and Next steps."),
    "summary": (
        "Summarize this transcript comprehensively: key topics, main points, "
        "important details, and takeaways."),
}


def _extract_audio(video_path: str) -> str:
    """Video -> 16k mono wav via ffmpeg. Returns wav path."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found. Install it (winget install ffmpeg) "
                           "to process video files; audio files work without it.")
    out = tempfile.mktemp(suffix=".wav")
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-vn", "-ar", "16000", "-ac", "1", out],
        capture_output=True, timeout=600)
    if r.returncode != 0 or not os.path.exists(out):
        raise RuntimeError("ffmpeg failed: " + r.stderr.decode(errors="ignore")[-300:])
    return out


def _synthesize(transcript: str, output: str) -> str:
    from providers import AI
    instruction = PROMPTS.get(output, PROMPTS["summary"])
    if len(transcript) <= 24000:
        return AI.generate(instruction + "\n\nTRANSCRIPT:\n" + transcript,
                           model="gpt-4o", max_tokens=2500, temperature=0.2)
    # Long recording: summarize chunks first, then synthesize
    chunks = [transcript[i:i + 20000] for i in range(0, len(transcript), 20000)]
    notes = []
    for i, ch in enumerate(chunks):
        notes.append(AI.generate(
            "Extract every step, decision, and detail from part %d/%d of a "
            "transcript. Dense bullet notes.\n\n%s" % (i + 1, len(chunks), ch),
            model="gpt-4o-mini", max_tokens=900, temperature=0.2))
    return AI.generate(instruction + "\n\nDETAILED NOTES FROM THE FULL RECORDING:\n"
                       + "\n\n".join(notes),
                       model="gpt-4o", max_tokens=2500, temperature=0.2)


def run(file_path: str = "", output: str = "sop", username: str = "default") -> dict:
    if not file_path or not os.path.exists(file_path):
        return {"error": "file not found: %s" % file_path}
    output = (output or "sop").lower().strip()
    ext = os.path.splitext(file_path)[1].lower()

    tmp_wav = None
    try:
        if ext in VIDEO_EXT and ext != ".webm":
            audio_path = tmp_wav = _extract_audio(file_path)
        elif ext in AUDIO_EXT:
            audio_path = file_path
        elif ext in VIDEO_EXT:
            audio_path = tmp_wav = _extract_audio(file_path)
        else:
            return {"error": "unsupported file type: %s" % ext}

        from services.voice_service import transcribe
        t = transcribe(audio_path, "en")
        if t.get("error"):
            return {"error": "transcription failed: %s" % t["error"]}
        transcript = t.get("text", "").strip()
        if not transcript:
            return {"error": "empty transcript - no speech detected"}

        result = _synthesize(transcript, output)
        return {"result": result, "output_type": output,
                "transcript_chars": len(transcript),
                "backend": t.get("backend", "?")}
    except Exception as e:
        log.error("video_sop failed: %s", e)
        return {"error": str(e)}
    finally:
        if tmp_wav and os.path.exists(tmp_wav):
            try: os.unlink(tmp_wav)
            except OSError: pass
