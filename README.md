<div align="center">

<img src="aiaurum_logo.png" alt="AI Aurum Logo" width="160"/>

# ✦ AI AURUM

**The Personal AI Operating System**

[![Made by Yuvan Industries](https://img.shields.io/badge/Made%20by-Yuvan%20Industries-gold?style=for-the-badge)](https://github.com)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-22%20Blueprints-black?style=for-the-badge&logo=flask)](https://flask.palletsprojects.com)
[![Multi-Agent](https://img.shields.io/badge/AI-12%2B%20Agents%20%7C%2048%20Tools-orange?style=for-the-badge)](https://github.com)
[![Providers](https://img.shields.io/badge/Providers-GitHub%20%7C%20Nara%20%7C%20Gemini%20%7C%20OpenAI%20%7C%20Ollama-46E3B7?style=for-the-badge)](https://github.com)

> *"The Future Is Not Coming. We Are Building It."*
> — Yuvan Industries

</div>

---

## ✨ What is AI Aurum?

**AI Aurum** is a full personal AI operating system that runs in your browser. A CEO agent
orchestrates a company of specialist agents (and hires new ones when needed), backed by a
5-tier memory system, a live knowledge graph, an experience database, 48 auto-discovered
tools, voice conversation, screen guidance, autonomous research, and a command palette that
puts all of it one keystroke away.

Everything runs against a **unified provider chain** — GitHub Models → NaraRouter → Gemini
→ OpenAI → Ollama — with automatic failover, so the assistant keeps working even when a
backend goes down or runs out of quota.

---

## 🚀 Quick Start

```bash
pip install -r requirements.txt
python app.py            # http://localhost:5000
```

`.env` keys (any ONE provider is enough — the chain handles the rest):

| Key | Purpose |
|---|---|
| `GITHUB_TOKEN` | GitHub Models (gpt-4o / gpt-4o-mini) — primary |
| `NARA_API_KEY` + `NARA_MODEL` | NaraRouter gateway (mistral-large, 5M free tokens) |
| `GEMINI_API_KEY` | Google Gemini + grounded web search |
| `OPENAI_API_KEY` | OpenAI API + Whisper STT |
| `ELEVENLABS_API_KEY` | Premium text-to-speech (falls back to edge-tts, then device voice) |
| `AI_PROVIDER_ORDER` | Optional, e.g. `nara,github,gemini,openai,ollama` |
| `SMTP_USER` / `SMTP_PASS` | Email tool |

---

## ⌨️ Command Palette — press **Ctrl+K**

One search bar controls everything: panels, tools, dashboards, missions, research,
personalities, and every shortcut below.

### Chat shortcuts

| Shortcut | What it does |
|---|---|
| `/team <goal>` | CEO + specialist agents with a **live status board**, message passing, and a self-critique review round |
| `/vibe <app idea>` | Vibe coding — dev team builds a working multi-file project |
| `/pm <project>` | Autonomous project manager: roadmap → code → tests → fixes → git |
| `/deep <topic>` | Autonomous research report with cited sources (`/deepppt` adds a PowerPoint) |
| `/mission <goal>` | Mission Mode: objectives, roadmap, tasks, deadlines, budget, progress |
| `/twin <question>` | Your Digital Twin answers the way *you* would |
| `/detective <problem>` | Evidence → hypotheses with confidence → best explanation |
| `/lab <prompt>` | AI Laboratory: run one prompt across models, judge the winner |
| `/innovate` `/strategy` `/resolve` `/textbook` `/negotiate` | Thinking modes: invention, strategy + scenarios + failure odds, source conflicts, mini-textbook, contract review |
| `/audit` / `/docs` | Code audit report / self-generated README + architecture docs |
| `/research <q>` or `/r` | Quick deep-research mode |

### The + menu

Upload files & photos · Take screenshot · **Live Screen Guidance** (AI sees your screen) ·
**Watch Screen for Errors** (auto-alerts) · **Voice Conversation** (hands-free, say "stop"/"continue") ·
**Meeting Mode** (record any Teams/Zoom/Meet tab → minutes + action items) · Deep Research ·
**Agent Team** · **Vibe Code** · **Document Canvas** · Analyze Data · Memory · Tools & Plugins · Code & Files

---

## 🧠 Intelligence Systems

| System | What it does |
|---|---|
| **CEO Orchestrator** | Routes goals to specialists, runs parallel waves, critiques its own answer, dispatches review rounds |
| **Agent Company** | 12 built-in employees with personalities — and the CEO **hires new specialists** (CFO, legal, robotics…) when a job needs one |
| **Agent Mailbox** | Agents message each other: `@reviewer: check the SQL` is delivered into the reviewer's context |
| **5-Tier Memory** | Working → conversation → knowledge graph → vector (ChromaDB) → archive (FTS5), unified behind one Memory API |
| **Live Knowledge Graph** | Every conversation extracts entities/relations in the background — browse it as the **Memory Map** |
| **Experience Database** | Every solved problem becomes a reusable strategy, auto-injected into similar future runs |
| **Standing Rules** | Say *"Always answer electrical questions using IS standards"* — stored and applied forever |
| **Memory DNA** | Identity profile: learning/decision/coding style, strengths, gaps, monthly evolution |
| **Memory Compression** | 1000s of facts → clusters → 3 permanent beliefs |
| **Dream Mode** | Nightly (permission-gated): mines the web for discoveries in your topics, writes a Dream Report |
| **RAG Pipeline** | Documents: chunk → embed → retrieve top-k instead of stuffing prompts |
| **Prediction Engine** | Clickable chips predict your next request after every answer |
| **Confidence Bars** | Every reply shows self-evaluated confidence (green/amber) |

## 📊 Dashboards

| View | Where |
|---|---|
| **Live Dashboard** | `/live` — SSE system stats + agents + economics + activity, auto-updating |
| **Consciousness Dashboard** | Ctrl+K — what the AI knows, is unsure about, and is waiting for; risk level |
| **AI Timeline** | Everything you did, day by day |
| **AI Universe** | Your topics as clickable planets |
| **Command Center / Skill Levels / Pattern Hunter / Research DB / Hired Agents** | Ctrl+K |

## 🛠️ Tools (48, auto-discovered)

Multi-step **web agent** (Playwright, goal-driven) · **video → SOP/minutes** (transcribe + synthesize) ·
website monitor · electrical engineering (IS/IEC) · document agent (PDF/DOCX/OCR + RAG Q&A) ·
meeting assistant · dev agent · code auditor · doc generator · simulator (preview destructive ops) ·
knowledge graph · email/messaging (permission-gated) · scheduler · vision · OCR · Excel/PPT/PDF ·
weather · news · YouTube · stock price plugin · **+ drop any .py into `plugins/` — zero config**

## 🔐 Safety

- **Permission Manager** (`/permissions`): browser, shell, file-delete, packages, messaging, self-improve, background-AI — dangerous ones OFF by default
- **Background AI toggle** — one switch kills all ambient AI calls (Ctrl+K)
- **Simulator** — destructive operations preview exactly what they'd do first
- **Self-improvement & Dream Mode** — suggestions only, rate-limited, never auto-commit
- Web agent refuses payment/password fields; guests are sandboxed

## 🏗️ Architecture

```
User ⇄ SSE Chat UI (PWA, mobile-ready, Ctrl+K palette)
          │
Flask (22 blueprints, 129 routes) ── tracer → /traces (thinking screen)
          │
CEO Agent ──► Planner · Researcher · Programmer · Reviewer · Debugger
   │          Browser · Vision · Security · Automation · Memory · Voice
   │          + dynamically hired specialists          (agent mailbox ⇄)
          │
providers/ ── GitHub → Nara → Gemini → OpenAI → Ollama (auto-failover)
          │
SQLite (WAL) + ChromaDB + NetworkX ── memory, experiences, missions,
timeline, research DB, canvas versions, benchmarks, agent logs
```

## 📁 Key Paths

| Path | Contents |
|---|---|
| `app.py` | 22 blueprints, scheduler (auto-learn 03:00, dream 02:30, self-review Sun 04:00) |
| `agents/` | BaseAgent + 12 specialists + CEO + `run_team_stream` |
| `providers/` | Unified AI layer — add a provider in ~40 lines |
| `services/` | memory, mailbox, experience, permissions, RAG, dream, activity log… |
| `tools/` | 48 tools — each: `NAME`, `DESCRIPTION`, `INPUTS`, `run()` |
| `routes/` | API blueprints (`aurum_routes.py` = dashboards/DNA/universe…) |
| `templates/` | `index.html` (single-page app) + `dashboard.html` (`/live`) |
| `plugins/` | Drop-in plugins, auto-loaded |

---

<div align="center">

**Built with ⚡ by Yuvan Industries**

*104 → 140+ tasks and counting.*

</div>
