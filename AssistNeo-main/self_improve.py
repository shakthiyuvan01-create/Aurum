import os, time, threading, logging, urllib.parse, random, json, datetime, ast

log = logging.getLogger("self_improve")

# ── Config ────────────────────────────────────────────────────────
SELF_IMPROVE_INTERVAL = 30  # 30 seconds

_HERE             = os.path.dirname(os.path.abspath(__file__))
ASSISTANT_FILE    = os.path.join(_HERE, "assistant.py")
IMPROVEMENTS_FILE = os.path.join(_HERE, "auto_improvements.py")
IMPROVE_LOG_FILE  = os.path.join(_HERE, "improve_log.txt")
MEMORY_FILE       = os.path.join(_HERE, "improve_memory.json")
REPORT_FILE       = os.path.join(_HERE, "improve_report.txt")

_SEARCH_TOPICS = [
    "best features of a personal AI assistant 2025",
    "what should an AI assistant be able to do",
    "common weaknesses in AI assistants",
    "how to improve a Python AI personal assistant",
    "missing features in AI chatbot assistants",
    "AI assistant capabilities checklist",
    "voice AI assistant best practices",
    "self healing AI systems",
    "AI assistant memory and learning",
]

# ── State ─────────────────────────────────────────────────────────
_running     = False
_iteration   = 0
_last_status = "Not started"
_thread      = None


# ── Memory system ─────────────────────────────────────────────────
def _load_memory() -> dict:
    """Load the self-improvement memory (past cycles, goals, weaknesses)."""
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "cycles": [],
            "goals": [
                "Improve voice interaction",
                "Add more smart commands",
                "Improve memory and context",
                "Make responses more natural",
                "Add self-healing on errors",
            ],
            "weaknesses": [],
            "fixed": [],
            "metrics": {
                "total_cycles": 0,
                "successful_fixes": 0,
                "failed_cycles": 0,
                "self_heals": 0,
            }
        }


def _save_memory(mem: dict) -> None:
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(mem, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log.warning("[self_improve] Could not save memory: %s", e)


# ── Experience learning ───────────────────────────────────────────
def _build_experience_context(mem: dict) -> str:
    """Build a summary of past experience to guide the next cycle."""
    lines = []
    if mem.get("weaknesses"):
        pending = [w for w in mem["weaknesses"] if w not in mem.get("fixed", [])]
        lines.append("KNOWN WEAKNESSES NOT YET FIXED:\n" +
                     "\n".join(f"- {w}" for w in pending[:5]))
    if mem.get("fixed"):
        lines.append("ALREADY FIXED (do not repeat):\n" +
                     "\n".join(f"- {f}" for f in mem["fixed"][-10:]))
    if mem.get("goals"):
        lines.append("CURRENT GOALS:\n" +
                     "\n".join(f"- {g}" for g in mem["goals"][:5]))
    if mem.get("cycles"):
        last = mem["cycles"][-1]
        lines.append(f"LAST CYCLE RESULT: {last.get('result', 'unknown')}")

        if mem.get("failed_fixes"):
            recent_fails = mem["failed_fixes"][-5:]
            lines.append("RECENT FAILED FIXES (do not repeat these approaches):\n" +
                         "\n".join(f"- Failed because: {f.get('reason', '?')}"
                                   for f in recent_fails))
    return "\n\n".join(lines)



# ── Priority system ───────────────────────────────────────────────
def _pick_priority(mem: dict) -> str:
    """Pick the highest priority goal/weakness to focus on this cycle."""
    pending = [w for w in mem.get("weaknesses", [])
               if w not in mem.get("fixed", [])]
    if pending:
        return f"Focus on fixing this known weakness: {pending[0]}"
    goals = mem.get("goals", [])
    if goals:
        return f"Focus on achieving this goal: {goals[0]}"
    return "Find any weakness and fix it."


# ── Self-healing ──────────────────────────────────────────────────
def _check_syntax(code: str) -> bool:
    """Check if generated code has valid Python syntax."""
    try:
        ast.parse(code)
        return True
    except SyntaxError as e:
        log.warning("[self_improve] Syntax error in generated code: %s", e)
        return False


def _self_heal(mem: dict) -> bool:
    """
    Check if assistant.py is valid Python.
    If broken, ask AI to find and fix the error.
    Returns True if healing was attempted.
    """
    try:
        with open(ASSISTANT_FILE, "r", encoding="utf-8") as f:
            code = f.read()
        ast.parse(code)
        return False  # no healing needed
    except SyntaxError as e:
        log.warning("[self_improve] SELF-HEAL triggered: %s", e)
        heal_prompt = (
            f"The file assistant.py has a Python syntax error:\n{e}\n\n"
            "Here is the broken code near the error:\n"
            f"{_read_own_code(3000)}\n\n"
            "Write ONLY a corrected version of the broken function or block. "
            "Raw Python only, no markdown."
        )
        fix = _ask_ai(heal_prompt)
        if fix and _check_syntax(fix):
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sep = f"\n\n# SELF-HEAL [{ts}]\n"
            with open(ASSISTANT_FILE, "a", encoding="utf-8") as f:
                f.write(sep + fix.strip() + "\n")
            mem["metrics"]["self_heals"] = mem["metrics"].get("self_heals", 0) + 1
            log.info("[self_improve] Self-heal applied.")
            return True
        return False


# ── Reflection ────────────────────────────────────────────────────
def _reflect(question: str, fix_code: str, mem: dict) -> str:
    """Ask AI to reflect on whether the fix was good and extract the weakness name."""
    prompt = (
        f"You just wrote this Python fix for an AI assistant:\n{fix_code}\n\n"
        f"The focus was: {question}\n\n"
        "In one sentence: what weakness did you fix?\n"
        "Then on a new line: was this fix good? (yes/no and why in one sentence)\n"
        "Return exactly 2 lines."
    )
    try:
        reflection = _ask_ai(prompt)
        return reflection.strip() if reflection else "No reflection."
    except Exception:
        return "Reflection failed."


# ── Metrics and reports ───────────────────────────────────────────
def _generate_report(mem: dict) -> None:
    """Write a human-readable report to improve_report.txt."""
    m = mem.get("metrics", {})
    lines = [
        "=" * 60,
        f"  ASSIST NEO — SELF-IMPROVEMENT REPORT",
        f"  Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 60,
        f"  Total cycles run   : {m.get('total_cycles', 0)}",
        f"  Successful fixes   : {m.get('successful_fixes', 0)}",
        f"  Failed cycles      : {m.get('failed_cycles', 0)}",
        f"  Self-heals done    : {m.get('self_heals', 0)}",
        "",
        "  GOALS:",
        *[f"    - {g}" for g in mem.get("goals", [])],
        "",
        "  KNOWN WEAKNESSES:",
        *[f"    - {w}" for w in mem.get("weaknesses", [])],
        "",
        "  FIXED SO FAR:",
        *[f"    ✓ {f}" for f in mem.get("fixed", [])],
        "",
        "  LAST 5 CYCLES:",
    ]
    for c in mem.get("cycles", [])[-5:]:
        lines.append(f"    [{c.get('time','')}] {c.get('result','')}")
    lines.append("=" * 60)
    try:
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        log.info("[self_improve] Report written to improve_report.txt")
    except Exception as e:
        log.warning("[self_improve] Could not write report: %s", e)


# ── Helpers ───────────────────────────────────────────────────────
def _search_best_practices() -> str:
    import urllib.request, json as _json
    topic = random.choice(_SEARCH_TOPICS)
    url = ("https://api.duckduckgo.com/?q="
           + urllib.parse.quote(topic)
           + "&format=json&no_html=1&skip_disambig=1")
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = _json.loads(r.read().decode("utf-8", "ignore"))
        abstract = data.get("AbstractText", "")
        related  = " | ".join(
            t.get("Text", "") for t in data.get("RelatedTopics", [])[:6]
            if isinstance(t, dict))
        result = (abstract + " " + related).strip()
        return result if result else topic
    except Exception:
        return topic


def _read_own_code(max_chars: int = 6000) -> str:
    try:
        with open(ASSISTANT_FILE, "r", encoding="utf-8") as f:
            return f.read()[:max_chars]
    except Exception as e:
        log.warning("[self_improve] Could not read own code: %s", e)
        return "(Could not read assistant.py)"


def _ask_ai(prompt: str) -> str:
    try:
        import assistant as _a
        return _a.ask_ai_brain(prompt, with_context=False)
    except Exception as e:
        log.warning("[self_improve] AI brain unavailable: %s", e)
        return ""

def _clean_code(code: str) -> str:
    """Strip markdown fences if the AI returned them."""
    import re
    code = code.strip()
    code = re.sub(r'^```(?:python)?\n?', '', code)
    code = re.sub(r'\n?```$', '', code)
    return code.strip()
def _test_fix(code: str) -> tuple:
    """Run the fix in a sandbox. Returns (passed, error_message)."""
    import tempfile, subprocess, sys
    test_code = (
        "import os, sys, time, logging, subprocess, urllib.parse\n"
        "import re, json, datetime, threading, smtplib\n\n"
        + code
    )
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(test_code)
            tmp = f.name
        result = subprocess.run(
            [sys.executable, tmp],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return True, ""
        return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "Test timed out"
    except Exception as e:
        return False, str(e)
    finally:
        try:
            if tmp: os.remove(tmp)
        except Exception:
            pass

def _save_and_apply(code: str, iteration: int) -> None:
    ts  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sep = (f"\n\n# {'─'*60}\n"
           f"# AUTO-IMPROVEMENT #{iteration}  [{ts}]\n"
           f"# {'─'*60}\n")
    # Save to auto_improvements.py
    try:
        with open(IMPROVEMENTS_FILE, "a", encoding="utf-8") as f:
            f.write(sep + code.strip() + "\n")
    except Exception as e:
        log.warning("[self_improve] Could not save to improvements file: %s", e)
    # Apply directly to assistant.py
    try:
        with open(ASSISTANT_FILE, "a", encoding="utf-8") as f:
            f.write(sep + code.strip() + "\n")
        log.info("[self_improve] Fix #%d applied to assistant.py.", iteration)
    except Exception as e:
        log.warning("[self_improve] Could not apply to assistant.py: %s", e)
    # Log
    try:
        with open(IMPROVE_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] Iteration {iteration}: fix applied.\n")
    except Exception:
        pass


# ── Core cycle ────────────────────────────────────────────────────
def run_one_cycle(iteration: int) -> str:
    global _last_status
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log.info("[self_improve] ── Cycle #%d started ──", iteration)

    mem = _load_memory()
    mem["metrics"]["total_cycles"] = mem["metrics"].get("total_cycles", 0) + 1

    # Self-heal first if assistant.py is broken
    _self_heal(mem)

    # Research
    research = _search_best_practices()
    log.info("[self_improve] Research: %s", research[:100])

    # Experience + priority
    experience = _build_experience_context(mem)
    priority   = _pick_priority(mem)

    # Read own code
    own_code = _read_own_code()

    # Ask AI with full context
    prompt = (
        "You are an expert Python developer doing a self-improvement pass.\n\n"
        f"PRIORITY THIS CYCLE:\n{priority}\n\n"
        f"EXPERIENCE FROM PAST CYCLES:\n{experience}\n\n"
        f"WEB RESEARCH:\n{research}\n\n"
        f"CURRENT CODE (first 6000 chars):\n{own_code}\n\n"
        "YOUR TASK:\n"
        "1. Based on the priority and experience above, find ONE weakness.\n"
        "2. Write a complete, safe Python function that fixes it.\n"
        "3. Must be self-contained and appendable to assistant.py.\n"
        "4. Start with: # FIX: <one-line description of weakness fixed>\n"
        "5. Return ONLY raw Python code — no markdown, no explanation.\n"
    )
    fix_code = _ask_ai(prompt)
    fix_code = _clean_code(fix_code)
    if not fix_code or len(fix_code.strip()) < 30:
        mem["metrics"]["failed_cycles"] = mem["metrics"].get("failed_cycles", 0) + 1
        mem["cycles"].append({"time": ts, "result": f"Cycle #{iteration}: no fix generated."})
        _save_memory(mem)
        msg = f"Cycle #{iteration}: AI returned nothing useful."
        _last_status = msg
        return msg

        # Validate syntax
        if not _check_syntax(fix_code):
            mem["metrics"]["failed_cycles"] = mem["metrics"].get("failed_cycles", 0) + 1
            mem.setdefault("failed_fixes", []).append({
                "time": ts, "reason": "syntax error", "code": fix_code[:200]
            })
            mem["cycles"].append({"time": ts, "result": f"Cycle #{iteration}: syntax error in fix."})
            _save_memory(mem)
            msg = f"Cycle #{iteration}: fix had syntax errors, skipped."
            _last_status = msg
            return msg

        # Test the fix in a sandbox
        passed, error = _test_fix(fix_code)
        if not passed:
            log.warning("[self_improve] Fix failed test: %s", error)
            mem["metrics"]["failed_cycles"] = mem["metrics"].get("failed_cycles", 0) + 1
            mem.setdefault("failed_fixes", []).append({
                "time": ts, "reason": error, "code": fix_code[:200]
            })
            mem["cycles"].append({"time": ts, "result": f"Cycle #{iteration}: test failed — {error[:80]}"})
            _save_memory(mem)
            msg = f"Cycle #{iteration}: fix failed test — {error[:80]}"
            _last_status = msg
            return msg

        log.info("[self_improve] Fix passed test. Applying...")

    # Reflection
    reflection = _reflect(priority, fix_code, mem)
    log.info("[self_improve] Reflection: %s", reflection)

    # Extract weakness name from reflection (first line)
    weakness_name = reflection.split("\n")[0].strip() if reflection else f"Fix #{iteration}"

    # Update memory
    if weakness_name and weakness_name not in mem.get("weaknesses", []):
        mem.setdefault("weaknesses", []).append(weakness_name)
    mem.setdefault("fixed", []).append(weakness_name)
    mem["metrics"]["successful_fixes"] = mem["metrics"].get("successful_fixes", 0) + 1
    mem["cycles"].append({"time": ts, "result": f"Cycle #{iteration}: {weakness_name}"})

    # Apply fix
    _save_and_apply(fix_code, iteration)

    # Generate report
    _generate_report(mem)

    _save_memory(mem)
    msg = f"Cycle #{iteration} complete — {weakness_name}"
    _last_status = msg
    log.info("[self_improve] %s", msg)
    return msg


# ── Infinite loop ─────────────────────────────────────────────────
def _loop() -> None:
    global _running, _iteration, _last_status
    _running   = True
    _iteration = 0
    log.info("[self_improve] 24-hour loop started.")
    while _running:
        _iteration += 1
        try:
            run_one_cycle(_iteration)
        except Exception as e:
            _last_status = f"Error in cycle #{_iteration}: {e}"
            log.warning("[self_improve] %s", _last_status)
        for _ in range(SELF_IMPROVE_INTERVAL):
            if not _running:
                break
            time.sleep(1)
    log.info("[self_improve] Loop stopped after %d cycles.", _iteration)


# ── Public API ────────────────────────────────────────────────────
def start(interval_seconds: int = None) -> None:
    global _thread, SELF_IMPROVE_INTERVAL
    if _thread and _thread.is_alive():
        log.info("[self_improve] Already running.")
        return
    if interval_seconds is not None:
        SELF_IMPROVE_INTERVAL = interval_seconds
    _thread = threading.Thread(target=_loop, daemon=True, name="self-improve")
    _thread.start()
    log.info("[self_improve] Background thread launched.")


def stop() -> None:
    global _running
    _running = False


def status() -> dict:
    mem = _load_memory()
    return {
        "running":    _running,
        "iteration":  _iteration,
        "interval":   SELF_IMPROVE_INTERVAL,
        "last_status": _last_status,
        "metrics":    mem.get("metrics", {}),
        "goals":      mem.get("goals", []),
        "fixed":      mem.get("fixed", []),
    }