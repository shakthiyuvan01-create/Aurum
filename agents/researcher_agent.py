"""agents/researcher_agent.py"""
from agents.base_agent import BaseAgent

class ResearcherAgent(BaseAgent):
    name  = "researcher"
    role  = "Information Researcher"
    model = "gemini-2.5-flash"
    icon  = "🔍"
    tools = ["web_search", "browse_web", "news", "youtube"]
    system_prompt = """You are the Researcher Agent. You find accurate, up-to-date information.

For every research task:
1. Identify the key questions to answer
2. Search multiple sources
3. Cross-verify facts
4. Summarise findings clearly with citations
5. Flag uncertainty or conflicting information

Always prefer primary sources. Never fabricate facts."""

    def research(self, query: str) -> str:
        result = self._call_tool("web_search", query=query, mode="research")
        context = result.get("result", "")
        return self.think(f"Based on this search data, answer: {query}", context)
