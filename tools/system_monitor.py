"""
tools/system_monitor.py — CPU / RAM / GPU / temp snapshot + threshold alerts.
Ported from Mark-XLVII system_monitor.py. No external APIs required.
"""
import logging
import platform
import subprocess
import time

log = logging.getLogger(__name__)

NAME        = "system_monitor"
DESCRIPTION = (
    "Get real-time system stats: CPU, RAM, GPU usage, CPU temperature, uptime. "
    "Actions: status (snapshot), thresholds (set alert levels)"
)
CATEGORY = "builtin"
ICON     = "💻"
INPUTS = [
    {"name": "action", "label": "Action", "type": "select",
     "options": [
         {"value": "status",     "label": "Get system status"},
         {"value": "thresholds", "label": "Check against thresholds"},
     ], "required": False, "default": "status"},
    {"name": "cpu_threshold",  "label": "CPU alert %",  "type": "number", "placeholder": "90"},
    {"name": "ram_threshold",  "label": "RAM alert %",  "type": "number", "placeholder": "90"},
    {"name": "temp_threshold", "label": "Temp alert °C","type": "number", "placeholder": "85"},
]

_OS = platform.system()

_DEFAULT_THRESHOLDS = {"cpu": 90.0, "ram": 90.0, "temp": 85.0, "gpu": 95.0}


def _get_gpu_usage() -> float:
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2,
        )
        if r.returncode == 0:
            vals = [float(v.strip()) for v in r.stdout.strip().split("\n") if v.strip()]
            return sum(vals) / len(vals) if vals else -1.0
    except Exception:
        pass
    if _OS == "Linux":
        try:
            r = subprocess.run(["rocm-smi", "--showuse", "--csv"],
                               capture_output=True, text=True, timeout=2)
            if r.returncode == 0:
                for line in r.stdout.strip().split("\n"):
                    parts = line.split(",")
                    if len(parts) >= 2:
                        try:
                            return float(parts[1].strip().replace("%", ""))
                        except ValueError:
                            pass
        except Exception:
            pass
    return -1.0


def _get_cpu_temp() -> float:
    try:
        import psutil
        temps = psutil.sensors_temperatures()
        for name in ["coretemp", "k10temp", "cpu_thermal", "acpitz",
                     "cpu-thermal", "zenpower", "it8688"]:
            if name in temps and temps[name]:
                return temps[name][0].current
        for entries in temps.values():
            if entries:
                return entries[0].current
    except Exception:
        pass
    if _OS == "Windows":
        try:
            r = subprocess.run(
                ["powershell", "-Command",
                 "(Get-WmiObject MSAcpi_ThermalZoneTemperature "
                 "-Namespace root/wmi).CurrentTemperature"],
                capture_output=True, text=True, timeout=3,
            )
            if r.returncode == 0 and r.stdout.strip():
                raw = float(r.stdout.strip().split("\n")[0])
                return (raw / 10.0) - 273.15
        except Exception:
            pass
    if _OS == "Darwin":
        try:
            r = subprocess.run(["osx-cpu-temp"], capture_output=True, text=True, timeout=2)
            if r.returncode == 0:
                import re
                m = re.search(r"([\d.]+)", r.stdout)
                if m:
                    return float(m.group(1))
        except Exception:
            pass
    return -1.0


def get_system_status() -> dict:
    """Snapshot of current system metrics."""
    try:
        import psutil
    except ImportError:
        return {"error": "psutil not installed. Run: pip install psutil"}

    cpu  = psutil.cpu_percent(interval=0.2)
    ram  = psutil.virtual_memory()
    temp = _get_cpu_temp()
    gpu  = _get_gpu_usage()

    boot_time   = psutil.boot_time()
    uptime_secs = time.time() - boot_time
    uptime_h    = int(uptime_secs // 3600)
    uptime_m    = int((uptime_secs % 3600) // 60)

    return {
        "cpu_percent":  round(cpu, 1),
        "ram_percent":  round(ram.percent, 1),
        "ram_used_gb":  round(ram.used   / 1024 ** 3, 1),
        "ram_total_gb": round(ram.total  / 1024 ** 3, 1),
        "cpu_temp_c":   round(temp, 1) if temp > 0 else None,
        "gpu_percent":  round(gpu,  1) if gpu  >= 0 else None,
        "uptime":       f"{uptime_h}h {uptime_m}m",
        "process_count":len(psutil.pids()),
    }


def _format_status(s: dict) -> str:
    lines = [
        f"CPU:      {s['cpu_percent']}%",
        f"RAM:      {s['ram_percent']}%  ({s['ram_used_gb']} / {s['ram_total_gb']} GB)",
    ]
    if s.get("cpu_temp_c") is not None:
        lines.append(f"CPU Temp: {s['cpu_temp_c']}°C")
    if s.get("gpu_percent") is not None:
        lines.append(f"GPU:      {s['gpu_percent']}%")
    lines.append(f"Uptime:   {s['uptime']}")
    lines.append(f"Processes:{s['process_count']}")
    return "\n".join(lines)


def _check_thresholds(s: dict, thresholds: dict) -> list:
    alerts = []
    if s["cpu_percent"]  >= thresholds.get("cpu",  90):
        alerts.append(f"⚠️ CPU at {s['cpu_percent']}% (threshold {thresholds['cpu']}%)")
    if s["ram_percent"]  >= thresholds.get("ram",  90):
        alerts.append(f"⚠️ RAM at {s['ram_percent']}% (threshold {thresholds['ram']}%)")
    if s.get("cpu_temp_c") and s["cpu_temp_c"] >= thresholds.get("temp", 85):
        alerts.append(f"🌡️ CPU temp {s['cpu_temp_c']}°C (threshold {thresholds['temp']}°C)")
    if s.get("gpu_percent") and s["gpu_percent"] >= thresholds.get("gpu", 95):
        alerts.append(f"⚠️ GPU at {s['gpu_percent']}% (threshold {thresholds['gpu']}%)")
    return alerts


def run(
    action:        str   = "status",
    cpu_threshold: float = 90.0,
    ram_threshold: float = 90.0,
    temp_threshold:float = 85.0,
    username:      str   = "",
) -> dict:
    action = (action or "status").strip().lower()

    s = get_system_status()
    if "error" in s:
        return s

    summary = _format_status(s)

    if action == "thresholds":
        try:
            thresholds = {
                "cpu":  float(cpu_threshold  or 90),
                "ram":  float(ram_threshold  or 90),
                "temp": float(temp_threshold or 85),
                "gpu":  95.0,
            }
        except (ValueError, TypeError):
            thresholds = _DEFAULT_THRESHOLDS

        alerts = _check_thresholds(s, thresholds)
        if alerts:
            alert_text = "\n".join(alerts)
            return {"result": f"{summary}\n\nAlerts:\n{alert_text}", "alerts": alerts, **s}
        return {"result": f"{summary}\n\n✅ All metrics within safe thresholds.", "alerts": [], **s}

    return {"result": summary, **s}
