"""
[INPUT]: Depends on scanned SkillRecord objects, rule_catalog, and rapidfuzz.
[OUTPUT]: Provides evidence-first judgments, review queues, duplicate groups,
and visibility snapshots.
[POS]: Deterministic rule engine; scripts are signals unless concrete evidence escalates them.
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

import re
from collections import defaultdict

from rapidfuzz import fuzz

from skill_doctor.models import (
    CheckReport,
    Diagnostic,
    DuplicateGroup,
    Finding,
    OwnerKind,
    ReviewQueue,
    SignalKind,
    SkillJudgment,
    SkillRecord,
    VisibilityRecord,
    VisibilitySnapshot,
)
from skill_doctor.organizer import apply_housekeeping
from skill_doctor.rule_catalog import build_finding

DANGEROUS_SHELL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("curl pipe shell", re.compile(r"\b(curl|wget)\b[^\n|;]*\|\s*(sh|bash)\b")),
    ("remote shell execute", re.compile(r"\b(sh|bash)\s+-c\s+['\"]?\$?\(?(curl|wget)\b")),
    ("recursive force delete", re.compile(r"\brm\s+-[^\n]*rf|-[^\n]*fr\b")),
    ("sudo command", re.compile(r"\bsudo\b")),
    ("world-writable chmod", re.compile(r"\bchmod\s+777\b")),
    ("netcat shell", re.compile(r"\b(nc|netcat)\b")),
    ("interactive bash", re.compile(r"\bbash\s+-i\b")),
)

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("openai api key", re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b")),
    ("github token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b")),
    ("aws access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "credential path",
        re.compile(r"((?<![A-Za-z0-9_])\.env\b|~/\.ssh\b|~/\.aws\b|id_rsa\b|id_ed25519\b)"),
    ),
    (
        "environment secret",
        re.compile(r"\b[A-Z][A-Z0-9_]*(API_KEY|TOKEN|SECRET|PRIVATE_KEY)\b"),
    ),
)

BEHAVIOR_OVERRIDE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ignore instructions", re.compile(r"\bignore (all )?(previous|prior) instructions\b")),
    ("reveal system prompt", re.compile(r"\b(reveal|show|print)\b.{0,40}system prompt\b")),
    ("disable safety", re.compile(r"\b(disable|bypass).{0,40}(safety|sandbox|guardrail)\b")),
    ("override system", re.compile(r"\boverride.{0,40}system instructions\b")),
)

PERSISTENCE_TARGETS = (
    "AGENTS.md",
    "MEMORY.md",
    "SOUL.md",
    ".bashrc",
    ".zshrc",
    "crontab",
    ".claude/settings",
    ".codex/config",
    "settings.json",
)
WRITE_MARKERS = ("write", "append", "overwrite", "modify", "tee ", "sed -i", ">>", ">")
TEACHING_HINTS = (
    "for example",
    "example:",
    "fake",
    "placeholder",
    "dummy",
    "red flag",
    "detect",
    "do not",
    "don't",
    "warning",
    "test fixture",
)
MAX_TEXT_BYTES = 300_000


def enrich_report(report: CheckReport) -> CheckReport:
    for skill in report.skills:
        existing_codes = {diagnostic.code for diagnostic in skill.diagnostics}
        for diagnostic in _skill_diagnostics(skill):
            if diagnostic.code not in existing_codes:
                skill.diagnostics.append(diagnostic)
                existing_codes.add(diagnostic.code)

    report.duplicate_groups = build_duplicate_groups(report.skills)
    duplicate_signals = _duplicate_signals(report.duplicate_groups)
    for skill in report.skills:
        skill.judgment = build_skill_judgment(skill, duplicate_signals.get(skill.id, []))
    apply_housekeeping(report.skills, report.duplicate_groups)
    report.review_queues = build_review_queues(report.skills, report.duplicate_groups)
    return report


def build_skill_judgment(
    skill: SkillRecord, duplicate_signals: list[SignalKind] | None = None
) -> SkillJudgment:
    signals = _dedupe_signals(
        [
            *(duplicate_signals or []),
            *(["execution_surface"] if skill.has_scripts else []),
        ]
    )
    findings = _skill_findings(skill)
    needs_attention = any(
        finding.severity in {"attention", "high"} and finding.confidence != "low"
        for finding in findings
    )
    return SkillJudgment(
        primary_bucket="needs_attention" if needs_attention else "no_cleanup_action",
        signals=signals,
        owner=_owner_from_skill(skill),
        discovered_by_runtime="unknown" if skill.load_status == "unknown" else "yes",
        mutation_allowed="none" if skill.protected or needs_attention else "metadata_only",
        findings=findings,
    )


def build_review_queues(
    skills: list[SkillRecord], duplicate_groups: list[DuplicateGroup] | None = None
) -> list[ReviewQueue]:
    duplicate_groups = duplicate_groups or build_duplicate_groups(skills)
    exact_duplicate_ids = {
        skill.id
        for group in duplicate_groups
        if group.kind == "same-content-copy"
        for skill in group.skills
    }
    near_duplicate_ids = {
        skill.id
        for group in duplicate_groups
        if group.kind == "near-duplicate"
        for skill in group.skills
    }

    return [
        ReviewQueue(
            name="needs_attention",
            title="Needs attention",
            skills=[
                skill
                for skill in skills
                if skill.judgment and skill.judgment.primary_bucket == "needs_attention"
            ],
        ),
        ReviewQueue(
            name="no_cleanup_action",
            title="No cleanup action",
            skills=[
                skill
                for skill in skills
                if skill.judgment and skill.judgment.primary_bucket == "no_cleanup_action"
            ],
        ),
        ReviewQueue(
            name="execution_surface",
            title="Execution surface",
            skills=[skill for skill in skills if skill.has_scripts],
        ),
        ReviewQueue(
            name="exact_duplicates",
            title="Exact copy signals",
            skills=[skill for skill in skills if skill.id in exact_duplicate_ids],
        ),
        ReviewQueue(
            name="likely_overlaps",
            title="Likely overlap signals",
            skills=[skill for skill in skills if skill.id in near_duplicate_ids],
        ),
        ReviewQueue(
            name="protected_sources",
            title="Runtime-managed system/plugin/cache sources",
            skills=[skill for skill in skills if skill.protected],
        ),
        ReviewQueue(
            name="unknown_runtime_paths",
            title="Unknown runtime paths",
            skills=[skill for skill in skills if skill.load_status == "unknown"],
        ),
    ]


def build_visibility_snapshot(report: CheckReport) -> VisibilitySnapshot:
    enriched = enrich_report(report)
    records: list[VisibilityRecord] = []

    for skill in enriched.skills:
        if skill.housekeeping:
            records.append(
                VisibilityRecord(
                    kind="record_visibility",
                    skill_id=skill.id,
                    skill_name=skill.name,
                    path=skill.path,
                    reason=skill.housekeeping.reason,
                    confidence=skill.housekeeping.confidence,
                    metadata=_housekeeping_metadata(skill),
                )
            )

    return VisibilitySnapshot(
        records=_dedupe_records(records),
        review_queues=enriched.review_queues,
    )


def build_duplicate_groups(skills: list[SkillRecord]) -> list[DuplicateGroup]:
    groups: list[DuplicateGroup] = []
    by_body_hash: dict[str, list[SkillRecord]] = defaultdict(list)
    for skill in skills:
        if skill.body_hash:
            by_body_hash[skill.body_hash].append(skill)

    for body_hash, matches in by_body_hash.items():
        if len(matches) > 1:
            groups.append(
                DuplicateGroup(
                    id=body_hash[:12],
                    kind="same-content-copy",
                    skills=matches,
                    reason="Normalized body content is identical.",
                    confidence=1.0,
                )
            )

    grouped_ids = {skill.id for group in groups for skill in group.skills}
    remaining = [skill for skill in skills if skill.id not in grouped_ids]
    for index, skill in enumerate(remaining):
        matches = [
            other
            for other in remaining[index + 1 :]
            if _near_duplicate_score(skill, other) >= 92
        ]
        if matches:
            groups.append(
                DuplicateGroup(
                    id=f"near-{skill.id}",
                    kind="near-duplicate",
                    skills=[skill, *matches],
                    reason="Name or description similarity is high.",
                    confidence=0.75,
                )
            )
    return groups


def _skill_diagnostics(skill: SkillRecord) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if skill.protected:
        diagnostics.append(
            Diagnostic(
                code="protected-source",
                severity="info",
                message="Skill belongs to a runtime-managed source.",
                evidence=[skill.source_kind, str(skill.path)],
                suggested_action="none",
                source_rule="rules.protected",
            )
        )
    if _is_cleanup_residue(skill):
        diagnostics.append(
            Diagnostic(
                code="legacy-looking-folder",
                severity="warning",
                message="Skill folder name looks like a backup, copy, old, or migration marker.",
                evidence=[skill.path.name],
                suggested_action="none",
                source_rule="rules.legacy-looking-folder",
            )
        )
    if skill.has_scripts:
        diagnostics.append(
            Diagnostic(
                code="execution-surface",
                severity="info",
                message="Skill contains helper scripts. Scripts are signals, not verdicts.",
                evidence=[str(path) for path in _script_files_inside_skill(skill)][:5],
                suggested_action="none",
                source_rule="rules.execution-surface",
            )
        )
        if _dangerous_shell_evidence(skill):
            diagnostics.append(
                Diagnostic(
                    code="dangerous-shell",
                    severity="blocked",
                    message="Script contains dangerous shell patterns.",
                    evidence=_dangerous_shell_evidence(skill)[:5],
                    confidence=0.9,
                    suggested_action="review",
                    source_rule="rules.dangerous-shell",
                )
            )
    return diagnostics


def _skill_findings(skill: SkillRecord) -> list[Finding]:
    findings: list[Finding] = []
    if skill.load_status == "unknown" or _owner_from_skill(skill) == "unknown":
        findings.append(build_finding("unknown-owner", [str(skill.path)]))

    parse_errors = [
        diagnostic
        for diagnostic in skill.diagnostics
        if diagnostic.severity in {"error", "blocked"}
        and diagnostic.code
        in {"unterminated-frontmatter", "invalid-frontmatter", "invalid-frontmatter-type"}
    ]
    if parse_errors:
        findings.append(
            build_finding(
                "broken-skill-file",
                _diagnostic_evidence(parse_errors),
            )
        )

    path_escape = _path_escape_evidence(skill)
    if path_escape:
        findings.append(build_finding("path-escape", path_escape[:5]))

    dangerous_shell = _dangerous_shell_evidence(skill)
    if dangerous_shell:
        findings.append(build_finding("dangerous-shell", dangerous_shell[:5]))

    sensitive = _sensitive_content_evidence(skill)
    if sensitive:
        findings.append(build_finding("sensitive-content", sensitive[:5]))

    override = _behavior_override_evidence(skill)
    if override:
        findings.append(build_finding("behavior-override", override[:5]))

    persistence = _persistence_write_evidence(skill)
    if persistence:
        findings.append(build_finding("persistence-write", persistence[:5]))

    return _dedupe_findings(findings)


def _duplicate_signals(groups: list[DuplicateGroup]) -> dict[str, list[SignalKind]]:
    signals: dict[str, list[SignalKind]] = defaultdict(list)
    for group in groups:
        signal: SignalKind = (
            "exact_copy" if group.kind == "same-content-copy" else "likely_overlap"
        )
        for skill in group.skills:
            signals[skill.id].append(signal)
    return signals


def _owner_from_skill(skill: SkillRecord) -> OwnerKind:
    if skill.source_kind == "shared":
        return "shared"
    if skill.source_kind == "warehouse":
        return "warehouse"
    if skill.source_kind == "project":
        return "project"
    if skill.source_kind in {"system", "plugin_cache", "plugin_marketplace"}:
        return "plugin" if skill.source_kind.startswith("plugin") else "runtime"
    if skill.source_kind in {"user", "migration_bundle"}:
        return "user"
    return "unknown"


def _near_duplicate_score(left: SkillRecord, right: SkillRecord) -> int:
    name_score = fuzz.token_set_ratio(left.name, right.name)
    description_score = fuzz.token_set_ratio(left.description, right.description)
    return max(name_score, description_score)


def _script_files_inside_skill(skill: SkillRecord):
    skill_root = skill.path.resolve()
    scripts_root = skill.path / "scripts"
    if scripts_root.is_symlink():
        yield scripts_root
        return
    try:
        paths = sorted(scripts_root.rglob("*"))
    except OSError:
        yield scripts_root
        return
    for path in paths:
        if not path.is_file() or path.is_symlink():
            continue
        try:
            path.resolve().relative_to(skill_root)
        except ValueError:
            continue
        yield path


def _text_candidates(
    skill: SkillRecord, *, scripts_only: bool = False, include_scripts: bool = False
):
    if scripts_only:
        paths = list(_script_files_inside_skill(skill))
    else:
        paths = [skill.skill_file]
        if include_scripts:
            paths.extend(_script_files_inside_skill(skill))
    for path in paths:
        if path.is_dir():
            continue
        try:
            if path.stat().st_size > MAX_TEXT_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        yield path, text


def _path_escape_evidence(skill: SkillRecord) -> list[str]:
    evidence: list[str] = []
    root = skill.path.resolve()
    try:
        paths = sorted(skill.path.rglob("*"))
    except OSError:
        return [f"{skill.path}: could not inspect nested paths"]
    for path in paths:
        if not path.is_symlink():
            continue
        if path.name == "SKILL.md":
            continue
        try:
            path.resolve().relative_to(root)
        except ValueError:
            evidence.append(f"{path}: symlink points outside skill folder")
    return evidence


def _dangerous_shell_evidence(skill: SkillRecord) -> list[str]:
    evidence: list[str] = []
    for path, text in _text_candidates(skill, scripts_only=True):
        for line_number, line in enumerate(text.splitlines(), start=1):
            if _looks_like_teaching_context(line):
                continue
            for label, pattern in DANGEROUS_SHELL_PATTERNS:
                if pattern.search(line):
                    evidence.append(f"{path}:{line_number}: {label}")
    return evidence


def _sensitive_content_evidence(skill: SkillRecord) -> list[str]:
    evidence: list[str] = []
    for path, text in _text_candidates(skill, include_scripts=True):
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if _looks_like_teaching_context(line) or _near_teaching_context(lines, index):
                continue
            for label, pattern in SECRET_PATTERNS:
                if label == "environment secret":
                    continue
                if (
                    label == "credential path"
                    and not _line_reads_secret(line)
                ):
                    continue
                if pattern.search(line):
                    evidence.append(f"{path}:{index + 1}: {label}")
    return evidence


def _behavior_override_evidence(skill: SkillRecord) -> list[str]:
    evidence: list[str] = []
    for path, text in _text_candidates(skill):
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if _looks_like_teaching_context(line) or _near_teaching_context(lines, index):
                continue
            for label, pattern in BEHAVIOR_OVERRIDE_PATTERNS:
                if pattern.search(line.lower()):
                    evidence.append(f"{path}:{index + 1}: {label}")
    return evidence


def _persistence_write_evidence(skill: SkillRecord) -> list[str]:
    evidence: list[str] = []
    for path, text in _text_candidates(skill, scripts_only=True):
        for line_number, line in enumerate(text.splitlines(), start=1):
            if _looks_like_teaching_context(line):
                continue
            lowered = line.lower()
            has_target = any(target.lower() in lowered for target in PERSISTENCE_TARGETS)
            has_write = any(marker in lowered for marker in WRITE_MARKERS)
            if has_target and has_write:
                evidence.append(f"{path}:{line_number}: persistence target write")
    return evidence


def _looks_like_teaching_context(line: str) -> bool:
    lowered = line.lower()
    return any(hint in lowered for hint in TEACHING_HINTS)


def _near_teaching_context(lines: list[str], index: int) -> bool:
    start = max(0, index - 8)
    context = "\n".join(lines[start : index + 1]).lower()
    return any(hint in context for hint in TEACHING_HINTS)


def _line_reads_secret(line: str) -> bool:
    lowered = line.lower()
    markers = (
        "cat ",
        "source ",
        "open(",
        "read_text",
    )
    return any(marker in lowered for marker in markers)


def _diagnostic_evidence(diagnostics: list[Diagnostic]) -> list[str]:
    evidence: list[str] = []
    for diagnostic in diagnostics:
        evidence.extend(diagnostic.evidence or [diagnostic.message])
    return evidence


def _is_cleanup_residue(skill: SkillRecord) -> bool:
    name = skill.path.name.lower()
    tokens = re.split(r"[^a-z0-9]+", name)
    description = skill.description.lower()
    if "backup" in tokens and any(
        phrase in description
        for phrase in ("backup and restore", "backup", "restore", "encrypted backup")
    ):
        return False
    return (
        _has_version_residue_token(tokens)
        or "migration" in tokens
        or name.endswith((".bak", ".backup", ".old", ".copy"))
        or bool(re.search(r"(backup|bak|old|copy)[-_]?\d{6,}", name))
    )


def _has_version_residue_token(tokens: list[str]) -> bool:
    residue = {"backup", "bak", "old", "copy"}
    return any(token in residue for token in tokens) and any(
        token.isdigit() or token.startswith("v") and token[1:].isdigit()
        for token in tokens
    )


def _is_background_source(skill: SkillRecord) -> bool:
    return (
        skill.source_kind in {"shared", "warehouse", "migration_bundle"}
        or skill.load_status in {"library", "imported", "bundled"}
    )


def _dedupe_signals(signals: list[SignalKind]) -> list[SignalKind]:
    seen: set[SignalKind] = set()
    unique: list[SignalKind] = []
    for signal in signals:
        if signal in seen:
            continue
        seen.add(signal)
        unique.append(signal)
    return unique


def _dedupe_findings(findings: list[Finding]) -> list[Finding]:
    seen: set[str] = set()
    unique: list[Finding] = []
    for finding in findings:
        if finding.rule_id in seen:
            continue
        seen.add(finding.rule_id)
        unique.append(finding)
    return unique


def _dedupe_records(records: list[VisibilityRecord]) -> list[VisibilityRecord]:
    seen: set[tuple[str, str]] = set()
    unique: list[VisibilityRecord] = []
    for record in records:
        key = (record.kind, record.skill_id)
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
    return unique


def _housekeeping_metadata(skill: SkillRecord) -> dict[str, object]:
    if not skill.housekeeping:
        return {}
    return {"housekeeping": skill.housekeeping.model_dump(mode="json")}
