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
        """Formatted string ready for a system prompt."""
        try:
            from services.memory_layers import mem
            return mem.context_string(username, query)
        except Exception:
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
