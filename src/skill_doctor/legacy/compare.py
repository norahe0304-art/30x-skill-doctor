"""
[INPUT]: Depends on CheckReport records and normalized runtime skill names.
[OUTPUT]: Provides runtime-to-runtime visibility comparisons without transfer decisions.
[POS]: Comparison layer for cross-runtime visibility; it never plans file mutation.
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

import re
from collections import defaultdict

from skill_doctor.models import (
    CheckReport,
    RuntimeComparison,
    RuntimeComparisonItem,
    SkillRecord,
)


def build_runtime_comparison(
    report: CheckReport,
    source_runtime: str,
    target_runtime: str,
) -> RuntimeComparison:
    source = _by_normalized_name(report.skills, source_runtime)
    target = _by_normalized_name(report.skills, target_runtime)
    names = sorted(set(source) | set(target))
    items = [
        _comparison_item(name, source.get(name, []), target.get(name, []))
        for name in names
    ]
    return RuntimeComparison(
        source_runtime=source_runtime,
        target_runtime=target_runtime,
        items=items,
    )


def _comparison_item(
    normalized_name: str,
    source_skills: list[SkillRecord],
    target_skills: list[SkillRecord],
) -> RuntimeComparisonItem:
    name = _display_name(normalized_name, source_skills, target_skills)
    if source_skills and target_skills:
        return RuntimeComparisonItem(
            relation="same_name",
            skill_name=name,
            source_paths=[skill.path for skill in source_skills],
            target_paths=[skill.path for skill in target_skills],
            reason="Same normalized skill name is visible in both runtimes.",
        )
    if source_skills:
        return RuntimeComparisonItem(
            relation="source_only",
            skill_name=name,
            source_paths=[skill.path for skill in source_skills],
            reason="Visible only in the source runtime.",
        )
    return RuntimeComparisonItem(
        relation="target_only",
        skill_name=name,
        target_paths=[skill.path for skill in target_skills],
        reason="Visible only in the target runtime.",
    )


def _by_normalized_name(
    skills: list[SkillRecord], runtime_id: str
) -> dict[str, list[SkillRecord]]:
    grouped: dict[str, list[SkillRecord]] = defaultdict(list)
    for skill in skills:
        if skill.runtime_id == runtime_id:
            grouped[_normalize_name(skill.name)].append(skill)
    return grouped


def _display_name(
    normalized_name: str,
    source_skills: list[SkillRecord],
    target_skills: list[SkillRecord],
) -> str:
    for skill in [*source_skills, *target_skills]:
        if skill.name:
            return skill.name
    return normalized_name


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
