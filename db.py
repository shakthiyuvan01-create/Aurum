"""
db.py — SQLite storage layer for Assist Neo
Replaces: users.json, chats/, neo_memory.json
"""
import sqlite3, os, time, json, logging, glob

log = logging.getLogger("db")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assistneo.db")

def _conn():
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init_db():
    with _conn() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                username   TEXT PRIMARY KEY,
                nick       TEXT NOT NULL DEFAULT '',
                pw_hash    TEXT NOT NULL,
                role       TEXT NOT NULL DEFAULT 'user',
                created_at INTEGER DEFAULT (strftime('%s','now'))
            );
            -- migrate: add role column if it doesn't exist yet
            -- (SQLite ALTER TABLE cannot add a column with a NOT NULL
            --  constraint if rows exist, so we use a default of 'user')

            CREATE TABLE IF NOT EXISTS chats (
                id         TEXT PRIMARY KEY,
                username   TEXT NOT NULL,
                title      TEXT DEFAULT '',
                created_at INTEGER DEFAULT (strftime('%s','now'))
            );
            CREATE TABLE IF NOT EXISTS messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id    TEXT NOT NULL,
                role       TEXT NOT NULL,
                text       TEXT NOT NULL,
                created_at INTEGER DEFAULT (strftime('%s','now'))
            );
            CREATE INDEX IF NOT EXISTS idx_chats_user ON chats(username, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_msgs_chat  ON messages(chat_id, id);
            CREATE TABLE IF NOT EXISTS neo_memories (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT NOT NULL,
                fact       TEXT NOT NULL,
                created_at INTEGER DEFAULT (strftime('%s','now')),
                UNIQUE(username, fact)
            );
            CREATE TABLE IF NOT EXISTS user_settings (
                username          TEXT PRIMARY KEY,
                persona_name      TEXT DEFAULT '',
                custom_instructions TEXT DEFAULT '',
                model_routing     INTEGER DEFAULT 1,
                self_reflect      INTEGER DEFAULT 0,
                updated_at        INTEGER DEFAULT (strftime('%s','now'))
            );
        """)
    # migration: add role column to existing DBs that predate it
    try:
        with _conn() as db:
            db.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
            log.info("DB migration: added 'role' column to users")
    except Exception:
        pass   # column already exists
    log.info("DB ready: %s", DB_PATH)

# ── Users ──────────────────────────────────────────────────────────
def get_user(username):
    with _conn() as db:
        row = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        return dict(row) if row else None

def create_user(username, nick, pw_hash, role: str = "user"):
    with _conn() as db:
        db.execute("INSERT INTO users (username,nick,pw_hash,role) VALUES (?,?,?,?)",
                   (username, nick, pw_hash, role))

def get_all_users():
    """Returns dict matching old users.json shape for login compat."""
    with _conn() as db:
        rows = db.execute("SELECT username,nick,pw_hash,role FROM users").fetchall()
        return {r["username"]: {"pw": r["pw_hash"], "nick": r["nick"], "role": r["role"]}
                for r in rows}

def get_user_role(username: str) -> str:
    """Return the user's role string ('user', 'admin', etc.) or 'user' if not found."""
    row = get_user(username)
    return (row or {}).get("role", "user")

def set_user_role(username: str, role: str) -> None:
    with _conn() as db:
        db.execute("UPDATE users SET role=? WHERE username=?", (role, username))

def list_all_users() -> list[dict]:
    """Admin helper — returns all users (without pw_hash)."""
    with _conn() as db:
        rows = db.execute(
            "SELECT username,nick,role,created_at FROM users ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]

# ── Chats ──────────────────────────────────────────────────────────
def get_chat(chat_id):
    with _conn() as db:
        chat = db.execute("SELECT * FROM chats WHERE id=?", (chat_id,)).fetchone()
        if not chat:
            return None
        msgs = db.execute(
            "SELECT role,text FROM messages WHERE chat_id=? ORDER BY id",
            (chat_id,)).fetchall()
        return {
            "id": chat["id"], "title": chat["title"], "ts": chat["created_at"],
            "messages": [{"role": r["role"], "text": r["text"]} for r in msgs]
        }

def save_chat(chat_id, username, title, messages):
    ts = int(time.time())
    with _conn() as db:
        db.execute("""
            INSERT INTO chats (id,username,title,created_at) VALUES (?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET title=excluded.title, created_at=excluded.created_at
        """, (chat_id, username, title, ts))
        db.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
        for m in messages:
            db.execute("INSERT INTO messages (chat_id,role,text,created_at) VALUES (?,?,?,?)",
                       (chat_id, m["role"], m["text"], ts))

def list_chats(username, limit=40):
    with _conn() as db:
        rows = db.execute(
            "SELECT id,title,created_at as ts FROM chats WHERE username=? ORDER BY created_at DESC LIMIT ?",
            (username, limit)).fetchall()
        return [dict(r) for r in rows]

def delete_chat(chat_id, username):
    with _conn() as db:
        db.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
        db.execute("DELETE FROM chats WHERE id=? AND username=?", (chat_id, username))

def rename_chat(chat_id, username, title):
    with _conn() as db:
        db.execute("UPDATE chats SET title=? WHERE id=? AND username=?",
                   (title, chat_id, username))

# ── Neo Memories ────────────────────────────────────────────────────
def get_memories(username):
    with _conn() as db:
        rows = db.execute(
            "SELECT fact FROM neo_memories WHERE username=? ORDER BY created_at",
            (username,)).fetchall()
        return [r["fact"] for r in rows]

def add_memory(username, fact):
    fact = fact.strip()
    if not fact:
        return
    with _conn() as db:
        try:
            db.execute("INSERT INTO neo_memories (username,fact) VALUES (?,?)", (username, fact))
        except sqlite3.IntegrityError:
            log.debug("Memory fact already exists for user %s, skipping", username)

def clear_memories(username):
    with _conn() as db:
        db.execute("DELETE FROM neo_memories WHERE username=?", (username,))

# ── Migration ───────────────────────────────────────────────────────
def migrate_json(users_file, chats_dir, neo_memory_file):
    """One-time migration from JSON files → SQLite. Safe to call repeatedly."""
    migrated = 0

    if os.path.exists(users_file):
        try:
            with open(users_file, encoding="utf-8") as f:
                users = json.load(f)
            with _conn() as db:
                for uname, data in users.items():
                    pw   = data.get("pw","")   if isinstance(data, dict) else data
                    nick = data.get("nick", uname.capitalize()) if isinstance(data, dict) else uname.capitalize()
                    db.execute("INSERT OR IGNORE INTO users (username,nick,pw_hash) VALUES (?,?,?)",
                               (uname, nick, pw))
            migrated += len(users)
            log.info("Migrated %d users from %s", len(users), users_file)
        except Exception as e:
            log.warning("User migration failed: %s", e)

    if os.path.exists(chats_dir):
        for cf in glob.glob(os.path.join(chats_dir, "**", "*.json"), recursive=True):
            try:
                with open(cf, encoding="utf-8") as f:
                    chat = json.load(f)
                rel   = os.path.relpath(cf, chats_dir).replace("\\", "/")
                parts = rel.split("/")
                uname = parts[0] if len(parts) > 1 else "default"
                save_chat(chat["id"], uname, chat.get("title",""), chat.get("messages",[]))
                migrated += 1
            except Exception as e:
                log.debug("Skip chat %s: %s", cf, e)
        log.info("Migrated chat files from %s", chats_dir)

    if os.path.exists(neo_memory_file):
        try:
            with open(neo_memory_file, encoding="utf-8") as f:
                facts = json.load(f)
            with _conn() as db:
                for uname in [r["username"] for r in db.execute("SELECT username FROM users").fetchall()]:
                    for fact in facts:
                        db.execute(
                            "INSERT OR IGNORE INTO neo_memories (username,fact) VALUES (?,?)",
                            (uname, fact))
            migrated += len(facts)
            log.info("Migrated %d memory facts from %s", len(facts), neo_memory_file)
        except Exception as e:
            log.warning("Memory migration failed: %s", e)

    return migrated

# ── User Settings ───────────────────────────────────────────────────
def get_settings(username: str) -> dict:
    with _conn() as db:
        row = db.execute("SELECT * FROM user_settings WHERE username=?", (username,)).fetchone()
    if row:
        return dict(row)
    return {
        "username": username,
        "persona_name": "",
        "custom_instructions": "",
        "model_routing": 1,
        "self_reflect": 0,
    }

def save_settings(username: str, persona_name: str = "", custom_instructions: str = "",
                  model_routing: int = 1, self_reflect: int = 0):
    with _conn() as db:
        db.execute("""
            INSERT INTO user_settings (username, persona_name, custom_instructions, model_routing, self_reflect)
            VALUES (?,?,?,?,?)
            ON CONFLICT(username) DO UPDATE SET
                persona_name=excluded.persona_name,
                custom_instructions=excluded.custom_instructions,
                model_routing=excluded.model_routing,
                self_reflect=excluded.self_reflect,
                updated_at=strftime('%s','now')
        """, (username, persona_name, custom_instructions, model_routing, self_reflect))
