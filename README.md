<div align="center">

<img src="aiaurum_logo.png" alt="AI Aurum Logo" width="160"/>

# ✦ AI AURUM

**The Personal, Self-Improving AI Operating System**

[![Made by Yuvan Industries](https://img.shields.io/badge/Made%20by-Yuvan%20Industries-gold?style=for-the-badge)](https://github.com)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-23%20Blueprints-black?style=for-the-badge&logo=flask)](https://flask.palletsprojects.com)
[![Multi-Agent](https://img.shields.io/badge/AI-12%2B%20Agents%20%7C%2049%20Tools-orange?style=for-the-badge)](https://github.com)
[![Providers](https://img.shields.io/badge/Providers-7--chain%20failover-46E3B7?style=for-the-badge)](https://github.com)

> *"The Future Is Not Coming. We Are Building It."*
> — Yuvan Industries

</div>

---

## ✨ What is AI Aurum?

**AI Aurum** is a full personal AI operating system that runs in your browser. A CEO agent
orchestrates a company of specialist agents (12 built-in + dynamic hires), backed by a
5-tier memory system, a live knowledge graph, a semantic cache, 49 auto-discovered tools,
voice conversation, screen guidance, autonomous research, and a command palette that puts
all of it one keystroke away.

It **improves itself** in three bounded, verifiable ways: a heartbeat loop that maintains
its own memory, a self-optimizer that tunes its prompt only when a change measurably raises
its eval score, and a tool forge that writes, tests and installs new tools at runtime.

Everything runs against a **7-provider chain** — GitHub Models → NaraRouter → BluesMinds →
Gemini → OmniRoute → OpenAI → Ollama — with automatic failover, circuit breakers, speculative
racing, and inline prompt compression, so it keeps working even when a backend rate-limits
or goes down.

Channels: **Web PWA** (desktop + mobile) · **Telegram bot** · **Discord bot** · **Slack bot** ·
**REST API** · **CLI**. Two-factor auth available.

---

## 🚀 Quick Start

```bash
pip install -r requirements.txt        # or requirements-render.txt on cloud
python app.py                          # http://localhost:5000
python app.py --https                  # HTTPS (needed for phone mic)
```

### Environment

`.env` — any ONE provider key is enough; the chain handles the rest:

| Key | Purpose |
|---|---|
| `GITHUB_TOKEN` | GitHub Models (gpt-4o / gpt-4o-mini) |
| `NARA_API_KEY` + `NARA_MODEL` | NaraRouter gateway (mistral-large, 5M free tokens) |
| `BLUESMINDS_KEY` | BluesMinds gateway |
| `GEMINI_API_KEY` + `GEMINI_MODEL` | Google Gemini (default gemini-2.5-flash) + vision fallback |
| `OPENAI_API_KEY` | OpenAI API + Whisper STT |
| `OMNIROUTE_API_KEY` + `OMNIROUTE_URL` + `OMNIROUTE_MODEL` | OmniRoute gateway |
| `ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_ID` | Voice (auto-falls back to edge-tts, then device) |
| `AI_PROVIDER_ORDER` | e.g. `github,gemini,nara,bluesminds,omniroute,openai,ollama` |
| `AURUM_API_KEY` | Enables the external API + CLI |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_ALLOWED_IDS` | Telegram bot channel |
| `DISCORD_BOT_TOKEN` + `DISCORD_ALLOWED_IDS` | Discord bot channel |
| `SLACK_BOT_TOKEN` | Slack bot channel |
| `GOOGLE_CLIENT_ID` + `GOOGLE_CLIENT_SECRET` | Google OAuth login |
| `SEED_USERS` | `name:pass,name2:pass2` — recreates accounts on boot (survives cloud wipes) |
| `AURUM_TZ` | Timezone (default `Asia/Kolkata`) |
| `OLLAMA_MODEL` | Local Ollama model (default `llama3.2`) |
| `WEB_SEARCH_KEY` | Web search API key |

---

## 🧬 Self-Improvement (bounded & verifiable)

Aurum improves what it *knows* and *does* — never its own core code unattended. Every loop
is gated (OFF by default), reversible, and human-visible.

| System | What it does | Trigger |
|---|---|---|
| **Heartbeat** | On a timer, reads your recent activity and rewrites its own MEMORY.md with durable new facts | Ctrl+K · `/heartbeat/run` — permission `heartbeat` |
| **Self-optimizer** | Runs the eval, tweaks its system prompt for the weakest area, keeps it ONLY if the score beats baseline by 3+, else reverts | `/self_optimize/run` — permission `self_improve` |
| **Tool forge** | Writes a new tool, scans it for unsafe ops, tests it in a subprocess, auto-installs missing pip packages, registers it live | Ctrl+K · `/forge` — permission `self_extend` |
| **Experience DB** | Every team run distills a reusable strategy; failures write "avoid" lessons injected into future runs | automatic |
| **Eval harness** | 8 golden prompts run nightly; a >15% quality drop alerts you on Telegram | `/eval_harness` (04:30 daily) |
| **Dream mode** | Nightly: mines the web for discoveries in your topics, writes a Dream Report | 02:30, permission `self_improve` |
| **Auto-learn** | Periodically ingests new information from your workspace and conversations | automatic |
| **Auto missions** | Automatically discovers and suggests missions based on your activity | automatic |

> These are the **bounded** rungs of self-improvement that actually work — the system can only
> climb a hill its evaluator can measure, and any change it cannot verify is rolled back.

---

## ⌨️ Command Palette — press **Ctrl+K** (or "Everything" in the + menu on phone)

### Chat shortcuts

| Shortcut | What it does |
|---|---|
| `/team <goal>` | CEO + specialists: live board, message passing, tree-of-thought branching, self-critique review, speculative provider racing |
| `/vibe <app idea>` | Vibe coding — builds a working multi-file project |
| `/pm <project>` | Autonomous project manager: roadmap → code → tests → fixes → git |
| `/deep <topic>` | Deep research (draft-and-verify), cited sources (`/deepppt` adds slides) |
| `/mission <goal>` | Mission Mode: objectives, roadmap, tasks, budget, progress |
| `/twin` | Digital twin — your personal AI replica that learns from you |
| `/detective` | Investigation mode — trace issues across files and systems |
| `/lab` | Model comparison lab — compare responses across providers |
| `/innovate` · `/strategy` · `/resolve` · `/textbook` · `/negotiate` | Thinking modes |
| `/audit` | Code audit report |
| `/docs` | Self-generated README + architecture docs |
| `/debate` | Multi-model debate with voting |
| `/canvas` | Document canvas for collaborative editing |

### The + menu
Upload files & photos · Screenshot (gallery picker on phone) · **Live Screen Guidance** ·
**Watch Screen for Errors** · **Voice Conversation** (say "stop"/"continue") ·
**Meeting Mode** (record → minutes) · Agent Team · Vibe Code · **Document Canvas** ·
Persona/Soul · Heartbeat · Forge a Tool · Tools & Plugins · Code & Files

---

## 🧠 Intelligence & Memory

- **CEO orchestrator** with dynamic hiring (creates specialist agents on demand)
- **Agent mailbox** — agents communicate via `@agentname: ...` messages
- **Speculative parallel execution** — races two providers, first good answer wins
- **Tree-of-thought planning** — explores multiple reasoning paths
- **5-tier memory** — working, short-term, long-term, semantic, episodic
- **GraphRAG** — multi-hop retrieval over a NetworkX knowledge graph
- **Semantic cache** — near-duplicate questions answered instantly, zero tokens
- **Live knowledge graph** — entities, relationships, and facts extracted from conversations
- **Memory DNA** — compressed representation of your unique patterns
- **Standing rules** — persistent behavioral rules you set
- **RAG with citations** — retrieves and cites sources
- **File-watcher auto-ingestion** — drops files into `workspace/inbox/` are auto-processed
- **Prompt compression** — long prompts are compressed inline before hitting providers
- **Self-critique review** — agent outputs are reviewed before delivery

---

## 🤖 Agents (12 built-in + dynamic)

| Agent | Role |
|---|---|
| **CEO** | Orchestrator — plans, delegates, synthesizes |
| **Planner** | Breaks goals into actionable steps |
| **Researcher** | Web + local research with citations |
| **Programmer** | Writes and debugs code |
| **Reviewer** | Code review and quality assurance |
| **Debugger** | Root-cause analysis and fixes |
| **Browser** | Web browsing and interaction |
| **Vision** | Image analysis and OCR |
| **Security** | Permission gating and safety checks |
| **Automation** | Scheduled and trigger-based tasks |
| **Memory Manager** | Knowledge graph and memory maintenance |
| **Voice** | Speech recognition and synthesis |
| **Dynamic agents** | Created on demand by the CEO for specialized tasks |

---

## 🛠️ 49 Tools

Tools auto-discover and register themselves. Categories include:

| Category | Tools |
|---|---|
| **Web** | `web_search`, `browse_web`, `web_agent`, `website_monitor`, `news`, `youtube`, `youtube_search`, `flight_finder`, `weather` |
| **Code** | `code_runner`, `code_auditor`, `git_tool`, `dev_agent`, `coding_team`, `project_manager` |
| **Files & Docs** | `docx_tool`, `excel_tool`, `pdf_tool`, `ppt_tool`, `ocr_tool`, `doc_generator`, `drawing_reader` |
| **AI & Data** | `ai_lab`, `auto_research`, `knowledge_graph`, `thinking_modes`, `mission_mode`, `detective`, `tool_metrics`, `skill_manager` |
| **Communication** | `email_tool`, `messaging`, `meeting_assistant`, `calendar_tool`, `reminders`, `scheduler_tool` |
| **System** | `system_monitor`, `calculator`, `simulator`, `video_sop`, `browser_agent`, `browser_tool` |
| **Productivity** | `workflow_tool`, `doc_generator`, `document_agent`, `mcp_client`, `skill_manager` |
| **Engineering** | `electrical_engineering`, `vision_tool` |

Plugins folder (`plugins/`) supports drop-in + AI-forged (`forged_*.py`) tools, auto-loaded.

---

## 🏗️ Architecture

```
User ⇄ SSE Chat UI (PWA, Ctrl+K palette, persona-shaped)
          │
Flask (23 blueprints, ~145 routes) ── tracer → thinking screen
          │
CEO Agent ─► Planner · Researcher · Programmer · Reviewer · Debugger · Browser
   │         Vision · Security · Automation · Memory · Voice + hired specialists
   │         (mailbox ⇄ · speculative racing · tree-of-thought · review round)
          │
providers/ ── GitHub → Nara → BluesMinds → Gemini → OmniRoute → OpenAI → Ollama
               (failover + circuit breakers + racing + prompt compression)
          │
Self-improvement ── heartbeat · self-optimizer · tool forge · experience DB ·
                    eval harness · dream mode · auto-learn · auto missions
          │
Memory ── SQLite (WAL) + ChromaDB + NetworkX + semantic cache + RAG
          │
Channels ── Web PWA · Telegram · Discord · Slack · REST API · CLI
```

---

## 🗺️ Project Structure

```
aurum/
├── app.py                 # 23 blueprints, schedulers, data persistence
├── agent.py               # CEO agent with ReAct tool-calling
├── subagent.py            # Dynamic subagent management
├── db.py                  # SQLite + ChromaDB + NetworkX integration
├── vector_memory.py       # Vector-based memory retrieval
├── debate.py              # Multi-model debate engine
├── self_eval.py           # Self-evaluation scoring
├── push.py                # Git push automation
├── aurum_cli.py           # Terminal client
├── smith_web.py           # Legacy entry-point wrapper
├── providers/             # 7-provider chain
│   ├── manager.py         # ProviderManager (AI.chat / generate / generate_json)
│   ├── base.py            # Abstract base provider
│   ├── github_models.py   # GitHub Models (GPT-4o / GPT-4o-mini)
│   ├── gemini.py          # Google Gemini
│   ├── openai_provider.py # OpenAI + Whisper
│   ├── nararouter.py      # NaraRouter gateway
│   ├── bluesminds.py      # BluesMinds gateway
│   ├── omniroute.py       # OmniRoute gateway
│   └── ollama.py          # Local Ollama
├── agents/                # 12 specialist agents + CEO
│   ├── ceo_agent.py       # Orchestrator
│   ├── base_agent.py      # Shared agent base
│   ├── planner_agent.py   # Task planning
│   ├── researcher_agent.py# Web research
│   ├── programmer_agent.py# Code generation
│   ├── reviewer_agent.py  # Code review
│   ├── debugger_agent.py  # Debugging
│   ├── browser_agent.py   # Web browsing
│   ├── vision_agent.py    # Image/vision
│   ├── security_agent.py  # Safety gating
│   ├── automation_agent.py# Automation
│   ├── memory_manager_agent.py  # Memory maintenance
│   └── voice_agent.py     # Voice I/O
├── services/              # 45+ services
│   ├── ai_service.py      # Model routing
│   ├── persona.py         # SOUL / IDENTITY / MEMORY management
│   ├── heartbeat.py       # Heartbeat loop
│   ├── self_optimize.py   # Self-optimization
│   ├── tool_forge.py      # Tool creation
│   ├── experience_db.py   # Experience learning
│   ├── semantic_cache.py  # Cache near-duplicate queries
│   ├── rag_service.py     # RAG retrieval
│   ├── memory_layers.py   # 5-tier memory
│   ├── memory_api.py      # Memory API
│   ├── permission_manager.py  # Permission gating
│   ├── voice_service.py   # Voice synthesis
│   ├── speech_service.py  # TTS engine
│   ├── telegram_bot.py    # Telegram channel
│   ├── discord_bot.py     # Discord channel
│   ├── slack_bot.py       # Slack channel
│   ├── auth_service.py    # Authentication
│   ├── twofa.py           # Two-factor auth
│   ├── eval_harness.py    # Eval framework
│   ├── dream_mode.py      # Dream/exploration
│   ├── auto_learn.py      # Auto-learning
│   ├── auto_missions.py   # Auto missions
│   ├── agent_mailbox.py   # Inter-agent messaging
│   ├── agent_health.py    # Agent health monitoring
│   ├── capability_registry.py  # Capability discovery
│   ├── budget.py          # Token budgeting
│   ├── compression.py     # Prompt compression
│   ├── content_os.py      # Content OS
│   ├── conversation_search.py  # Search conversations
│   ├── dynamic_agents.py  # On-demand agent creation
│   ├── error_handler.py   # Error handling
│   ├── event_bus.py       # Event system
│   ├── file_watcher.py    # File ingestion
│   ├── image_restyle.py   # Image restyling
│   ├── learning.py        # Learning engine
│   ├── model_voting.py    # Model voting
│   ├── ollama_service.py  # Ollama integration
│   ├── personal_twin.py   # Digital twin
│   ├── sandbox.py         # Code sandbox
│   ├── skill_store.py     # Skill management
│   ├── snapshots.py       # State snapshots
│   ├── task_queue.py      # Task queuing
│   ├── tracer.py          # Request tracing
│   └── activity_log.py    # Activity logging
├── tools/                 # 49 auto-discovered tools
│   ├── web_search.py      # Web search
│   ├── browse_web.py      # Web browsing
│   ├── code_runner.py     # Code execution
│   ├── code_auditor.py    # Code auditing
│   ├── ...                # (47 more)
├── routes/                # 23 Flask route blueprints
│   ├── chat.py            # Chat routes
│   ├── stream_routes.py   # SSE streaming
│   ├── auth.py            # Auth routes
│   ├── api_routes.py      # REST API
│   ├── dashboard_routes.py# /live dashboard
│   ├── voice_routes.py    # Voice routes
│   ├── ...                # (17 more)
├── templates/             # UI templates
│   ├── index.html         # Main app (PWA)
│   ├── dashboard.html     # /live dashboard
│   ├── login.html         # Login page
│   └── register.html      # Registration page
├── static/                # Static assets
│   ├── manifest.json      # PWA manifest
│   ├── sw.js              # Service worker
│   └── creator.jpg        # Creator photo
├── persona/               # Personality files
│   ├── SOUL.md            # Core soul / essence
│   ├── IDENTITY.md        # Identity definition
│   ├── MEMORY.md          # Persistent memory
│   └── HEARTBEAT.md       # Heartbeat prompt
├── planning/              # Planning subsystem
│   ├── planner.py         # Plan generation
│   └── executor.py        # Plan execution
├── workflows/             # Workflow engine
│   └── engine.py          # Workflow execution
├── config/                # Configuration environments
│   ├── base.py            # Base config
│   ├── development.py     # Dev overrides
│   ├── production.py      # Prod overrides
│   └── testing.py         # Test overrides
├── plugins/               # Drop-in + forged tools
│   └── stock_price.py     # Example plugin
└── render.yaml            # Render.com deployment blueprint
```

---

## 📊 Dashboards

| Dashboard | Route | Description |
|---|---|---|
| **Live Console** | `/live` | Auto-updating command center |
| **Consciousness** | — | Agent thought stream |
| **Timeline** | — | Activity timeline |
| **Universe** | — | Knowledge graph explorer |
| **Memory Map** | — | Memory tier visualization |
| **Skills** | — | Skill levels (1–50 + rank) |
| **Usage/Cost** | — | Per-provider metrics |
| **Pattern Hunter** | — | Pattern discovery |
| **Research DB** | — | Research database browser |
| **Debug** | `/debug` | Provider test, voice test, system info |

---

## 🔐 Safety

- **Login + role-based access** — session auth with optional Google OAuth
- **Two-factor authentication** — TOTP-based 2FA
- **Permission Manager** — granular permissions per feature:
  - `browser`, `shell`, `files_delete`, `packages`, `messaging`
  - `self_improve`, `self_extend`, `heartbeat`, `background_ai`
  - Dangerous ones **OFF** by default
- **Simulate-before-send** — email/deletes prompt for confirmation
- **Tool forge sandboxed + scanned** — unsafe operations blocked
- **Background-AI kill switch** — disable unattended AI activity
- **Circuit breakers** — failing providers auto-skipped for cooldown period
- **Deduplication** — identical concurrent low-temp calls share one result

---

## ☁️ Deploy on Render

1. Push to GitHub → Render → New → Blueprint (uses `render.yaml`, `requirements-render.txt`).
2. In the dashboard **Environment**, set your provider keys + `SEED_USERS` (free tier wipes
   the disk on redeploy, so seeded accounts recreate on boot).
3. Render gives HTTPS automatically → phone mic/voice/camera work with no setup.
4. Start command: `gunicorn app:app --workers 1 --worker-class gthread --threads 12 --timeout 300 --bind 0.0.0.0:$PORT`
5. Verify providers at `/debug`; verify voice at `/voice/test`.

> Persistent disks need a paid plan. On free tier, drop the `disk:` block — everything works,
> but data resets on redeploy/spin-down.

---

## 🔧 CLI Usage

```bash
python aurum_cli.py "your question here"
```

Or use the REST API:

```bash
curl -X POST http://localhost:5000/api/ask \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: your-api-key" \
  -d '{"message": "Hello, Aurum!"}'
```

---

## 🐍 Requirements

Core dependencies (see `requirements.txt`):
- Flask + Jinja2 + Werkzeug
- requests + httpx
- Python-dotenv
- ChromaDB (vector store)
- NetworkX (knowledge graph)
- PyMuPDF / python-docx / openpyxl / python-pptx (document handling)
- Pillow + pytesseract + opencv-python (vision/OCR)
- edge-tts + sounddevice + soundfile + pyttsx3 (voice)
- APScheduler (scheduling)
- google-genai / openai / ollama SDKs

---

## 📁 Key Paths Summary

| Path | Contents |
|---|---|
| `app.py` | 23 blueprints; schedulers: auto-learn, dream, self-review, missions, eval, heartbeat |
| `providers/` | 7-provider chain with failover, racing, circuit breakers, prompt compression |
| `agents/` | BaseAgent + 12 specialists + CEO + `run_team_stream` |
| `services/` | 45+ services: persona, heartbeat, self_optimize, tool_forge, experience_db, semantic_cache, memory_api, permissions… |
| `persona/` | SOUL / IDENTITY / MEMORY / HEARTBEAT markdown |
| `tools/` | 49 tools — each `NAME` / `DESCRIPTION` / `INPUTS` / `run()` |
| `plugins/` | drop-in + AI-forged (`forged_*.py`) tools, auto-loaded |
| `templates/` | `index.html` app + `dashboard.html` (`/live`) + auth pages |
| `aurum_cli.py` | terminal client |
| `render.yaml` | Render.com deployment blueprint |

---

<div align="center">

**Built with ⚡ by Yuvan Industries** — *and increasingly, by itself.*

</div>
