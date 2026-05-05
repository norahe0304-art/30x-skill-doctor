"""
[INPUT]: 依赖 pytest fixture 机制与 pathlib，构造临时 runtime/skill 树。
[OUTPUT]: 共享 fixture: tmp_runtime_root（4 个 runtime 子目录），make_skill 工厂函数。
[POS]: 测试夹具层。Phase 1 已落地基础 fixture，后续 phase 增补。
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from skill_doctor.models import Runtime


def _write_skill(root: Path, name: str, body: str = "Body content.\n", *,
                 description: str = "Test skill", version: str | None = "1.0.0",
                 frontmatter_extra: str = "") -> Path:
    """Write a SKILL.md under <root>/<name>/SKILL.md and return the directory."""
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    parts = ["---", f"name: {name}", f'description: "{description}"']
    if version is not None:
        parts.extend(["metadata:", f"  version: {version}"])
    if frontmatter_extra:
        parts.append(frontmatter_extra)
    parts.append("---")
    parts.append(body)
    skill_md.write_text("\n".join(parts), encoding="utf-8")
    return skill_dir


@pytest.fixture
def tmp_runtime_root(tmp_path: Path) -> dict[Runtime, Path]:
    """Create 4 runtime root directories under tmp_path. Returns mapping."""
    layout = {
        Runtime.CLAUDE: tmp_path / ".claude" / "skills",
        Runtime.CODEX: tmp_path / ".codex" / "skills",
        Runtime.OPENCLAW: tmp_path / ".openclaw" / "skills",
        Runtime.AGENTS: tmp_path / ".agents" / "skills",
    }
    for path in layout.values():
        path.mkdir(parents=True, exist_ok=True)
    return layout


@pytest.fixture
def make_skill() -> Callable[..., Path]:
    """Factory for writing a single SKILL.md inside a runtime root."""
    return _write_skill


@pytest.fixture
def make_symlink() -> Callable[[Path, Path], None]:
    """Factory for creating a directory symlink (relative target if given as Path)."""

    def _make(target: Path, link: Path) -> None:
        link.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(target, link)

    return _make
