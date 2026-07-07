"""
services/memory_api.py -- Unified Memory API.

One facade over every memory store in AI Aurum:
  - user facts (db.neo_memories)          - vector semantic (ChromaDB)
  - 5-tier memory_layers (working/conversation/knowledge/vector/archive)
  - skills (db.user_skills)               - project context

Usage:
    from services.memory_api import memory
    memory.remember(user, "Prefers metric units")
    memory.recall(user, "what units does he like?")   # dict from all stores
    memory.search(user, "cable sizing")               # flat ranked list
    memory.forget(user, fact_id=3)
    memory.context(user, query)                       # system-prompt string
"""
import logging

log = logging.getLogger("services.memory_api")


class UnifiedMemory:

    # ── write ────────────────────────────────────────────────────────────────
    def remember(self, username: str, fact: str, kind: str = "fact") -> dict:
        """Store a fact. kind: fact | insight | relation ("a|rel|b")."""
        try:
            if kind == "relation" and fact.count("|") == 2:
                from services.memory_layers import mem
                a, rel, b = [s.strip() for s in fact.split("|")]
                return mem.knowledge.add_relation(username, a, rel, b)
            import db
            db.add_memory(username, fact)
            try:
                from services.memory_layers import mem
                mem.archive.store(username, fact, source=kind)
            except Exception:
                pass
            return {"ok": True, "stored": fact}
        except Exception as e:
            log.error("remember failed: %s", e)
            return {"error": str(e)}

    def store_conversation(self, username: str, user_msg: str, ai_reply: str,
                           chat_id: str = "") -> None:
        try:
            import vector_memory as vmem
            vmem.store_conversation(username, user_msg, ai_reply, chat_id)
        except Exception as e:
            log.debug("store_conversation: %s", e)

    # ── read ─────────────────────────────────────────────────────────────────
    def recall(self, username: str, query: str) -> dict:
        """Everything relevant, grouped by store."""
        out = {}
        try:
            from services.memory_layers import mem
            out.update(mem.recall(username, query))
        except Exception as e:
            log.debug("tier recall: %s", e)
        try:
            import db
            facts = db.get_memories(username)
            ql = query.lower()
            hits = [f for f in facts if any(w in str(f).lower()
                                            for w in ql.split() if len(w) > 3)]
            out["facts"] = (hits or facts)[:5]
        except Exception as e:
            log.debug("facts recall: %s", e)
        try:
            import db
            skills = db.search_skills(username, query, limit=3)
            if skills:
                out["skills"] = skills
        except Exception as e:
            log.debug("skills recall: %s", e)
        return out

    def search(self, username: str, query: str, limit: int = 10) -> list:
        """Flat ranked list of memory strings across all stores."""
        r = self.recall(username, query)
        flat = []
        for key in ("semantic", "facts", "archive"):
            for item in r.get(key, []) or []:
                flat.append(str(item))
        if r.get("knowledge"):
            flat.append(str(r["knowledge"]))
        return flat[:limit]

    def context(self, username: str, query: str) -> str:
        """Formatted string ready for a system prompt (memory + GraphRAG)."""
        parts = []
        try:
            from services.memory_layers import mem
            c = mem.context_string(username, query)
            if c:
                parts.append(c)
        except Exception:
            pass
        g = self.graph_walk(username, query)
        if g:
            parts.append("Connected knowledge (graph):\n" + g)
        return "\n\n".join(parts)

    def graph_walk(self, username: str, query: str, hops: int = 2,
                   limit: int = 12) -> str:
        """GraphRAG: find entities mentioned in the query, walk the knowledge
        graph N hops out, return the connected triples. Answers multi-hop
        questions flat vector search cannot ("who did I discuss X with, and
        what did they recommend?")."""
        try:
            import sqlite3, db as _db
            words = {w.lower() for w in query.split() if len(w) > 3}
            if not words:
                return ""
            con = sqlite3.connect(_db.DB_PATH, timeout=5)
            con.row_factory = sqlite3.Row
            try:
                clause = " OR ".join("lower(name) LIKE ?" for _ in words)
                seeds = {r["name"] for r in con.execute(
                    "SELECT name FROM kg_entities WHERE username=? AND (%s) LIMIT 5"
                    % clause, [username] + ["%%%s%%" % w for w in words])}
                if not seeds:
                    return ""
                triples, frontier, seen = [], set(seeds), set(seeds)
                for _ in range(hops):
                    if not frontier or len(triples) >= limit:
                        break
                    ph = ",".join("?" for _ in frontier)
                    rows = con.execute(
                        "SELECT source, relation, target FROM kg_relations "
                        "WHERE username=? AND (source IN (%s) OR target IN (%s)) "
                        "LIMIT ?" % (ph, ph),
                        [username] + list(frontier) * 2 + [limit]).fetchall()
                    nxt = set()
                    for r in rows:
                        t = "%s %s %s" % (r["source"], r["relation"], r["target"])
                        if t not in triples:
                            triples.append(t)
                        for node in (r["source"], r["target"]):
                            if node not in seen:
                                nxt.add(node); seen.add(node)
                    frontier = nxt
                return "\n".join("- " + t for t in triples[:limit])
            finally:
                con.close()
        except Exception as e:
            log.debug("graph walk failed: %s", e)
            return ""

    # ── delete ───────────────────────────────────────────────────────────────
    def forget(self, username: str, fact_id=None, fact_text: str = "") -> dict:
        try:
            import db, sqlite3
            con = sqlite3.connect(db.DB_PATH)
            if fact_id is not None:
                con.execute("DELETE FROM neo_memories WHERE id=? AND username=?",
                            (fact_id, username))
            elif fact_text:
                con.execute("DELETE FROM neo_memories WHERE username=? AND fact LIKE ?",
                            (username, "%" + fact_text + "%"))
            else:
                con.close()
                return {"error": "fact_id or fact_text required"}
            n = con.total_changes
            con.commit(); con.close()
            return {"ok": True, "deleted": n}
        except Exception as e:
            log.error("forget failed: %s", e)
            return {"error": str(e)}


memory = UnifiedMemory()
