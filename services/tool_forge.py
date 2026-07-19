"""
services/tool_forge.py -- Multi-phase tool forge (Ada-SI pattern).

Pipeline: plan -> codegen -> verify -> fix (loop) -> install
Supports HEADLESS and INTERACTIVE tools.
"""
from __future__ import annotations
import json, logging, os, re, sys, subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from services.forge_routing import infer_codegen_profile
from services.tool_verify import verify_tool

log = logging.getLogger("services.tool_forge")
BASE = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN_DIR = BASE / "plugins"
PLUGIN_DIR.mkdir(exist_ok=True)
MAX_FORGED = 30
FORBIDDEN = re.compile(r"os\.system|os\.remove|os\.unlink|shutil\.rmtree|eval\(|exec\(|__import__\(", re.I)

PLAN_PROMPT = "You are an expert Python tool architect. Produce a plan in markdown with sections:\n## Skill Kind and UI (headless vs interactive)\n## Architecture Changes\n## Function Schema\n## Execution Steps\n## Risks and Limitations\nDo not write code."
CODEGEN_PROMPT = "You are an expert Python developer building tools.\nEach tool module MUST define:\n1. NAME (snake_case str)\n2. DESCRIPTION (str)\n3. CATEGORY (str) = \"forged\"\n4. ICON (str) - emoji\n5. INPUTS (list of dicts with name/label/type)\n6. run(**kwargs) -> dict\n\nRules:\n- Standard library + requests. Other packages in requirements list.\n- Lazy imports inside run() only.\n- Handle all exceptions, return {\"error\": str(e)}.\nOutput ONLY valid JSON: {\"tool_name\",\"description\",\"requirements\":[],\"tool_code\":\"\",\"test_code\":\"\"}"
FIX_PROMPT = "The tool failed verification. Fix and return corrected JSON.\nError: {error}\nPrevious code: ```python\n{previous_code}```\nOutput ONLY valid JSON with keys: tool_name, description, requirements, tool_code, test_code"

def _call_ai(prompt, system="", max_t=2000, temp=0.2):
    try:
        from providers import AI
        r = AI.generate(prompt, system=system, model="gpt-4o", max_tokens=max_t, temperature=temp)
        return r or ""
    except Exception as e:
        log.error("AI call: %s", e)
        return ""

def _parse_json(text):
    if not text: return None
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try: return json.loads(m.group(0))
        except: pass
    try: return json.loads(text)
    except: return None

def _save_tool(name, code):
    p = PLUGIN_DIR / f"forged_{name}.py"
    p.write_text(code, encoding="utf-8")
    return p

def _register(name):
    try:
        import tools as _tools; _tools.reload()
        return {"ok": True, "registered": True}
    except Exception as e:
        return {"ok": True, "registered": False, "note": str(e)}

def forge(capability, username="default"):
    from services.permission_manager import perms
    if not perms.check("self_extend"):
        return {"error": "self_extend disabled"}
    forged = [f for f in os.listdir(str(PLUGIN_DIR)) if f.startswith("forged_") and f.endswith(".py")]
    if len(forged) >= MAX_FORGED:
        return {"error": f"limit {MAX_FORGED}"}
    plan = _call_ai(PLAN_PROMPT + f"\n\nCapability: {capability}", max_t=1200, temp=0.3)
    if not plan: return {"error": "plan failed"}
    profile = infer_codegen_profile(plan)
    log.info("forge profile: %s", profile)
    raw = _call_ai(CODEGEN_PROMPT + f"\n\nPlan:\n{plan}\nCapability: {capability}", max_t=3000)
    parsed = _parse_json(raw)
    if not parsed: return {"error": "parse failed", "raw": raw[:500]}
    tool_name = parsed.get("tool_name", "")
    tool_code = parsed.get("tool_code", "")
    test_code = parsed.get("test_code", "")
    requirements = parsed.get("requirements", [])
    description = parsed.get("description", capability)
    if not tool_name or not tool_code: return {"error": "missing tool_name or tool_code"}
    if FORBIDDEN.search(tool_code): return {"error": "forbidden pattern in code"}
    installed = []
    for attempt in range(4):
        vr = verify_tool(tool_name, tool_code, requirements, test_code)
        if vr.get("ok"): break
        missing = vr.get("missing_module")
        if missing and missing not in installed:
            try:
                r = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", missing], capture_output=True, text=True, timeout=300)
                if r.returncode == 0: installed.append(missing); requirements.append(missing); continue
            except: pass
        if attempt >= 3: return {"error": "verify failed x4", "phase": vr.get("phase"), "detail": vr.get("error", "")[:500]}
        fx = _call_ai(FIX_PROMPT.format(error=vr.get("error", ""), previous_code=tool_code), max_t=3000)
        fixed = _parse_json(fx)
        if fixed:
            tool_code = fixed.get("tool_code", tool_code)
            test_code = fixed.get("test_code", test_code)
            requirements = fixed.get("requirements", requirements)
        if FORBIDDEN.search(tool_code): return {"error": "forbidden in fixed code"}
    path = _save_tool(tool_name, tool_code)
    reg = _register(tool_name)
    try:
        from services.persona import append_daily_log
        append_daily_log(f"Forged: {tool_name} ({description[:60]})")
    except: pass
    return {"ok": True, "tool": tool_name, "description": description, "file": str(path), "requirements": requirements, "installed_pkgs": installed, "profile": profile, "registered": reg.get("registered", False)}

def list_forged_tools():
    tools = []
    for f in sorted(PLUGIN_DIR.glob("forged_*.py")):
        name = f.stem.replace("forged_", "")
        mp = PLUGIN_DIR / f"{name}.manifest.json"
        manifest = None
        if mp.is_file():
            try: manifest = json.loads(mp.read_text(encoding="utf-8"))
            except: pass
        tools.append({"name": name, "filename": f.name, "path": str(f), "manifest": manifest, "kind": manifest.get("kind", "headless") if manifest else "headless"})
    return tools

def delete_tool(name):
    deleted = []
    for p in [PLUGIN_DIR / f"forged_{name}.py", PLUGIN_DIR / f"{name}.manifest.json"]:
        if p.is_file(): p.unlink(); deleted.append(str(p))
    ui_dir = PLUGIN_DIR / "ui" / name
    if ui_dir.is_dir():
        import shutil; shutil.rmtree(ui_dir, ignore_errors=True); deleted.append(str(ui_dir))
    if not deleted: return {"error": f"not found: {name}"}
    try: import tools as _tools; _tools.reload()
    except: pass
    return {"ok": True, "deleted": deleted, "tool": name}
