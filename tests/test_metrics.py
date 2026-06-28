"""
tests/test_metrics.py — Unit tests for tools/tool_metrics.py
"""
import os, time, pytest

os.environ.setdefault("APP_ENV", "testing")


@pytest.fixture(autouse=True)
def patch_db_path(tmp_path, monkeypatch):
    """Point tool_metrics at a fresh temp DB for each test."""
    import tools.tool_metrics as tm
    monkeypatch.setattr(tm, "_DB_PATH", str(tmp_path / "metrics.db"))


# ── record_call ───────────────────────────────────────────────────────────────

def test_record_success():
    from tools.tool_metrics import record_call, get_metrics
    record_call("weather", success=True, runtime_ms=120.5)
    m = get_metrics("weather")
    assert m["success_count"] == 1
    assert m["failure_count"] == 0
    assert m["avg_runtime_ms"] == pytest.approx(120.5, rel=0.01)


def test_record_failure():
    from tools.tool_metrics import record_call, get_metrics
    record_call("weather", success=False, runtime_ms=50.0)
    m = get_metrics("weather")
    assert m["failure_count"] == 1
    assert m["last_failure_ts"] > 0


def test_avg_runtime_rolling():
    """Average runtime should update incrementally."""
    from tools.tool_metrics import record_call, get_metrics
    record_call("calc", success=True, runtime_ms=100.0)
    record_call("calc", success=True, runtime_ms=200.0)
    m = get_metrics("calc")
    assert m["success_count"] == 2
    # avg = (100 + 200) / 2 = 150
    assert m["avg_runtime_ms"] == pytest.approx(150.0, rel=0.05)


# ── should_warn ───────────────────────────────────────────────────────────────

def test_should_warn_below_threshold():
    from tools.tool_metrics import record_call, should_warn
    record_call("web_search", success=False, runtime_ms=10)
    record_call("web_search", success=False, runtime_ms=10)
    assert not should_warn("web_search")  # only 2 failures, threshold is 3


def test_should_warn_at_threshold():
    from tools.tool_metrics import record_call, should_warn
    for _ in range(3):
        record_call("news", success=False, runtime_ms=5)
    assert should_warn("news")


def test_should_warn_new_tool():
    from tools.tool_metrics import should_warn
    assert not should_warn("brand_new_tool_xyz")


# ── get_metrics ───────────────────────────────────────────────────────────────

def test_get_metrics_all():
    from tools.tool_metrics import record_call, get_metrics
    record_call("tool_a", success=True, runtime_ms=10)
    record_call("tool_b", success=True, runtime_ms=20)
    all_m = get_metrics()
    assert isinstance(all_m, dict)
    assert "tool_a" in all_m
    assert "tool_b" in all_m


def test_get_metrics_unknown():
    from tools.tool_metrics import get_metrics
    m = get_metrics("tool_that_never_ran")
    # should return an empty dict or a row with zeros
    assert isinstance(m, dict)


# ── reset_metrics ─────────────────────────────────────────────────────────────

def test_reset_metrics():
    from tools.tool_metrics import record_call, reset_metrics, get_metrics, should_warn
    for _ in range(5):
        record_call("scheduler", success=False, runtime_ms=1)
    assert should_warn("scheduler")
    reset_metrics("scheduler")
    assert not should_warn("scheduler")
    m = get_metrics("scheduler")
    assert m.get("failure_count", 0) == 0


# ── cost_tier defaults ────────────────────────────────────────────────────────

def test_cost_tier_default():
    from tools.tool_metrics import get_metrics, COST_TIERS
    tool_name = list(COST_TIERS.keys())[0]   # e.g. "weather"
    get_metrics(tool_name)   # ensure row created
    m = get_metrics(tool_name)
    assert m.get("cost_tier") == COST_TIERS[tool_name]
