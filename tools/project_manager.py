"""
tools/project_manager.py -- autonomous project manager.

"Build me a CRM" ->
  1. AI writes a roadmap with milestones
  2. dev_agent generates the full project into workspace/
  3. every Python file is syntax-tested; failures go to the debugger agent
     for fixes (up to 2 rounds)
  4. optional git commit of the workspace
Returns the roadmap, build summary, test results, and fix log.

Heavy: run via /tools/run_async.
"""
import os
import py_compile
import logging

log = logging.getLogger("tools.project_manager")

NAME        = "project_manager"
DESCRIPTION = (
    "Autonomous software project manager: roadmap -> milestones -> generate "
    "code -> test -> fix bugs -> optional git commit. "
    "Inputs: description, language, commit (true/false)."
)
CATEGORY = "builtin"
ICON     = "briefcase"
INPUTS = [
    {"name": "description", "label": "What to build", "type": "textarea", "required": True},
    {"name": "language",    "label": "Language", "type": "text"},
    {"name": "commit",      "label": "Git commit when done (true/false)", "type": "text"},
    {"name": "username",    "label": "Username", "type": "text"},
]


def _test_python_files(root: str) -> list:
    failures = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "node_modules")]
        for f in files:
            if f.endswith(".py"):
                p = os.path.join(dirpath, f)
                try:
                    py_compile.compile(p, doraise=True)
                except Exception as e:
                    failures.append({"file": p, "error": str(e)[:400]})
    return failures


def run(description: str = "", language: str = "python", commit: str = "false",
        username: str = "default") -> dict:
    if not description.strip():
        return {"error": "description required"}
    from providers import AI
    import tools as _tools

    report = {"milestones": [], "fix_log": []}

    # 1. Roadmap
    roadmap = AI.generate(
        "Create a concise project roadmap for: %s\n"
        "Sections: Overview, Milestones (numbered, each with deliverable), "
        "Tech stack, Risks." % description,
        model="gpt-4o", max_tokens=800, temperature=0.3)
    report["roadmap"] = roadmap
    report["milestones"].append("Roadmap created")

    # 2. Generate the project
    build = _tools.call("dev_agent", description=description,
                        language=language or "python", username=username)
    if build.get("error"):
        return {"error": "build failed: %s" % build["error"], "roadmap": roadmap}
    report["build_summary"] = (build.get("result") or "")[:1500]
    saved_to = build.get("saved_to") or ""
    report["milestones"].append("Code generated")

    # 3. Test + fix loop (Python projects)
    ws = saved_to if saved_to and os.path.isdir(saved_to) else \
        os.path.normpath(os.getenv("WORKSPACE_DIR", os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "workspace")))
    for round_no in (1, 2):
        failures = _test_python_files(ws)
        if not failures:
            report["milestones"].append("All tests pass (round %d)" % round_no)
            break
        report["milestones"].append("%d file(s) failing (round %d)" % (len(failures), round_no))
        for f in failures[:5]:
            try:
                code = open(f["file"], encoding="utf-8", errors="ignore").read()
                fixed = AI.generate(
                    "Fix this %s file so it compiles. Return ONLY the complete "
                    "corrected file, no fences.\n\nERROR: %s\n\nFILE:\n%s"
                    % (language, f["error"], code[:12000]),
                    model="gpt-4o", max_tokens=3000, temperature=0.1)
                if fixed and not fixed.startswith("[AI error"):
                    fixed = fixed.strip()
                    if fixed.startswith("```"):
                        fixed = fixed.split("\n", 1)[1].rsplit("```", 1)[0]
                    with open(f["file"], "w", encoding="utf-8") as fh:
                        fh.write(fixed)
                    report["fix_log"].append("fixed " + os.path.basename(f["file"]))
            except Exception as e:
                report["fix_log"].append("could not fix %s: %s"
                                         % (os.path.basename(f["file"]), e))

    # 4. Optional git commit
    if str(commit).lower() in ("true", "1", "yes"):
        g = _tools.call("git_tool", action="commit",
                        message="project_manager: " + description[:60],
                        username=username)
        report["milestones"].append("Git: " + str(g.get("message", g))[:150])

    summary = ("# Project built\n\n## Roadmap\n%s\n\n## Build\n%s\n\n"
               "## Milestones\n%s\n\n## Fixes\n%s" % (
                   roadmap, report["build_summary"],
                   "\n".join("- " + m for m in report["milestones"]),
                   "\n".join("- " + f for f in report["fix_log"]) or "- none needed"))
    report["result"] = summary
    return report
