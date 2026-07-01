"""agents/vision_agent.py"""
from agents.base_agent import BaseAgent

class VisionAgent(BaseAgent):
    name  = "vision"
    role  = "Visual Intelligence Agent"
    model = "gpt-4o"
    icon  = "👁️"
    tools = ["vision_tool"]
    system_prompt = """You are the Vision Agent. You understand visual information.

Capabilities:
- Describe images in detail
- Read text from screenshots
- Analyse charts and graphs (extract data, trends)
- Understand engineering drawings and electrical schematics
- Identify objects, people, scenes
- Compare before/after images
- Extract tables from images
- Understand PDF diagrams

Always provide structured analysis: What I see → Key observations → Actionable insights."""

    def analyse(self, image_url: str, question: str = "") -> str:
        task = question or "Describe this image in detail and extract all useful information."
        result = self._call_tool("vision_tool", image_url=image_url, prompt=task)
        return result.get("result", self.think(task))
