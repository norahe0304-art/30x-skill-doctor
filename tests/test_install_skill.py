"""Tests for the install-skill command — the most adoption-critical surface.

We don't touch the user's real ~/.claude — every test redirects SKILL_TARGETS
to a tmp tree so the suite is hermetic and idempotency is observable."""

from __future__ import annotations

from pathlib import Path

import pytest

from skill_doctor import install_skill


@pytest.fixture
def isolated_targets(tmp_path, monkeypatch):
    """Redirect SKILL_TARGETS to a tmp home so the test never touches user state."""
    new_targets = {
        "claude":   ("Claude Code", tmp_path / ".claude"   / "skills" / "skill-doctor"),
        "codex":    ("Codex",       tmp_path / ".codex"    / "skills" / "skill-doctor"),
        "cursor":   ("Cursor",      tmp_path / ".cursor"   / "skills" / "skill-doctor"),
        "openclaw": ("OpenClaw",    tmp_path / ".openclaw" / "skills" / "skill-doctor"),
    }
    monkeypatch.setattr(install_skill, "SKILL_TARGETS", new_targets)
    return tmp_path


def test_template_is_packaged(isolated_targets: Path) -> None:
    """The SKILL.md template must be readable via importlib.resources — if it
    isn't, the wheel build is missing the templates dir and install will break
    silently in production."""
    content = install_skill._read_template()
    assert content.lstrip().startswith("---")
    assert "name: skill-doctor" in content
    assert "description:" in content
    # description should be long enough to actually trigger Agent invocation
    assert len(content) > 500


def test_install_to_unknown_runtime() -> None:
    result = install_skill.install_skill_for("nonexistent")
    assert result.status == "error"
    assert "unknown runtime" in result.detail


def test_install_writes_file(isolated_targets: Path) -> None:
    result = install_skill.install_skill_for("claude")
    assert result.status == "installed"
    assert result.dest.exists()
    content = result.dest.read_text(encoding="utf-8")
    assert "name: skill-doctor" in content


def test_install_is_idempotent(isolated_targets: Path) -> None:
    """Second install without --force should skip, not overwrite."""
    first = install_skill.install_skill_for("claude")
    assert first.status == "installed"
    second = install_skill.install_skill_for("claude")
    assert second.status == "skipped_exists"


def test_force_overwrites(isolated_targets: Path) -> None:
    install_skill.install_skill_for("claude")
    # write garbage to verify --force replaces it
    target = install_skill.SKILL_TARGETS["claude"][1] / "SKILL.md"
    target.write_text("stale content", encoding="utf-8")
    result = install_skill.install_skill_for("claude", force=True)
    assert result.status == "overwritten"
    assert "name: skill-doctor" in target.read_text(encoding="utf-8")


def test_detected_runtimes_excludes_missing(isolated_targets: Path) -> None:
    # Nothing exists yet under tmp_path — detection should return empty
    assert install_skill.detected_runtimes() == []
    # Create the .claude root, detection should find it
    (isolated_targets / ".claude").mkdir(parents=True)
    detected = install_skill.detected_runtimes()
    assert detected == ["claude"]


def test_install_all_only_detected(isolated_targets: Path) -> None:
    (isolated_targets / ".claude").mkdir(parents=True)
    (isolated_targets / ".codex").mkdir(parents=True)
    results = install_skill.install_skill_all(only_detected=True)
    runtimes_installed = {r.runtime for r in results}
    assert runtimes_installed == {"claude", "codex"}
    # The other two should NOT have been touched
    assert not (isolated_targets / ".cursor").exists()
    assert not (isolated_targets / ".openclaw").exists()


def test_install_all_creates_runtime_root(isolated_targets: Path) -> None:
    """only_detected=False should create roots that don't exist yet."""
    results = install_skill.install_skill_all(only_detected=False)
    assert all(r.status == "installed" for r in results)
    assert (isolated_targets / ".cursor" / "skills" / "skill-doctor" / "SKILL.md").exists()
