Here are the modified functions with improved error handling for the `ask_gemini`, `ask_github`, and `ask_ollama` functions:


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

        r.raise_for_status()  # Raise an HTTPError for bad responses

        data = r.json()

        return data["candidates"][0]["content"]["parts"][0]["text"]

    except requests.exceptions.HTTPError as http_err:
        print(f"Gemini HTTP error: {http_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"Gemini Request failed: {req_err}")
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

        r.raise_for_status()  # Raise an HTTPError for bad responses

        return r.json()["choices"][0]["message"]["content"]

    except requests.exceptions.HTTPError as http_err:
        print(f"GitHub HTTP error: {http_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"GitHub Request failed: {req_err}")
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

        r.raise_for_status()  # Raise an HTTPError for bad responses

        return r.json()["response"]

    except requests.exceptions.HTTPError as http_err:
        print(f"Ollama HTTP error: {http_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"Ollama Request failed: {req_err}")
    except Exception as e:
        print("Ollama failed:", e)

    return None
 

### Key Improvements:
1. Added more specific exception handling for HTTP errors using `r.raise_for_status()`.
2. Separate handlers for general requests exceptions for better clarity on failures.
3. Enhanced error messaging to include context about the type of error encountered.