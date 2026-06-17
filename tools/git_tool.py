"""
git_tool.py — Git integration for Assist Neo
Runs git commands in a configurable workspace directory.
"""
import os, subprocess, logging, platform

NAME        = "git"
DESCRIPTION = "Git operations: status, log, diff, commit, push, pull, branch"
CATEGORY    = "builtin"
ICON        = "🌿"
INPUTS = [
    {"name": "action", "label": "Action", "type": "select",
     "options": [{"value": "status",  "label": "Status"},
                 {"value": "log",     "label": "Commit Log"},
                 {"value": "diff",    "label": "Diff (unstaged)"},
                 {"value": "add",     "label": "Stage All (git add .)"},
                 {"value": "commit",  "label": "Commit"},
                 {"value": "push",    "label": "Push"},
                 {"value": "pull",    "label": "Pull"},
                 {"value": "branch",  "label": "List Branches"},
                 {"value": "custom",  "label": "Custom command"}],
     "required": True, "default": "status"},
    {"name": "message",    "label": "Commit message (for commit)", "type": "text",
     "placeholder": "feat: add new feature", "required": False},
    {"name": "custom_cmd", "label": "Custom git command",          "type": "text",
     "placeholder": "e.g. stash, reset --hard, checkout main",     "required": False},
    {"name": "repo_path",  "label": "Repo path (leave blank for auto)", "type": "text",
     "required": False},
]

log = logging.getLogger("tools.git")
IS_WIN = platform.system() == "Windows"

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_REPO = os.getenv("GIT_REPO_PATH", BASE)

# Commands that could be destructive — require explicit intent
_DANGEROUS = {"push --force", "reset --hard", "clean -fd", "rm -rf"}


def _git(args: list, cwd: str, timeout: int = 30) -> dict:
    cmd = ["git"] + args
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, capture_output=True,
            text=True, timeout=timeout, encoding="utf-8", errors="replace",
        )
        out = proc.stdout.strip()
        err = proc.stderr.strip()
        return {
            "output":    out or err or "(no output)",
            "stderr":    err,
            "exit_code": proc.returncode,
            "success":   proc.returncode == 0,
            "command":   "git " + " ".join(args),
        }
    except FileNotFoundError:
        return {"error": "git not found. Is Git installed and on PATH?"}
    except subprocess.TimeoutExpired:
        return {"error": f"git command timed out after {timeout}s"}
    except Exception as e:
        log.error("git error: %s", e)
        return {"error": str(e)}


def _resolve_repo(repo_path: str) -> str:
    path = (repo_path or "").strip() or DEFAULT_REPO
    if not os.path.isabs(path):
        path = os.path.join(BASE, path)
    return os.path.normpath(path)


def run(action: str = "status", message: str = "",
        custom_cmd: str = "", repo_path: str = "") -> dict:
    cwd = _resolve_repo(repo_path)
    if not os.path.isdir(cwd):
        return {"error": f"Directory not found: {cwd}"}

    if action == "status":
        r = _git(["status", "-sb"], cwd)
        if r.get("success"):
            # Also get short stats
            r2 = _git(["diff", "--stat"], cwd)
            if r2.get("success") and r2["output"] != "(no output)":
                r["output"] += "\n\n" + r2["output"]
        return r

    elif action == "log":
        return _git(
            ["log", "--oneline", "--graph", "--decorate", "-20"],
            cwd
        )

    elif action == "diff":
        return _git(["diff", "--color=never"], cwd)

    elif action == "add":
        return _git(["add", "."], cwd)

    elif action == "commit":
        msg = message.strip()
        if not msg:
            return {"error": "Commit message is required."}
        # Stage all first, then commit
        add_r = _git(["add", "."], cwd)
        if not add_r.get("success"):
            return add_r
        return _git(["commit", "-m", msg], cwd)

    elif action == "push":
        return _git(["push"], cwd, timeout=60)

    elif action == "pull":
        return _git(["pull"], cwd, timeout=60)

    elif action == "branch":
        return _git(["branch", "-a"], cwd)

    elif action == "custom":
        raw = (custom_cmd or "").strip()
        if not raw:
            return {"error": "Enter a git subcommand (e.g. stash, log -5, checkout -b new-branch)"}
        # Strip leading "git " if user typed it
        if raw.lower().startswith("git "):
            raw = raw[4:].strip()
        # Warn on dangerous commands
        for danger in _DANGEROUS:
            if raw.startswith(danger):
                return {"error": f"Blocked: '{raw}' is potentially destructive. Run it manually in your terminal."}
        args = raw.split()
        return _git(args, cwd, timeout=60)

    else:
        return {"error": f"Unknown action: {action}"}
