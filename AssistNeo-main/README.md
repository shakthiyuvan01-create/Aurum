# 🚀 Assist Neo

**Assist Neo** is a powerful multi-brain AI assistant designed to run locally and on the web. It combines multiple AI models, voice interaction, file analysis, memory, automation, and self-improving capabilities into one intelligent assistant.

🌐 **Live Website:** https://assistneo.onrender.com

---

# ✨ Features

* 🧠 Multi-AI System
* 🌐 Web Interface
* 🎤 Voice Assistant
* 🔊 Natural Text-to-Speech
* 📁 File Analysis
* 🖼 Image Generation
* 🔍 Web Search
* 💾 Memory System
* 🖥 System Monitoring
* 🤖 Self-Evolution Engine
* 🔒 Privacy Focused

---

# 🧠 AI Providers

Assist Neo automatically switches between:

1. **Google Gemini 2.0 Flash**
2. **GitHub Models**
3. **Local Ollama Models**

If one AI is unavailable, another takes over automatically.

---

# 📦 Installation

## 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/Assist-Neo.git
cd Assist-Neo
```

---

## 2. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 3. Install Ollama

Download Ollama:

https://ollama.com

Install required models:

```bash
ollama pull llama3.2
ollama pull llava
```

---

## 4. Create a `.env` File

Create a file named `.env` and add:

```env
GEMINI_API_KEY=your_gemini_api_key
GITHUB_TOKEN=your_github_token
WEB_SEARCH_KEY=your_tavily_api_key
```

---

## 5. Start Ollama

```bash
ollama serve
```

---

# 🚀 Running Assist Neo

### Chat Mode

```bash
python assistant.py --chat
```

### Voice Mode

```bash
python assistant.py --voice
```

### Background Assistant

```bash
python assistant.py
```

### Web Interface

```bash
python smith_web.py
```

Open:

```
http://localhost:5000
```

---

# 🌐 Online Version

Visit:

### https://assistneo.onrender.com

No installation is required to try the web version.

---

# 📁 Project Structure

```
Assist-Neo
│
├── assistant.py
├── ai_brain.py
├── smith_web.py
├── evolution_worker.py
├── uploads/
├── chats/
├── memory.json
├── users.json
├── .env
└── requirements.txt
```

---

# 🛣 Roadmap

* Multi-Agent System
* Vector Memory
* RAG Knowledge Base
* Vision Agent
* Coding Agent
* Planner Agent
* Android Application
* Desktop GUI
* Robotics Integration

---

# 👨‍💻 Created By

# Yuvan Industries

### A Future Technology Company

Yuvan Industries is an upcoming technology company focused on building:

* Artificial Intelligence
* Robotics
* Autonomous Systems
* Smart Software
* Intelligent Platforms
* Future Technologies

> **"The Future Is Not Coming. We Are Building It."**

---

# 📧 Contact

For questions, suggestions, or collaborations:

**Email:** [shakthiyuvan01@gmail.com](mailto:shakthiyuvan01@gmail.com)

---

⭐ If you like this project, please consider giving it a star and supporting **Yuvan Industries** on its journey to build the future.
