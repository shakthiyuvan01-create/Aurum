"""
tools/auto_research.py -- autonomous research pipeline.

"Research BESS in India" ->
  multiple search queries -> read results -> synthesized report with sections
  and cited sources -> optional PowerPoint deck via ppt_tool.

Heavy: run via /tools/run_async.
"""
import logging

log = logging.getLogger("tools.auto_research")

NAME        = "auto_research"
DESCRIPTION = (
    "Autonomous deep research: plans search queries, gathers sources, writes "
    "a structured report with citations, and can generate a PowerPoint. "
    "Inputs: topic, make_ppt (true/false)."
)
CATEGORY = "builtin"
ICON     = "book"
INPUTS = [
    {"name": "topic",    "label": "Research topic", "type": "text", "required": True},
    {"name": "make_ppt", "label": "Also make a PPT (true/false)", "type": "text"},
    {"name": "username", "label": "Username", "type": "text"},
]


def run(topic: str = "", make_ppt: str = "false", username: str = "default") -> dict:
    if not topic.strip():
        return {"error": "topic required"}
    from providers import AI
    import tools as _tools

    # 1. Plan search queries
    plan = AI.generate(
        "List 4 focused web search queries (one per line, no numbering) that "
        "together cover: %s" % topic,
        model="gpt-4o-mini", max_tokens=150, temperature=0.3)
    queries = [q.strip("-* ").strip() for q in plan.splitlines() if q.strip()][:4]
    if not queries:
        queries = [topic]

    # 2. Gather sources
    findings = []
    for q in queries:
        try:
            r = _tools.call("web_search", query=q, username=username)
            txt = str(r.get("result") or r.get("message") or r.get("error", ""))[:4000]
            findings.append("### Query: %s\n%s" % (q, txt))
        except Exception as e:
            findings.append("### Query: %s\n(search failed: %s)" % (q, e))

    # 3. Synthesize report (draft-and-verify: mini drafts, gpt-4o verifies)
    report = AI.draft_verify(
        "Write a professional research report on '%s' using ONLY the research "
        "notes below. Structure: Executive Summary, Background, Key Findings "
        "(with specifics and figures), Comparison/Analysis, Outlook, and a "
        "Sources section listing every source URL or reference that appears in "
        "the notes. Use markdown.\n\nRESEARCH NOTES:\n%s"
        % (topic, "\n\n".join(findings)[:26000]),
        max_tokens=3000)

    out = {"result": report, "queries": queries}

    # Research graph: persist the session as a growing research database
    try:
        import sqlite3, os as _os, json as _json
        dbp = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                            "aiaurum.db")
        con = sqlite3.connect(dbp, timeout=10)
        con.execute("""CREATE TABLE IF NOT EXISTS research_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT, question TEXT, queries TEXT, report TEXT,
            open_questions TEXT DEFAULT '',
            created_at INTEGER DEFAULT (strftime('%s','now')))""")
        oq = AI.generate(
            "List 3 open questions this research did NOT answer (one per line):\n\n"
            + report[:4000], model="gpt-4o-mini", max_tokens=120, temperature=0.3)
        con.execute("INSERT INTO research_sessions (username, question, queries, report, open_questions) "
                    "VALUES (?,?,?,?,?)",
                    (username, topic[:300], _json.dumps(queries), report[:8000], oq[:500]))
        con.commit(); con.close()
        out["open_questions"] = oq
    except Exception as e:
        log.debug("research graph store failed: %s", e)

    # 4. Optional PPT
    if str(make_ppt).lower() in ("true", "1", "yes"):
        try:
            slides_src = AI.generate(
                "Convert this report into concise slide content: 6-8 slides, "
                "each as 'Slide N: Title' followed by 3-5 bullet lines."
                "\n\n%s" % report[:8000],
                model="gpt-4o-mini", max_tokens=900, temperature=0.3)
            p = _tools.call("ppt_tool", content=slides_src,
                            title=topic[:60], username=username)
            out["ppt"] = p.get("message") or p.get("file") or p.get("error")
        except Exception as e:
            out["ppt"] = "PPT generation failed: %s" % e
    return out
