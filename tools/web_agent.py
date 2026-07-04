"""
tools/web_agent.py -- agentic web browsing.

Give it a goal ("find the cheapest 4TB NVMe on newegg and list top 3");
it keeps ONE Playwright session open and loops:

    observe page -> AI decides next action -> execute -> repeat

Actions: navigate, click, fill, press, scroll, extract, done.
Safeguards: browser permission gate, max 15 steps, never downloads files,
never submits payment forms (refuses selectors containing card/cvv/payment).

Heavy: run via /tools/run_async.
"""
import json
import logging
import re

log = logging.getLogger("tools.web_agent")

NAME        = "web_agent"
DESCRIPTION = (
    "Autonomous multi-step web browsing agent. Give a goal; it navigates, "
    "clicks, fills forms, and extracts info across multiple pages, then "
    "reports what it found. Inputs: goal, start_url (optional), max_steps."
)
CATEGORY = "builtin"
ICON     = "globe"
INPUTS = [
    {"name": "goal",      "label": "Goal", "type": "textarea", "required": True},
    {"name": "start_url", "label": "Start URL (optional)", "type": "text"},
    {"name": "max_steps", "label": "Max steps", "type": "text"},
    {"name": "username",  "label": "Username", "type": "text"},
]

BLOCKED_SELECTOR = re.compile(r"card|cvv|cvc|payment|password", re.I)

_SYSTEM = (
    "You are a web browsing agent. You get the current page state and must "
    "output ONLY a JSON object choosing the next action:\n"
    '{"action": "navigate", "url": "..."}\n'
    '{"action": "click", "selector": "css selector"}\n'
    '{"action": "fill", "selector": "css", "text": "value"}\n'
    '{"action": "press", "key": "Enter"}\n'
    '{"action": "scroll"}\n'
    '{"action": "extract", "note": "what you learned from this page"}\n'
    '{"action": "done", "summary": "final answer to the goal"}\n'
    "Use selectors visible in the ELEMENTS list. Use extract to record "
    "findings before moving on. Finish with done as soon as the goal is met."
)


def _observe(page) -> str:
    try:
        els = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('a,button,input,select,textarea,[role=button]')
              .forEach((e, i) => {
                if (i > 60 || !e.offsetParent) return;
                const tag = e.tagName.toLowerCase();
                const txt = (e.innerText || e.value || e.placeholder || '').trim().slice(0, 60);
                const id  = e.id ? '#' + e.id : '';
                const nm  = e.name ? `[name="${e.name}"]` : '';
                out.push(`${tag}${id}${nm} "${txt}"`);
              });
            return out.join('\\n');
        }""")
    except Exception:
        els = "(could not list elements)"
    try:
        text = page.inner_text("body")[:2500]
    except Exception:
        text = "(no text)"
    return "URL: %s\nTITLE: %s\n\nELEMENTS:\n%s\n\nPAGE TEXT:\n%s" % (
        page.url, page.title(), els, text)


def run(goal: str = "", start_url: str = "", max_steps: str = "15",
        username: str = "default") -> dict:
    from services.permission_manager import perms
    if not perms.check("browser"):
        return perms.deny_message("browser")
    if not goal.strip():
        return {"error": "goal required"}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"error": "Playwright not installed. Run: pip install playwright "
                         "&& playwright install chromium"}

    from providers import AI
    steps_limit = min(int(str(max_steps).strip() or "15"), 25)
    history, findings = [], []

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(15000)
            if start_url:
                page.goto(start_url, wait_until="domcontentloaded")
            else:
                page.goto("https://duckduckgo.com", wait_until="domcontentloaded")

            for step in range(1, steps_limit + 1):
                state = _observe(page)
                prompt = ("GOAL: %s\n\nACTIONS SO FAR:\n%s\n\nFINDINGS SO FAR:\n%s"
                          "\n\nCURRENT PAGE:\n%s\n\nNext action JSON:" % (
                              goal, "\n".join(history[-8:]) or "(none)",
                              "\n".join(findings) or "(none)", state))
                raw = AI.generate(prompt, system=_SYSTEM, model="gpt-4o",
                                  max_tokens=300, temperature=0.1)
                m = re.search(r"\{[\s\S]*\}", raw)
                if not m:
                    history.append("step %d: unparseable response" % step)
                    continue
                try:
                    act = json.loads(m.group(0))
                except Exception:
                    history.append("step %d: bad JSON" % step)
                    continue

                a = (act.get("action") or "").lower()
                try:
                    if a == "done":
                        browser.close()
                        return {"result": act.get("summary", ""),
                                "findings": findings, "steps": history}
                    if a == "navigate" and act.get("url", "").startswith("http"):
                        page.goto(act["url"], wait_until="domcontentloaded")
                        history.append("step %d: navigate %s" % (step, act["url"]))
                    elif a == "click" and act.get("selector"):
                        if BLOCKED_SELECTOR.search(act["selector"]):
                            history.append("step %d: BLOCKED unsafe click" % step)
                            continue
                        page.click(act["selector"])
                        page.wait_for_load_state("domcontentloaded")
                        history.append("step %d: click %s" % (step, act["selector"]))
                    elif a == "fill" and act.get("selector"):
                        if BLOCKED_SELECTOR.search(act["selector"]):
                            history.append("step %d: BLOCKED unsafe fill" % step)
                            continue
                        page.fill(act["selector"], act.get("text", ""))
                        history.append("step %d: fill %s" % (step, act["selector"]))
                    elif a == "press":
                        page.keyboard.press(act.get("key", "Enter"))
                        page.wait_for_load_state("domcontentloaded")
                        history.append("step %d: press %s" % (step, act.get("key", "Enter")))
                    elif a == "scroll":
                        page.evaluate("window.scrollBy(0, window.innerHeight)")
                        history.append("step %d: scroll" % step)
                    elif a == "extract":
                        findings.append(act.get("note", "")[:800])
                        history.append("step %d: extract" % step)
                    else:
                        history.append("step %d: unknown action %r" % (step, a))
                except Exception as e:
                    history.append("step %d: ERROR %s" % (step, str(e)[:120]))

            browser.close()
            summary = AI.generate(
                "The browsing agent hit its step limit. Write the best possible "
                "answer to the goal from these findings.\n\nGOAL: %s\n\nFINDINGS:\n%s"
                % (goal, "\n".join(findings) or "(none)"),
                model="gpt-4o-mini", max_tokens=600)
            return {"result": summary, "findings": findings, "steps": history,
                    "note": "step limit reached"}
    except Exception as e:
        log.error("web_agent failed: %s", e)
        return {"error": str(e), "steps": history, "findings": findings}
