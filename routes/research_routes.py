"""
routes/research_routes.py — Deep research SSE endpoint
=======================================================
POST /research  →  multi-step web research streamed back as SSE

Steps:
  1. Break query into 3 sub-queries (LLM)
  2. DuckDuckGo search each sub-query
  3. Fetch top page for each
  4. LLM synthesises a full report
  5. Stream report token-by-token
"""

from __future__ import annotations
import json, logging, os
import requests as _rq

from flask import Blueprint, request, session, jsonify, Response, stream_with_context

research_bp = Blueprint("research", __name__)
log = logging.getLogger("routes.research")

_deps: dict = {}

def _init(deps: dict) -> None:
    _deps.update(deps)

def _current_user() -> str:
    return session.get("username", "default")

GITHUB_API = "https://models.inference.ai.azure.com/chat/completions"
_HEADERS_TMPL = lambda token: {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}

def _llm(messages, token, model, stream=False, max_tokens=2000):
    return _rq.post(GITHUB_API, headers=_HEADERS_TMPL(token), json={
        "model": model, "messages": messages,
        "temperature": 0.4, "max_tokens": max_tokens, "stream": stream,
    }, stream=stream, timeout=60)


def _ddg_search(query: str, n: int = 3) -> list[dict]:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as d:
            return list(d.text(query, max_results=n))
    except Exception:
        return []


def _fetch_page(url: str, max_chars: int = 2000) -> str:
    try:
        import requests
        from bs4 import BeautifulSoup
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script","style","nav","footer","header"]):
            t.decompose()
        text = "\n".join(l for l in soup.get_text("\n", strip=True).splitlines() if l.strip())
        return text[:max_chars]
    except Exception:
        return ""


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@research_bp.route("/research", methods=["POST"])
def deep_research():
    if not session.get("auth"):
        return jsonify({"error": "login"}), 401

    body  = request.json or {}
    query = body.get("query", "").strip()
    if not query:
        return jsonify({"error": "empty query"}), 400

    asst  = _deps["assistant"]
    token = asst.GITHUB_TOKEN or ""
    model = os.getenv("MAIN_MODEL", asst.GITHUB_MODEL)

    def generate():
        # ── Step 1: Generate sub-queries ─────────────────────────────
        yield _sse({"status": "🔍 Planning research sub-queries..."})
        try:
            r = _llm([
                {"role": "system", "content": "You are a research planner. Output ONLY a JSON array of 3 short search queries (strings) to thoroughly research the given topic. No explanation."},
                {"role": "user",   "content": f"Topic: {query}"},
            ], token, model, max_tokens=200)
            r.raise_for_status()
            raw = r.json()["choices"][0]["message"]["content"].strip()
            # strip markdown code fences if present
            raw = raw.strip("`").strip()
            if raw.startswith("json"):
                raw = raw[4:]
            sub_queries = json.loads(raw)
            if not isinstance(sub_queries, list):
                sub_queries = [query]
        except Exception as e:
            sub_queries = [query, f"{query} explained", f"{query} details"]
            log.warning("Sub-query generation failed: %s", e)

        # ── Step 2 & 3: Search + fetch pages ─────────────────────────
        context_chunks = []
        for i, sq in enumerate(sub_queries[:3], 1):
            yield _sse({"status": f"🌐 Searching ({i}/3): {sq}"})
            results = _ddg_search(sq, n=2)
            for res in results[:2]:
                title   = res.get("title", "")
                url     = res.get("href", "")
                snippet = res.get("body", "")
                yield _sse({"status": f"📄 Reading: {title[:60]}..."})
                page_text = _fetch_page(url) or snippet
                context_chunks.append(
                    f"### {title}\nSource: {url}\n\n{page_text}"
                )

        if not context_chunks:
            yield _sse({"status": "⚠️ No web results found. Answering from knowledge..."})

        # ── Step 4 & 5: Synthesise + stream ──────────────────────────
        yield _sse({"status": "✍️ Writing research report..."})
        context = "\n\n---\n\n".join(context_chunks[:6])
        system_prompt = (
            "You are an expert research analyst. Write a comprehensive, well-structured "
            "research report answering the user's query. Use the provided web sources. "
            "Format with markdown: headers, bullet points, bold key terms. "
            "End with a **Sources** section listing URLs used."
        )
        user_prompt = (
            f"Query: {query}\n\n"
            f"Web sources gathered:\n\n{context}\n\n"
            "Write a thorough research report."
        )
        try:
            stream_r = _llm([
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ], token, model, stream=True, max_tokens=2000)
            stream_r.raise_for_status()
        except Exception as e:
            yield _sse({"error": f"LLM call failed: {e}"})
            return

        full_reply = []
        for line in stream_r.iter_lines():
            if not line:
                continue
            decoded = line.decode("utf-8") if isinstance(line, bytes) else line
            if not decoded.startswith("data: "):
                continue
            raw = decoded[6:]
            if raw == "[DONE]":
                break
            try:
                chunk = json.loads(raw)
                delta = chunk["choices"][0]["delta"].get("content", "")
                if delta:
                    full_reply.append(delta)
                    yield _sse({"delta": delta})
            except Exception:
                pass

        yield _sse({"done": True, "reply": "".join(full_reply)})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
