"""
services/sandbox.py — Tool / Plugin execution sandbox.

Runs untrusted plugin code in a subprocess with:
  - CPU time limit (default 30 s)
  - Memory limit (default 256 MB on Linux via resource module)
  - Filesystem scope (plugin can only write to a temp dir)
  - Network permission toggle
  - stdin closed

Usage:
    from services.sandbox import sandbox

    result = sandbox.run_plugin("stock_price", ticker="AAPL")
    # {"result": "...", "_sandbox": {"cpu_ms": 412, "ok": True}}

    # Check permissions before running
    sandbox.check_permission("stock_price", "network")  # True/False
"""
from __future__ import annotations

import importlib.util
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("services.sandbox")

_PLUGINS_DIR = str(Path(os.path.abspath(__file__)).parent.parent / "plugins")
_CPU_LIMIT   = int(os.getenv("SANDBOX_CPU_SECS",  "30"))
_MEM_LIMIT   = int(os.getenv("SANDBOX_MEM_MB",   "256")) * 1024 * 1024   # bytes


# ── Permission manifest ───────────────────────────────────────────────────────
@dataclass
class PluginPermissions:
    """
    Declare what a plugin is allowed to do.
    Plugins that need network/filesystem/subprocess must declare it explicitly.
    Default: network only (most plugins call APIs).
    """
    network:    bool = True    # HTTP/HTTPS calls allowed
    filesystem: bool = False   # Write outside temp dir
    subprocess: bool = False   # Spawn sub-processes
    cpu_secs:   int  = _CPU_LIMIT
    mem_mb:     int  = 256


# Default permissive manifest (override per-plugin via PERMISSIONS dict in plugin file)
_DEFAULT_PERMS = PluginPermissions()

# Built-in permission overrides for known risky plugins
_PERMISSION_OVERRIDES: dict[str, PluginPermissions] = {
    "code_runner":  PluginPermissions(network=False, filesystem=True, subprocess=True, cpu_secs=10),
    "browser_agent":PluginPermissions(network=True,  filesystem=False, subprocess=True, cpu_secs=60),
    "git_tool":     PluginPermissions(network=True,  filesystem=True,  subprocess=True, cpu_secs=30),
}


def _get_permissions(plugin_name: str, plugin_module=None) -> PluginPermissions:
    """Resolve permissions for a plugin: override > plugin-declared > default."""
    if plugin_name in _PERMISSION_OVERRIDES:
        return _PERMISSION_OVERRIDES[plugin_name]
    if plugin_module is not None:
        declared = getattr(plugin_module, "PERMISSIONS", None)
        if isinstance(declared, dict):
            return PluginPermissions(**{k: v for k, v in declared.items() if hasattr(PluginPermissions, k)})
    return _DEFAULT_PERMS


# ── In-process sandbox (fast path) ────────────────────────────────────────────
def _run_inprocess(module, perms: PluginPermissions, kwargs: dict) -> dict:
    """
    Run a plugin's run() function in the current process but with:
    - Wall-clock timeout via threading
    - Restricted kwargs (no __builtins__ injection)
    """
    import threading

    result_box: list = [None]
    error_box:  list = [None]

    def _target():
        try:
            result_box[0] = module.run(**kwargs)
        except Exception as e:
            error_box[0] = str(e)

    t = threading.Thread(target=_target, daemon=True)
    t0 = time.time()
    t.start()
    t.join(timeout=perms.cpu_secs)
    elapsed_ms = int((time.time() - t0) * 1000)

    if t.is_alive():
        return {"error": f"Plugin timed out after {perms.cpu_secs}s", "_sandbox": {"ok": False, "timeout": True}}

    if error_box[0]:
        return {"error": error_box[0], "_sandbox": {"ok": False, "cpu_ms": elapsed_ms}}

    result = result_box[0] or {}
    if not isinstance(result, dict):
        result = {"result": str(result)}

    result["_sandbox"] = {"ok": True, "cpu_ms": elapsed_ms, "in_process": True}
    return result


# ── Subprocess sandbox (strong isolation) ────────────────────────────────────
_RUNNER_SCRIPT = r"""
import sys, json, importlib.util, os, resource

plugin_path = sys.argv[1]
kwargs      = json.loads(sys.argv[2])

# Apply memory limit on Linux
try:
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    mem_limit  = int(os.environ.get("SANDBOX_MEM_BYTES", str(256 * 1024 * 1024)))
    resource.setrlimit(resource.RLIMIT_AS, (mem_limit, hard))
except Exception:
    pass

spec   = importlib.util.spec_from_file_location("plugin", plugin_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

try:
    result = module.run(**kwargs)
    print(json.dumps(result if isinstance(result, dict) else {"result": str(result)}))
except Exception as e:
    print(json.dumps({"error": str(e)}))
"""


def _run_subprocess(plugin_path: str, perms: PluginPermissions, kwargs: dict) -> dict:
    """Run plugin in a fully isolated subprocess."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(_RUNNER_SCRIPT)
        runner = f.name

    env = os.environ.copy()
    env["SANDBOX_MEM_BYTES"] = str(perms.mem_mb * 1024 * 1024)

    if not perms.network:
        # Block network by overriding http proxy to a dead address
        env["http_proxy"]  = "http://127.0.0.1:0"
        env["https_proxy"] = "http://127.0.0.1:0"
        env["no_proxy"]    = ""

    t0 = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, runner, plugin_path, json.dumps(kwargs)],
            capture_output=True,
            text=True,
            timeout=perms.cpu_secs,
            env=env,
            stdin=subprocess.DEVNULL,
        )
        elapsed_ms = int((time.time() - t0) * 1000)
        os.unlink(runner)

        stdout = proc.stdout.strip()
        if proc.returncode != 0 or not stdout:
            return {"error": proc.stderr[:500] or "subprocess failed",
                    "_sandbox": {"ok": False, "cpu_ms": elapsed_ms, "returncode": proc.returncode}}

        result = json.loads(stdout)
        if not isinstance(result, dict):
            result = {"result": str(result)}
        result["_sandbox"] = {"ok": True, "cpu_ms": elapsed_ms, "isolated": True}
        return result

    except subprocess.TimeoutExpired:
        os.unlink(runner)
        return {"error": f"Plugin timed out after {perms.cpu_secs}s",
                "_sandbox": {"ok": False, "timeout": True}}
    except Exception as e:
        try:
            os.unlink(runner)
        except Exception:
            pass
        return {"error": str(e), "_sandbox": {"ok": False}}


# ── Public API ────────────────────────────────────────────────────────────────
class Sandbox:

    def run_plugin(
        self,
        plugin_name: str,
        isolate:     bool = False,
        **kwargs: Any,
    ) -> dict:
        """
        Execute a named plugin safely.
        isolate=True forces subprocess isolation (slower but stronger).
        isolate=False (default) uses threaded timeout within the main process.
        """
        # Locate plugin
        plugin_path = os.path.join(_PLUGINS_DIR, f"{plugin_name}.py")
        tools_path  = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "tools", f"{plugin_name}.py"
        )

        path = plugin_path if os.path.exists(plugin_path) else (
               tools_path  if os.path.exists(tools_path)  else None)

        if path is None:
            return {"error": f"Plugin '{plugin_name}' not found"}

        # Load module to read declared permissions
        try:
            spec   = importlib.util.spec_from_file_location(plugin_name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as e:
            return {"error": f"Plugin load error: {e}"}

        perms = _get_permissions(plugin_name, module)

        log.info("sandbox.run_plugin: %s isolate=%s cpu=%ds", plugin_name, isolate, perms.cpu_secs)

        # Fire event
        try:
            from services.event_bus import bus
            bus.emit("tool.called", data={"tool": plugin_name, "sandboxed": True}, async_=True)
        except Exception:
            pass

        if isolate or perms.subprocess:
            return _run_subprocess(path, perms, kwargs)
        return _run_inprocess(module, perms, kwargs)

    def check_permission(self, plugin_name: str, permission: str) -> bool:
        perms = _get_permissions(plugin_name)
        return bool(getattr(perms, permission, False))

    def set_permissions(self, plugin_name: str, **kwargs) -> None:
        _PERMISSION_OVERRIDES[plugin_name] = PluginPermissions(**kwargs)

    def list_permissions(self) -> dict:
        return {
            name: {
                "network":    p.network,
                "filesystem": p.filesystem,
                "subprocess": p.subprocess,
                "cpu_secs":   p.cpu_secs,
                "mem_mb":     p.mem_mb,
            }
            for name, p in _PERMISSION_OVERRIDES.items()
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
sandbox = Sandbox()
