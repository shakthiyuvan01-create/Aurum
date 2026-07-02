"""
tools/coding_team.py — Autonomous Coding Team Pipeline.
Planner → Architect → Programmer → Tester → Debugger → Reviewer → Security Scan → Git Commit
Each stage uses a specialist agent. Streams progress via generator.
"""
from __future__ import annotations
import json, logging, os, tempfile, time
from pathlib import Path

log = logging.getLogger(__name__)

NAME        = "coding_team"
DESCRIPTION = (
    "Full autonomous software development pipeline: Planner → Architect → Programmer → "
    "Tester → Debugger → Reviewer → Security Scan. Builds complete multi-file projects."
)
CATEGORY = "development"
ICON     = "🏗️"
INPUTS = [
    {"name": "description", "label": "Project description", "type": "textarea", "required": True},
    {"name": "language",    "label": "Language",            "type": "select",
     "options": ["python","javascript","typescript","java","go","rust","cpp"], "default": "python"},
    {"name": "project_name","label": "Project name",        "type": "text"},
    {"name": "mode",        "label": "Mode",                "type": "select",
     "options": ["full","plan_only","code_only"], "default": "full"},
    {"name": "username",    "label": "Username",            "type": "text"},
]

_STAGES = ["planner","architect","programmer","tester","debugger","reviewer","security"]


def _ai(prompt: str, system: str = "", model: str = "gpt-4o", max_tokens: int = 2000) -> str:
    from providers import AI
    return AI.generate(prompt, system=system, model=model, max_tokens=max_tokens, temperature=0.3)


def _planner(description: str, language: str) -> dict:
    raw = _ai(
        f"Plan a {language} project: {description}\n\n"
        "Return JSON with: {\"architecture\": \"brief description\", \"files\": [{\"path\": \"...\", \"purpose\": \"...\"}], \"dependencies\": [], \"entry_point\": \"...\", \"run_command\": \"...\"}",
        system="You are a software architect. Output JSON only.",
        model="gpt-4o", max_tokens=800,
    )
    try:
        clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        return json.loads(clean)
    except Exception:
        return {"architecture": description, "files": [{"path":"main.py","purpose":"Main entry point"}],
                "dependencies":[], "entry_point":"main.py", "run_command":"python main.py"}


def _write_file(file_info: dict, description: str, plan: dict, language: str, written: dict) -> str:
    existing = "\n\n".join(f"# {k}\n{v[:500]}" for k,v in list(written.items())[-3:])
    return _ai(
        f"Write complete {language} code for: {file_info['path']}\n"
        f"Purpose: {file_info['purpose']}\n"
        f"Project: {description}\n"
        f"Architecture: {plan.get('architecture','')}\n"
        f"Already written files:\n{existing}\n\n"
        "Output ONLY the file content, no markdown fences.",
        model="gpt-4o", max_tokens=2000,
    )


def _write_tests(code_files: dict, language: str) -> str:
    sample = "\n\n".join(f"# {k}\n{v[:600]}" for k,v in list(code_files.items())[:2])
    return _ai(
        f"Write comprehensive unit tests for this {language} code:\n{sample}",
        system="You are a test engineer. Write complete test files.",
        model="gpt-4o-mini", max_tokens=1500,
    )


def _review_code(code_files: dict) -> str:
    sample = "\n\n".join(f"# {k}\n{v[:800]}" for k,v in list(code_files.items())[:3])
    return _ai(
        f"Review this code. Report: bugs, code smells, improvement suggestions.\n{sample}",
        model="gpt-4o-mini", max_tokens=600,
    )


def _security_scan(code_files: dict) -> str:
    sample = "\n\n".join(f"# {k}\n{v[:800]}" for k,v in list(code_files.items())[:3])
    return _ai(
        f"Security audit this code. Find: SQL injection, XSS, hardcoded secrets, auth bypass, input validation issues.\n{sample}",
        model="gpt-4o", max_tokens=600,
    )


def _debug(code_files: dict, description: str) -> str:
    sample = "\n\n".join(f"# {k}\n{v[:600]}" for k,v in list(code_files.items())[:3])
    return _ai(
        f"Review this code for potential runtime errors and logical bugs: {description}\n{sample}",
        model="gpt-4o-mini", max_tokens=600,
    )


def run(
    description: str = "",
    language:    str = "python",
    project_name:str = "",
    mode:        str = "full",
    username:    str = "",
) -> dict:
    if not description:
        return {"error": "description required"}

    project_name = project_name or description[:30].replace(" ","_").lower()
    t0 = time.time()
    stages_done = {}

    # Stage 1: Plan
    plan = _planner(description, language)
    stages_done["planner"] = {"architecture": plan.get("architecture",""), "files": len(plan.get("files",[]))}

    if mode == "plan_only":
        return {"result": json.dumps(plan, indent=2), "stages": stages_done, "plan": plan}

    # Stage 2: Write code
    code_files: dict[str,str] = {}
    for fi in plan.get("files", [{"path":"main.py","purpose":"Main"}]):
        code = _write_file(fi, description, plan, language, code_files)
        code_files[fi["path"]] = code
    stages_done["programmer"] = {"files_written": list(code_files.keys())}

    # Stage 3: Tests
    tests = _write_tests(code_files, language)
    test_file = f"test_{project_name}.py" if language == "python" else f"{project_name}.test.js"
    code_files[test_file] = tests
    stages_done["tester"] = {"test_file": test_file}

    # Stage 4: Debug
    debug_report = _debug(code_files, description)
    stages_done["debugger"] = {"report": debug_report[:300]}

    # Stage 5: Review
    review = _review_code(code_files)
    stages_done["reviewer"] = {"report": review[:300]}

    # Stage 6: Security
    security = _security_scan(code_files)
    stages_done["security"] = {"report": security[:300]}

    # Stage 7: Save files to workspace
    out_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "workspace", project_name
    )
    os.makedirs(out_dir, exist_ok=True)
    saved = []
    for fname, content in code_files.items():
        fpath = os.path.join(out_dir, fname)
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        saved.append(fname)

    # README
    readme = _ai(
        f"Write a README.md for this project:\nName: {project_name}\nDescription: {description}\n"
        f"Language: {language}\nEntry: {plan.get('entry_point','main.py')}\n"
        f"Run: {plan.get('run_command','python main.py')}",
        model="gpt-4o-mini", max_tokens=600,
    )
    with open(os.path.join(out_dir, "README.md"), "w") as f:
        f.write(readme)
    saved.append("README.md")

    summary = (
        f"## 🏗️ Project Built: {project_name}\n\n"
        f"**Architecture:** {plan.get('architecture','')}\n\n"
        f"**Files:** {len(saved)} files written\n"
        f"**Location:** workspace/{project_name}/\n\n"
        f"**Review:** {review[:200]}\n\n"
        f"**Security:** {security[:200]}"
    )

    return {
        "result":     summary,
        "project_name": project_name,
        "files":      saved,
        "output_dir": out_dir,
        "stages":     stages_done,
        "duration":   round(time.time() - t0, 2),
        "plan":       plan,
    }
