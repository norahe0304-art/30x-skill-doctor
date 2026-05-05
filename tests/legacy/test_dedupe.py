from __future__ import annotations

from skill_doctor.rules import build_duplicate_groups, enrich_report
from skill_doctor.runtime_registry import build_runtime_registry

from skill_doctor.scanner import scan_skills


def test_duplicate_groups_detect_exact_content_copies(skill_world):
    registry = build_runtime_registry(home=skill_world["home"], project=skill_world["project"])
    report = scan_skills(registry)

    groups = build_duplicate_groups(report.skills)
    exact_groups = [group for group in groups if group.kind == "same-content-copy"]

    assert exact_groups
    assert {"duplicate-a", "duplicate-b"} <= {skill.name for skill in exact_groups[0].skills}


def test_enrichment_is_idempotent(skill_world):
    registry = build_runtime_registry(home=skill_world["home"], project=skill_world["project"])
    report = scan_skills(registry)

    enrich_report(report)
    first_counts = {skill.id: len(skill.diagnostics) for skill in report.skills}
    enrich_report(report)
    second_counts = {skill.id: len(skill.diagnostics) for skill in report.skills}

    assert second_counts == first_counts
