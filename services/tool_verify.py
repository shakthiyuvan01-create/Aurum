"""Ephemeral venv verification for forged tools (Ada-SI pattern).

Generated tool code runs in a temporary subprocess under a throwaway Python
environment. The workspace directory is cleaned after each verify attempt.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

log = logging.getLogger("services.tool_verify")

BASE = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STAGING_DIR = BASE / "staging"
STAGING_DIR.mkdir(exist_ok=True)

VERIFY_TIMEOUT = 120
PIP_TIMEOUT = 300
LOG_LIMIT = 8192
MISSING_MODULE_MAX_RETRIES = 4

# Regex patterns for detecting missing modules
_MISSING_MODULE_PATTERNS = (
    r"No module named '([^']+)'",
    r'No module named "([^"]+)"',
    r"ModuleNotFoundError: No module named ([^\s]+)",
)


def parse_missing_module(text: str) -> str | None:
    """Extract top-level PyPI package name from import errors in verify output."""
    if not text:
        return None
    for pattern in _MISSING_MODULE_PATTERNS:
        match = re.search(pattern, text)
        if not match:
            continue
        raw = match.group(1).strip().strip("'\"")
        if not raw:
            continue
        return raw.split(".")[0]
    return None


def _create_temp_workspace() -> Path:
    """Create a temporary workspace for tool verification."""
    ws = Path(tempfile.mkdtemp(prefix="aurum_forge_", dir=str(STAGING_DIR)))
    return ws


def _cleanup_workspace(ws: Path):
    """Remove temporary workspace."""
    try:
        if ws.exists():
            shutil.rmtree(ws, ignore_errors=True)
    except Exception as e:
        log.debug("workspace cleanup: %s", e)


def verify_tool(
    tool_name: str,
    tool_code: str,
    requirements: list[str],
    test_code: str = "",
) -> dict:
    """Verify a forged tool in an ephemeral environment.

    Tests compilation, import, and optionally runs test_code.

    Args:
        tool_name: Name of the tool module (snake_case)
        tool_code: Python source code for the tool
        requirements: List of pip requirements
        test_code: Optional test code to verify tool behavior

    Returns:
        {"ok": True, ...} or {"error": ..., "detail": ...}
    """
    workspace = _create_temp_workspace()
    try:
        # Write tool module
        tool_path = workspace / f"{tool_name}.py"
        tool_path.write_text(tool_code, encoding="utf-8")

        # Write test if provided
        test_path = None
        if test_code:
            test_code_fixed = test_code.replace(
                "/workspace/", f"{workspace.as_posix()}/"
            )
            test_path = workspace / "test_run.py"
            test_path.write_text(test_code_fixed, encoding="utf-8")

        # Write requirements
        req_path = workspace / "requirements.txt"
        req_path.write_text("\n".join(requirements), encoding="utf-8")

        # Phase 1: Compile check (no imports executed)
        log.info("verify %s: phase 1 compile check", tool_name)
        r = subprocess.run(
            [sys.executable, "-c", f"import py_compile; py_compile.compile(r'{tool_path}', doraise=True)"],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode != 0:
            return {
                "ok": False, "phase": "compile",
                "error": f"Syntax error: {(r.stderr or r.stdout)[:LOG_LIMIT]}",
            }

        # Phase 2: Import check (load module, verify shape)
        log.info("verify %s: phase 2 import check", tool_name)
        import_check = (
            f"import importlib.util; "
            f"spec = importlib.util.spec_from_file_location('{tool_name}', r'{tool_path}'); "
            f"mod = importlib.util.module_from_spec(spec); "
            f"spec.loader.exec_module(mod); "
            f"assert hasattr(mod, 'NAME') and isinstance(mod.NAME, str), 'Missing NAME'; "
            f"assert hasattr(mod, 'run') and callable(mod.run), 'Missing run()'; "
            f"print('IMPORT_OK')"
        )
        r = subprocess.run(
            [sys.executable, "-c", import_check],
            capture_output=True, text=True, timeout=15,
        )
        if "IMPORT_OK" not in r.stdout:
            err = (r.stderr or r.stdout)[:LOG_LIMIT]
            # Check for missing packages
            missing = parse_missing_module(err)
            if missing:
                return {
                    "ok": False, "phase": "import",
                    "error": f"Missing module: {missing}",
                    "missing_module": missing,
                    "detail": err,
                }
            return {
                "ok": False, "phase": "import",
                "error": f"Import failed: {err}",
            }

        # Install requirements (if any) for test phase
        if requirements:
            log.info("verify %s: installing %d requirements", tool_name, len(requirements))
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--quiet", *requirements],
                capture_output=True, text=True, timeout=PIP_TIMEOUT,
            )
            if r.returncode != 0:
                return {
                    "ok": False, "phase": "pip_install",
                    "error": f"Pip install failed: {(r.stderr or r.stdout)[:LOG_LIMIT]}",
                }

        # Phase 3: Test run
        if test_code and test_path:
            log.info("verify %s: phase 3 running tests", tool_name)
            r = subprocess.run(
                [sys.executable, str(test_path)],
                capture_output=True, text=True, timeout=VERIFY_TIMEOUT,
            )
            if r.returncode != 0:
                return {
                    "ok": False, "phase": "test",
                    "error": f"Tests failed (exit {r.returncode})",
                    "detail": (r.stderr or r.stdout)[:LOG_LIMIT],
                    "stdout": r.stdout[:LOG_LIMIT],
                }
            log.info("verify %s: all tests passed", tool_name)

        return {
            "ok": True,
            "tool_name": tool_name,
            "requirements": requirements,
            "workspace": str(workspace),
        }

    except subprocess.TimeoutExpired as e:
        return {
            "ok": False, "phase": str(e.cmd)[:50],
            "error": f"Timed out after {VERIFY_TIMEOUT}s",
        }
    except Exception as e:
        return {
            "ok": False, "phase": "runtime",
            "error": str(e),
        }
    finally:
        _cleanup_workspace(workspace)


def augment_requirements(
    requirements: list[str],
    error_text: str,
) -> tuple[list[str], str | None]:
    """If error_text names a missing module, append it to requirements."""
    missing = parse_missing_module(error_text)
    if not missing:
        return requirements, None
    existing_lower = {pkg.lower() for pkg in requirements}
    if missing.lower() not in existing_lower:
        requirements.append(missing)
        return requirements, missing
    return requirements, None
