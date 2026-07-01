"""
plugins/__init__.py — Dynamic plugin auto-discovery.
Any .py file in plugins/ with NAME, DESCRIPTION, and run() is loaded automatically.
No changes to core code needed — just drop a file in plugins/.
"""
import importlib.util, logging, os
from pathlib import Path

log = logging.getLogger("plugins")
_LOADED: dict[str, object] = {}   # name -> module


def discover(plugins_dir: str = None) -> dict[str, object]:
    """
    Scan plugins_dir (defaults to this folder) for valid plugin modules.
    A valid plugin must have: NAME (str), DESCRIPTION (str), run (callable).
    Returns dict of {name: module}.
    """
    if plugins_dir is None:
        plugins_dir = os.path.dirname(os.path.abspath(__file__))

    _LOADED.clear()
    for path in sorted(Path(plugins_dir).glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            spec   = importlib.util.spec_from_file_location(path.stem, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            name = getattr(module, "NAME", None)
            desc = getattr(module, "DESCRIPTION", None)
            run  = getattr(module, "run", None)

            if name and desc and callable(run):
                _LOADED[name] = module
                log.info("Plugin loaded: %s — %s", name, desc[:60])
            else:
                log.debug("Skipping %s — missing NAME/DESCRIPTION/run()", path.name)
        except Exception as e:
            log.warning("Plugin load error (%s): %s", path.name, e)

    return _LOADED


def list_plugins() -> list[dict]:
    return [
        {
            "name":        getattr(m, "NAME",        ""),
            "description": getattr(m, "DESCRIPTION", ""),
            "category":    getattr(m, "CATEGORY",    "general"),
            "icon":        getattr(m, "ICON",        "🔌"),
            "inputs":      getattr(m, "INPUTS",      []),
            "version":     getattr(m, "VERSION",     "1.0"),
        }
        for m in _LOADED.values()
    ]


def call_plugin(name: str, **kwargs) -> dict:
    module = _LOADED.get(name)
    if not module:
        return {"error": f"Plugin '{name}' not found. Available: {list(_LOADED.keys())}"}
    try:
        return module.run(**kwargs) or {}
    except Exception as e:
        log.error("Plugin %s error: %s", name, e)
        return {"error": str(e)}


def reload_all() -> int:
    discover()
    return len(_LOADED)
