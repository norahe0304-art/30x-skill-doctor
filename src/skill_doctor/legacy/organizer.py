"""
[INPUT]: Depends on enriched SkillRecord judgments and duplicate groups.
[OUTPUT]: Provides deterministic visibility categories, statuses, tags, and hints.
[POS]: Metadata-only visibility layer; turns health signals into shelves without moving files.
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from skill_doctor.models import (
    DuplicateGroup,
    HousekeepingJudgment,
    HousekeepingStatus,
    QualityLens,
    SkillRecord,
    UseCategory,
)

CATEGORY_TERMS: dict[UseCategory, tuple[str, ...]] = {
    "seo": (
        "seo",
        "serp",
        "schema",
        "sitemap",
        "backlink",
        "keyword",
        "hreflang",
        "redirect",
    ),
    "ads": (
        "ads",
        "ad ",
        "advertising",
        "campaign",
        "ppc",
        "meta ads",
        "tiktok",
        "linkedin",
        "youtube",
    ),
    "image-video": (
        "image",
        "video",
        "remotion",
        "flux",
        "tts",
        "podcast",
        "photo",
        "visual",
        "figma-generate",
    ),
    "browser": ("browser", "playwright", "scrape", "web automation", "chrome"),
    "design": ("figma", "ui", "ux", "design", "hig", "tailwind", "native ui"),
    "docs": ("docx", "pdf", "slides", "presentation", "spreadsheet", "document"),
    "data": ("data", "analytics", "csv", "excel", "bigquery", "dataset", "metrics"),
    "coding": (
        "code",
        "refactor",
        "test",
        "github",
        "ci",
        "architecture",
        "debug",
        "deploy",
    ),
    "product": ("product", "roadmap", "pricing", "onboarding", "persona", "jtbd"),
    "ops": ("ops", "backup", "monitor", "incident", "support", "workflow"),
    "research": ("research", "literature", "paper", "scout", "investigate"),
    "writing": ("writing", "copywriting", "copy editing", "content", "blog", "linkedin"),
    "personal": ("personal", "memory", "identity", "preference"),
}

GENERIC_TERMS = {"helper", "helpers", "utils", "tools", "workflow", "skill"}
MAX_SKILL_LINES = 500


def apply_housekeeping(skills: list[SkillRecord], groups: list[DuplicateGroup]) -> None:
    exact_ids = _duplicate_ids(groups, kind="same-content-copy")
    cross_runtime_ids = _cross_runtime_pair_ids(skills)
    for skill in skills:
        skill.housekeeping = build_housekeeping(skill, exact_ids, cross_runtime_ids)


def build_housekeeping(
    skill: SkillRecord, exact_ids: set[str], cross_runtime_ids: set[str]
) -> HousekeepingJudgment:
    category, category_tags, category_confidence = _category_for(skill)
    quality = _quality_lens(skill, category, category_tags)
    status = _status_for(skill, exact_ids, cross_runtime_ids)
    visibility_hint = _visibility_hint_for(status, quality)
    tags = _tags_for(skill, category, category_tags, status, quality)
    return HousekeepingJudgment(
        use_category=category,
        housekeeping_status=status,
        quality_lens=quality,
        collection_tags=tags,
        visibility_hint=visibility_hint,
        confidence=_confidence_for(status, category_confidence, quality),
        reason=_reason_for(status, category, quality),
    )


def _category_for(skill: SkillRecord) -> tuple[UseCategory, list[str], float]:
    name_text = f"{skill.name} {skill.path.name}".lower()
    description_text = skill.description.lower()
    path_text = str(skill.path).lower()
    scores: Counter[UseCategory] = Counter()
    tags: list[str] = []

    for category, terms in CATEGORY_TERMS.items():
        for term in terms:
            if term in name_text:
                scores[category] += 3
            if term in path_text:
                scores[category] += 2
            if term in description_text:
                scores[category] += 1
        if scores[category] > 0:
            tags.append(category)

    if not scores:
        return "unknown", [], 0.0

    category, score = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[0]
    confidence = min(0.95, 0.45 + score / 10)
    return category, sorted(tags), confidence


def _status_for(
    skill: SkillRecord, exact_ids: set[str], cross_runtime_ids: set[str]
) -> HousekeepingStatus:
    if skill.judgment and skill.judgment.primary_bucket == "needs_attention":
        return "needs_attention"
    if skill.protected or skill.source_kind in {"system", "plugin_cache", "plugin_marketplace"}:
        return "runtime_managed"
    if skill.id in exact_ids:
        return "exact_copy"
    if skill.id in cross_runtime_ids:
        return "cross_runtime_pair"
    if _is_background(skill):
        return "background"
    if _strong_legacy_name(skill):
        return "legacy_candidate"
    return "active_candidate"


def _quality_lens(
    skill: SkillRecord, category: UseCategory, category_tags: list[str]
) -> list[QualityLens]:
    values: list[QualityLens] = []
    description = skill.description.strip()
    if not description or len(description) < 30 or _has_vague_description(skill):
        values.append("description_needs_work")
    if len(category_tags) > 2 or _generic_name(skill.name):
        values.append("too_broad")
    if len(skill.body.splitlines()) > MAX_SKILL_LINES:
        values.append("large_skill")
    if skill.has_scripts:
        values.append("script_surface")
    if skill.judgment and any(
        finding.rule_id == "broken-skill-file" for finding in skill.judgment.findings
    ):
        values.append("broken_metadata")
    if not values and category != "unknown":
        values.append("good_scope")
    return _dedupe_quality(values)


def _visibility_hint_for(status: HousekeepingStatus, quality: list[QualityLens]) -> str:
    if status == "needs_attention":
        if "broken_metadata" in quality:
            return "fix_metadata"
        return "review_evidence"
    if status == "exact_copy":
        return "review_if_needed"
    if status == "cross_runtime_pair":
        return "compare_if_needed"
    if status == "legacy_candidate":
        return "review_if_needed"
    if "description_needs_work" in quality or "too_broad" in quality:
        return "label_if_useful"
    return "no_action"


def _tags_for(
    skill: SkillRecord,
    category: UseCategory,
    category_tags: list[str],
    status: HousekeepingStatus,
    quality: list[QualityLens],
) -> list[str]:
    tags = {
        category,
        skill.runtime_id,
        skill.source_kind.replace("_", "-"),
        status.replace("_", "-"),
        *category_tags,
        *(lens.replace("_", "-") for lens in quality),
    }
    if skill.has_scripts:
        tags.add("script-surface")
    if skill.protected:
        tags.add("runtime-owned")
    tags.discard("unknown")
    return sorted(tags)


def _confidence_for(
    status: HousekeepingStatus, category_confidence: float, quality: list[QualityLens]
) -> float:
    status_confidence = {
        "needs_attention": 0.95,
        "runtime_managed": 0.95,
        "exact_copy": 0.95,
        "cross_runtime_pair": 0.85,
        "background": 0.85,
        "legacy_candidate": 0.75,
        "active_candidate": 0.75,
    }[status]
    quality_penalty = 0.1 if "too_broad" in quality or "description_needs_work" in quality else 0
    confidence = (status_confidence + category_confidence) / 2 - quality_penalty
    return round(max(0.0, min(0.99, confidence)), 2)


def _reason_for(
    status: HousekeepingStatus, category: UseCategory, quality: list[QualityLens]
) -> str:
    if status == "needs_attention":
        return "Health check found evidence that should be reviewed first."
    if status == "runtime_managed":
        return "Runtime or plugin managed source; outside Skill Doctor file changes."
    if status == "exact_copy":
        return "Exact content copy found in more than one visible location."
    if status == "cross_runtime_pair":
        return "Same-name user skill appears in more than one first-class runtime."
    if status == "background":
        return "Imported, shared, warehouse, or library skill visible as background."
    if status == "legacy_candidate":
        return "Folder name strongly suggests an old backup, copy, or migration marker."
    if "description_needs_work" in quality:
        return "Active-looking skill with a short or broad runtime description."
    return f"Active-looking {category} skill observed in its runtime."


def _duplicate_ids(groups: list[DuplicateGroup], *, kind: str) -> set[str]:
    return {
        skill.id
        for group in groups
        if group.kind == kind
        for skill in group.skills
    }


def _cross_runtime_pair_ids(skills: list[SkillRecord]) -> set[str]:
    by_name: dict[str, list[SkillRecord]] = defaultdict(list)
    for skill in skills:
        if skill.protected or skill.source_kind not in {"user", "shared", "project"}:
            continue
        if skill.runtime_id not in {"claude", "codex", "shared"}:
            continue
        by_name[_normalize_name(skill.name)].append(skill)
    return {
        skill.id
        for matches in by_name.values()
        if len({skill.runtime_id for skill in matches}) > 1
        for skill in matches
    }


def _is_background(skill: SkillRecord) -> bool:
    return (
        skill.source_kind in {"shared", "warehouse", "migration_bundle"}
        or skill.load_status in {"library", "imported", "bundled"}
    )


def _strong_legacy_name(skill: SkillRecord) -> bool:
    name = skill.path.name.lower()
    return bool(re.search(r"(backup|bak|old|copy|migration)[-_]?\d{6,}", name))


def _has_vague_description(skill: SkillRecord) -> bool:
    text = skill.description.strip().lower()
    return text in {"useful workflow", "helper script", "workflow", "helper"}


def _generic_name(name: str) -> bool:
    tokens = set(re.split(r"[^a-z0-9]+", name.lower()))
    return bool(tokens & GENERIC_TERMS)


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _dedupe_quality(values: list[QualityLens]) -> list[QualityLens]:
    seen: set[QualityLens] = set()
    unique: list[QualityLens] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique
