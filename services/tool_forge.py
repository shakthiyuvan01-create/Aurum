"""
services/tool_forge.py -- self-generated tools (true self-extension).

Missing a capability? The programmer agent writes a plugin, it gets syntax-
checked and import-tested in a SUBPROCESS (never the live app), and only then
lands in plugins/ and registers into the tool registry.

Safeguards:
  - permission "self_extend" (OFF by default)
  - generated code is scanned for forbidden calls (network exec, os.system...)
  - tested in an isolated subprocess with a 10s timeout
  - capped at 15 forged tools
"""
import os
import re
import subprocess
import sys
import logging

log = logging.getLogger("services.tool_forge")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_DIR = os.path.join(BASE, "plugins")
MAX_FORGED = 15

_FORBIDDEN = re.compile(
    r"os\.system|subprocess|eval\(|exec\(|__import__|shutil\.rmtree|"
    r"os\.remove|os\.unlink|open\([^)]*[\'\"]w", re.I)


def forge(capability: str, username: str = "default") -> dict:
    from services.permission_manager import perms
    if not perms.check("self_extend"):
        return perms.deny_message("self_extend")
    if not capability.strip():
        return {"error": "describe the capability"}

    forged = [f for f in os.listdir(PLUGIN_DIR)
              if f.startswith("forged_") and f.endswith(".py")]
    if len(forged) >= MAX_FORGED:
        return {"error": "forge limit reached (%d tools)" % MAX_FORGED}

    from providers import AI
    code = AI.generate(
        "Write a complete AI Aurum plugin (single Python file) for this "
        "capability: %s\n\nRules:\n"
        "- Must define: NAME (snake_case str), DESCRIPTION (str), CATEGORY = "
        "'forged', ICON = 'sparkles', INPUTS (list of dicts with name/label/"
        "type), and run(**kwargs) -> dict returning {'result': ...} or "
        "{'error': ...}\n"
        "- Standard library only, plus 'requests' for public APIs\n"
        "- No file writes, no subprocess, no os.system, no eval/exec\n"
        "- Handle all exceptions inside run()\n"
        "Output ONLY the Python code, no fences." % capability,
        model="gpt-4o", max_tokens=1800, temperature=0.2)
    if code.startswith("[AI error"):
        return {"error": code}
    code = code.strip()
    if code.startswith("```"):
        code = code.split("\n", 1)[1].rsplit("```", 1)[0]

    if _FORBIDDEN.search(code):
        return {"error": "generated code used a forbidden operation - rejected",
                "detail": _FORBIDDEN.search(code).group(0)}

    m = re.search(r'NAME\s*=\s*["\']([a-z0-9_]+)["\']', code)
    if not m:
        return {"error": "generated code has no valid NAME"}
    name = m.group(1)
    path = os.path.join(PLUGIN_DIR, "forged_%s.py" % name)

    # test in an isolated subprocess: compile + import + shape check
    test_path = path + ".candidate"
    with open(test_path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        r = subprocess.run(
            [sys.executable, "-c",
             "import importlib.util,sys;"
             "spec=importlib.util.spec_from_file_location('cand', %r);"
             "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);"
             "assert isinstance(m.NAME,str) and callable(m.run) and m.DESCRIPTION;"
             "print('SHAPE_OK')" % test_path],
            capture_output=True, text=True, timeout=10)
        if "SHAPE_OK" not in r.stdout:
            os.unlink(test_path)
            return {"error": "candidate failed testing",
                    "detail": (r.stderr or r.stdout)[-300:]}
    except subprocess.TimeoutExpired:
        os.unlink(test_path)
        return {"error": "candidate import timed out (possible infinite loop)"}

    os.replace(test_path, path)
    try:
        import tools as _tools
        _tools.reload()
    except Exception as e:
        return {"ok": True, "tool": name, "file": path,
                "note": "registered on next restart (%s)" % e}
    log.info("forged new tool: %s", name)
    return {"ok": True, "tool": name, "file": path,
            "result": "New tool '%s' forged, tested and registered. "
                      "Run it from Tools & Plugins or /tools/run." % name}
