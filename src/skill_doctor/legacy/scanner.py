"""
[INPUT]: Depends on runtime_registry, parser, hashlib, and pathlib for discovery.
[OUTPUT]: Provides scan_skills returning a runtime-first CheckReport.
[POS]: Read-only inventory engine; it never mutates source skill directories.
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from skill_doctor.models import AgentRuntime, CheckReport, Diagnostic, ReviewQueue, SkillRecord
from skill_doctor.parser import parse_skill_file
from skill_doctor.runtime_registry import classify_source


def scan_skills(registry: list[AgentRuntime], limit: int | None = None) -> CheckReport:
    skills: list[SkillRecord] = []
    seen_files: set[Path] = set()

    for runtime in registry:
        for root in runtime.roots:
            if not root.exists():
                continue
            for skill_file in sorted(root.rglob("SKILL.md")):
                resolved = skill_file.resolve()
                if resolved in seen_files:
                    continue
                seen_files.add(resolved)
                skills.append(_record_from_file(skill_file, runtime))
                if limit is not None and len(skills) >= limit:
                    return _report(skills)

    return _report(skills)


def _record_from_file(skill_file: Path, runtime: AgentRuntime) -> SkillRecord:
    skill_dir = skill_file.parent
    raw = skill_file.read_bytes()
    frontmatter, body, diagnostics = parse_skill_file(skill_file)
    source_kind, load_status, protected = classify_source(skill_dir, runtime.id)
    name = str(frontmatter.get("name") or skill_dir.name)
    description = str(frontmatter.get("description") or "")

    if not description:
        diagnostics.append(
            Diagnostic(
                code="missing-description",
                severity="warning",
                message="Skill frontmatter is missing a description.",
                evidence=[str(skill_file)],
                source_rule="rules.required-frontmatter",
            )
        )

    scripts = skill_dir / "scripts"
    references = skill_dir / "references"
    assets = skill_dir / "assets"
    normalized = _normalized_body(body)
    body_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else ""

    return SkillRecord(
        id=_stable_id(runtime.id, skill_dir),
        name=name,
        description=description,
        path=skill_dir,
        skill_file=skill_file,
        runtime_id=runtime.id,
        source_kind=source_kind,
        load_status=load_status,
        protected=protected,
        portable=source_kind not in {"system", "plugin_cache", "plugin_marketplace"},
        frontmatter=frontmatter,
        body=body,
        content_hash=hashlib.sha256(raw).hexdigest(),
        body_hash=body_hash,
        has_scripts=scripts.exists(),
        has_references=references.exists(),
        has_assets=assets.exists(),
        modified_at=skill_file.stat().st_mtime,
        diagnostics=diagnostics,
    )


def _report(skills: list[SkillRecord]) -> CheckReport:
    runtime_counts: dict[str, int] = {}
    for skill in skills:
        runtime_counts[skill.runtime_id] = runtime_counts.get(skill.runtime_id, 0) + 1

    return CheckReport(
        skills=skills,
        runtime_counts=runtime_counts,
        review_queues=[
            ReviewQueue(
                name="protected_sources",
                title="Protected system/plugin/cache skills",
                skills=[skill for skill in skills if skill.protected],
            )
        ],
    )


def _stable_id(runtime_id: str, path: Path) -> str:
    return hashlib.sha1(f"{runtime_id}:{path}".encode()).hexdigest()[:16]


def _normalized_body(body: str) -> str:
    lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped:
            lines.append(stripped.lower())
    return "\n".join(lines)
