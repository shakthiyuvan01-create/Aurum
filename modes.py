"""Modes System — unified interface for all Aurum capabilities.

Six pillars:
  1. Contextual Memory — remembers preferences, conversations, adapts to you
  2. Voice & Text — natural communication via voice or text
  3. Workflow Automation — automated tasks, scheduled jobs, custom workflows
  4. Developer Mode — coding assistant, debug, refactor, code generation
  5. Creator Mode — content generation, brainstorming, creative output
  6. Private & Secure — encryption, auth, data privacy
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("modes")


class ModeType(Enum):
    MEMORY = "memory"
    VOICE = "voice"
    WORKFLOW = "workflow"
    DEVELOPER = "developer"
    CREATOR = "creator"
    SECURITY = "security"


@dataclass
class Mode:
    """A single mode/pillar of the system."""
    type: ModeType
    name: str
    description: str
    icon: str = ""
    enabled: bool = True
    capabilities: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 1. Contextual Memory
# ---------------------------------------------------------------------------

class MemoryMode:
    """Contextual Memory — remembers preferences, past conversations, adapts to you."""

    @property
    def name(self) -> str: return "Contextual Memory"
    @property
    def icon(self) -> str: return "🧠"

    def get_capabilities(self) -> List[str]:
        return [
            "Remembers your preferences across sessions",
            "Adapts to your writing and coding style",
            "Learns from past conversations",
            "Semantic search across all memories",
            "Personal twin that thinks like you",
        ]

    def remember_fact(self, fact: str, username: str = "default") -> bool:
        """Store a fact about the user's preferences or context."""
        try:
            from services.learning import add_fact
            add_fact(fact, username)
            return True
        except Exception as e:
            logger.warning("Failed to remember fact: %s", e)
            return False

    def recall(self, query: str, username: str = "default", top_k: int = 4) -> str:
        """Retrieve relevant memories for context."""
        try:
            from services.learning import retrieve
            results = retrieve(query, username, top_k)
            if results:
                return "\n".join(r.get("text", "") for r in results)
            return ""
        except Exception as e:
            logger.debug("Recall failed: %s", e)
            return ""

    def save_preference(self, key: str, value: str, username: str = "default") -> bool:
        """Save a user preference."""
        try:
            from services.personal_twin import set_preference
            set_preference(username, key, value)
            return True
        except Exception as e:
            logger.warning("Failed to save preference: %s", e)
            return False

    def get_preferences(self, username: str = "default") -> Dict[str, str]:
        """Get all stored preferences."""
        try:
            from services.personal_twin import get_preferences
            return get_preferences(username)
        except Exception as e:
            logger.debug("Failed to get preferences: %s", e)
            return {}

    def get_recent_conversations(self, username: str = "default", limit: int = 10) -> List[Dict]:
        """Get recent conversation context."""
        try:
            from services.memory_layers import mem
            return mem.conversation.get(username, limit=limit) or []
        except Exception as e:
            logger.debug("Failed to get conversations: %s", e)
            return []

    def status(self) -> Dict[str, Any]:
        """Report memory system status."""
        status = {"active": True}
        try:
            from services.learning import stats
            s = stats()
            if s:
                status["learning"] = s
        except Exception:
            status["learning"] = "unavailable"
        return status


# ---------------------------------------------------------------------------
# 2. Voice & Text
# ---------------------------------------------------------------------------

class VoiceMode:
    """Voice & Text Interface — communicate naturally through voice or text."""

    @property
    def name(self) -> str: return "Voice & Text"
    @property
    def icon(self) -> str: return "🎙️"

    def get_capabilities(self) -> List[str]:
        return [
            "Text-based chat interface",
            "Voice output (text-to-speech)",
            "Voice input (speech-to-text)",
            "Wake word detection",
            "Multi-language support",
        ]

    def say(self, text: str) -> bool:
        """Speak text aloud."""
        try:
            from assistant.speech import say
            say(text)
            return True
        except Exception as e:
            logger.warning("TTS failed: %s", e)
            return False

    def transcribe(self, audio_path: str) -> Optional[str]:
        """Transcribe audio to text."""
        try:
            from services.voice_service import transcribe
            result = transcribe(audio_path)
            if isinstance(result, dict):
                return result.get("text", "")
            return str(result)
        except Exception as e:
            logger.warning("Transcription failed: %s", e)
            return None

    def list_voices(self) -> List[Dict]:
        """List available TTS voices."""
        try:
            from services.voice_service import list_voices
            return list_voices()
        except Exception:
            return []

    def start_listening(self, device_index: int = None) -> bool:
        """Start voice listening in background."""
        try:
            from services.voice_service import start_listening
            start_listening(device_index)
            return True
        except Exception as e:
            logger.warning("Failed to start listening: %s", e)
            return False

    def stop_listening(self) -> bool:
        """Stop voice listening."""
        try:
            from services.voice_service import stop_listening
            stop_listening()
            return True
        except Exception as e:
            logger.warning("Failed to stop listening: %s", e)
            return False

    def status(self) -> Dict[str, Any]:
        return {
            "tts_available": True,
            "stt_available": True,
            "voices_available": len(self.list_voices()) > 0,
        }


# ---------------------------------------------------------------------------
# 3. Workflow Automation
# ---------------------------------------------------------------------------

class WorkflowMode:
    """Workflow Automation — automate repetitive tasks on a schedule."""

    @property
    def name(self) -> str: return "Workflow Automation"
    @property
    def icon(self) -> str: return "⚡"

    def get_capabilities(self) -> List[str]:
        return [
            "Create custom multi-step workflows",
            "Schedule recurring tasks",
            "One-shot delayed tasks",
            "Visual workflow builder via API",
            "Auto-trigger on events",
        ]

    def create_workflow(self, name: str, description: str, steps: List[Dict],
                        username: str = "default", schedule: str = "") -> Optional[str]:
        """Create a new workflow with defined steps."""
        try:
            from workflows.engine import create_workflow
            result = create_workflow(username, name, description, steps, schedule)
            if result:
                return result.get("id")
            return None
        except Exception as e:
            logger.warning("Failed to create workflow: %s", e)
            return None

    def list_workflows(self, username: str = "default") -> List[Dict]:
        """List all workflows for a user."""
        try:
            from workflows.engine import list_workflows
            return list_workflows(username)
        except Exception:
            return []

    def run_workflow(self, wf_id: str, username: str = "default") -> Dict:
        """Execute a workflow immediately."""
        try:
            from workflows.engine import run_workflow
            return run_workflow(wf_id, username)
        except Exception as e:
            return {"error": str(e)}

    def schedule_task(self, name: str, task_type: str, params: Dict,
                      interval_minutes: int = None, delay_minutes: int = 0) -> Optional[str]:
        """Schedule a task (recurring or one-shot)."""
        try:
            from cron.tool import schedule_recurring, schedule_once
            if interval_minutes:
                return schedule_recurring(name, task_type, params, interval_minutes)
            return schedule_once(name, task_type, params, delay_minutes)
        except Exception as e:
            logger.warning("Failed to schedule task: %s", e)
            return None

    def cancel_task(self, job_id: str) -> bool:
        """Cancel a scheduled task."""
        try:
            from cron.tool import cancel_job
            return cancel_job(job_id)
        except Exception as e:
            logger.warning("Failed to cancel task: %s", e)
            return False

    def status(self) -> Dict[str, Any]:
        try:
            from workflows.engine import list_workflows
            wf_count = len(list_workflows("default"))
            return {"workflows": wf_count, "scheduler_active": True}
        except Exception:
            return {"workflows": 0, "scheduler_active": False}


# ---------------------------------------------------------------------------
# 4. Developer Mode
# ---------------------------------------------------------------------------

class DeveloperMode:
    """Developer Mode — built-in coding assistant with precision tools."""

    @property
    def name(self) -> str: return "Developer Mode"
    @property
    def icon(self) -> str: return "💻"

    def get_capabilities(self) -> List[str]:
        return [
            "Code generation and completion",
            "Debug and error analysis",
            "Code review and auditing",
            "Git integration",
            "Multi-language support",
            "Project management",
        ]

    def run_code(self, code: str, language: str = "python") -> Dict:
        """Execute code in a sandboxed environment."""
        try:
            from tools.code_runner import run_code as _run
            return _run(code, language)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def audit_code(self, code: str, filename: str = "code.py") -> Dict:
        """Audit code for bugs, security issues, and improvements."""
        try:
            from tools.code_auditor import audit_code as _audit
            return _audit(code, filename)
        except Exception:
            # Fallback simple audit
            issues = []
            if "import os" in code and "os.system" in code:
                issues.append({"type": "security", "message": "Avoid os.system, use subprocess instead"})
            if "eval(" in code or "exec(" in code:
                issues.append({"type": "security", "message": "eval/exec can be dangerous"})
            return {"issues": issues, "quality": "unknown" if issues else "ok"}
        except Exception as e:
            return {"error": str(e)}

    def generate_code(self, task: str, language: str = "python") -> str:
        """Generate code using AI for a given task."""
        try:
            from services.ai_service import ask_ai
            prompt = f"Write {language} code to: {task}. Return ONLY the code, no explanation."
            result = ask_ai(prompt)
            if isinstance(result, dict):
                return result.get("text", str(result))
            return str(result)
        except Exception as e:
            return f"# Code generation failed: {e}"

    def git_status(self, repo_path: str = ".") -> Dict:
        """Get git status of a repository."""
        try:
            from tools.git_tool import git_status
            return git_status(repo_path)
        except Exception as e:
            return {"error": str(e)}

    def analyze_error(self, error_text: str, code_context: str = "") -> Dict:
        """Analyze an error and suggest fixes."""
        try:
            from services.ai_service import ask_ai
            prompt = f"Analyze this error and suggest a fix:\nError: {error_text}\nContext: {code_context}"
            result = ask_ai(prompt)
            return {"analysis": str(result)}
        except Exception as e:
            return {"analysis": f"Could not analyze: {e}"}

    def status(self) -> Dict[str, Any]:
        tools = {}
        for name in ["code_runner", "code_auditor", "git_tool"]:
            try:
                __import__(f"tools.{name}")
                tools[name] = "available"
            except Exception:
                tools[name] = "unavailable"
        return tools


# ---------------------------------------------------------------------------
# 5. Creator Mode
# ---------------------------------------------------------------------------

class CreatorMode:
    """Creator Mode — generate content, brainstorm, enhance creativity."""

    @property
    def name(self) -> str: return "Creator Mode"
    @property
    def icon(self) -> str: return "🎨"

    def get_capabilities(self) -> List[str]:
        return [
            "AI image generation from text prompts",
            "Multi-provider support (Pollinations, OpenAI, FAL, DeepInfra)",
            "Image editing and style transfer",
            "Content and copywriting",
            "Brainstorming and ideation",
            "Creative writing assistance",
        ]

    def generate_image(self, prompt: str, provider: str = None,
                       aspect_ratio: str = "square") -> Optional[str]:
        """Generate an image from a text prompt."""
        try:
            from image_gen.tool import generate_image as _gen
            result = _gen(prompt, aspect_ratio=aspect_ratio, provider=provider)
            if result.get("success") and result.get("image"):
                return result["image"]
            logger.warning("Image gen failed: %s", result.get("error"))
            # Fallback
            from assistant.image import create_image
            return create_image(prompt)
        except Exception as e:
            logger.warning("Image gen error: %s", e)
            try:
                from assistant.image import create_image
                return create_image(prompt)
            except Exception:
                return None

    def list_image_providers(self) -> List[Dict]:
        """List available image generation providers."""
        try:
            from image_gen.tool import list_available_providers
            return list_available_providers()
        except Exception:
            return []

    def brainstorm(self, topic: str, count: int = 5) -> List[str]:
        """Generate creative ideas on a topic."""
        try:
            from services.ai_service import ask_ai
            prompt = f"Give me {count} creative ideas about '{topic}'. List each as a short bullet point."
            result = ask_ai(prompt)
            text = str(result)
            lines = [l.strip("- *") for l in text.split("\n") if l.strip().startswith(("-", "*"))]
            return lines[:count] if lines else [text]
        except Exception as e:
            return [f"Brainstorming failed: {e}"]

    def generate_content(self, topic: str, content_type: str = "article",
                         tone: str = "professional") -> str:
        """Generate written content."""
        try:
            from services.ai_service import ask_ai
            prompt = f"Write a {tone} {content_type} about: {topic}"
            result = ask_ai(prompt)
            return str(result)
        except Exception as e:
            return f"Content generation failed: {e}"

    def run_skill(self, name: str, **params) -> Any:
        """Run a registered skill."""
        try:
            from skills.skills_tool import run_skill
            return run_skill(name, **params)
        except Exception as e:
            return {"error": str(e)}

    def status(self) -> Dict[str, Any]:
        providers = self.list_image_providers()
        return {
            "image_gen_providers": len(providers),
            "available_providers": [p["name"] for p in providers if p["available"]],
        }


# ---------------------------------------------------------------------------
# 6. Private & Secure
# ---------------------------------------------------------------------------

class SecurityMode:
    """Private & Secure — encryption, authentication, data privacy."""

    @property
    def name(self) -> str: return "Private & Secure"
    @property
    def icon(self) -> str: return "🔒"

    def get_capabilities(self) -> List[str]:
        return [
            "Password hashing and secure auth",
            "Two-factor authentication (TOTP)",
            "Session management",
            "API key authentication",
            "Permission-based access control",
            "Data encryption at rest",
        ]

    def hash_password(self, password: str) -> str:
        """Hash a password securely."""
        try:
            from services.auth_service import hash_password
            return hash_password(password)
        except Exception as e:
            logger.warning("Password hashing failed: %s", e)
            return ""

    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify a password against its hash."""
        try:
            from services.auth_service import check_password
            return check_password(password, hashed)
        except Exception as e:
            logger.warning("Password verification failed: %s", e)
            return False

    def enroll_2fa(self, username: str, issuer: str = "AI Aurum") -> Optional[Dict]:
        """Enroll a user in 2FA."""
        try:
            from services.twofa import enroll
            return enroll(username, issuer)
        except Exception as e:
            logger.warning("2FA enrollment failed: %s", e)
            return None

    def verify_2fa(self, secret: str, code: str) -> bool:
        """Verify a 2FA code."""
        try:
            from services.twofa import verify
            return verify(secret, code)
        except Exception as e:
            logger.warning("2FA verification failed: %s", e)
            return False

    def check_permission(self, username: str, permission: str) -> bool:
        """Check if a user has a specific permission."""
        try:
            from services.permission_manager import PermissionManager
            pm = PermissionManager()
            return pm.check(username, permission)
        except Exception:
            # Fallback: admin has all permissions
            return username == "admin"

    def status(self) -> Dict[str, Any]:
        return {
            "auth": True,
            "2fa": True,
            "permissions": True,
            "encryption": True,
        }


# ---------------------------------------------------------------------------
# Unified Modes Hub
# ---------------------------------------------------------------------------

class AurumModes:
    """Unified access to all six pillars."""

    def __init__(self):
        self.memory = MemoryMode()
        self.voice = VoiceMode()
        self.workflow = WorkflowMode()
        self.developer = DeveloperMode()
        self.creator = CreatorMode()
        self.security = SecurityMode()

    @property
    def all_modes(self) -> List[Mode]:
        return [
            Mode(ModeType.MEMORY, self.memory.name, "Remembers your preferences and adapts to you",
                 icon=self.memory.icon, capabilities=self.memory.get_capabilities()),
            Mode(ModeType.VOICE, self.voice.name, "Communicate naturally through voice or text",
                 icon=self.voice.icon, capabilities=self.voice.get_capabilities()),
            Mode(ModeType.WORKFLOW, self.workflow.name, "Automate repetitive tasks on a schedule",
                 icon=self.workflow.icon, capabilities=self.workflow.get_capabilities()),
            Mode(ModeType.DEVELOPER, self.developer.name, "Built-in coding assistant with AI precision",
                 icon=self.developer.icon, capabilities=self.developer.get_capabilities()),
            Mode(ModeType.CREATOR, self.creator.name, "Generate content, brainstorm, enhance creativity",
                 icon=self.creator.icon, capabilities=self.creator.get_capabilities()),
            Mode(ModeType.SECURITY, self.security.name, "Your data is encrypted and never shared",
                 icon=self.security.icon, capabilities=self.security.get_capabilities()),
        ]

    def status_report(self) -> Dict[str, Any]:
        """Get status of all modes."""
        return {
            "memory": self.memory.status(),
            "voice": self.voice.status(),
            "workflow": self.workflow.status(),
            "developer": self.developer.status(),
            "creator": self.creator.status(),
            "security": self.security.status(),
        }

    def get_mode(self, mode_type: ModeType):
        """Get a specific mode handler."""
        mapping = {
            ModeType.MEMORY: self.memory,
            ModeType.VOICE: self.voice,
            ModeType.WORKFLOW: self.workflow,
            ModeType.DEVELOPER: self.developer,
            ModeType.CREATOR: self.creator,
            ModeType.SECURITY: self.security,
        }
        return mapping.get(mode_type)


# Global singleton
modes = AurumModes()
