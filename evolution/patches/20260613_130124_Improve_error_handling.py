Here are the modified functions with improved error handling:

```python
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
        r.raise_for_status()  # Raise an error for bad responses

        data = r.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    except requests.exceptions.RequestException as e:
        print("Gemini request failed:", e)
    except (KeyError, IndexError) as e:
        print("Gemini response parsing failed:", e)
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
        r.raise_for_status()  # Raise an error for bad responses

        return r.json()["choices"][0]["message"]["content"]

    except requests.exceptions.RequestException as e:
        print("GitHub Models request failed:", e)
    except (KeyError, IndexError) as e:
        print("GitHub Models response parsing failed:", e)
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
        r.raise_for_status()  # Raise an error for bad responses

        return r.json()["response"]

    except requests.exceptions.RequestException as e:
        print("Ollama request failed:", e)
    except (KeyError, IndexError) as e:
        print("Ollama response parsing failed:", e)
    except Exception as e:
        print("Ollama failed:", e)

    return None
``` 

In these modifications:
- Added `r.raise_for_status()` to throw an error for any HTTP response that is not successful (i.e., status codes 4xx or 5xx).
- Separated exceptions for request failures (using `requests.exceptions.RequestException`) and response parsing failures (using `KeyError` and `IndexError`).
- Improved error messages for clearer identification of the failure point.