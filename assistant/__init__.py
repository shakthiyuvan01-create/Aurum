"""
assistant/__init__.py — public API re-exports for backward compatibility.
All existing code that does `import assistant as _asst` still works unchanged.
"""
from assistant.config   import (
    ASSISTANT_NAME, USER_NAME, GITHUB_TOKEN, GITHUB_MODEL,
    GEMINI_API_KEY, BLUESMINDS_KEY, BLUESMINDS_MODEL,
    AI_MODEL, OLLAMA_URL, USE_AI_BRAIN, USE_GITHUB_MODELS,
)
from assistant.memory   import (
    save_neo_memory, get_memory, clear_memory,
    _memory_context, load_memory, save_memory, user_name,
)
from assistant.speech   import say, speak, alert, _powershell_speak
from assistant.models   import (
    _remember_turn, ask_gemini, ask_github_models, analyze_and_pick,
    ask_bluesminds, ask_ollama, ask_ai_brain, _recent_turns,
)
from assistant.image    import create_image, handle_images
from assistant.commands import (
    greet, handle_personal, handle_commands, handle_basics,
    add_reminder, start_reminder_watcher,
)
from assistant.web      import (
    fetch_web_search, needs_web, open_url, launch_app,
    get_open_target, do_open,
)
from assistant.router   import answer

__all__ = [
    "ASSISTANT_NAME", "USER_NAME", "GITHUB_TOKEN", "GITHUB_MODEL",
    "GEMINI_API_KEY", "AI_MODEL", "USE_AI_BRAIN",
    "say", "speak", "alert",
    "_remember_turn", "ask_ai_brain", "ask_gemini", "ask_github_models",
    "ask_bluesminds", "ask_ollama", "analyze_and_pick",
    "save_neo_memory", "get_memory", "clear_memory", "_memory_context",
    "load_memory", "save_memory", "user_name",
    "create_image", "handle_images",
    "greet", "handle_personal", "handle_commands", "handle_basics",
    "add_reminder", "start_reminder_watcher",
    "fetch_web_search", "needs_web", "open_url", "do_open",
    "answer",
]
