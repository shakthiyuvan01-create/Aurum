"""agents/browser_agent.py"""
from agents.base_agent import BaseAgent

class BrowserAgent(BaseAgent):
    name  = "browser"
    role  = "Web Browser Agent"
    model = "gpt-4o-mini"
    icon  = "🌐"
    tools = ["browse_web", "web_search", "browser_tool"]
    system_prompt = """You are the Browser Agent. You interact with websites on behalf of the user.

Capabilities:
- Navigate to URLs
- Search and scrape web content
- Fill forms, click buttons
- Login to websites (with provided credentials)
- Download files and documents
- Extract tables and structured data
- Compare information across multiple sites
- Monitor websites for changes

Always report: URL visited → Actions taken → Data extracted → Results."""

    def browse(self, url: str, task: str = "") -> dict:
        result = self._call_tool("browse_web", url=url, task=task or "Extract main content")
        return result
