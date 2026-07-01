"""
tools/youtube.py — YouTube: search, summarize (transcript + Gemini), get_info, trending.
Ported from Mark-XLVII youtube_video.py. Actions play/open are excluded (no desktop).
"""
import logging
import re
from urllib.parse import quote_plus

log = logging.getLogger(__name__)

NAME        = "youtube"
DESCRIPTION = (
    "YouTube tool. Actions: search (find videos), summarize (transcript summary), "
    "get_info (title/views/duration), trending (top videos by region)"
)
CATEGORY = "builtin"
ICON     = "▶️"
INPUTS = [
    {"name": "action", "label": "Action", "type": "select",
     "options": [
         {"value": "search",    "label": "Search videos"},
         {"value": "summarize", "label": "Summarize video (needs url)"},
         {"value": "get_info",  "label": "Get video info (needs url)"},
         {"value": "trending",  "label": "Trending videos"},
     ], "required": True, "default": "search"},
    {"name": "query",  "label": "Search query",  "type": "text",   "placeholder": "search term", "required": False},
    {"name": "url",    "label": "YouTube URL",   "type": "text",   "placeholder": "https://youtube.com/watch?v=...", "required": False},
    {"name": "region", "label": "Trending region (2-letter country code)", "type": "text", "placeholder": "US", "required": False},
    {"name": "max_results", "label": "Max search results", "type": "number", "placeholder": "5"},
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_YT_VIDEO_FILTER = "EgIQAQ%3D%3D"


def _extract_video_id(url: str):
    m = re.search(r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})", url or "")
    return m.group(1) if m else None


def _is_valid_yt_url(url: str) -> bool:
    return bool(re.search(r"(youtube\.com|youtu\.be)", url or ""))


def _gemini_key() -> str:
    import os
    k = os.getenv("GEMINI_API_KEY", "")
    if not k:
        raise EnvironmentError("GEMINI_API_KEY not set")
    return k


# ── Search ────────────────────────────────────────────────────────────────────

def _search_videos(query: str, max_results: int) -> dict:
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(f"site:youtube.com {query}", max_results=max_results):
                url = r.get("href", "")
                if "watch?v=" in url:
                    results.append({"title": r.get("title", ""), "url": url, "snippet": r.get("body", "")})
        if results:
            lines = [f"{i+1}. {r['title']}\n   {r['url']}" for i, r in enumerate(results)]
            return {"result": "\n\n".join(lines), "videos": results}
    except Exception as e:
        log.warning("DDG youtube search failed: %s", e)

    # fallback: return search URL
    search_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}&sp={_YT_VIDEO_FILTER}"
    return {"result": f"Search URL: {search_url}", "videos": [{"url": search_url}]}


# ── Summarize ─────────────────────────────────────────────────────────────────

def _get_transcript(video_id: str):
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        tlist = YouTubeTranscriptApi.list_transcripts(video_id)
        langs = ["en", "tr", "de", "fr", "es", "it", "pt", "ru", "ja", "ko"]
        transcript = None
        try:
            transcript = tlist.find_manually_created_transcript(langs)
        except Exception:
            pass
        if not transcript:
            try:
                transcript = tlist.find_generated_transcript(langs)
            except Exception:
                for t in tlist:
                    transcript = t
                    break
        if not transcript:
            return None
        fetched = transcript.fetch()
        return " ".join(e["text"] for e in fetched)
    except ImportError:
        return None
    except Exception as e:
        log.warning("Transcript fetch failed: %s", e)
        return None


def _summarize_video(url: str) -> dict:
    if not _is_valid_yt_url(url):
        return {"error": "Not a valid YouTube URL."}
    video_id = _extract_video_id(url)
    if not video_id:
        return {"error": "Could not extract video ID from URL."}

    transcript = _get_transcript(video_id)
    if not transcript:
        return {"error": "No transcript available for this video. It may be private, live, or have disabled captions."}

    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=_gemini_key())
        truncated = transcript[:80000] + ("..." if len(transcript) > 80000 else "")
        response  = client.models.generate_content(
            model   = "gemini-2.5-flash",
            contents= f"Summarize this YouTube video transcript:\n\n{truncated}",
            config  = types.GenerateContentConfig(
                system_instruction=(
                    "Summarize YouTube transcripts clearly and concisely. "
                    "Structure: 1-sentence overview, then 3-5 key points as a bullet list. "
                    "Be direct and informative."
                )
            ),
        )
        return {"result": response.text.strip(), "video_id": video_id}
    except Exception as e:
        log.error("Gemini summarize failed: %s", e)
        return {"error": f"Summary failed: {e}"}


# ── Get Info ──────────────────────────────────────────────────────────────────

def _get_info(url: str) -> dict:
    if not _is_valid_yt_url(url):
        return {"error": "Not a valid YouTube URL."}
    video_id = _extract_video_id(url)
    if not video_id:
        return {"error": "Could not extract video ID."}
    try:
        import requests
        r    = requests.get(f"https://www.youtube.com/watch?v={video_id}", headers=HEADERS, timeout=12)
        html = r.text
        info = {}
        for key, pattern in [
            ("title",    r'"title":\{"runs":\[\{"text":"([^"]+)"'),
            ("channel",  r'"ownerChannelName":"([^"]+)"'),
            ("views",    r'"viewCount":"(\d+)"'),
            ("duration", r'"lengthSeconds":"(\d+)"'),
            ("likes",    r'"label":"([0-9,]+ likes)"'),
        ]:
            m = re.search(pattern, html)
            if m:
                raw = m.group(1)
                if key == "views":
                    info[key] = f"{int(raw):,}"
                elif key == "duration":
                    secs = int(raw)
                    info[key] = f"{secs // 60}:{secs % 60:02d}"
                else:
                    info[key] = raw
        if not info:
            return {"error": "Could not retrieve video information."}
        lines = [f"{k.capitalize()}: {v}" for k, v in info.items()]
        return {"result": "\n".join(lines), **info}
    except ImportError:
        return {"error": "requests not installed."}
    except Exception as e:
        return {"error": f"Info fetch failed: {e}"}


# ── Trending ──────────────────────────────────────────────────────────────────

def _get_trending(region: str, max_results: int) -> dict:
    region = (region or "US").upper()
    try:
        import requests
        url  = f"https://www.youtube.com/feed/trending?gl={region}"
        r    = requests.get(url, headers=HEADERS, timeout=12)
        html = r.text

        titles   = re.findall(r'"title":\{"runs":\[\{"text":"([^"]+)"\}\]', html)
        channels = re.findall(r'"ownerText":\{"runs":\[\{"text":"([^"]+)"', html)

        results, seen = [], set()
        for i, title in enumerate(titles):
            if title in seen or len(title) < 5:
                continue
            seen.add(title)
            channel = channels[i] if i < len(channels) else "Unknown"
            results.append({"rank": len(results) + 1, "title": title, "channel": channel})
            if len(results) >= max_results:
                break

        if not results:
            return {"error": f"Could not fetch trending videos for {region}."}

        lines = [f"Trending in {region}:"] + [
            f"{v['rank']}. {v['title']} — {v['channel']}" for v in results
        ]
        return {"result": "\n".join(lines), "trending": results}
    except ImportError:
        return {"error": "requests not installed."}
    except Exception as e:
        return {"error": f"Trending fetch failed: {e}"}


# ── Public entry point ────────────────────────────────────────────────────────

def run(
    action:      str = "search",
    query:       str = "",
    url:         str = "",
    region:      str = "US",
    max_results: int = 5,
    username:    str = "",
) -> dict:
    action = (action or "search").lower().strip()
    try:
        max_results = max(1, min(int(str(max_results).strip() or 5), 20))
    except (ValueError, TypeError):
        max_results = 5

    log.info("youtube action=%s query=%r url=%r region=%r", action, query, url, region)

    if action == "search":
        if not query:
            return {"error": "Please provide a search query."}
        return _search_videos(query, max_results)
    if action == "summarize":
        if not url:
            return {"error": "Please provide a YouTube video URL to summarize."}
        return _summarize_video(url)
    if action == "get_info":
        if not url:
            return {"error": "Please provide a YouTube video URL."}
        return _get_info(url)
    if action == "trending":
        return _get_trending(region, max_results)
    return {"error": f"Unknown action: {action}. Use: search, summarize, get_info, trending"}
