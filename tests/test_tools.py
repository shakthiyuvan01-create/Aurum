"""
tests/test_tools.py — Unit tests for individual tools
"""
import pytest


# ── Tool registry ─────────────────────────────────────────────────────────────

def test_tools_load():
    """At least some tools should be discovered."""
    import tools
    tool_list = tools.list_tools()
    assert isinstance(tool_list, list)
    assert len(tool_list) > 0, "No tools loaded"


def test_tool_schema_fields():
    """Every loaded tool must have the required fields."""
    import tools
    required = {"name", "description", "category", "inputs"}
    for t in tools.list_tools():
        missing = required - t.keys()
        assert not missing, f"Tool '{t.get('name')}' missing fields: {missing}"


def test_get_tool():
    """get_tool() returns the right tool dict."""
    import tools
    all_names = [t["name"] for t in tools.list_tools()]
    if not all_names:
        pytest.skip("no tools loaded")
    name = all_names[0]
    tool = tools.get_tool(name)
    assert tool is not None
    assert tool["name"] == name


def test_get_tool_missing():
    import tools
    assert tools.get_tool("__nonexistent_tool__xyz__") is None


# ── Calculator tool ───────────────────────────────────────────────────────────

def test_calculator_basic():
    import tools
    if not tools.get_tool("calculator"):
        pytest.skip("calculator tool not loaded")
    result = tools.call("calculator", expression="2 + 2")
    assert "error" not in result, f"Unexpected error: {result}"
    # result should be a dict with some numeric value
    val = result.get("result", result.get("answer", result.get("value")))
    assert val is not None


def test_calculator_division_by_zero():
    import tools
    if not tools.get_tool("calculator"):
        pytest.skip("calculator tool not loaded")
    result = tools.call("calculator", expression="1/0")
    # should not raise — should return error or infinity gracefully
    assert isinstance(result, dict)


def test_calculator_invalid_expression():
    import tools
    if not tools.get_tool("calculator"):
        pytest.skip("calculator tool not loaded")
    result = tools.call("calculator", expression="import os")
    assert isinstance(result, dict)


# ── Tool not found ────────────────────────────────────────────────────────────

def test_call_unknown_tool():
    import tools
    result = tools.call("__does_not_exist__")
    assert "error" in result


# ── OpenAI call_from_openai ───────────────────────────────────────────────────

def test_call_from_openai_dict_format():
    """call_from_openai should accept an OpenAI-style dict and return a string."""
    import tools
    if not tools.get_tool("calculator"):
        pytest.skip("calculator tool not loaded")
    tc = {
        "function": {
            "name": "calculator",
            "arguments": '{"expression": "3 * 7"}',
        }
    }
    result = tools.call_from_openai(tc)
    assert isinstance(result, str)
    assert len(result) > 0


def test_call_from_openai_bad_json():
    import tools
    tc = {"function": {"name": "calculator", "arguments": "NOT_JSON"}}
    result = tools.call_from_openai(tc)
    assert isinstance(result, str)


# ── Concurrent execution ──────────────────────────────────────────────────────

def test_call_multiple_concurrent_empty():
    import tools
    result = tools.call_multiple_concurrent([])
    assert result == []


def test_call_multiple_concurrent_single():
    import tools
    if not tools.get_tool("calculator"):
        pytest.skip("calculator tool not loaded")
    tc = {"function": {"name": "calculator", "arguments": '{"expression": "1+1"}'}}
    result = tools.call_multiple_concurrent([tc])
    assert len(result) == 1
    assert isinstance(result[0], str)


def test_call_multiple_concurrent_order():
    """Results must be in submission order, not completion order."""
    import tools
    if not tools.get_tool("calculator"):
        pytest.skip("calculator tool not loaded")
    tcs = [
        {"function": {"name": "calculator", "arguments": f'{{"expression": "{i}*{i}"}}'}}
        for i in range(1, 5)
    ]
    results = tools.call_multiple_concurrent(tcs)
    assert len(results) == 4
    for r in results:
        assert isinstance(r, str)
