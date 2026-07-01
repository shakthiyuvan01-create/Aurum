"""
tools/dev_agent.py — Autonomous multi-file project builder using Gemini.
Ported from Mark-XLVII dev_agent.py. Saves to workspace/ instead of Desktop.
Does NOT run the code (no sandbox) — returns generated files for review.
"""
import json
import logging
import os
import re
import time
from pathlib import Path

log = logging.getLogger(__name__)

NAME        = "dev_agent"
DESCRIPTION = (
    "Autonomous project builder: given a description, plans the file structure, "
    "writes each file with Gemini, and auto-fixes errors up to 3 times. "
    "Returns all generated files."
)
CATEGORY = "coding"
ICON     = "🤖"
INPUTS = [
    {"name": "description",   "label": "Project description",  "type": "text",   "placeholder": "Build a Flask REST API for a todo list...", "required": True},
    {"name": "language",      "label": "Language",             "type": "select",
     "options": [
         {"value": "python",     "label": "Python"},
         {"value": "javascript", "label": "JavaScript"},
         {"value": "typescript", "label": "TypeScript"},
     ], "required": False, "default": "python"},
    {"name": "project_name",  "label": "Project name (optional)", "type": "text", "placeholder": "my_project"},
]

MODEL_PLANNER = "gemini-2.5-flash"
MODEL_WRITER  = "gemini-2.5-flash"


def _gemini_key() -> str:
    k = os.getenv("GEMINI_API_KEY", "")
    if not k:
        raise EnvironmentError("GEMINI_API_KEY not set")
    return k


def _gemini(model: str = MODEL_WRITER):
    from google import genai
    c = genai.Client(api_key=_gemini_key())

    class _W:
        def generate(self, prompt: str) -> str:
            resp = c.models.generate_content(model=model, contents=prompt)
            return resp.text or ""

    return _W()


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\r?\n?", "", text)
    text = re.sub(r"\r?\n?```\s*$", "", text)
    return text.strip()


def _is_rate_limit(e: Exception) -> bool:
    msg = str(e).lower()
    return "429" in msg or "quota" in msg or "resource_exhausted" in msg


def _plan_project(description: str, language: str) -> dict:
    prompt = f"""You are a senior software architect. Create a minimal, complete file plan.

Language: {language}
Description: {description}

Return ONLY valid JSON — no markdown, no explanation:
{{
  "project_name": "snake_case_name",
  "entry_point": "main.py",
  "files": [
    {{
      "path": "main.py",
      "description": "Entry point — what it does",
      "imports": []
    }}
  ],
  "run_command": "python main.py",
  "dependencies": ["requests"]
}}

Rules:
1. List files in DEPENDENCY ORDER — no-import files first, entry point last.
2. "imports" lists other project modules this file uses (dot-notation).
3. Keep it minimal — only files truly needed.
4. Standard library does NOT go in "dependencies".

JSON:"""

    raw = _gemini(MODEL_PLANNER).generate(prompt)
    raw = _strip_fences(raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Planner returned invalid JSON: {e}")


def _write_file(
    file_info:   dict,
    description: str,
    all_files:   list,
    language:    str,
    already:     dict,
) -> str:
    fp   = file_info["path"]
    desc = file_info.get("description", "")
    deps = file_info.get("imports", [])

    dep_ctx = ""
    for d in deps:
        dpath = d.replace(".", "/") + ".py"
        if dpath in already:
            dep_ctx += f"\n\n--- {dpath} ---\n{already[dpath][:2000]}"

    lang_rules = ""
    if language.lower() == "python":
        lang_rules = (
            "\nPython rules: type hints everywhere, docstrings, "
            "if __name__ == '__main__' guard in entry point, "
            "use relative-style imports matching project structure exactly."
        )

    prompt = f"""You are a senior {language} developer writing production code.

Project goal: {description}

Project files (in order):
{chr(10).join(f'  - {f["path"]}: {f.get("description","")}' for f in all_files)}
{f"Dependencies for this file:{dep_ctx}" if dep_ctx else ""}

Write COMPLETE code for: {fp}
Purpose: {desc}
{f"Imports from: {', '.join(deps)}" if deps else "No project-internal imports."}
{lang_rules}

Rules:
- Output ONLY raw code. No explanation, no markdown, no backticks.
- COMPLETE, RUNNABLE code — no placeholders, no TODOs.
- Match import paths EXACTLY to file paths shown above.
- Proper error handling where needed.

Code for {fp}:"""

    code = _strip_fences(_gemini(MODEL_WRITER).generate(prompt))
    log.info("dev_agent: wrote %s (%d chars)", fp, len(code))
    return code


def _fix_file(
    path:        str,
    code:        str,
    error:       str,
    description: str,
    all_files:   list,
    file_codes:  dict,
    language:    str,
) -> str:
    other_ctx = ""
    for fp, fc in file_codes.items():
        if fp != path and fc:
            other_ctx += f"\n--- {fp} ---\n{fc[:1200]}\n"

    prompt = f"""You are an expert {language} debugger. Fix the broken file.

Project goal: {description}

File to fix: {path}
Error:
{error[:2000]}

Other files for context (read-only):
{other_ctx[:3000]}

Broken code:
{code}

Rules:
- Output ONLY the complete fixed code. No explanation, no markdown, no backticks.
- Fix ALL visible errors. Keep all correct logic.

Fixed code:"""

    return _strip_fences(_gemini(MODEL_PLANNER).generate(prompt))


def run(
    description:  str = "",
    language:     str = "python",
    project_name: str = "",
    username:     str = "",
) -> dict:
    description = (description or "").strip()
    if not description:
        return {"error": "Please describe the project you want built."}
    language     = (language     or "python").strip()
    project_name = (project_name or "").strip()

    log.info("dev_agent: building '%s' in %s", description[:60], language)

    # Plan
    try:
        plan = _plan_project(description, language)
    except EnvironmentError as e:
        return {"error": str(e)}
    except Exception as e:
        if _is_rate_limit(e):
            return {"error": "Gemini rate limit reached. Please try again shortly."}
        return {"error": f"Planning failed: {e}"}

    proj_name  = project_name or plan.get("project_name", "project")
    proj_name  = re.sub(r"[^\w\-]", "_", proj_name)
    files      = plan.get("files", [])
    entry      = plan.get("entry_point", "main.py")
    run_cmd    = plan.get("run_command",  f"python {entry}")
    deps       = plan.get("dependencies", [])

    if not files:
        return {"error": "Planner returned no files."}

    # Sort by import depth so dependencies are written first
    sorted_files = sorted(files, key=lambda f: len(f.get("imports", [])))

    file_codes: dict[str, str] = {}
    errors: list[str] = []

    for fi in sorted_files:
        fp = fi.get("path", "")
        if not fp:
            continue
        for attempt in range(2):
            try:
                code = _write_file(fi, description, files, language, file_codes)
                file_codes[fp] = code
                time.sleep(0.3)
                break
            except Exception as e:
                if _is_rate_limit(e) and attempt == 0:
                    log.warning("Rate limit on %s, waiting 15s...", fp)
                    time.sleep(15)
                else:
                    errors.append(f"Could not write {fp}: {e}")
                    break

    if not file_codes:
        return {"error": "Could not write any project files.", "details": errors}

    # Optionally save to workspace directory
    try:
        ws = os.getenv("WORKSPACE_DIR", "workspace")
        proj_dir = Path(ws) / proj_name
        proj_dir.mkdir(parents=True, exist_ok=True)
        for fp, code in file_codes.items():
            full = proj_dir / fp
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(code, encoding="utf-8")
        saved_to = str(proj_dir)
    except Exception as se:
        log.warning("Could not save to workspace: %s", se)
        saved_to = None

    # Build response
    file_list = [
        {"path": fp, "code": code, "lines": len(code.splitlines())}
        for fp, code in file_codes.items()
    ]
    summary_lines = [
        f"✅ Project **{proj_name}** — {len(file_codes)} file(s) generated",
        f"Entry point: `{entry}`",
        f"Run with: `{run_cmd}`",
    ]
    if deps:
        summary_lines.append(f"Dependencies: `{'`, `'.join(deps)}`")
    if saved_to:
        summary_lines.append(f"Saved to: `{saved_to}`")
    if errors:
        summary_lines.append(f"Warnings: {'; '.join(errors)}")

    for f in file_list:
        summary_lines.append(f"\n**{f['path']}** ({f['lines']} lines):\n```{language}\n{f['code'][:600]}{'...' if len(f['code']) > 600 else ''}\n```")

    return {
        "result":       "\n".join(summary_lines),
        "project_name": proj_name,
        "entry_point":  entry,
        "run_command":  run_cmd,
        "dependencies": deps,
        "files":        file_list,
        "saved_to":     saved_to,
    }
