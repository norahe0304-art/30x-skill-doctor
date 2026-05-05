from __future__ import annotations

from skill_doctor.runtime_registry import build_runtime_registry

from skill_doctor.scanner import scan_skills


def test_scan_classifies_runtime_source_and_protected_paths(skill_world):
    registry = build_runtime_registry(home=skill_world["home"], project=skill_world["project"])

    report = scan_skills(registry)
    by_name = {skill.name: skill for skill in report.skills}

    assert by_name["architecture-advisor"].runtime_id == "codex"
    assert by_name["copywriter"].runtime_id == "claude"
    assert by_name["30x-image.backup-1777235615597"].runtime_id == "shared"
    assert by_name["canvas"].runtime_id == "cursor"
    assert by_name["warehouse-skill"].runtime_id == "openclaw"
    assert by_name["openai-docs"].protected is True
    assert by_name["openai-docs"].source_kind == "system"


def test_scan_report_groups_counts_by_runtime(skill_world):
    registry = build_runtime_registry(home=skill_world["home"], project=skill_world["project"])

    report = scan_skills(registry)

    assert report.runtime_counts["codex"] == 2
    assert report.runtime_counts["claude"] == 1
    assert report.runtime_counts["shared"] == 5
    assert report.runtime_counts["cursor"] == 1
    assert report.runtime_counts["openclaw"] == 1
