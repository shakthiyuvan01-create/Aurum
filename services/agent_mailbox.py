"""
services/agent_mailbox.py -- addressed agent-to-agent messages.

Agents communicate during team runs:
  - an agent writes "@reviewer: please double-check the SQL" in its output
  - run_team delivers it; the reviewer sees it in its context as
    "[Message from programmer]: please double-check the SQL"

Also fires "agent.message" on the event bus for logs/analytics.
"""
import re
import threading
import logging

log = logging.getLogger("services.agent_mailbox")


class AgentMailbox:
    def __init__(self):
        self._lock = threading.Lock()
        self._boxes: dict = {}   # (username, agent) -> list[dict]

    def send(self, username: str, from_agent: str, to_agent: str, content: str):
        with self._lock:
            self._boxes.setdefault((username, to_agent), []).append(
                {"from": from_agent, "content": content.strip()[:2000]})
        try:
            from services.event_bus import bus
            bus.emit("agent.message", {"username": username, "from": from_agent,
                                       "to": to_agent, "content": content[:200]},
                     async_=True)
        except Exception:
            pass
        log.info("mail %s -> %s (%s)", from_agent, to_agent, username)

    def drain(self, username: str, agent: str) -> list:
        """Read and clear this agent's inbox."""
        with self._lock:
            return self._boxes.pop((username, agent), [])

    def deliver_mentions(self, username: str, from_agent: str, text: str,
                         known_agents: list) -> int:
        """Parse '@agent: message' mentions out of an agent's output and
        deliver them. Returns number of messages sent."""
        n = 0
        for m in re.finditer(r"@(\w+):\s*([^\n]+)", text or ""):
            to, content = m.group(1).lower(), m.group(2)
            if to in known_agents and to != from_agent:
                self.send(username, from_agent, to, content)
                n += 1
        return n


mailbox = AgentMailbox()
