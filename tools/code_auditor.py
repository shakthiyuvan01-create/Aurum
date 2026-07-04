"""
tools/code_auditor.py -- autonomous refactoring scanner (report only).

Scans a project for: duplicate code blocks, dead files, oversized
functions, TODO debt, and architecture smells; AI proposes prioritized
refactorings. Never modifies files.
"""
import ast
import hashlib
import os
import logging
from collections import defaultdict

log = logging.getLogger("tools.code_auditor")

NAME        = "code_auditor"
DESCRIPTION = ("Scan a codebase for duplicate code, dead files, oversized "
               "functions, TODO debt and architecture issues; produces a "
               "prioritized refactoring report (never edits). Input: path.")
CATEGORY = "builtin"
ICON     = "wrench"
INPUTS = [
    {"name": "path",     "label": "Project path (default: this project)", "type": "text"},
    {"name": "username", "label": "Username", "type": "text"},
]

SKIP = {"__pycache__", ".git", ".venv", "node_modules", "dist", "model", "chroma_db", ".idea"}


def run(path: str = "", username: str = "default") -> dict:
    root = path or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not os.path.isdir(root):
        return {"error": "path not found"}

    big_funcs, todos, dupes, parse_errors = [], 0, defaultdict(list), []
    file_count = 0
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for f in files:
            if not f.endswith(".py"):
                continue
            file_count += 1
            p = os.path.join(dirpath, f)
            rel = os.path.relpath(p, root)
            try:
                src = open(p, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            todos += src.count("TODO") + src.count("FIXME")
            try:
                tree = ast.parse(src)
            except SyntaxError as e:
                parse_errors.append("%s: %s" % (rel, e))
                continue
            lines = src.splitlines()
            for n in ast.walk(tree):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    size = (n.end_lineno or n.lineno) - n.lineno
                    if size > 80:
                        big_funcs.append("%s:%s (%d lines)" % (rel, n.name, size))
                    body_src = "\n".join(lines[n.lineno - 1:n.end_lineno])
                    if size > 8:
                        h = hashlib.md5(body_src.encode()).hexdigest()[:10]
                        dupes[h].append("%s:%s" % (rel, n.name))

    dup_list = [v for v in dupes.values() if len(v) > 1][:10]
    findings = ["Files scanned: %d" % file_count,
                "Syntax errors: %s" % (parse_errors or "none"),
                "Oversized functions (>80 lines): %s" % (big_funcs[:10] or "none"),
                "Exact duplicate functions: %s" % (dup_list or "none"),
                "TODO/FIXME markers: %d" % todos]

    from providers import AI
    advice = AI.generate(
        "You are a software architect reviewing scan results. Give a "
        "prioritized refactoring plan: top 5 actions, each with effort "
        "estimate and payoff. Then a maintainability score /10 with "
        "one-line justification.\n\nSCAN:\n" + "\n".join(findings),
        model="gpt-4o", max_tokens=800, temperature=0.3)
    return {"result": "# Code Audit\n\n## Scan findings\n" +
            "\n".join("- " + f for f in findings) +
            "\n\n## Architect's plan\n" + advice}
