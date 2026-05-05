"""Phase 4 — asm_bridge: graceful degradation when asm is absent or errors."""

from __future__ import annotations

from pathlib import Path

from skill_doctor import asm_bridge
from skill_doctor.asm_bridge import quality_sample


def test_quality_sample_returns_none_when_asm_missing(monkeypatch) -> None:
    monkeypatch.setattr(asm_bridge, "has_asm", lambda: False)
    result = quality_sample([Path("/tmp/x")])
    assert result is None


def test_quality_sample_returns_empty_when_all_calls_fail(monkeypatch) -> None:
    monkeypatch.setattr(asm_bridge, "has_asm", lambda: True)
    monkeypatch.setattr(asm_bridge, "_eval_one", lambda path, timeout: None)
    result = quality_sample([Path("/tmp/x"), Path("/tmp/y")])
    assert result == []


def test_quality_full_uses_cache_on_second_run(monkeypatch, tmp_path) -> None:
    """Second run with same mtime should hit cache and skip subprocess."""
    monkeypatch.setattr(asm_bridge, "has_asm", lambda: True)
    cache_path = tmp_path / "cache.json"
    monkeypatch.setattr(asm_bridge, "QUALITY_CACHE_PATH", cache_path)

    skill_dir = tmp_path / "x"
    (skill_dir / "SKILL.md").parent.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("body")

    call_count = {"n": 0}

    def fake_eval(p, t):
        call_count["n"] += 1
        return asm_bridge.QualityRow(name="x", score=50, grade="D", suggestions=[], path=p)

    monkeypatch.setattr(asm_bridge, "_eval_one", fake_eval)

    asm_bridge.quality_full([skill_dir])
    asm_bridge.quality_full([skill_dir])
    assert call_count["n"] == 1, "second run should hit cache"


def test_quality_sample_sorts_by_score_ascending(monkeypatch) -> None:
    monkeypatch.setattr(asm_bridge, "has_asm", lambda: True)

    QR = asm_bridge.QualityRow
    rows = {
        Path("/a"): QR(name="a", score=80, grade="B", suggestions=[], path=Path("/a")),
        Path("/b"): QR(name="b", score=20, grade="F", suggestions=[], path=Path("/b")),
        Path("/c"): QR(name="c", score=60, grade="D", suggestions=[], path=Path("/c")),
    }
    monkeypatch.setattr(asm_bridge, "_eval_one", lambda p, t: rows.get(p))

    result = quality_sample(list(rows.keys()))
    assert result is not None
    assert [r.score for r in result] == [20, 60, 80]
