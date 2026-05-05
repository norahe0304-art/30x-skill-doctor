"""
[INPUT]: Depends on Skill Doctor Pydantic models for compact data projection.
[OUTPUT]: Provides JSON-safe dictionaries that omit large SKILL.md bodies.
[POS]: Serialization boundary for CLI JSON and index cache.
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

from typing import Any

from skill_doctor.models import (
    CheckReport,
    DuplicateGroup,
    ReviewQueue,
    RunManifest,
    RuntimeComparison,
    RuntimeComparisonItem,
    SkillRecord,
    VisibilityRecord,
    VisibilitySnapshot,
)


def compact_model(model: Any, limit: int | None = None) -> dict[str, Any]:
    if isinstance(model, CheckReport):
        return _compact_check_report(model, limit=limit)
    if isinstance(model, VisibilitySnapshot):
        return _compact_visibility_snapshot(model)
    if isinstance(model, RuntimeComparison):
        return _compact_runtime_comparison(model)
    if isinstance(model, RunManifest):
        return _compact_run_manifest(model)
    return model.model_dump(mode="json")


def _compact_check_report(report: CheckReport, limit: int | None = None) -> dict[str, Any]:
    skills = report.skills[:limit] if limit is not None else report.skills
    duplicate_groups = (
        report.duplicate_groups[:limit] if limit is not None else report.duplicate_groups
    )
    return {
        "generated_at": report.generated_at.isoformat(),
        "runtime_counts": report.runtime_counts,
        "skills_total": len(report.skills),
        "skills": [_compact_skill(skill) for skill in skills],
        "review_queues": [_compact_queue(queue, limit=limit) for queue in report.review_queues],
        "duplicate_groups_total": len(report.duplicate_groups),
        "duplicate_groups": [
            _compact_duplicate_group(group, limit=limit) for group in duplicate_groups
        ],
    }


def _compact_skill(skill: SkillRecord) -> dict[str, Any]:
    return {
        "id": skill.id,
        "name": skill.name,
        "description": skill.description,
        "path": str(skill.path),
        "skill_file": str(skill.skill_file),
        "runtime_id": skill.runtime_id,
        "source_kind": skill.source_kind,
        "load_status": skill.load_status,
        "protected": skill.protected,
        "portable": skill.portable,
        "frontmatter_keys": sorted(skill.frontmatter.keys()),
        "content_hash": skill.content_hash,
        "body_hash": skill.body_hash,
        "has_scripts": skill.has_scripts,
        "has_references": skill.has_references,
        "has_assets": skill.has_assets,
        "modified_at": skill.modified_at,
        "diagnostics": [item.model_dump(mode="json") for item in skill.diagnostics],
        "judgment": skill.judgment.model_dump(mode="json") if skill.judgment else None,
        "housekeeping": (
            skill.housekeeping.model_dump(mode="json") if skill.housekeeping else None
        ),
    }


def _compact_visibility_snapshot(snapshot: VisibilitySnapshot) -> dict[str, Any]:
    return {
        "generated_at": snapshot.generated_at.isoformat(),
        "records": [_compact_visibility_record(record) for record in snapshot.records],
        "review_queues": [_compact_queue(queue) for queue in snapshot.review_queues],
    }


def _compact_visibility_record(record: VisibilityRecord) -> dict[str, Any]:
    return {
        "kind": record.kind,
        "skill_id": record.skill_id,
        "skill_name": record.skill_name,
        "path": str(record.path),
        "reason": record.reason,
        "confidence": record.confidence,
        "reversible": record.reversible,
        "metadata": record.metadata,
    }


def _compact_runtime_comparison(comparison: RuntimeComparison) -> dict[str, Any]:
    return {
        "generated_at": comparison.generated_at.isoformat(),
        "source_runtime": comparison.source_runtime,
        "target_runtime": comparison.target_runtime,
        "items": [_compact_runtime_comparison_item(item) for item in comparison.items],
    }


def _compact_runtime_comparison_item(item: RuntimeComparisonItem) -> dict[str, Any]:
    return {
        "relation": item.relation,
        "skill_name": item.skill_name,
        "source_paths": [str(path) for path in item.source_paths],
        "target_paths": [str(path) for path in item.target_paths],
        "reason": item.reason,
    }


def _compact_run_manifest(manifest: RunManifest) -> dict[str, Any]:
    return {
        "generated_at": manifest.generated_at.isoformat(),
        "run_id": manifest.run_id,
        "kind": manifest.kind,
        "applied": manifest.applied,
        "written_files": manifest.written_files,
        "records": manifest.records,
    }


def _compact_queue(queue: ReviewQueue, limit: int | None = None) -> dict[str, Any]:
    skills = queue.skills[:limit] if limit is not None else queue.skills
    return {
        "name": queue.name,
        "title": queue.title,
        "total": len(queue.skills),
        "skills": [_skill_ref(skill) for skill in skills],
    }


def _compact_duplicate_group(group: DuplicateGroup, limit: int | None = None) -> dict[str, Any]:
    skills = group.skills[:limit] if limit is not None else group.skills
    return {
        "id": group.id,
        "kind": group.kind,
        "reason": group.reason,
        "confidence": group.confidence,
        "total": len(group.skills),
        "skills": [_skill_ref(skill) for skill in skills],
    }


def _skill_ref(skill: SkillRecord) -> dict[str, str]:
    return {"id": skill.id, "name": skill.name, "path": str(skill.path)}
