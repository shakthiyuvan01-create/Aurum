"""agents/memory_manager_agent.py"""
from agents.base_agent import BaseAgent

class MemoryManagerAgent(BaseAgent):
    name  = "memory_manager"
    role  = "Knowledge & Memory Manager"
    model = "gpt-4o-mini"
    icon  = "🧠"
    tools = ["knowledge_graph", "skill_manager"]
    system_prompt = """You are the Memory Manager Agent. You curate and organise the AI's long-term knowledge.

Tasks:
- Extract important facts from conversations
- Store entities and relationships in the knowledge graph
- Identify patterns across sessions
- Surface relevant past knowledge for current tasks
- Prune stale or incorrect memories

Always classify knowledge: fact / relationship / preference / lesson / skill."""

    def extract_and_store(self, conversation: str, username: str) -> dict:
        prompt = f"""Extract key facts, entities, and relationships from this conversation.
Return JSON: {{"facts": [], "entities": [], "relationships": [{{"source":"","relation":"","target":""}}]}}
Conversation:
{conversation[:2000]}"""
        raw = self.think(prompt)
        try:
            import json
            clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            data = json.loads(clean)
            # Store relationships in knowledge graph
            for rel in data.get("relationships", []):
                self._call_tool("knowledge_graph", action="add_relation",
                               source=rel.get("source",""), target=rel.get("target",""),
                               relation=rel.get("relation",""), username=username)
            return data
        except Exception:
            return {"facts": [], "entities": [], "relationships": []}
