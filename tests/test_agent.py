"""
tests/test_agent.py — Tests for the ReAct agent loop
Uses monkeypatching to avoid real LLM API calls.
"""
import os, json, pytest

os.environ.setdefault("APP_ENV", "testing")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_chat_chunk(content: str) -> bytes:
    """Fake an OpenAI streaming SSE chunk with a content delta."""
    payload = json.dumps({
        "choices": [{"delta": {"content": content}, "finish_reason": None}]
    })
    return f"data: {payload}\n\n".encode()


def _make_final_chunk() -> bytes:
    return b"data: [DONE]\n\n"


# ── _sse helper ───────────────────────────────────────────────────────────────

def test_sse_format():
    """_sse() should produce valid JSON-wrapped SSE lines."""
    import agent
    line = agent._sse({"type": "token", "text": "hello"})
    assert line.startswith("data: ")
    assert line.endswith("\n\n")
    parsed = json.loads(line[6:])
    assert parsed["type"] == "token"


# ── Agent with mocked LLM (no tool calls) ────────────────────────────────────

def test_agent_stream_plain_answer(monkeypatch):
    """
    When the LLM returns a plain text answer (no tool_calls),
    the agent should stream that content directly.
    """
    import agent, tools as _tools

    # Fake a simple streaming response with no tool calls
    class _FakeResponse:
        status_code = 200
        def iter_lines(self):
            yield b"data: " + json.dumps({
                "choices": [{"delta": {"content": "The answer is 42."}, "finish_reason": None}]
            }).encode()
            yield b"data: " + json.dumps({
                "choices": [{"delta": {}, "finish_reason": "stop"}]
            }).encode()
            yield b"data: [DONE]"
        def raise_for_status(self): pass

    import requests
    monkeypatch.setattr(requests, "post", lambda *a, **kw: _FakeResponse())

    # Also patch the initial tool-plan call (first LLM call) to return no tool_calls
    class _FakePlanResponse:
        status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": "42", "tool_calls": None}}]}
        def raise_for_status(self): pass

    call_count = [0]
    orig_post = requests.post

    def _patched_post(*a, **kw):
        call_count[0] += 1
        if call_count[0] == 1:
            return _FakePlanResponse()
        return _FakeResponse()

    monkeypatch.setattr(requests, "post", _patched_post)

    events = list(agent.run_stream(
        messages=[{"role": "user", "content": "What is 6×7?"}],
        username="testuser",
        model="gpt-4o-mini",
    ))
    assert len(events) > 0
    # At least one event should contain a delta or done
    text_events = [e for e in events if b'"delta"' in e or b'"done"' in e]
    assert len(text_events) > 0


# ── Agent stream yields SSE lines ─────────────────────────────────────────────

def test_agent_stream_yields_bytes(monkeypatch):
    """run_stream is a generator — it must yield bytes."""
    import agent, requests

    class _FakeResponse:
        status_code = 200
        def json(self):
            return {"choices": [{"message": {"content": "hi", "tool_calls": None}}]}
        def iter_lines(self):
            yield b"data: " + json.dumps({
                "choices": [{"delta": {"content": "hi"}, "finish_reason": "stop"}]
            }).encode()
            yield b"data: [DONE]"
        def raise_for_status(self): pass

    monkeypatch.setattr(requests, "post", lambda *a, **kw: _FakeResponse())

    for chunk in agent.run_stream(
        messages=[{"role": "user", "content": "hello"}],
        username="testuser",
        model="gpt-4o-mini",
    ):
        assert isinstance(chunk, (bytes, str))
        break   # just check the first chunk


# ── Config values ─────────────────────────────────────────────────────────────

def test_config_loaded():
    from config import cfg
    assert hasattr(cfg, "MAX_AGENT_ITERATIONS")
    assert hasattr(cfg, "SIMILARITY_THRESHOLD")
    assert hasattr(cfg, "TOOL_WARN_FAILURES")


def test_testing_config_values():
    from config.testing import TestingConfig
    assert TestingConfig.TESTING is True
    assert TestingConfig.DEBUG is True
    assert TestingConfig.MAX_AGENT_ITERATIONS == 2
