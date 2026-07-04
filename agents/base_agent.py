"""agents/base_agent.py — Base class for all specialist agents."""
from __future__ import annotations
import json, logging, os, time
from abc import ABC

log = logging.getLogger("agents")


class BaseAgent(ABC):
    name:          str       = "agent"
    role:          str       = ""
    model:         str       = "gpt-4o-mini"
    system_prompt: str       = ""
    tools:         list[str] = []
    icon:          str       = "🤖"

    def __init__(self, username: str = "default"):
        self.username = username
        self._memory: list[dict] = []
        self._log = logging.getLogger(f"agents.{self.name}")

    def _call_model(self, messages: list[dict], max_tokens: int = 1500) -> str:
        # Unified provider layer: GitHub -> Gemini -> OpenAI -> Ollama fallback
        try:
            from providers import AI
            return AI.chat(messages, model=self.model,
                           max_tokens=max_tokens, temperature=0.4)
        except Exception as e:
            self._log.error("_call_model: %s", e)
            return f"[Exception: {e}]"

    # ── Agent-to-agent messaging (services/agent_mailbox) ────────────────────
    def send_message(self, to_agent: str, content: str) -> None:
        from services.agent_mailbox import mailbox
        mailbox.send(self.username, self.name, to_agent, content)

    def read_messages(self) -> list[dict]:
        from services.agent_mailbox import mailbox
        return mailbox.drain(self.username, self.name)

    def _call_tool(self, tool_name: str, **kwargs) -> dict:
        try:
            import tools as _tools
            return _tools.call(tool_name, username=self.username, **kwargs)
        except Exception as e:
            return {"error": str(e)}

    def think(self, task: str, context: str = "") -> str:
        """Run agent on task. Records health metrics and fires events. Returns text."""
        t0      = time.time()
        success = True
        result  = ""
        try:
            sys_msg = self.system_prompt
            if context:
                sys_msg += f"\n\nContext:\n{context}"
            messages = [
                {"role": "system",    "content": sys_msg},
                *self._memory[-6:],
                {"role": "user",      "content": task},
            ]
            result = self._call_model(messages)
            self._memory.append({"role": "user",      "content": task})
            self._memory.append({"role": "assistant", "content": result})
        except Exception as e:
            success = False
            result  = f"[Agent error: {e}]"

        latency_ms = int((time.time() - t0) * 1000)

        try:
            from services.agent_health import health
            health.record(self.name, latency_ms=latency_ms, success=success)
        except Exception:
            pass

        try:
            from services.event_bus import bus
            topic = "agent.completed" if success else "agent.failed"
            bus.emit(topic, data={"agent": self.name, "task": task[:80], "latency_ms": latency_ms},
                     source=self.name, async_=True)
        except Exception:
            pass

        return result

    def scored_think(self, task: str, context: str = "") -> dict:
        """Like think() but returns confidence + reasoning_quality for CEO decision-making."""
        answer     = self.think(task, context)
        confidence = 0.75
        reasoning  = 0.75

        try:
            token = os.getenv("GITHUB_TOKEN", "")
            if token and answer and not answer.startswith("["):
                import requests as _r
                prompt = (
                    f"Rate this AI response (0.0-1.0 each).\n"
                    f"Question: {task[:200]}\nResponse: {answer[:400]}\n\n"
                    'Reply ONLY valid JSON: {"confidence": 0.XX, "reasoning_quality": 0.XX}'
                )
                r = _r.post(
                    "https://models.inference.ai.azure.com/chat/completions",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}],
                          "max_tokens": 40, "temperature": 0.0},
                    timeout=8,
                )
                if r.status_code == 200:
                    raw  = r.json()["choices"][0]["message"]["content"].strip()
                    data = json.loads(raw.lstrip("```json").lstrip("```").rstrip("```").strip())
                    confidence = max(0.0, min(1.0, float(data.get("confidence", 0.75))))
                    reasoning  = max(0.0, min(1.0, float(data.get("reasoning_quality", 0.75))))
        except Exception:
            pass

        return {
            "answer":            answer,
            "confidence":        round(confidence, 2),
            "reasoning_quality": round(reasoning,  2),
            "agent":             self.name,
            "model":             self.model,
        }

    def to_dict(self) -> dict:
        return {"name": self.name, "role": self.role, "model": self.model,
                "icon": self.icon, "tools": self.tools}
