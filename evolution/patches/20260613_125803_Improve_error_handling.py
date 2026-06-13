Certainly! Below is the improved version of the `ai_brain.py` file with enhanced error handling in the functions that call external APIs.

```python
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
    """Function to query the Gemini model with a given prompt."""
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
        r.raise_for_status()  # Raise an error for bad responses

        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    except requests.exceptions.HTTPError as http_err:
        print(f"Gemini HTTP error occurred: {http_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"Gemini request error occurred: {req_err}")
    except KeyError as key_err:
        print(f"Key error in Gemini response: {key_err}")
    except Exception as e:
        print("Gemini failed:", e)

    return None


# ========= GITHUB MODELS =========

def ask_github(prompt):
    """Function to query the GitHub model with a given prompt."""
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
        r.raise_for_status()  # Raise an error for bad responses

        return r.json()["choices"][0]["message"]["content"]

    except requests.exceptions.HTTPError as http_err:
        print(f"GitHub HTTP error occurred: {http_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"GitHub request error occurred: {req_err}")
    except KeyError as key_err:
        print(f"Key error in GitHub response: {key_err}")
    except Exception as e:
        print("GitHub failed:", e)

    return None


# ========= OLLAMA =========

def ask_ollama(prompt):
    """Function to query the Ollama model with a given prompt."""
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
        r.raise_for_status()  # Raise an error for bad responses

        return r.json()["response"]

    except requests.exceptions.HTTPError as http_err:
        print(f"Ollama HTTP error occurred: {http_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"Ollama request error occurred: {req_err}")
    except KeyError as key_err:
        print(f"Key error in Ollama response: {key_err}")
    except Exception as e:
        print("Ollama failed:", e)

    return None


# ========= MASTER FALLBACK =========

def ask_ai(prompt):
    """Master function to attempt querying multiple AI models."""
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
```

### Improvements made:
1. **Error Handling**: Added specific error handling for HTTP errors, request exceptions, and KeyError to capture issues more granularly.
2. **Documentation**: Provided brief docstrings for each function for better clarity.

These changes should enhance the resilience and maintainability of your project