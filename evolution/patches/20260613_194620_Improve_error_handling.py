FILE: ai_brain.py

FUNCTION: ask_gemini

REPLACE WITH:

def ask_gemini(prompt):
    response = None
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
        response = data["candidates"][0]["content"]["parts"][0]["text"]

    except requests.exceptions.HTTPError as http_err:
        print("HTTP error occurred:", http_err)
    except requests.exceptions.ConnectionError as conn_err:
        print("Connection error occurred:", conn_err)
    except requests.exceptions.Timeout:
        print("Request timed out.")
    except Exception as e:
        print("Gemini failed:", e)

    return response