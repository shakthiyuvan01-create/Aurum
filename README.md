# Smith — your personal assistant (one file)

Everything in a single program, `assistant.py`. Runs on your own computer.
The only thing that uses the internet is the natural voice, image creation,
and weather — all free and key-free.

## Install

1. Install Python (https://www.python.org/downloads/) — tick *Add to PATH*.
2. In this folder:  `pip install -r requirements.txt`
3. (For real answers & image recognition) install Ollama from
   https://ollama.com then run:  `ollama pull llama3.2`  and  `ollama pull llava`

## Run it

```
python assistant.py            background mode (watches & alerts you)
python assistant.py --tray      run with a little system-tray icon
python assistant.py --chat      type to it
python assistant.py --voice     talk to it (say "Hey Smith, ...")
python assistant.py --install   start automatically with Windows
python assistant.py --uninstall stop starting automatically
```

It calls you **Yuvan**, is named **Smith**, and wakes to **"Hey Smith"**.
Change these at the top of the file (ASSISTANT_NAME, USER_NAME, WAKE_WORD).

## Things you can say or type

**Open & ask**
- "Open youtube" / "open notepad"
- "What is the capital of France?"  (answered by the local AI)
- "What's the latest news?"  (searches the web)

**Reminders** — "Remind me to call mom at 6 pm" / "...in 10 minutes"

**Controls** — "Volume up", "mute", "play music", "pause", "next song",
"brightness up", "lock my computer"

**Type for you** — "Type Dear team, thanks for your help" (click the target
window within 3 seconds)

**Images** — "Create an image of a sunset", "draw a robot";
"What is in this image?", "describe image C:/path/pic.jpg"

**Screen & text** — "Take a screenshot", "what do you see on my screen",
"read the text on my screen"

**Translate** — "How do I say good morning in Japanese?"

**Personal** — "My name is Yuvan", "remember that I like cricket",
"what do you know about me", "I'm tired", "how are you"

**Briefing** — "Daily briefing" (also runs automatically each morning).

## Natural human voice

By default Smith uses **edge-tts** — free, no key, much warmer than the
robotic built-in voice (needs internet). Pick a voice with `EDGE_VOICE`
(e.g. `en-US-JennyNeural`, `en-GB-SoniaNeural`). Set `USE_EDGE_TTS = False`
to use the fully-offline voice.

## Email alerts (optional)

Use an **app password** (Gmail: https://myaccount.google.com/apppasswords).
Set `EMAIL_ENABLED = True`, `EMAIL_ADDRESS`, `EMAIL_APP_PASSWORD`,
`IMAP_SERVER`. It only reads unread counts and the latest sender/subject —
never sends, deletes, or marks mail read. Keep this file private.

## Reading text needs Tesseract (one-time)

For "read the text…", install Tesseract:
https://github.com/UB-Mannheim/tesseract/wiki — then check `TESSERACT_PATH`
in the settings points to `tesseract.exe`.

## Voice setup

Download `vosk-model-small-en-us-0.15` from
https://alphacephei.com/vosk/models , unzip it, rename the folder to
`model`, and put it next to `assistant.py`. Then `python assistant.py --voice`.

## Auto-start

`python assistant.py --install` adds a quiet launcher to your Startup folder.
Remove with `--uninstall`.

Your name and notes are saved locally in `memory.json`.


#created by#
YUVAN