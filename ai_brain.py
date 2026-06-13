import os
import requests
from dotenv import load_dotenv

load_dotenv()

# ========= CONFIG =========

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_MODEL = "gpt-4o-mini"

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"


# ========= GEMINI =========

def ask_gemini(prompt):

    try:

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.0-flash:generateContent"
        )

        r = requests.post(
            url,
            params={"key": GEMINI_API_KEY},
            json={
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ]
            },
            timeout=60
        )

        if r.status_code == 200:

            data = r.json()

            return data["candidates"][0]["content"]["parts"][0]["text"]

    except Exception as e:

        print("Gemini failed:", e)

    return None


# ========= GITHUB MODELS =========

def ask_github(prompt):

    try:

        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": GITHUB_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 1000
        }

        r = requests.post(
            "https://models.inference.ai.azure.com/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )

        if r.status_code == 200:

            return r.json()["choices"][0]["message"]["content"]

    except Exception as e:

        print("GitHub failed:", e)

    return None


# ========= OLLAMA =========

def ask_ollama(prompt):

    try:

        r = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )

        if r.status_code == 200:

            return r.json()["response"]

    except Exception as e:

        print("Ollama failed:", e)

    return None


# ========= MASTER FALLBACK =========

def ask_ai(prompt):

    print("Trying Gemini...")

    answer = ask_gemini(prompt)

    if answer:
        print("Gemini success")
        return answer

    print("Trying GitHub Models...")

    answer = ask_github(prompt)

    if answer:
        print("GitHub success")
        return answer

    print("Trying Ollama...")

    answer = ask_ollama(prompt)

    if answer:
        print("Ollama success")
        return answer

    return "All AI systems failed."