"""assistant/config.py — All constants and environment config."""
import os
from dotenv import load_dotenv
load_dotenv()

ASSISTANT_NAME   = "AI Aurum"
USER_NAME        = "Yuvan"

# GitHub Models (OpenAI-compatible)
GITHUB_TOKEN     = os.getenv("GITHUB_TOKEN", "")
GITHUB_MODEL     = "gpt-4o-mini"
USE_GITHUB_MODELS = True

# Gemini
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL       = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# Bluesminds (GPT-5)
BLUESMINDS_KEY   = os.getenv("BLUESMINDS_KEY", "")
BLUESMINDS_URL   = "https://api.bluesminds.com/v1/chat/completions"
BLUESMINDS_MODEL = "gpt-5-chat"

# Ollama (local)
USE_AI_BRAIN     = True
AI_MODEL         = "llama3.2"
OLLAMA_URL       = "http://localhost:11434/api/generate"

# Image generation
IMAGE_SAVE_FOLDER = os.path.join(os.path.expanduser("~"), "Pictures", "SmithAI")

# Speech
SPEAK_REPLIES    = True
SHOW_NOTIFICATIONS = True
SPEAK_ALERTS     = True

# Browser / search
SEARCH_ENGINE    = "https://www.google.com/search?q="
CHROME_PATH      = r"C:/Program Files/Google/Chrome/Application/chrome.exe %s"

SEARCH_TRIGGER_WORDS = [
    "latest","news","today","current","now","price","weather","score","stock",
    "2025","2026","release","who won","near me","buy","review","search","find",
    "look up","what happened","when did","who is","where is","how much","is there",
    "tell me about","what is the","recent","update","live",
]

OPEN_WORDS = ("open","launch","start","go to")

WEBSITES = {
    "youtube":   "https://www.youtube.com",
    "google":    "https://www.google.com",
    "gmail":     "https://mail.google.com",
    "maps":      "https://maps.google.com",
    "github":    "https://github.com",
    "whatsapp":  "https://web.whatsapp.com",
    "chatgpt":   "https://chat.openai.com",
    "claude":    "https://claude.ai",
    "facebook":  "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "twitter":   "https://twitter.com",
    "x":         "https://x.com",
}

APPS = {
    "notepad":"notepad","calculator":"calc","calc":"calc","paint":"mspaint",
    "chrome":"chrome","explorer":"explorer","file explorer":"explorer",
    "cmd":"cmd","command prompt":"cmd","settings":"ms-settings:",
    "word":"winword","excel":"excel","powerpoint":"powerpnt","spotify":"spotify",
}
