"""Phase 3 — apply.py: action building, execution, and undo round-trip."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from skill_doctor.analyze import analyze
from skill_doctor.apply import apply_actions, build_actions, undo_last
from skill_doctor.models import ActionType, Runtime
from skill_doctor.scanner import scan_all


def _custom_roots(layout: dict[Runtime, Path]) -> tuple:
    return tuple((path, runtime, "*") for runtime, path in layout.items())


def _scan(layout: dict[Runtime, Path]):
    instances, junk, broken = scan_all(_custom_roots(layout))
    return analyze(instances, junk, broken)


def test_build_actions_for_dup_group(
    tmp_runtime_root: dict[Runtime, Path],
    make_skill: Callable[..., Path],
) -> None:
    body = "shared body\n"
    make_skill(tmp_runtime_root[Runtime.CLAUDE], "x", body=body)
    make_skill(tmp_runtime_root[Runtime.OPENCLAW], "x", body=body)
    report = _scan(tmp_runtime_root)
    actions = build_actions(report)
    dedups = [a for a in actions if a.type == ActionType.DEDUP]
    assert len(dedups) == 1
    assert "x" in dedups[0].title


def test_build_actions_skips_already_correct_symlink(
    tmp_runtime_root: dict[Runtime, Path],
    make_skill: Callable[..., Path],
    make_symlink: Callable[[Path, Path], None],
) -> None:
    real = make_skill(tmp_runtime_root[Runtime.OPENCLAW], "x", body="b\n")
    make_symlink(real, tmp_runtime_root[Runtime.CLAUDE] / "x")
    report = _scan(tmp_runtime_root)
    actions = build_actions(report)
    dedups = [a for a in actions if a.type == ActionType.DEDUP]
    assert dedups == [], "already-correct symlink should not generate a DEDUP action"


def test_apply_dedup_then_undo_roundtrip(
    tmp_runtime_root: dict[Runtime, Path],
    make_skill: Callable[..., Path],
    monkeypatch,
    tmp_path: Path,
) -> None:
    body = "round-trip body\n"
    make_skill(tmp_runtime_root[Runtime.CLAUDE], "x", body=body)
    real = make_skill(tmp_runtime_root[Runtime.OPENCLAW], "x", body=body)
    report = _scan(tmp_runtime_root)

    # Redirect backup root to tmp_path so we don't pollute ~/.skill-doctor.
    backup_root = tmp_path / "backup"
    monkeypatch.setattr("skill_doctor.config.BACKUP_ROOT", backup_root)
    monkeypatch.setattr("skill_doctor.apply.BACKUP_ROOT", backup_root)

    summary = apply_actions(report, interactive=False)
    assert summary.completed == 1

    claude_path = tmp_runtime_root[Runtime.CLAUDE] / "x"
    assert claude_path.is_symlink()
    assert claude_path.resolve() == real.resolve()

    undo_summary = undo_last()
    assert undo_summary.failed == 0
    assert claude_path.is_dir()
    assert not claude_path.is_symlink()


def test_apply_handles_macos_junk(
    tmp_runtime_root: dict[Runtime, Path],
    make_skill: Callable[..., Path],
    monkeypatch,
    tmp_path: Path,
) -> None:
    skill_dir = make_skill(tmp_runtime_root[Runtime.CLAUDE], "x")
    junk_file = skill_dir / "CHANGELOG 2.md"
    junk_file.write_text("junk", encoding="utf-8")

    backup_root = tmp_path / "backup"
    monkeypatch.setattr("skill_doctor.config.BACKUP_ROOT", backup_root)
    monkeypatch.setattr("skill_doctor.apply.BACKUP_ROOT", backup_root)

    report = _scan(tmp_runtime_root)
    summary = apply_actions(report, interactive=False)
    assert summary.completed >= 1
    assert not junk_file.exists()


def test_apply_removes_broken_symlink(
    tmp_runtime_root: dict[Runtime, Path],
    make_symlink: Callable[[Path, Path], None],
    monkeypatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "vanished"
    link = tmp_runtime_root[Runtime.CLAUDE] / "broken"
    make_symlink(target, link)

    backup_root = tmp_path / "backup"
    monkeypatch.setattr("skill_doctor.config.BACKUP_ROOT", backup_root)
    monkeypatch.setattr("skill_doctor.apply.BACKUP_ROOT", backup_root)

    report = _scan(tmp_runtime_root)
    summary = apply_actions(report, interactive=False)
    assert summary.completed == 1
    assert not link.is_symlink() and not link.exists()
