<div align="center">

<img src="assistneo_logo.png" alt="Assist Neo Logo" width="140"/>

# ✦ ASSIST NEO

**The Personal AI Assistant from the Future**

[![Made by Yuvan Industries](https://img.shields.io/badge/Made%20by-Yuvan%20Industries-blueviolet?style=for-the-badge)](https://github.com)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-Web%20App-black?style=for-the-badge&logo=flask)](https://flask.palletsprojects.com)
[![AI Powered](https://img.shields.io/badge/AI-GPT%20%2B%20Gemini%20%2B%20Bluesminds-orange?style=for-the-badge)](https://github.com)

> *"The Future Is Not Coming. We Are Building It."*
> — Yuvan Industries

🌐 **Live Demo:** [https://assistneo.onrender.com](https://assistneo.onrender.com)

</div>

---

## ✨ What is Assist Neo?

**Assist Neo** is a multi-brain AI assistant that runs in your browser. It combines three AI models working in parallel, remembers things about you, generates images, answers questions, and even writes code — all from a clean, modern web interface.

Built by **Yuvan Industries** — a forward-thinking technology company from the future.

---

## ⚡ Features

| Feature | Description |
|---|---|
| 🧠 **Triple AI Brain** | GPT-4o-mini + Gemini 2.0 Flash + Bluesminds (coding) run in parallel |
| 🤝 **Smart Answer Fusion** | Combines the best parts of multiple AI answers automatically |
| 💻 **Coding Mode** | Switches to Bluesminds (gpt-5-chat) for all code questions |
| 🖼️ **Image Generation** | Creates images via Pollinations AI — no API key needed |
| 💬 **Chat Memory** | Saves all conversations; browse history in the sidebar |
| 🧩 **Personal Memory** | Remembers your name, notes, and preferences across sessions |
| 🔍 **Live Web Search** | Searches DuckDuckGo for real-time information automatically |
| 📊 **Mermaid Diagrams** | Renders flowcharts and architecture diagrams in chat |
| 📐 **Math / LaTeX** | Renders equations with MathJax |
| ⏰ **Reminders** | Set reminders by just saying "remind me to..." |
| 🌍 **Translation** | Translates text to any language on request |
| 🚀 **Open Apps & Sites** | Say "open YouTube" or "open Notepad" and it does it |
| 🔒 **Privacy First** | All data stays on your machine |

---

## 🧠 AI Architecture

```
Your Message
     │
     ▼
┌────────────────────────────────────────────────────┐
│                   Assist Neo Brain                 │
│                                                    │
│  Is it a coding question?                          │
│  ┌─────────────────────────────────────────────┐  │
│  │  YES → Bluesminds (gpt-5-chat)              │  │
│  │  NO  → GPT-4o-mini ──┐                      │  │
│  │         Gemini 2.0 ──┼──► Answer Fusion     │  │
│  │                       │    (best of both)   │  │
│  └───────────────────────┘                     │  │
│                                                    │
│  Fallback: Ollama (local, offline)                 │
└────────────────────────────────────────────────────┘
     │
     ▼
 Perfect Answer
```

---

## 📦 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/AssistNeo.git
cd AssistNeo
```

### 2. Install Dependencies

```bash
pip install flask python-dotenv requests ddgs plyer
```

### 3. Create a `.env` File

Create a file named `.env` in the project root:

```env
GITHUB_TOKEN=your_github_token_here
GEMINI_API_KEY=your_gemini_api_key_here
BLUESMINDS_KEY=your_bluesminds_key_here
```

| Key | Where to get it |
|---|---|
| `GITHUB_TOKEN` | [github.com/settings/tokens](https://github.com/settings/tokens) → Models permission |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) → Get API Key |
| `BLUESMINDS_KEY` | [bluesminds.com](https://bluesminds.com) |

### 4. (Optional) Install Ollama for offline fallback

```bash
# Download from https://ollama.com
ollama pull llama3.2
```

---

## 🚀 Running Assist Neo

```bash
python smith_web.py
```

Then open your browser at:

```
http://localhost:5000
```

That's it. 🎉

---

## 🗂️ Project Structure

```
AssistNeo/
│
├── smith_web.py        # Flask web server & all routes
├── assistant.py        # AI brains, memory, image gen, commands
├── uploads/            # Files uploaded in chat
├── chats/              # Saved conversation history (per user)
├── memory.json         # Your name & personal notes
├── neo_memory.json     # Extended memory facts
├── users.json          # User accounts
├── .env                # Your API keys (keep private!)
└── requirements.txt    # Python dependencies
```

---

## 🛣️ Roadmap

- [ ] Multi-Agent System
- [ ] Vector Memory (RAG)
- [ ] Vision / Image Analysis
- [ ] Android Application
- [ ] Desktop GUI
- [ ] Robotics Integration
- [ ] Voice Mode (browser-based)
- [ ] Plugin System

---

## 🔒 Security Notes

- Never share your `.env` file
- Use a GitHub Fine-Grained Token (Models permission only)
- Use a Gemini App Password, not your main account
- All chat data is stored locally on your machine

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

📧 **Contact:** [shakthiyuvan01@gmail.com](mailto:shakthiyuvan01@gmail.com)

<br/>

⭐ **If you find Assist Neo useful, give it a star and support Yuvan Industries on its journey to build the future.**

<br/>

---

*© 2026 Yuvan Industries. All rights reserved.*

</div>