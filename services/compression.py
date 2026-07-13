"""
services/compression.py -- token compression (OmniRoute RTK + Caveman idea).

Shrinks prompts before they hit the model so free tiers stretch further.
Two stacked passes, both lossless-ish for meaning:

  RTK    -- collapse noisy tool output: dedup repeated lines, trim long logs,
            strip ANSI, cap giant blocks (git diff / grep / test output).
  Caveman-- squeeze prose: collapse whitespace, drop filler words/politeness,
            shorten runs of blank lines.

Pure-Python, no external dependency. Inflation guard: if the result is longer
than the original, the original is kept.
"""
import os
import re
import logging

log = logging.getLogger("services.compression")

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_FILLER = re.compile(
    r"\b(?:please|kindly|just|really|very|actually|basically|simply|"
    r"i think|i believe|in order to|as you can see|it should be noted that|"
    r"note that|of course|obviously)\b", re.I)


def _rtk(text: str) -> str:
    """Collapse noisy tool/log output."""
    text = _ANSI.sub("", text)
    lines = text.split("\n")
    out, prev, repeat = [], None, 0
    for ln in lines:
        s = ln.rstrip()
        if s == prev:
            repeat += 1
            if repeat == 1:
                out.append("  ... (repeated line)")
            continue
        repeat = 0
        prev = s
        out.append(s)
    # cap very long blocks (keep head + tail)
    if len(out) > 400:
        out = out[:200] + ["  ... (%d lines trimmed) ..." % (len(out) - 300)] + out[-100:]
    return "\n".join(out)


def _caveman(text: str) -> str:
    """Squeeze prose."""
    text = _FILLER.sub("", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def compress(text: str, mode: str = "auto") -> dict:
    """Returns {text, original_len, compressed_len, saved_pct, engine}."""
    if not text or len(text) < 400 or os.getenv("COMPRESSION", "1") == "0":
        return {"text": text, "saved_pct": 0, "engine": "off"}

    # Pure-Python stacked pass (RTK -> Caveman)
    out = _caveman(_rtk(text))
    if len(out) >= len(text):   # inflation guard
        return {"text": text, "saved_pct": 0, "engine": "guard"}
    return {"text": out, "original_len": len(text), "compressed_len": len(out),
            "saved_pct": round(100 * (1 - len(out) / len(text))),
            "engine": "python:rtk+caveman"}
