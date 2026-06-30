<div align="center">

<img src="aiaurum_logo.png" alt="AI Aurum Logo" width="160"/>

# ✦ AI AURUM

**The Personal AI Assistant from the Future**

[![Made by Yuvan Industries](https://img.shields.io/badge/Made%20by-Yuvan%20Industries-gold?style=for-the-badge)](https://github.com)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-Web%20App-black?style=for-the-badge&logo=flask)](https://flask.palletsprojects.com)
[![AI Powered](https://img.shields.io/badge/AI-GPT--4o%20%2B%20Agent%20Loop-orange?style=for-the-badge)](https://github.com)
[![Deploy on Render](https://img.shields.io/badge/Deploy-Render.com-46E3B7?style=for-the-badge&logo=render)](https://yuvanaurum.onrender.com)

> *"The Future Is Not Coming. We Are Building It."*
> — Yuvan Industries

</div>

---

## ✨ What is AI Aurum?

**AI Aurum** is a full-featured personal AI assistant that runs in your browser. It combines a smart ReAct agent loop, long-term semantic memory, real-time SSE streaming, multimodal vision, image generation, a built-in code editor, file browser, Git integration, browser automation, task scheduling, document generation, deep web research, and a plugin tool system — all from a clean, modern web interface.

Built by **Yuvan Industries** — a forward-thinking technology company from the future.

🌐 **Live:** [yuvanaurum.onrender.com](https://yuvanaurum.onrender.com)

---

## ⚡ Features

### 🤖 AI & Chat
| Feature | Description |
|---|---|
| 🧠 **Multi-Model Routing** | Auto-routes to GPT-4o (code), GPT-4o-mini (fast), or main model based on query type |
| 🔄 **ReAct Agent Loop** | Plan → Execute Tools concurrently → Stream Answer in one turn |
| 📡 **SSE Streaming** | Token-by-token streaming with animated typing indicator |
| 🖼️ **Image Generation** | Creates images via Pollinations AI — no extra API key needed |
| 🗂️ **Chat History** | Full conversation history with sidebar browser |
| 👁️ **Vision / Multimodal** | Send images to GPT-4o for analysis, description, or OCR |
| 📷 **Camera Capture** | Take a photo directly from the UI and send it to the AI |

### 🧩 Memory
| Feature | Description |
|---|---|
| 🗄️ **SQLite Memory** | All user data, chats, settings, and memories stored in `aiaurum.db` |
| 🔍 **Vector Memory** | ChromaDB semantic search — retrieves relevant past conversations |
| 📝 **Personal Facts** | Remembers your name, notes, and preferences permanently |
| ⚡ **Smart Retrieval** | Recency + importance + similarity scoring for best memory results |

### 🔧 Tools & Plugins
| Tool | What it does |
|---|---|
| 🌤️ **Weather** | Live weather for any city |
| 🧮 **Calculator** | Arithmetic and expression evaluation |
| 📰 **News** | Latest headlines on any topic |
| ⏰ **Reminders** | Set reminders by natural language |
| 📅 **Calendar** | Add and view calendar events |
| 📧 **Email** | Draft and send emails |
| 💻 **Code Runner** | Execute Python/JS/Bash in sandbox |
| 🔀 **Git** | Run Git commands from the UI |
| 🌐 **Web Search** | Live DuckDuckGo search |
| 🔗 **Web Browse** | Fetch and read any URL |
| 📺 **YouTube** | Search and summarise YouTube videos |
| 🔬 **Deep Research** | Multi-step research with synthesis |
| 📄 **PDF / DOCX / PPT** | Generate and analyse documents |
| 🤖 **Browser Automation** | Playwright-powered web automation |
| ⏱️ **Task Scheduler** | Schedule recurring AI tasks with APScheduler |
| 🔗 **Workflow Chains** | Chain multiple tools in sequence |

Tools are auto-discovered from `tools/` — drop a `.py` file to add a new plugin.

### 💻 Coding Panel
| Tab | Feature |
|---|---|
| ✏️ **Editor** | CodeMirror 5 with syntax highlighting, multi-language, run & save |
| 📁 **Files** | Full project file browser — navigate, open, edit, create files & folders |
| 🔀 **Git** | Run any Git command and see output inline |
| 🐛 **Debugger** | Paste broken code → AI explains what's wrong and how to fix it |

### 🔒 Security & Users
| Feature | Description |
|---|---|
| 👤 **Multi-User Login** | Per-user sessions, memory, and settings |
| 👻 **Guest Mode** | One-click guest access — chat works, account features locked |
| 🛡️ **Role-Based Access** | `user`, `admin`, `readonly`, `guest` roles |
| 🔑 **Admin Panel** | `/admin/users` and `/admin/metrics` for managing users and tool stats |
| 🧱 **Centralised Errors** | Typed exceptions (`BadRequest`, `Forbidden`, etc.) with JSON responses |

---

## 🧠 Architecture

```
User Message
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│                      AI Aurum Agent                     │
│                                                         │
│  Phase 1 — Plan (low tokens, fast)                      │
│    LLM sees tools schema → decides which tools needed   │
│                                                         │
│  Phase 2 — Execute (concurrent via ThreadPoolExecutor)  │
│    weather / calculator / news / web_search / vision …  │
│    → results injected back into context                 │
│                                                         │
│  Phase 3 — Stream Answer                                │
│    Final LLM call streams token-by-token via SSE        │
└─────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│                     Memory System                       │
│                                                         │
│  SQLite (aiaurum.db)     ←→   ChromaDB (vector store)   │
│  • chats                       • semantic retrieval     │
│  • memories / facts            • recency + importance   │
│  • settings / users / roles                             │
└─────────────────────────────────────────────────────────┘
```

---

## 📦 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/AIAurum.git
cd AIAurum
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Create a `.env` File

```env
GITHUB_TOKEN=your_github_token_here
OPENAI_API_KEY=your_openai_key_here        # optional
GEMINI_API_KEY=your_gemini_key_here        # optional
OPENWEATHER_API_KEY=your_weather_key       # optional
GOOGLE_API_KEY=your_google_key             # optional
ADMIN_USERNAMES=yourusername               # comma-separated admin accounts

# Optional model overrides
MAIN_MODEL=gpt-4o-mini
CODE_MODEL=gpt-4o
FAST_MODEL=gpt-4o-mini
```

| Key | Where to get it |
|---|---|
| `GITHUB_TOKEN` | [github.com/settings/tokens](https://github.com/settings/tokens) → Models permission |
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) |

### 4. Run

```bash
python app.py
```

Open `http://localhost:5000` — log in or continue as Guest. 🎉

---

## ☁️ Deploy to Render

A `render.yaml` is included. Connect this repo at [render.com](https://render.com) and it deploys automatically to `yuvanaurum.onrender.com`. Set your API keys in the Render dashboard under Environment Variables.

---

## 🗂️ Project Structure

```
AIAurum/
│
├── app.py                  # Flask entry point — Blueprint registration
├── assistant.py            # AI calls, image gen, memory helpers
├── agent.py                # ReAct agent loop (Plan → Execute → Stream)
├── db.py                   # SQLite helpers — users, chats, memory, settings
├── vector_memory.py        # ChromaDB semantic memory
│
├── config/
│   ├── base.py             # All settings with env-var overrides
│   ├── development.py
│   ├── production.py
│   └── testing.py
│
├── routes/
│   ├── auth.py             # /login  /register  /guest  /logout
│   ├── chat.py             # /  /ask  /greet  /project  /chats  /memory
│   ├── stream_routes.py    # /stream (SSE)
│   ├── files.py            # /files/*  /code/run  /git/push
│   ├── upload.py           # /upload/image  /screenshot  /logo
│   ├── tools_routes.py     # /tools  /tools/run  /tts  /docs  /reminders
│   ├── settings.py         # /settings/personality
│   ├── research_routes.py  # /research  /analyze
│   └── admin.py            # /admin/users  /admin/metrics
│
├── services/
│   ├── auth_service.py     # login_required, no_guests, require_role
│   ├── ai_service.py       # Model routing (fast/code/main)
│   ├── error_handler.py    # Typed exceptions + Flask error handlers
│   ├── chat_service.py     # Chat history helpers
│   └── speech_service.py   # TTS
│
├── tools/
│   ├── __init__.py         # Tool registry, concurrent execution
│   ├── tool_metrics.py     # Per-tool SQLite metrics (runtime, failures)
│   ├── weather.py
│   ├── calculator.py
│   ├── news.py
│   ├── reminders.py
│   ├── calendar_tool.py
│   ├── web_search.py
│   ├── browser_tool.py
│   ├── youtube_tool.py
│   ├── deep_research.py
│   ├── vision_tool.py
│   ├── code_runner.py
│   ├── git_tool.py
│   ├── pdf_tool.py
│   ├── ppt_tool.py
│   ├── scheduler_tool.py
│   └── workflow_tool.py
│
├── tests/
│   ├── conftest.py
│   ├── test_tools.py
│   ├── test_memory.py
│   ├── test_metrics.py
│   ├── test_api.py
│   └── test_agent.py
│
├── templates/
│   ├── index.html          # Main UI — chat, sidebar, coding panel
│   ├── login.html          # Login + Guest access
│   └── register.html
│
├── static/
│   ├── manifest.json       # PWA manifest
│   └── sw.js               # Service Worker
│
├── aiaurum_logo.png        # App logo
├── aiaurum.db              # SQLite: chats, users, memories, settings
├── render.yaml             # Render.com deployment config
├── requirements.txt
├── requirements-dev.txt    # pytest, pytest-cov, pytest-mock
└── .env                    # API keys (keep private!)
```

---

## 🛣️ Roadmap

- [x] Multi-Model Routing (GPT-4o / GPT-4o-mini / Gemini)
- [x] ReAct Agent with Concurrent Tool Calling
- [x] SSE Token Streaming
- [x] SQLite Memory (chats, users, facts, settings)
- [x] Vector Memory (ChromaDB semantic search + recency scoring)
- [x] Image Generation (Pollinations AI)
- [x] Vision / Multimodal (GPT-4o image analysis)
- [x] Plugin Tool System (auto-discovery)
- [x] Coding Panel (editor, file browser, git, debugger)
- [x] Internet Tools (web search, browse, YouTube, deep research)
- [x] Document Tools (PDF, DOCX, PPT generation & analysis)
- [x] Browser Automation (Playwright)
- [x] Task Scheduler (APScheduler)
- [x] Multi-User Login & Role-Based Access
- [x] Guest Mode (ephemeral access without an account)
- [x] Admin Panel (user management, tool metrics)
- [x] Centralised Error Handling
- [x] Configuration Layer (dev / prod / test)
- [x] Test Suite (pytest — tools, memory, metrics, API, agent)
- [x] Mobile PWA Support
- [x] Render.com Deployment
- [ ] Voice Mode (live speech input/output)
- [ ] Multi-Agent System
- [ ] Marketplace Plugin Store

---

## 🔒 Security Notes

- Never share your `.env` file
- Use a GitHub Fine-Grained Token (Models permission only)
- All chat data is stored locally in `aiaurum.db`
- File browser is sandboxed to the project workspace directory
- Guest sessions are fully ephemeral — no data written to DB

---

## 🧪 Testing

```bash
pip install -r requirements-dev.txt
pytest
```

| Test File | Covers |
|---|---|
| `test_tools.py` | Tool loading, schema, calculator, concurrent execution |
| `test_memory.py` | Recency scoring, importance, store/retrieve |
| `test_metrics.py` | Record calls, rolling average, warn threshold |
| `test_api.py` | All route groups — auth, chat, tools, admin |
| `test_agent.py` | SSE format, agent stream with mocked LLM |

---

<div align="center">

## 👨‍💻 Created By

<br/>

### ✦ YUVAN INDUSTRIES ✦

**A Future Technology Company**

*Building the intelligent systems of tomorrow — today.*

<br/>

| Focus Area | |
|---|---|
| 🤖 Artificial Intelligence | 🦾 Robotics |
| 🧬 Autonomous Systems | 💡 Smart Software |
| 🌐 Intelligent Platforms | 🔭 Future Technologies |

<br/>

> *Yuvan Industries is on a mission to build AI that feels human,*
> *software that thinks ahead, and technology that changes lives.*

<br/>

📧 **Contact:** [shakthiyuvan01@gmail.com](mailto:kalakotinagajyothi@gmail.com)

🌐 **Live App:** [yuvanaurum.onrender.com](https://yuvanaurum.onrender.com)

<br/>

⭐ **If you find AI Aurum useful, give it a star.**

<br/>

---

*© 2026 Yuvan Industries. All rights reserved.*

</div>
