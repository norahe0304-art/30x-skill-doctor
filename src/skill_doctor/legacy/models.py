"""
[INPUT]: Depends on pydantic for stable JSON-ready contracts.
[OUTPUT]: Provides runtime, skill, finding, judgment, visibility, comparison, and manifest models.
[POS]: Core schema layer shared by scanner, rules, comparison, config, and CLI.
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

SourceKind = Literal[
    "user",
    "project",
    "system",
    "plugin_cache",
    "plugin_marketplace",
    "shared",
    "warehouse",
    "migration_bundle",
    "unknown",
]
LoadStatus = Literal["active", "available", "library", "bundled", "imported", "unknown"]
Severity = Literal["info", "warning", "error", "blocked"]
FindingSeverity = Literal["info", "attention", "high"]
FindingConfidence = Literal["low", "medium", "high"]
SourceMaturity = Literal[
    "standard",
    "runtime_practice",
    "emerging",
    "community_practice",
    "product_hygiene",
]
PrimaryBucket = Literal["needs_attention", "no_cleanup_action"]
SignalKind = Literal[
    "execution_surface",
    "exact_copy",
    "likely_overlap",
    "typosquat_candidate",
]
OwnerKind = Literal["user", "project", "shared", "runtime", "plugin", "warehouse", "unknown"]
DiscoveredByRuntime = Literal["yes", "no", "unknown"]
MutationAllowed = Literal["metadata_only", "none"]
UseCategory = Literal[
    "coding",
    "docs",
    "data",
    "browser",
    "image-video",
    "seo",
    "ads",
    "design",
    "product",
    "ops",
    "research",
    "writing",
    "personal",
    "unknown",
]
HousekeepingStatus = Literal[
    "active_candidate",
    "background",
    "runtime_managed",
    "exact_copy",
    "needs_attention",
    "legacy_candidate",
    "cross_runtime_pair",
]
QualityLens = Literal[
    "description_needs_work",
    "too_broad",
    "good_scope",
    "large_skill",
    "script_surface",
    "broken_metadata",
]
VisibilityHint = Literal[
    "no_action",
    "review_evidence",
    "label_if_useful",
    "review_if_needed",
    "compare_if_needed",
    "fix_metadata",
]


class AgentRuntime(BaseModel):
    id: str
    name: str
    roots: list[Path] = Field(default_factory=list)
    first_class: bool = False
    apply_enabled: bool = False


class Diagnostic(BaseModel):
    code: str
    severity: Severity
    message: str
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    suggested_action: str = "review"
    source_rule: str = "unknown"


class StandardRef(BaseModel):
    label: str
    maturity: SourceMaturity


class Finding(BaseModel):
    rule_id: str
    title: str
    reason: str
    severity: FindingSeverity
    confidence: FindingConfidence
    evidence: list[str] = Field(default_factory=list)
    standard_refs: list[StandardRef] = Field(default_factory=list)
    what_next: str = "Review this skill before relying on it."


class SkillJudgment(BaseModel):
    primary_bucket: PrimaryBucket
    signals: list[SignalKind] = Field(default_factory=list)
    owner: OwnerKind
    discovered_by_runtime: DiscoveredByRuntime
    mutation_allowed: MutationAllowed
    findings: list[Finding] = Field(default_factory=list)


class HousekeepingJudgment(BaseModel):
    use_category: UseCategory
    housekeeping_status: HousekeepingStatus
    quality_lens: list[QualityLens] = Field(default_factory=list)
    collection_tags: list[str] = Field(default_factory=list)
    visibility_hint: VisibilityHint
    confidence: float = 0.0
    reason: str = ""


class SkillRecord(BaseModel):
    id: str
    name: str
    description: str = ""
    path: Path
    skill_file: Path
    runtime_id: str
    source_kind: SourceKind
    load_status: LoadStatus
    protected: bool = False
    portable: bool = True
    frontmatter: dict[str, object] = Field(default_factory=dict)
    body: str = ""
    content_hash: str
    body_hash: str
    has_scripts: bool = False
    has_references: bool = False
    has_assets: bool = False
    modified_at: float = 0.0
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    judgment: SkillJudgment | None = None
    housekeeping: HousekeepingJudgment | None = None


class DuplicateGroup(BaseModel):
    id: str
    kind: Literal["same-content-copy", "near-duplicate", "capability-overlap"]
    skills: list[SkillRecord]
    reason: str
    confidence: float


class ReviewQueue(BaseModel):
    name: str
    title: str
    skills: list[SkillRecord] = Field(default_factory=list)


class CheckReport(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    skills: list[SkillRecord] = Field(default_factory=list)
    runtime_counts: dict[str, int] = Field(default_factory=dict)
    review_queues: list[ReviewQueue] = Field(default_factory=list)
    duplicate_groups: list[DuplicateGroup] = Field(default_factory=list)


class VisibilityRecord(BaseModel):
    kind: Literal[
        "record_visibility",
    ]
    skill_id: str
    skill_name: str
    path: Path
    reason: str
    confidence: float = 1.0
    reversible: bool = True
    metadata: dict[str, object] = Field(default_factory=dict)


class VisibilitySnapshot(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    records: list[VisibilityRecord] = Field(default_factory=list)
    review_queues: list[ReviewQueue] = Field(default_factory=list)


class RuntimeComparisonItem(BaseModel):
    relation: Literal["same_name", "source_only", "target_only"]
    skill_name: str
    source_paths: list[Path] = Field(default_factory=list)
    target_paths: list[Path] = Field(default_factory=list)
    reason: str


class RuntimeComparison(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_runtime: str
    target_runtime: str
    items: list[RuntimeComparisonItem] = Field(default_factory=list)


class RunManifest(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    run_id: str
    kind: Literal["snapshot"]
    applied: bool
    written_files: list[str] = Field(default_factory=list)
    records: list[dict[str, object]] = Field(default_factory=list)
