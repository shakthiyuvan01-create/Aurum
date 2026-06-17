"""
code_runner.py — Multi-language code execution for Assist Neo
Supports: Python, JavaScript (Node), Bash/CMD
Each run is a subprocess with timeout + captured stdout/stderr.
"""
import os, subprocess, sys, tempfile, time, platform, logging

NAME        = "code_runner"
DESCRIPTION = "Execute Python, JavaScript, or Bash code and see the output"
CATEGORY    = "builtin"
ICON        = "⚡"
INPUTS = [
    {"name": "code",     "label": "Code",     "type": "textarea",
     "placeholder": "print('Hello, World!')", "required": True},
    {"name": "language", "label": "Language", "type": "select",
     "options": [{"value": "python",     "label": "Python"},
                 {"value": "javascript", "label": "JavaScript (Node)"},
                 {"value": "bash",       "label": "Bash / CMD"},
                 {"value": "sql",        "label": "SQL (SQLite)"}],
     "required": True, "default": "python"},
    {"name": "timeout", "label": "Timeout (s)", "type": "select",
     "options": [{"value": "10",  "label": "10s"},
                 {"value": "30",  "label": "30s"},
                 {"value": "60",  "label": "60s"},
                 {"value": "120", "label": "2 min"}],
     "required": False, "default": "30"},
    {"name": "stdin", "label": "Stdin (optional)", "type": "text",
     "placeholder": "Input for input() calls", "required": False},
]

log = logging.getLogger("tools.code_runner")
IS_WIN = platform.system() == "Windows"

# ── Language → executor config ────────────────────────────────────

def _python_cmd(path): return [sys.executable, path]
def _node_cmd(path):   return ["node", path]
def _bash_cmd(path):   return (["cmd", "/c", path] if IS_WIN else ["bash", path])
def _sql_cmd(path):    return [sys.executable, "-c", _sql_wrapper(path)]

def _sql_wrapper(query_file: str) -> str:
    return f"""
import sqlite3, sys
q = open({repr(query_file)}).read()
con = sqlite3.connect(':memory:')
try:
    for stmt in q.split(';'):
        stmt = stmt.strip()
        if not stmt: continue
        cur = con.execute(stmt)
        if cur.description:
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            print(' | '.join(cols))
            print('-' * 40)
            for r in rows: print(' | '.join(str(x) for x in r))
    con.commit()
except Exception as e:
    print('Error:', e, file=sys.stderr)
"""

_EXTS = {"python": ".py", "javascript": ".js", "bash": ".sh", "sql": ".sql"}
_CMDS = {"python": _python_cmd, "javascript": _node_cmd,
         "bash": _bash_cmd, "sql": _sql_cmd}


def run(code: str = "", language: str = "python",
        timeout: str = "30", stdin: str = "") -> dict:
    if not code.strip():
        return {"error": "No code provided."}

    lang = language.lower().strip()
    if lang not in _CMDS:
        return {"error": f"Unsupported language: {lang}. Choose: {list(_CMDS)}"}

    timeout_s = min(int(str(timeout).strip() or "30"), 120)
    ext = _EXTS[lang]

    # Write code to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=ext, delete=False,
                                     encoding="utf-8") as tf:
        tf.write(code)
        tmp_path = tf.name

    cmd = _CMDS[lang](tmp_path)
    t0 = time.perf_counter()

    try:
        proc = subprocess.run(
            cmd,
            input=stdin or None,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            encoding="utf-8",
            errors="replace",
        )
        elapsed = round(time.perf_counter() - t0, 3)
        stdout  = proc.stdout or ""
        stderr  = proc.stderr or ""
        rc      = proc.returncode

        return {
            "stdout":    stdout,
            "stderr":    stderr,
            "exit_code": rc,
            "elapsed":   elapsed,
            "language":  lang,
            "success":   rc == 0,
            "has_error": rc != 0 or bool(stderr.strip()),
        }

    except subprocess.TimeoutExpired:
        return {
            "stdout": "", "stderr": f"Timed out after {timeout_s}s",
            "exit_code": -1, "elapsed": timeout_s,
            "language": lang, "success": False, "has_error": True,
        }
    except FileNotFoundError:
        runtime = {"javascript": "Node.js", "bash": "Bash"}.get(lang, lang)
        return {"error": f"{runtime} not found. Is it installed and on PATH?"}
    except Exception as e:
        log.error("code_runner error: %s", e)
        return {"error": str(e)}
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
