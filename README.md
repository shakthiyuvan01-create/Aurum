<div align="center">

<img src="aiaurum_logo.png" alt="AI Aurum Logo" width="160"/>

# ✦ AI AURUM

**The Personal, Self-Improving AI Operating System**

[![Made by Yuvan Industries](https://img.shields.io/badge/Made%20by-Yuvan%20Industries-gold?style=for-the-badge)](https://github.com)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-23%20Blueprints-black?style=for-the-badge&logo=flask)](https://flask.palletsprojects.com)
[![Multi-Agent](https://img.shields.io/badge/AI-12%2B%20Agents%20%7C%2048%20Tools-orange?style=for-the-badge)](https://github.com)
[![Providers](https://img.shields.io/badge/Providers-6--chain%20failover-46E3B7?style=for-the-badge)](https://github.com)

> *"The Future Is Not Coming. We Are Building It."*
> — Yuvan Industries

</div>

---

## ✨ What is AI Aurum?

**AI Aurum** is a full personal AI operating system that runs in your browser. A CEO agent
orchestrates a company of specialist agents (and hires new ones on demand), backed by a
5-tier memory system, a live knowledge graph, an experience database, 48 auto-discovered
tools, voice conversation, screen guidance, autonomous research, and a command palette that
puts all of it one keystroke away.

It **improves itself** in three bounded, verifiable ways: a heartbeat loop that maintains
its own memory, a self-optimizer that tunes its prompt only when a change measurably raises
its eval score, and a tool forge that writes, tests and installs new tools at runtime.

Everything runs against a **6-provider chain** — GitHub Models → NaraRouter → BluesMinds →
Gemini → OpenAI → Ollama — with automatic failover and speculative racing, so it keeps
working even when a backend rate-limits or goes down.

---

## 🚀 Quick Start

```bash
pip install -r requirements.txt        # or requirements-render.txt on cloud
python app.py                          # http://localhost:5000
python app.py --https                  # HTTPS (needed for phone mic)
```

`.env` — any ONE provider key is enough; the chain handles the rest:

| Key | Purpose |
|---|---|
| `GITHUB_TOKEN` | GitHub Models (gpt-4o / gpt-4o-mini) |
| `NARA_API_KEY` + `NARA_MODEL` | NaraRouter gateway (mistral-large, 5M free tokens) |
| `BLUESMINDS_KEY` | BluesMinds gateway |
| `GEMINI_API_KEY` + `GEMINI_MODEL` | Google Gemini (default gemini-2.5-flash) + vision fallback |
| `OPENAI_API_KEY` | OpenAI API + Whisper STT |
| `ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_ID` | Voice (auto-falls back to edge-tts, then device) |
| `AI_PROVIDER_ORDER` | e.g. `nara,github,bluesminds,gemini,openai,ollama` |
| `AURUM_API_KEY` | enables the external API + CLI |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_ALLOWED_IDS` | Telegram bot channel |
| `SEED_USERS` | `name:pass,name2:pass2` — recreates accounts on boot (survives cloud wipes) |

---

## 🧬 Self-Improvement (bounded & verifiable)

Aurum improves what it *knows* and *does* — never its own core code unattended. Every loop
is gated (OFF by default), reversible, and human-visible.

| System | What it does | Trigger |
|---|---|---|
| **Heartbeat** | On a timer, reads your recent activity and rewrites its own MEMORY.md with durable new facts | Ctrl+K / `/heartbeat/run` — permission `heartbeat` |
| **Self-optimizer** | Runs the eval, tweaks its system prompt for the weakest area, keeps it ONLY if the score beats baseline by 3+, else reverts | `/self_optimize/run` — permission `self_improve` |
| **Tool forge** | Writes a new tool, scans it for unsafe ops, tests it in a subprocess, auto-installs missing pip packages, registers it live | Ctrl+K / `/forge` — permission `self_extend` |
| **Experience DB** | Every team run distills a reusable strategy; failures write "avoid" lessons injected into future runs | automatic |
| **Eval harness** | 8 golden prompts run nightly; a >15% quality drop alerts you on Telegram | `/eval_harness` (04:30 daily) |
| **Persona / Soul** | Editable SOUL / IDENTITY / MEMORY / HEARTBEAT markdown shape behavior; AI may self-edit MEMORY only | Ctrl+K → Persona / Soul |
| **Dream mode** | Nightly: mines the web for discoveries in your topics, writes a Dream Report | 02:30, permission `self_improve` |

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
| `/twin` `/detective` `/lab` | Digital twin · investigation · model comparison |
| `/innovate` `/strategy` `/resolve` `/textbook` `/negotiate` | Thinking modes |
| `/audit` `/docs` | Code audit report · self-generated README + architecture |

### The + menu
Upload files & photos · Screenshot (gallery picker on phone) · **Live Screen Guidance** ·
**Watch Screen for Errors** · **Voice Conversation** (say "stop"/"continue") ·
**Meeting Mode** (record → minutes) · Agent Team · Vibe Code · **Document Canvas** ·
Persona/Soul · Heartbeat · Forge a Tool · Tools & Plugins · Code & Files

---

## 🧠 Intelligence & Memory

CEO orchestrator with dynamic hiring · agent mailbox (`@reviewer: ...`) · **speculative
parallel execution** (races two providers, first good answer wins) · **tree-of-thought**
planning · 5-tier memory · **GraphRAG** multi-hop retrieval · **semantic cache** (near-
duplicate questions answered instantly, zero tokens) · live knowledge graph · Memory DNA ·
standing rules · RAG with citations · **file-watcher** auto-ingestion (`workspace/inbox/`).

## 📊 Dashboards
`/live` auto-updating command center · Consciousness · Timeline · Universe · Memory Map ·
Skill Levels (1–50 + rank) · Usage/cost per provider · Pattern Hunter · Research DB · Ctrl+K.

## 🔐 Safety
Login + role-based access · **Permission Manager** (browser, shell, files_delete, packages,
messaging, self_improve, self_extend, heartbeat, background_ai) — dangerous ones OFF by
default · simulate-before-send on email/deletes · forge sandboxed + scanned · background-AI
kill switch.

## 🛠️ Channels & Interfaces
Web PWA (mobile-ready) · **Telegram bot** · **external API + webhooks** (`/api/ask`,
`/api/team`, `/api/tool`) · **CLI** (`python aurum_cli.py "..."`) · one-click **`/export`**
backup zip.

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
providers/ ── GitHub → Nara → BluesMinds → Gemini → OpenAI → Ollama (failover + racing)
          │
Self-improvement ── heartbeat · self-optimizer · tool forge · experience DB · eval harness
          │
SQLite (WAL) + ChromaDB + NetworkX ── memory, missions, timeline, research DB, canvas,
                                       usage, benchmarks, persona files
```

## 📁 Key Paths

| Path | Contents |
|---|---|
| `app.py` | 23 blueprints; schedulers: auto-learn, dream, self-review, missions, eval, heartbeat |
| `providers/` | 6-provider chain (`AI.chat` / `generate` / `generate_json` / `draft_verify`) |
| `agents/` | BaseAgent + 12 specialists + CEO + `run_team_stream` |
| `services/` | persona, heartbeat, self_optimize, tool_forge, experience_db, semantic_cache, memory_api, permissions… |
| `persona/` | SOUL / IDENTITY / MEMORY / HEARTBEAT markdown |
| `tools/` | 48 tools — each `NAME` / `DESCRIPTION` / `INPUTS` / `run()` |
| `plugins/` | drop-in + AI-forged (`forged_*.py`) tools, auto-loaded |
| `templates/` | `index.html` app + `dashboard.html` (`/live`) |
| `aurum_cli.py` | terminal client |

---

## ☁️ Deploy on Render

1. Push to GitHub → Render → New → Blueprint (uses `render.yaml`, `requirements-render.txt`).
2. In the dashboard **Environment**, set your provider keys + `SEED_USERS` (free tier wipes
   the disk on redeploy, so seeded accounts recreate on boot).
3. Render gives HTTPS automatically → phone mic/voice/camera work with no setup.
4. Start command: `gunicorn app:app --workers 1 --worker-class gthread --threads 12 --timeout 300 --bind 0.0.0.0:$PORT` (1 worker so schedulers and async jobs share state).
5. Verify providers at `/providers/test`; verify voice at `/voice/test`.

> Persistent disks need a paid plan. On free tier, drop the `disk:` block — everything works,
> but data resets on redeploy/spin-down.

---

<div align="center">

**Built with ⚡ by Yuvan Industries** — *and increasingly, by itself.*

</div>
