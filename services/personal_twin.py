"""
services/personal_twin.py — Personal AI Twin.
Learns the user's writing style, coding style, engineering preferences,
and recurring decisions. Drafts work that sounds consistently like them.
"""
from __future__ import annotations
import json, logging, os, sqlite3, time
from contextlib import contextmanager
from pathlib import Path

log = logging.getLogger("services.personal_twin")

_DB = str(Path(os.path.abspath(__file__)).parent.parent / "aiaurum.db")


@contextmanager
def _conn():
    con = sqlite3.connect(_DB)
    con.row_factory = sqlite3.Row
    con.executescript("""
    CREATE TABLE IF NOT EXISTS twin_samples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        category TEXT NOT NULL,
        content TEXT NOT NULL,
        source TEXT DEFAULT 'user',
        created_at INTEGER DEFAULT (strftime('%s','now'))
    );
    CREATE TABLE IF NOT EXISTS twin_preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        updated_at INTEGER DEFAULT (strftime('%s','now')),
        UNIQUE(username, key)
    );
    CREATE INDEX IF NOT EXISTS idx_twin_user ON twin_samples(username, category);
    """)
    con.commit()
    try:
        yield con
        con.commit()
    finally:
        con.close()


# ── Sample management ─────────────────────────────────────────────────────────
def add_sample(username: str, category: str, content: str, source: str = "user") -> None:
    """Add a writing/coding sample to train the twin. category: writing|code|engineering|email|report"""
    with _conn() as con:
        con.execute(
            "INSERT INTO twin_samples(username,category,content,source) VALUES(?,?,?,?)",
            (username, category, content[:3000], source),
        )


def get_samples(username: str, category: str = "", limit: int = 10) -> list[dict]:
    with _conn() as con:
        if category:
            rows = con.execute(
                "SELECT * FROM twin_samples WHERE username=? AND category=? ORDER BY created_at DESC LIMIT ?",
                (username, category, limit)
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM twin_samples WHERE username=? ORDER BY created_at DESC LIMIT ?",
                (username, limit)
            ).fetchall()
        return [dict(r) for r in rows]


def set_preference(username: str, key: str, value: str) -> None:
    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO twin_preferences(username,key,value,updated_at) VALUES(?,?,?,?)",
            (username, key, value, int(time.time())),
        )


def get_preferences(username: str) -> dict:
    with _conn() as con:
        rows = con.execute(
            "SELECT key, value FROM twin_preferences WHERE username=?", (username,)
        ).fetchall()
        return {r["key"]: r["value"] for r in rows}


# ── Style analysis ─────────────────────────────────────────────────────────────
def _ai(prompt: str, max_tokens: int = 1000) -> str:
    from providers import AI
    out = AI.generate(prompt, model="gpt-4o", max_tokens=max_tokens, temperature=0.2)
    return "" if out.startswith("[AI error") else out


def analyse_style(username: str) -> dict:
    """Analyse user samples to extract style fingerprint."""
    samples = get_samples(username, limit=20)
    if not samples:
        return {"error": "No samples yet. Add writing samples first."}

    combined = "\n\n---\n\n".join(s["content"][:500] for s in samples[:8])
    raw = _ai(
        f"""Analyse these writing samples from one person and extract their style fingerprint.
Return JSON with:
{{
  "tone": "formal|informal|technical|conversational",
  "sentence_length": "short|medium|long|varied",
  "vocabulary": "simple|technical|mixed",
  "structure": "bullet-points|paragraphs|numbered-lists|mixed",
  "punctuation_style": "minimal|standard|heavy",
  "key_phrases": ["phrase1", "phrase2"],
  "avoids": ["thing they avoid"],
  "typical_greeting": "how they start emails/reports",
  "typical_closing": "how they end emails/reports",
  "summary": "2-sentence style description"
}}

Samples:
{combined}""",
        max_tokens=600,
    )
    try:
        clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        style = json.loads(clean)
        # Cache the style profile
        set_preference(username, "style_profile", json.dumps(style))
        return style
    except Exception:
        return {"summary": "Style analysis failed — add more writing samples."}


# ── Draft generation ──────────────────────────────────────────────────────────
def draft_as_twin(username: str, task: str, content_type: str = "writing") -> str:
    """
    Generate content that mimics the user's style.
    content_type: writing | code | email | report | engineering
    """
    # Get style profile
    prefs   = get_preferences(username)
    style   = prefs.get("style_profile", "")
    if style:
        try:
            style_data = json.loads(style)
            style_desc = style_data.get("summary", "")
            key_traits = (
                f"Tone: {style_data.get('tone','professional')}. "
                f"Structure: {style_data.get('structure','mixed')}. "
                f"Vocabulary: {style_data.get('vocabulary','technical')}."
            )
        except Exception:
            style_desc = style
            key_traits = ""
    else:
        style_desc = "professional technical writing"
        key_traits = ""

    # Get recent samples as examples
    samples = get_samples(username, category=content_type if content_type in ("code","engineering") else "", limit=3)
    examples = "\n\n---\n\n".join(s["content"][:400] for s in samples) if samples else ""

    system = (
        f"You are a Personal AI Twin. Draft content that exactly matches this person's style.\n"
        f"Style: {style_desc}\n{key_traits}\n"
        + (f"\nExample of their work:\n{examples}" if examples else "")
    )

    return _ai(
        f"Task: {task}\n\nWrite this in the user's exact style. Be authentic to how they write.",
    ) or f"Draft for: {task}"


# ── Auto-learn from chats ─────────────────────────────────────────────────────
def learn_from_message(username: str, message: str, category: str = "writing") -> None:
    """
    Passively learn from a user message if it looks like real writing
    (not a command or short query).
    """
    if len(message.split()) < 15:
        return  # Too short to be informative
    if message.startswith("/") or message.startswith("!"):
        return  # Command
    add_sample(username, category, message, source="chat")
