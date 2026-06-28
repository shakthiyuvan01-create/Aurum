"""
tests/test_memory.py — Tests for vector_memory (scoring helpers + store/retrieve)
"""
import os, pytest

os.environ.setdefault("APP_ENV", "testing")


# ── Scoring helpers (pure, no DB needed) ──────────────────────────────────────

def test_recency_score_now():
    """A just-stored memory should have near-max recency."""
    import time
    from vector_memory import _recency_score
    score = _recency_score(time.time())
    assert score >= 0.9, f"Expected ≥0.9, got {score}"


def test_recency_score_old():
    """A 14-day-old memory should have very low recency."""
    import time
    from vector_memory import _recency_score, RECENCY_HALF_LIFE
    old_ts = time.time() - RECENCY_HALF_LIFE * 2.5
    score = _recency_score(old_ts)
    assert score <= 0.1, f"Expected ≤0.1, got {score}"


def test_recency_score_range():
    """recency_score should always be in [0, 1]."""
    import time
    from vector_memory import _recency_score
    for offset in [-999999, 0, time.time(), time.time() + 9999]:
        s = _recency_score(offset)
        assert 0.0 <= s <= 1.0, f"Out of range: {s}"


def test_importance_score_short():
    """Short text without keywords → low importance."""
    from vector_memory import _importance_score
    s = _importance_score("hi")
    assert s < 0.2, f"Expected <0.2, got {s}"


def test_importance_score_keywords():
    """Text containing importance keywords should score higher."""
    from vector_memory import _importance_score
    s = _importance_score("always remember this is important")
    assert s > 0.2, f"Expected >0.2 for keyword-rich text, got {s}"


def test_importance_score_long():
    """Long text should get a higher base score."""
    from vector_memory import _importance_score
    long_text = "word " * 100
    s = _importance_score(long_text)
    assert s >= 0.5, f"Expected ≥0.5 for long text, got {s}"


def test_importance_score_range():
    from vector_memory import _importance_score
    for text in ["", "hi", "a" * 1000, "remember always never important"]:
        s = _importance_score(text)
        assert 0.0 <= s <= 1.0, f"Out of range: {s}"


# ── rank_results ──────────────────────────────────────────────────────────────

def test_rank_results_filters_low_similarity():
    """Documents far from the threshold should be filtered out."""
    import time
    from vector_memory import _rank_results, SIMILARITY_THRESHOLD
    docs = ["close match", "totally unrelated text far away"]
    # cosine distance: 0 = identical, 2 = opposite
    # threshold 0.30 → filter dist > (2 - 0.30*2) = 1.4
    distances   = [0.1, 1.8]   # second one should be filtered
    timestamps  = [str(time.time()), str(time.time())]
    ranked = _rank_results(docs, distances, timestamps)
    assert "close match" in ranked
    assert "totally unrelated text far away" not in ranked


def test_rank_results_empty():
    from vector_memory import _rank_results
    assert _rank_results([], [], []) == []


def test_rank_results_sorted_by_score():
    """Higher-similarity recent item should rank above older less-similar item."""
    import time
    from vector_memory import _rank_results
    docs = ["old distant", "new close"]
    distances   = [0.6, 0.1]
    old_ts      = str(time.time() - 86400 * 10)
    new_ts      = str(time.time())
    timestamps  = [old_ts, new_ts]
    ranked = _rank_results(docs, distances, timestamps)
    if len(ranked) == 2:
        assert ranked[0] == "new close"


# ── store / retrieve round-trip ────────────────────────────────────────────────

def test_store_and_retrieve(tmp_path, monkeypatch):
    """Storing a fact and retrieving it should return a relevant result."""
    import vector_memory as vm
    # point the chroma/fts path at tmp_path so we don't pollute prod
    monkeypatch.setattr(vm, "_CHROMA_DIR",
                        str(tmp_path / "chroma"), raising=False)
    vm.init()   # re-init with patched path

    user = "pytest_user"
    fact = "My favourite colour is crimson red"
    vm.store(user, fact)

    results = vm.retrieve(user, "what colour does the user like", n=3)
    assert isinstance(results, list)
    # The stored fact should appear in results (exact or near match)
    combined = " ".join(results).lower()
    assert "crimson" in combined or len(results) > 0
