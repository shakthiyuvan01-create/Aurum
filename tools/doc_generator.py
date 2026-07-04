"""
tools/doc_generator.py -- self-generated documentation.

Scans a project and writes README_AI.md + ARCHITECTURE_AI.md: overview,
module map, API routes, dependency list, mermaid flowchart.
"""
import os
import re
import logging

log = logging.getLogger("tools.doc_generator")

NAME        = "doc_generator"
DESCRIPTION = ("Generate documentation from code: README_AI.md and "
               "ARCHITECTURE_AI.md with module map, routes, dependencies "
               "and a mermaid diagram. Input: path (default: this project).")
CATEGORY = "builtin"
ICON     = "file"
INPUTS = [
    {"name": "path",     "label": "Project path", "type": "text"},
    {"name": "username", "label": "Username", "type": "text"},
]

SKIP = {"__pycache__", ".git", ".venv", "node_modules", "dist", "model", "chroma_db", ".idea"}


def run(path: str = "", username: str = "default") -> dict:
    root = path or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not os.path.isdir(root):
        return {"error": "path not found"}

    modules, routes, deps = [], [], set()
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for f in sorted(files):
            if not f.endswith(".py"):
                continue
            p = os.path.join(dirpath, f)
            rel = os.path.relpath(p, root)
            try:
                src = open(p, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            doc = ""
            m = re.match(r'\s*(?:\'\'\'|""")(.{10,200}?)(?:\'\'\'|"""|\n\n)', src, re.S)
            if m:
                doc = " ".join(m.group(1).split())[:120]
            modules.append("%s -- %s" % (rel, doc or "(no docstring)"))
            routes += re.findall(r'\.route\("(/[^"]+)"(?:.*?methods=\[([^\]]*)\])?', src)
            for im in re.findall(r"^(?:import|from)\s+([a-zA-Z0-9_]+)", src, re.M):
                deps.add(im)

    std = {"os", "re", "sys", "json", "time", "logging", "sqlite3", "typing",
           "collections", "pathlib", "subprocess", "threading", "uuid", "ast",
           "hashlib", "shutil", "tempfile", "datetime", "importlib", "abc",
           "functools", "math", "random", "base64", "io", "glob", "wave"}
    ext_deps = sorted(d for d in deps if d not in std and not
                      os.path.exists(os.path.join(root, d)) and not
                      os.path.exists(os.path.join(root, d + ".py")))

    from providers import AI
    summary_input = "\n".join(modules[:120])
    readme = AI.generate(
        "Write a README.md for this project based on its module map. Sections: "
        "title + one-paragraph description, Features (from the modules), "
        "Quick start, Project structure (condensed tree). Markdown.\n\nMODULES:\n"
        + summary_input, model="gpt-4o", max_tokens=1500, temperature=0.3)
    arch = AI.generate(
        "Write ARCHITECTURE.md: high-level architecture description, then a "
        "mermaid flowchart (graph TD) of the main components and data flow, "
        "then a table of API routes.\n\nMODULES:\n%s\n\nROUTES:\n%s"
        % (summary_input, ", ".join(r[0] for r in routes[:80])),
        model="gpt-4o", max_tokens=1500, temperature=0.3)

    out1 = os.path.join(root, "README_AI.md")
    out2 = os.path.join(root, "ARCHITECTURE_AI.md")
    open(out1, "w", encoding="utf-8").write(readme)
    open(out2, "w", encoding="utf-8").write(
        arch + "\n\n## External dependencies\n" +
        "\n".join("- " + d for d in ext_deps))
    return {"result": "Documentation generated:\n- README_AI.md\n- ARCHITECTURE_AI.md\n\n"
                      "%d modules, %d routes, %d external deps documented."
                      % (len(modules), len(routes), len(ext_deps)),
            "files": [out1, out2]}
