"""
tools/__init__.py — Plugin/Tool registry for Assist Neo
=========================================================
Each tool is a .py file in this directory that exports:
    NAME        str   — unique tool id (e.g. "weather")
    DESCRIPTION str   — one-line description shown in the UI
    CATEGORY    str   — "builtin" | "custom"
    INPUTS      list  — [{"name","label","type","placeholder","required"},...]
    run(**kwargs) -> dict  — executes the tool, returns {"result":..., ...}

Drop a new .py file here to add a plugin automatically.
"""

import os, importlib, logging, traceback, time as _time

log = logging.getLogger("tools")

# ── Metrics (optional — graceful-degrade if DB unavailable) ──────────────────
try:
    from tools.tool_metrics import record_call as _record_call, should_warn as _should_warn
    _METRICS_OK = True
except Exception as _me:
    log.debug("tool_metrics unavailable: %s", _me)
    _METRICS_OK = False
    def _record_call(name, success, runtime_ms): pass   # noqa: E731
    def _should_warn(name): return False                 # noqa: E731
_TOOLS: dict = {}

def _load_all():
    """Auto-discover every tool module in this directory."""
    _TOOLS.clear()
    here = os.path.dirname(os.path.abspath(__file__))
    for fname in sorted(os.listdir(here)):
        if fname.startswith("_") or not fname.endswith(".py"):
            continue
        mod_name = fname[:-3]
        try:
            mod = importlib.import_module(f"tools.{mod_name}")
            name = getattr(mod, "NAME", mod_name)
            _TOOLS[name] = {
                "name":        name,
                "description": getattr(mod, "DESCRIPTION", ""),
                "category":    getattr(mod, "CATEGORY", "builtin"),
                "icon":        getattr(mod, "ICON", "🔧"),
                "inputs":      getattr(mod, "INPUTS", []),
                "run":         getattr(mod, "run", None),
                "module":      mod_name,
            }
            log.debug("Tool loaded: %s (%s)", name, mod_name)
        except Exception:
            log.warning("Failed to load tool %s:\n%s", mod_name, traceback.format_exc())
    log.info("Tools loaded: %d", len(_TOOLS))

def reload():
    _load_all()

def list_tools() -> list:
    return [
        {k: v for k, v in t.items() if k != "run"}
        for t in _TOOLS.values()
    ]

def get_tool(name: str) -> dict | None:
    return _TOOLS.get(name)

def call(name: str, **kwargs) -> dict:
    tool = _TOOLS.get(name)
    if not tool:
        return {"error": f"Tool '{name}' not found."}
    fn = tool.get("run")
    if not fn:
        return {"error": f"Tool '{name}' has no run() function."}
    # ── warn if this tool has been failing recently ───────────────────────────
    if _should_warn(name):
        log.warning("Tool '%s' has ≥3 failures in the last hour — proceeding anyway", name)
    log.info("tool call: %s kwargs=%s", name, list(kwargs.keys()))
    t0 = _time.monotonic()
    try:
        result = fn(**kwargs)
        runtime_ms = (_time.monotonic() - t0) * 1000
        if not isinstance(result, dict):
            result = {"result": result}
        _record_call(name, success=True, runtime_ms=runtime_ms)
        log.debug("tool %s ok in %.0fms, result keys: %s", name, runtime_ms, list(result.keys()))
        return result
    except TypeError as e:
        runtime_ms = (_time.monotonic() - t0) * 1000
        _record_call(name, success=False, runtime_ms=runtime_ms)
        return {"error": f"Bad arguments: {e}"}
    except Exception as e:
        runtime_ms = (_time.monotonic() - t0) * 1000
        _record_call(name, success=False, runtime_ms=runtime_ms)
        log.error("Tool %s failed in %.0fms: %s", name, runtime_ms, e)
        return {"error": str(e)}


# ── OpenAI Function-Calling schema ───────────────────────────────

_TYPE_MAP = {
    "text": "string", "textarea": "string", "number": "number",
    "select": "string", "datetime-local": "string",
    "hidden": "string", "email": "string",
}

def _input_to_property(inp: dict) -> dict:
    prop: dict = {"type": _TYPE_MAP.get(inp.get("type", "text"), "string")}
    if inp.get("placeholder"):
        prop["description"] = inp["placeholder"]
    elif inp.get("label"):
        prop["description"] = inp["label"]
    if inp.get("options"):
        prop["enum"] = [o["value"] for o in inp["options"] if "value" in o]
    return prop


def to_openai_tools(exclude: set | None = None) -> list:
    """Return tools formatted as OpenAI function-calling schemas.

    exclude: set of tool names to omit (e.g. {"code_runner"} for chat context).
    Hidden inputs (username, etc.) are excluded from the schema automatically.
    """
    exclude = exclude or set()
    schemas = []
    for t in _TOOLS.values():
        if t["name"] in exclude:
            continue
        props, required = {}, []
        for inp in t.get("inputs", []):
            if inp.get("type") == "hidden":
                continue
            pname = inp["name"]
            props[pname] = _input_to_property(inp)
            if inp.get("required"):
                required.append(pname)
        schemas.append({
            "type": "function",
            "function": {
                "name":        t["name"],
                "description": t["description"],
                "parameters": {
                    "type":       "object",
                    "properties": props,
                    **({"required": required} if required else {}),
                },
            },
        })
    return schemas


def call_from_openai(tool_call, username: str = "default") -> str:
    """Execute a single OpenAI tool_call object (dict or obj with .function).

    Returns a plain-text result string to feed back as a tool message.
    """
    import json as _j
    if isinstance(tool_call, dict):
        name = tool_call.get("function", {}).get("name", "")
        raw  = tool_call.get("function", {}).get("arguments", "{}")
    else:
        name = tool_call.function.name
        raw  = tool_call.function.arguments
    try:
        kwargs = _j.loads(raw) if isinstance(raw, str) else raw
    except Exception as _e:
        log.debug("Failed to parse tool args JSON: %s", _e)
        kwargs = {}
    # Always inject username for tools that accept it
    tool = _TOOLS.get(name)
    if tool:
        for inp in tool.get("inputs", []):
            if inp["name"] == "username" and "username" not in kwargs:
                kwargs["username"] = username
    result = call(name, **kwargs)
    # Flatten result to a readable string
    if "error" in result:
        return f"Tool error: {result['error']}"
    # Prefer 'message', else JSON-serialise
    if "message" in result:
        return result["message"]
    try:
        return _j.dumps(result, ensure_ascii=False, default=str)
    except Exception as _e:
        log.debug("JSON serialise result failed: %s", _e)
        return str(result)


# Load on import
_load_all()


# ── Concurrent tool execution ──────────────

def call_multiple_concurrent(tool_calls: list, username: str = "default") -> list[str]:
    """
    Execute multiple OpenAI-format tool calls concurrently via a thread pool.
    Returns results in the same order as input tool_calls.
    Independent tools (weather + news + web_search) run in parallel,
    cutting multi-tool response time from O(N) to O(1).
    """
    import concurrent.futures

    if not tool_calls:
        return []
    if len(tool_calls) == 1:
        return [call_from_openai(tool_calls[0], username)]

    workers = min(len(tool_calls), 8)
    t0 = _time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(call_from_openai, tc, username) for tc in tool_calls]
        results = [f.result() for f in futures]   # preserve order

    elapsed = _time.monotonic() - t0
    names   = [tc["function"]["name"] if isinstance(tc, dict) else tc.function.name
               for tc in tool_calls]
    log.info("Concurrent tools %s finished in %.2fs", names, elapsed)
    return results
         for tc in tool_calls]
    log.info("Concurrent tools %s finished in %.2fs", names, elapsed)
    return results
