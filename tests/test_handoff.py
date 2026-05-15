"""
[INPUT]: 依赖 conftest 的 tmp_runtime_root / make_skill,
         依赖 skill_doctor.handoff / models / asm_bridge.QualityRow。
[OUTPUT]: 验证 write_drift_handoff / write_stale_handoff / write_quality_handoff
         三个函数的输出文件结构 (disclaimer + task header + per-item section)
         + 边界 (空 list / diff > cap / 缺失 SKILL.md)。
[POS]: handoff 模块行为测试. 与 test_apply.py 互补 (后者测交互流, 这里测内容生成).
[PROTOCOL]: 变更时更新此头部, 然后检查 AGENTS.md
"""

from __future__ import annotations

from pathlib import Path

import pytest

from skill_doctor import handoff as handoff_mod
from skill_doctor.asm_bridge import QualityRow
from skill_doctor.models import (
    AnalysisReport,
    Category,
    DriftGroup,
    Runtime,
    SkillInstance,
    StaleSkill,
)


@pytest.fixture(autouse=True)
def _redirect_handoff_root(monkeypatch, tmp_path):
    """Redirect HANDOFF_ROOT into tmp so tests can't touch ~/.skill-doctor/."""
    monkeypatch.setattr(handoff_mod, "HANDOFF_ROOT", tmp_path / "handoff")


def _make_inst(skill_md: Path, runtime: Runtime, version: str | None,
               body_hash: str, description: str = "test") -> SkillInstance:
    return SkillInstance(
        path=skill_md.parent,
        skill_md=skill_md,
        runtime=runtime,
        name=skill_md.parent.name,
        dir_name=skill_md.parent.name,
        description=description,
        version=version,
        body_hash=body_hash,
        body_lines=skill_md.read_text().count("\n") if skill_md.exists() else 0,
        is_symlink=False,
        symlink_target=None,
        real_path=skill_md.parent.resolve(),
        file_is_symlink=False,
        mtime=0.0,
        category=Category.UNCATEGORIZED,
    )


def _empty_report(drifts=None, stale=None, instances=None) -> AnalysisReport:
    return AnalysisReport(
        instances=instances or [],
        duplicates=[],
        drifts=drifts or [],
        broken_links=[],
        junk_files=[],
        stale=stale or [],
    )


# ----- drift handoff ---------------------------------------------------------

def test_drift_handoff_includes_disclaimer_and_task(make_skill, tmp_runtime_root):
    a = make_skill(tmp_runtime_root[Runtime.CLAUDE], "foo", body="claude body\n")
    b = make_skill(tmp_runtime_root[Runtime.OPENCLAW], "foo", body="openclaw body\n",
                   version=None)
    inst_a = _make_inst(a / "SKILL.md", Runtime.CLAUDE, "1.1.0", "h1")
    inst_b = _make_inst(b / "SKILL.md", Runtime.OPENCLAW, None, "h2")
    drift = DriftGroup(name="foo", instances=[inst_a, inst_b])

    out = handoff_mod.write_drift_handoff(_empty_report(drifts=[drift]))
    text = out.read_text(encoding="utf-8")

    assert "for an AI, not a human" in text
    assert "# Drift triage" in text
    assert "### 1. foo" in text
    assert "```diff" in text  # pair render emitted a unified diff


def test_drift_handoff_caps_diff_when_structurally_divergent(
    make_skill, tmp_runtime_root, monkeypatch,
):
    a = make_skill(tmp_runtime_root[Runtime.CLAUDE], "big",
                   body="\n".join(f"alpha line {i}" for i in range(200)) + "\n")
    b = make_skill(tmp_runtime_root[Runtime.OPENCLAW], "big",
                   body="\n".join(f"beta line {i}" for i in range(200)) + "\n",
                   version=None)
    inst_a = _make_inst(a / "SKILL.md", Runtime.CLAUDE, "1.0.0", "h1")
    inst_b = _make_inst(b / "SKILL.md", Runtime.OPENCLAW, None, "h2")
    drift = DriftGroup(name="big", instances=[inst_a, inst_b])

    monkeypatch.setattr(handoff_mod, "DIFF_LINE_CAP", 10)
    out = handoff_mod.write_drift_handoff(_empty_report(drifts=[drift]))
    text = out.read_text(encoding="utf-8")
    assert "Structural divergence" in text
    assert "```diff" not in text


def test_drift_handoff_handles_three_or_more_instances(make_skill, tmp_runtime_root):
    a = make_skill(tmp_runtime_root[Runtime.CLAUDE], "tri", body="a\n")
    b = make_skill(tmp_runtime_root[Runtime.CODEX], "tri", body="b\n", version=None)
    c = make_skill(tmp_runtime_root[Runtime.OPENCLAW], "tri", body="c\n", version=None)
    drift = DriftGroup(
        name="tri",
        instances=[
            _make_inst(a / "SKILL.md", Runtime.CLAUDE, "1.0.0", "h1"),
            _make_inst(b / "SKILL.md", Runtime.CODEX, None, "h2"),
            _make_inst(c / "SKILL.md", Runtime.OPENCLAW, None, "h3"),
        ],
    )
    out = handoff_mod.write_drift_handoff(_empty_report(drifts=[drift]))
    text = out.read_text(encoding="utf-8")
    assert "3+ divergent instances" in text


# ----- stale handoff ---------------------------------------------------------

def test_stale_handoff_emits_path_and_body(make_skill, tmp_runtime_root):
    skill = make_skill(tmp_runtime_root[Runtime.OPENCLAW], "old-skill",
                       body="content of old skill\n")
    inst = _make_inst(skill / "SKILL.md", Runtime.OPENCLAW, "1.0.0", "h1",
                      description="An old thing")
    stale = StaleSkill(instance=inst, days_ago=180)

    out = handoff_mod.write_stale_handoff(_empty_report(stale=[stale]))
    text = out.read_text(encoding="utf-8")

    assert "for an AI, not a human" in text
    assert "# Stale skill triage" in text
    assert "### 1. old-skill (180 days idle)" in text
    assert "openclaw" in text
    assert "An old thing" in text


# ----- quality handoff -------------------------------------------------------

def test_quality_handoff_renders_suggestions_and_caps_top_n(
    make_skill, tmp_runtime_root,
):
    skills = [
        make_skill(tmp_runtime_root[Runtime.CLAUDE], f"low-{i}",
                   body=f"low quality body {i}\n")
        for i in range(15)
    ]
    rows = [
        QualityRow(
            name=p.name,
            score=20 + i,
            grade="F",
            suggestions=[f"fix-{i}-a", f"fix-{i}-b"],
            path=p,
        )
        for i, p in enumerate(skills)
    ]
    out = handoff_mod.write_quality_handoff(rows, top_n=5)
    text = out.read_text(encoding="utf-8")

    assert "for an AI, not a human" in text
    assert "# Quality fix triage" in text
    # Only top_n=5 included.
    assert "### 5." in text
    assert "### 6." not in text
    # Suggestions are surfaced verbatim.
    assert "fix-0-a" in text


def test_quality_handoff_handles_unreadable_skill_md(tmp_path):
    """Row whose path has no SKILL.md should not blow up — placeholder is shown."""
    bogus = tmp_path / "ghost"
    bogus.mkdir()
    row = QualityRow(name="ghost", score=10, grade="F",
                     suggestions=["x"], path=bogus)
    out = handoff_mod.write_quality_handoff([row])
    text = out.read_text(encoding="utf-8")
    assert "SKILL.md unreadable" in text


# ----- defensive: empty inputs -----------------------------------------------

def test_write_drift_handoff_with_empty_drifts_still_writes_file():
    """Defensive: even if called with 0 drifts (apply.py guards this, but
    handoff.py shouldn't crash). The output stays valid markdown."""
    out = handoff_mod.write_drift_handoff(_empty_report(drifts=[]))
    text = out.read_text(encoding="utf-8")
    assert "# Drift triage" in text
    assert "## Drifted skills" in text


def test_write_stale_handoff_with_empty_stale_still_writes_file():
    out = handoff_mod.write_stale_handoff(_empty_report(stale=[]))
    text = out.read_text(encoding="utf-8")
    assert "# Stale skill triage" in text
