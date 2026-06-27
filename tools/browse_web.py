"""Browse web tool — fetch and read any webpage."""

NAME        = "browse_web"
DESCRIPTION = "Fetch and read the content of any webpage URL. Use for website summarization."
CATEGORY    = "builtin"
ICON        = "🌐"
INPUTS = [
    {"name": "url",      "label": "URL",         "type": "text",   "placeholder": "https://example.com", "required": True},
    {"name": "max_chars","label": "Max Characters","type": "number","placeholder": "3000"},
]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def run(url: str, max_chars: int = 3000) -> dict:
    try:
        import requests
        from bs4 import BeautifulSoup

        r = requests.get(url.strip(), headers=_HEADERS, timeout=15)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        # Remove noise
        for tag in soup(["script", "style", "nav", "footer", "header",
                          "aside", "form", "noscript", "iframe"]):
            tag.decompose()

        title = (soup.title.string or url).strip() if soup.title else url
        text  = soup.get_text(separator="\n", strip=True)
        # Collapse blank lines
        lines = [l for l in text.splitlines() if l.strip()]
        text  = "\n".join(lines)

        limit = int(max_chars)
        if len(text) > limit:
            text = text[:limit] + f"\n\n[...content truncated at {limit} chars]"

        return {"message": f"**{title}**\n🔗 {url}\n\n{text}", "url": url, "title": title}

    except ImportError:
        return {"error": "beautifulsoup4 not installed. Run: pip install beautifulsoup4"}
    except Exception as e:
        return {"error": f"Could not fetch page: {e}"}
