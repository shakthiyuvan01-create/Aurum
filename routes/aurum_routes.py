"""
routes/aurum_routes.py -- Timeline, Memory Map, Digital Twin, Predictions,
Universe, Skill Levels, Company org chart, Command Center.
"""
import json
import os
import re
import sqlite3
import time
import logging
from collections import Counter
from flask import Blueprint, request, jsonify, session
from services.auth_service import login_required

aurum_bp = Blueprint("aurum", __name__)
log = logging.getLogger("routes.aurum")

_deps: dict = {}

def _init(deps: dict) -> None:
    _deps.update(deps)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "aiaurum.db")


def _conn():
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def _user():
    return session.get("username", "guest")


# ── 1. AI Timeline: everything you have done, by day ─────────────────────────
@aurum_bp.route("/timeline")
@login_required
def timeline():
    days = min(int(request.args.get("days", 7)), 90)
    since = int(time.time()) - days * 86400
    uname = _user()
    events = []
    with _conn() as con:
        try:
            for r in con.execute(
                    "SELECT title, kind, status, created_at FROM task_history "
                    "WHERE username=? AND created_at>? ORDER BY created_at DESC LIMIT 200",
                    (uname, since)):
                events.append({"ts": r["created_at"], "kind": r["kind"],
                               "text": r["title"], "status": r["status"]})
        except sqlite3.OperationalError:
            pass
        try:
            for r in con.execute(
                    "SELECT title, created_at FROM chats WHERE username=? AND "
                    "created_at>? ORDER BY created_at DESC LIMIT 200", (uname, since)):
                events.append({"ts": r["created_at"], "kind": "chat", "text": r["title"]})
        except sqlite3.OperationalError:
            pass
    events.sort(key=lambda e: e["ts"], reverse=True)
    grouped = {}
    for e in events[:300]:
        day = time.strftime("%A %d %b", time.localtime(e["ts"]))
        grouped.setdefault(day, []).append(e)
    return jsonify({"days": days, "timeline": grouped})


# ── 2. Memory Map / Live Knowledge Graph data ────────────────────────────────
@aurum_bp.route("/memory_map")
@login_required
def memory_map():
    uname = _user()
    with _conn() as con:
        try:
            nodes = [dict(r) for r in con.execute(
                "SELECT name, entity_type FROM kg_entities WHERE username=? LIMIT 150",
                (uname,))]
            edges = [dict(r) for r in con.execute(
                "SELECT source, relation, target FROM kg_relations WHERE username=? LIMIT 300",
                (uname,))]
        except sqlite3.OperationalError:
            nodes, edges = [], []
    return jsonify({"nodes": nodes, "edges": edges})


# ── 3. Digital Twin: answer as the user would ────────────────────────────────
@aurum_bp.route("/twin/ask", methods=["POST"])
@login_required
def twin_ask():
    body = request.get_json(force=True) or {}
    q = (body.get("question") or "").strip()
    if not q:
        return jsonify({"error": "question required"}), 400
    uname = _user()
    facts = []
    try:
        import db as _db
        facts = _db.get_memories(uname)[:20]
    except Exception:
        pass
    style = {}
    try:
        from services import personal_twin
        style = personal_twin.analyse_style(uname) or {}
    except Exception:
        pass
    from providers import AI
    answer = AI.generate(
        "You are %s's digital twin. Answer the question the way THEY would, "
        "using their background, interests, and past work. First person.\n\n"
        "WHAT YOU KNOW ABOUT THEM:\n%s\n\nTHEIR STYLE:\n%s\n\nQUESTION: %s"
        % (uname, "\n".join("- " + f for f in facts) or "(learning still)",
           json.dumps(style, default=str)[:800], q),
        model="gpt-4o", max_tokens=900, temperature=0.4)
    return jsonify({"ok": True, "answer": answer})


# ── 4. Prediction engine ─────────────────────────────────────────────────────
@aurum_bp.route("/predict", methods=["POST"])
@login_required
def predict():
    from services.permission_manager import perms
    if not perms.check("background_ai"):
        return jsonify({"suggestions": []})
    body = request.get_json(force=True) or {}
    from providers import AI
    raw = AI.generate(
        "Given this exchange, predict the user's 3 most likely next requests. "
        'Reply ONLY JSON: {"suggestions": ["...", "...", "..."]} - each under '
        "8 words, actionable.\n\nUser: %s\nAssistant: %s"
        % ((body.get("msg") or "")[:400], (body.get("reply") or "")[:600]),
        model="gpt-4o-mini", max_tokens=100, temperature=0.4)
    m = re.search(r"\{[\s\S]*\}", raw)
    try:
        return jsonify({"suggestions": json.loads(m.group(0)).get("suggestions", [])[:3]})
    except Exception:
        return jsonify({"suggestions": []})


# ── 5. AI Universe: everything as connected planets ──────────────────────────
_STOP = set("the a an and or of to in for with on at from by about into is are was "
            "what how why when help me my i you it this that new make create".split())

@aurum_bp.route("/universe")
@login_required
def universe():
    uname = _user()
    words = Counter()
    samples = {}
    with _conn() as con:
        rows = []
        try:
            rows += [(r["title"], "chat", r["id"]) for r in con.execute(
                "SELECT id, title FROM chats WHERE username=? ORDER BY created_at DESC LIMIT 150",
                (uname,))]
        except sqlite3.OperationalError:
            pass
        try:
            rows += [(r["fact"], "memory", None) for r in con.execute(
                "SELECT fact FROM neo_memories WHERE username=? LIMIT 100", (uname,))]
        except sqlite3.OperationalError:
            pass
    for text, kind, ref in rows:
        for w in re.findall(r"[A-Za-z]{4,}", (text or "").lower()):
            if w not in _STOP:
                words[w] += 1
                samples.setdefault(w, []).append({"kind": kind, "text": text[:80], "ref": ref})
    planets = [{"topic": w.capitalize(), "size": n,
                "items": samples[w][:8]}
               for w, n in words.most_common(12) if n >= 2]
    return jsonify({"planets": planets})


# ── 6. Skill Evolution: XP levels for every capability ───────────────────────
@aurum_bp.route("/skills/levels")
@login_required
def skill_levels():
    levels = []
    try:
        from tools.tool_metrics import get_metrics
        m = get_metrics() or {}
        for name, stat in (m.items() if isinstance(m, dict) else []):
            if not isinstance(stat, dict):
                continue
            calls = stat.get("calls", stat.get("total_calls", 0)) or 0
            ok    = stat.get("successes", stat.get("success", calls)) or 0
            xp    = int(ok) * 10 + int(calls) * 2
            if calls:
                levels.append({"skill": name, "level": max(1, int(xp ** 0.5 // 3)),
                               "xp": xp, "calls": calls})
    except Exception as e:
        log.debug("levels: %s", e)
    levels.sort(key=lambda x: -x["xp"])
    return jsonify({"levels": levels[:20]})


# ── 7. AI Company org chart ──────────────────────────────────────────────────
@aurum_bp.route("/company")
@login_required
def company():
    from agents import PERSONALITIES
    return jsonify({"org": [
        {"agent": k, "title": v[0], "personality": v[1]}
        for k, v in PERSONALITIES.items()]})


# ── 8. Command Center snapshot ───────────────────────────────────────────────
@aurum_bp.route("/command_center")
@login_required
def command_center():
    out = {"ts": int(time.time())}
    try:
        import tools as _tools
        out["system"] = _tools.call("system_monitor", action="status")
    except Exception as e:
        out["system"] = {"error": str(e)}
    try:
        from services.agent_health import health
        out["agents"] = health.summary() if hasattr(health, "summary") else {}
    except Exception:
        out["agents"] = {}
    uname = _user()
    with _conn() as con:
        try:
            out["tasks_today"] = con.execute(
                "SELECT COUNT(*) FROM task_history WHERE username=? AND "
                "created_at > strftime('%s','now','start of day')", (uname,)).fetchone()[0]
            out["chats_total"] = con.execute(
                "SELECT COUNT(*) FROM chats WHERE username=?", (uname,)).fetchone()[0]
            out["memories"] = con.execute(
                "SELECT COUNT(*) FROM neo_memories WHERE username=?", (uname,)).fetchone()[0]
        except sqlite3.OperationalError:
            pass
    return jsonify(out)


# ── Consciousness Dashboard: the AI's live internal state ────────────────────
@aurum_bp.route("/consciousness")
@login_required
def consciousness():
    uname = _user()
    out = {}
    try:
        from providers import AI
        st = AI.status()
        out["providers"] = st["available"]
        out["last_provider"] = st["last_used"]
        out["recent_errors"] = len(st["last_errors"])
    except Exception:
        pass
    with _conn() as con:
        def _q(sql, args=()):
            try:
                return con.execute(sql, args).fetchone()[0]
            except sqlite3.OperationalError:
                return 0
        out["memories_loaded"] = _q("SELECT COUNT(*) FROM neo_memories WHERE username=?", (uname,))
        out["knowledge_entities"] = _q("SELECT COUNT(*) FROM kg_entities WHERE username=?", (uname,))
        out["experiences"] = _q("SELECT COUNT(*) FROM experiences WHERE username=?", (uname,))
        out["standing_rules"] = _q(
            "SELECT COUNT(*) FROM neo_memories WHERE username=? AND fact LIKE 'STANDING RULE:%'", (uname,))
        out["missions_open"] = _q("SELECT COUNT(*) FROM missions WHERE username=?", (uname,))
        out["custom_agents"] = _q("SELECT COUNT(*) FROM custom_agents")
        out["tasks_waiting"] = _q(
            "SELECT COUNT(*) FROM task_history WHERE username=? AND status NOT IN ('done','failed')", (uname,))
    try:
        import agents as _agents
        out["active_agents"] = len(_agents._REGISTRY) + out.get("custom_agents", 0)
    except Exception:
        pass
    try:
        from services.permission_manager import perms
        risky = [k for k, v in perms.all().items()
                 if v and k in ("shell", "files_delete", "packages", "self_improve")]
        out["risk_level"] = "elevated" if risky else "low"
        out["risky_permissions"] = risky
    except Exception:
        out["risk_level"] = "unknown"
    # knowledge gaps: unanswered-well topics from recent evals stored in logs
    out["confidence"] = 90 if out.get("recent_errors", 0) == 0 else 70
    return jsonify(out)


# ── Memory DNA: identity profile + monthly evolution ─────────────────────────
@aurum_bp.route("/dna")
@login_required
def memory_dna():
    uname = _user()
    with _conn() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS dna_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL, profile TEXT NOT NULL,
            created_at INTEGER DEFAULT (strftime('%s','now')))""")
        last = con.execute(
            "SELECT profile, created_at FROM dna_snapshots WHERE username=? "
            "ORDER BY id DESC LIMIT 1", (uname,)).fetchone()
        if last and time.time() - last["created_at"] < 86400 and not request.args.get("refresh"):
            prev = con.execute(
                "SELECT profile FROM dna_snapshots WHERE username=? "
                "ORDER BY id DESC LIMIT 1 OFFSET 1", (uname,)).fetchone()
            return jsonify({"profile": json.loads(last["profile"]),
                            "previous": json.loads(prev["profile"]) if prev else None,
                            "cached": True})
        facts, titles = [], []
        try:
            facts = [r["fact"] for r in con.execute(
                "SELECT fact FROM neo_memories WHERE username=? LIMIT 60", (uname,))]
            titles = [r["title"] for r in con.execute(
                "SELECT title FROM chats WHERE username=? ORDER BY created_at DESC LIMIT 60",
                (uname,))]
        except sqlite3.OperationalError:
            pass
        from providers import AI
        raw = AI.generate(
            "Build this user's identity profile from their data. Reply ONLY JSON:\n"
            '{"learning_style": "...", "decision_style": "...", '
            '"communication_style": "...", "risk_profile": "...", '
            '"favorite_topics": ["..."], "coding_style": "...", '
            '"strengths": ["..."], "gaps": ["skills they likely lack given their '
            'goals"], "forecast": "what they will likely work on next month"}\n\n'
            "FACTS: %s\n\nRECENT TOPICS: %s"
            % ("; ".join(facts)[:2500], "; ".join(titles)[:1500]),
            model="gpt-4o", max_tokens=500, temperature=0.3)
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return jsonify({"error": "profiling failed"}), 502
        profile = json.loads(m.group(0))
        prev = json.loads(last["profile"]) if last else None
        con.execute("INSERT INTO dna_snapshots (username, profile) VALUES (?,?)",
                    (uname, json.dumps(profile)))
        return jsonify({"profile": profile, "previous": prev, "cached": False})


# ── Memory Compression: chats -> memories -> clusters -> beliefs ─────────────
@aurum_bp.route("/memory/compress", methods=["POST"])
@login_required
def memory_compress():
    uname = _user()
    with _conn() as con:
        try:
            facts = [(r["id"], r["fact"]) for r in con.execute(
                "SELECT id, fact FROM neo_memories WHERE username=? AND "
                "fact NOT LIKE 'STANDING RULE:%' AND fact NOT LIKE 'BELIEF:%' "
                "ORDER BY created_at", (uname,))]
        except sqlite3.OperationalError:
            return jsonify({"error": "no memories table"}), 500
        if len(facts) < 25:
            return jsonify({"ok": True, "message":
                            "Only %d memories - compression starts being useful at 25+." % len(facts)})
        from providers import AI
        raw = AI.generate(
            "Compress these %d memory facts. Reply ONLY JSON:\n"
            '{"clusters": [{"name": "...", "summary": "1-2 sentence distillation"}], '
            '"beliefs": ["permanent core fact about the user", ...]}\n'
            "Max 8 clusters, max 3 beliefs. Lose no important information.\n\n%s"
            % (len(facts), "\n".join(f[1] for f in facts)[:12000]),
            model="gpt-4o", max_tokens=800, temperature=0.2)
        m = re.search(r"\{[\s\S]*\}", raw)
        if not m:
            return jsonify({"error": "compression failed"}), 502
        d = json.loads(m.group(0))
        # replace old facts with clusters + beliefs
        con.execute("DELETE FROM neo_memories WHERE username=? AND id IN (%s)"
                    % ",".join("?" * len(facts)), [uname] + [f[0] for f in facts])
        for c in d.get("clusters", [])[:8]:
            con.execute("INSERT OR IGNORE INTO neo_memories (username, fact) VALUES (?,?)",
                        (uname, "CLUSTER [%s]: %s" % (c.get("name", "?"), c.get("summary", ""))))
        for b in d.get("beliefs", [])[:3]:
            con.execute("INSERT OR IGNORE INTO neo_memories (username, fact) VALUES (?,?)",
                        (uname, "BELIEF: " + b))
        return jsonify({"ok": True, "compressed": len(facts),
                        "clusters": len(d.get("clusters", [])),
                        "beliefs": len(d.get("beliefs", []))})


# ── Autonomous Benchmarking ──────────────────────────────────────────────────
_BENCH = [
    ("coding",   "Write a Python function that returns the n-th Fibonacci number iteratively."),
    ("math",     "A tank fills at 40 L/min and drains at 25 L/min. It holds 600 L. How long to fill from empty? Show working."),
    ("research", "Name the three main lithium battery chemistries for grid storage and one tradeoff of each."),
    ("planning", "Plan the steps to migrate a Flask app from SQLite to PostgreSQL with zero downtime."),
    ("reasoning","If all Zorks are Mips and some Mips are Tars, can we conclude some Zorks are Tars? Explain."),
]

@aurum_bp.route("/benchmark", methods=["POST"])
@login_required
def benchmark():
    from providers import AI
    import self_eval as _se
    scores = {}
    for area, q in _BENCH:
        try:
            ans = AI.generate(q, model="gpt-4o-mini", max_tokens=400, temperature=0.2)
            ev = _se.evaluate(q, ans)
            scores[area] = round(100 * float(ev.get("overall", 0.5)))
        except Exception:
            scores[area] = 0
    weak = min(scores, key=scores.get) if scores else None
    with _conn() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS benchmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, scores TEXT,
            created_at INTEGER DEFAULT (strftime('%s','now')))""")
        con.execute("INSERT INTO benchmarks (scores) VALUES (?)", (json.dumps(scores),))
    return jsonify({"scores": scores, "weakest": weak})


# ── Experience database view ─────────────────────────────────────────────────
@aurum_bp.route("/experience")
@login_required
def experience_list():
    from services.experience_db import list_experiences
    return jsonify({"experiences": list_experiences(_user())})


# ── Hired workforce ──────────────────────────────────────────────────────────
@aurum_bp.route("/agents/hired")
@login_required
def hired_agents():
    from services import dynamic_agents
    return jsonify({"hired": dynamic_agents.list_all()})


@aurum_bp.route("/research_graph")
@login_required
def research_graph():
    with _conn() as con:
        try:
            rows = [dict(r) for r in con.execute(
                "SELECT id, question, open_questions, created_at FROM research_sessions "
                "WHERE username=? ORDER BY id DESC LIMIT 30", (_user(),))]
        except sqlite3.OperationalError:
            rows = []
    return jsonify({"sessions": rows})


# ── Economic Brain: estimated cost of everything ─────────────────────────────
_MODEL_COST = {"gpt-4o": 0.0075, "gpt-4o-mini": 0.0004}  # rough $/1k tokens blend

@aurum_bp.route("/economics")
@login_required
def economics():
    uname = _user()
    with _conn() as con:
        def _q(sql, args=()):
            try:
                return con.execute(sql, args).fetchall()
            except sqlite3.OperationalError:
                return []
        week_tasks = _q("SELECT kind, COUNT(*) c, SUM(duration) d FROM task_history "
                        "WHERE username=? AND created_at > strftime('%s','now','-7 days') "
                        "GROUP BY kind", (uname,))
        events = _q("SELECT COUNT(*) FROM agent_logs WHERE "
                    "created_at > strftime('%s','now','-7 days')")
        msgs = _q("SELECT COUNT(*) FROM messages WHERE chat_id IN "
                  "(SELECT id FROM chats WHERE username=?) ", (uname,))
    n_events = events[0][0] if events else 0
    n_msgs   = msgs[0][0] if msgs else 0
    # rough estimate: each chat message ~1.5k tokens gpt-4o + ~3 mini calls
    est_main = n_msgs * 1.5 * _MODEL_COST["gpt-4o"]
    est_bg   = n_msgs * 3 * 0.6 * _MODEL_COST["gpt-4o-mini"]
    return jsonify({
        "week_tasks": [{"kind": r[0], "count": r[1], "seconds": round(r[2] or 0)}
                       for r in week_tasks],
        "events_7d": n_events,
        "messages_total": n_msgs,
        "estimated_api_cost_total_usd": round(est_main + est_bg, 2),
        "note": "Estimates assume ~1.5k tokens per exchange plus background calls. "
                "GitHub Models free tier absorbs most of this.",
    })


# ── Pattern Hunter: hidden habits across your history ────────────────────────
@aurum_bp.route("/patterns")
@login_required
def patterns():
    uname = _user()
    with _conn() as con:
        try:
            titles = [r["title"] for r in con.execute(
                "SELECT title FROM chats WHERE username=? ORDER BY created_at DESC LIMIT 150",
                (uname,))]
            hist = [(r["kind"], r["title"]) for r in con.execute(
                "SELECT kind, title FROM task_history WHERE username=? "
                "ORDER BY created_at DESC LIMIT 80", (uname,))]
        except sqlite3.OperationalError:
            titles, hist = [], []
    if len(titles) + len(hist) < 10:
        return jsonify({"result": "Not enough history yet - patterns emerge after more sessions."})
    from providers import AI
    out = AI.generate(
        "You are a pattern hunter analyzing a user's work history. Find hidden "
        "habits and patterns they may not have noticed: recurring tools/stacks, "
        "time-of-work patterns, repeated problem types, what their successful "
        "sessions have in common, and 2 habits worth changing. Be specific and "
        "cite examples from the data.\n\nCHAT TOPICS: %s\n\nTASKS: %s"
        % ("; ".join(titles)[:4000], "; ".join("%s:%s" % h for h in hist)[:2000]),
        model="gpt-4o", max_tokens=900, temperature=0.4)
    return jsonify({"result": out})


# ── Token/cost usage per provider (the missing piece for a 6-provider chain) ─
_COST_PER_1K = {"github": 0.0, "nara": 0.0, "bluesminds": 0.0,
                "gemini": 0.0, "openai": 0.005, "ollama": 0.0}

@aurum_bp.route("/usage")
@login_required
def provider_usage():
    days = min(int(request.args.get("days", 7)), 90)
    with _conn() as con:
        try:
            rows = [dict(r) for r in con.execute(
                "SELECT day, provider, calls, est_tokens, total_ms, failovers "
                "FROM provider_usage WHERE day >= date('now', ?) "
                "ORDER BY day DESC, est_tokens DESC", ("-%d days" % days,))]
        except sqlite3.OperationalError:
            rows = []
    totals = {}
    for r in rows:
        t = totals.setdefault(r["provider"], {"calls": 0, "est_tokens": 0,
                                              "total_ms": 0, "failovers": 0})
        for k in ("calls", "est_tokens", "total_ms", "failovers"):
            t[k] += r[k]
    for prov, t in totals.items():
        t["avg_latency_ms"] = round(t["total_ms"] / max(t["calls"], 1))
        t["est_cost_usd"] = round(t["est_tokens"] / 1000 * _COST_PER_1K.get(prov, 0), 4)
    return jsonify({"days": days, "totals": totals, "daily": rows})


# ── Scheduled autonomous missions ────────────────────────────────────────────
@aurum_bp.route("/auto_missions", methods=["GET", "POST", "DELETE"])
@login_required
def auto_missions():
    from services import auto_missions as am
    uname = _user()
    if request.method == "POST":
        b = request.get_json(force=True) or {}
        goal = (b.get("goal") or "").strip()
        if not goal:
            return jsonify({"error": "goal required"}), 400
        mid = am.create(uname, goal, hour=int(b.get("hour", 7)),
                        minute=int(b.get("minute", 0)),
                        deliver=b.get("deliver", "canvas"),
                        deliver_to=b.get("deliver_to", ""))
        return jsonify({"ok": True, "mission_id": mid})
    if request.method == "DELETE":
        am.remove(uname, int(request.args.get("id", 0)))
        return jsonify({"ok": True})
    return jsonify({"missions": am.list_missions(uname)})


# ── One-click backup: memory, chats, settings, canvas, missions -> zip ───────
@aurum_bp.route("/export")
@login_required
def export_all():
    import io, zipfile, time as _t
    uname = _user()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        with _conn() as con:
            def dump(name, sql, args=()):
                try:
                    rows = [dict(r) for r in con.execute(sql, args).fetchall()]
                    z.writestr(name, json.dumps(rows, indent=1, default=str))
                except sqlite3.OperationalError as e:
                    z.writestr(name, json.dumps({"error": str(e)}))
            dump("memories.json", "SELECT * FROM neo_memories WHERE username=?", (uname,))
            dump("chats.json",
                 "SELECT c.id, c.title, c.created_at, m.role, m.text FROM chats c "
                 "LEFT JOIN messages m ON m.chat_id=c.id WHERE c.username=? "
                 "ORDER BY c.created_at, m.id", (uname,))
            dump("canvas.json", "SELECT * FROM canvas_docs WHERE username=?", (uname,))
            dump("missions.json", "SELECT * FROM missions WHERE username=?", (uname,))
            dump("auto_missions.json", "SELECT * FROM auto_missions WHERE username=?", (uname,))
            dump("experiences.json", "SELECT * FROM experiences WHERE username=?", (uname,))
            dump("knowledge_graph.json",
                 "SELECT source, relation, target FROM kg_relations WHERE username=?", (uname,))
            dump("skills.json", "SELECT * FROM user_skills WHERE username=?", (uname,))
            dump("settings.json", "SELECT * FROM user_settings WHERE username=?", (uname,))
            dump("timeline.json", "SELECT * FROM task_history WHERE username=?", (uname,))
    buf.seek(0)
    from flask import send_file
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name="aurum_backup_%s_%s.zip"
                                    % (uname, _t.strftime("%Y%m%d")))


@aurum_bp.route("/eval_harness", methods=["POST"])
@login_required
def eval_harness_run():
    """Run the golden-set quality eval right now (8 prompts, ~1 min)."""
    from services.eval_harness import run_eval
    return jsonify(run_eval(alert=False))
