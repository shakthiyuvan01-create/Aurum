"""
services/content_os.py -- Content Agent OS (ported from the Node.js project).

Sources -> scheduled scrape -> AI rank (0-100) -> freshness window -> feed.
RSS via stdlib xml; arbitrary URLs + search via the web_search tool; ranking +
captions via the provider chain; images via assistant.image (Pollinations).
No new dependency.
"""
import os
import re
import sqlite3
import time
import logging
import urllib.request
import xml.etree.ElementTree as ET

log = logging.getLogger("services.content_os")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "aiaurum.db")
DEFAULT_FRESHNESS_HOURS = int(os.getenv("DEFAULT_FRESHNESS_HOURS", "24"))


def _con():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.executescript("""
        CREATE TABLE IF NOT EXISTS content_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT, url TEXT, kind TEXT DEFAULT 'auto',
            tags TEXT DEFAULT '', interval_hours REAL DEFAULT 6,
            last_scraped INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT (strftime('%s','now')));
        CREATE TABLE IF NOT EXISTS content_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT, source_id INTEGER, title TEXT, url TEXT UNIQUE,
            summary TEXT DEFAULT '', score INTEGER DEFAULT 0,
            published INTEGER DEFAULT 0,
            created_at INTEGER DEFAULT (strftime('%s','now')));
    """)
    return con


# ── sources ──────────────────────────────────────────────────────────────────
def add_source(username, url, tags="", interval_hours=6, kind="auto"):
    with _con() as con:
        cur = con.execute(
            "INSERT INTO content_sources (username,url,kind,tags,interval_hours) "
            "VALUES (?,?,?,?,?)", (username, url.strip(), kind, tags, interval_hours))
        return cur.lastrowid


def list_sources(username):
    with _con() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM content_sources WHERE username=? ORDER BY id DESC",
            (username,))]


def remove_source(username, sid):
    with _con() as con:
        con.execute("DELETE FROM content_sources WHERE id=? AND username=?", (sid, username))


# ── scraping ─────────────────────────────────────────────────────────────────
def _parse_rss(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Aurum)"})
        raw = urllib.request.urlopen(req, timeout=20).read()
        root = ET.fromstring(raw)
        items = []
        for it in root.iter():
            tag = it.tag.lower().split("}")[-1]
            if tag in ("item", "entry"):
                title = url_ = summ = ""
                for c in it:
                    ct = c.tag.lower().split("}")[-1]
                    if ct == "title": title = (c.text or "").strip()
                    elif ct == "link":
                        url_ = (c.text or c.get("href") or "").strip()
                    elif ct in ("description", "summary", "content"):
                        summ = re.sub("<[^>]+>", " ", (c.text or ""))[:400].strip()
                if title and url_:
                    items.append({"title": title, "url": url_, "summary": summ})
        return items[:20]
    except Exception as e:
        log.debug("rss parse failed for %s: %s", url, e)
        return []


def _scrape_source(src):
    kind = src["kind"]
    items = []
    if kind in ("auto", "rss"):
        items = _parse_rss(src["url"])
    if not items and kind in ("auto", "url", "search"):
        try:
            import tools as _tools
            mode = "search" if not src["url"].startswith("http") else "research"
            r = _tools.call("web_search", query=src["url"], mode=mode, max_results=8)
            txt = str(r.get("result") or r.get("message") or "")
            for m in re.finditer(r"(https?://[^\s)]+)", txt):
                items.append({"title": m.group(1)[:80], "url": m.group(1), "summary": ""})
            items = items[:8]
        except Exception as e:
            log.debug("web scrape failed: %s", e)
    return items


def _rank(title, summary, niche):
    try:
        from providers import AI
        v = AI.generate_json(
            "Score this article 0-100 for relevance/importance to a creator whose "
            'niche is: %s. Reply JSON {"score": N, "why": "..."}.\n\nTitle: %s\n%s'
            % (niche or "general tech/AI", title, summary[:300]),
            model="gpt-4o-mini", max_tokens=60)
        s = v.get("score", 50)
        return int(s) if isinstance(s, (int, float)) else 50
    except Exception:
        return 50


def scrape_due(username=None, force=False):
    """Scrape any source whose interval has elapsed; rank + store new articles."""
    niche = os.getenv("CONTENT_NICHE", "")
    with _con() as con:
        q = "SELECT * FROM content_sources"
        args = []
        if username:
            q += " WHERE username=?"; args.append(username)
        srcs = [dict(r) for r in con.execute(q, args).fetchall()]
    new_count = 0
    now = time.time()
    for src in srcs:
        if not force and now - src["last_scraped"] < src["interval_hours"] * 3600:
            continue
        for art in _scrape_source(src):
            try:
                with _con() as con:
                    exists = con.execute("SELECT 1 FROM content_articles WHERE url=?",
                                         (art["url"],)).fetchone()
                    if exists:
                        continue
                    score = _rank(art["title"], art.get("summary", ""), niche)
                    con.execute(
                        "INSERT OR IGNORE INTO content_articles "
                        "(username,source_id,title,url,summary,score) VALUES (?,?,?,?,?,?)",
                        (src["username"], src["id"], art["title"], art["url"],
                         art.get("summary", ""), score))
                    new_count += 1
            except Exception as e:
                log.debug("store article: %s", e)
        with _con() as con:
            con.execute("UPDATE content_sources SET last_scraped=? WHERE id=?",
                        (int(now), src["id"]))
    if new_count:
        log.info("content_os: %d new articles ranked", new_count)
    return new_count


def feed(username, bypass_freshness=False, limit=40):
    hours = int(os.getenv("DEFAULT_FRESHNESS_HOURS", str(DEFAULT_FRESHNESS_HOURS)))
    with _con() as con:
        q = "SELECT * FROM content_articles WHERE username=?"
        args = [username]
        if not bypass_freshness:
            q += " AND created_at > ?"; args.append(int(time.time() - hours * 3600))
        q += " ORDER BY score DESC, created_at DESC LIMIT ?"; args.append(limit)
        return [dict(r) for r in con.execute(q, args).fetchall()]


def supervisor():
    """APScheduler hook: scrape all due sources."""
    try:
        scrape_due()
    except Exception as e:
        log.debug("content supervisor: %s", e)
