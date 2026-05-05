"""
[INPUT]: Depends on dataclasses and Skill Doctor model enums for rule metadata.
[OUTPUT]: Provides standards-backed rule specs and Finding builders.
[POS]: Central catalog for user-facing judgment rules, kept separate from detection.
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

from dataclasses import dataclass

from skill_doctor.models import (
    Finding,
    FindingConfidence,
    FindingSeverity,
    StandardRef,
)


@dataclass(frozen=True)
class RuleSpec:
    id: str
    title: str
    reason: str
    severity: FindingSeverity
    confidence: FindingConfidence
    standards: tuple[StandardRef, ...]
    what_next: str


RULES: dict[str, RuleSpec] = {
    "unknown-owner": RuleSpec(
        id="unknown-owner",
        title="Unknown owner",
        reason="Skill Doctor could not match this skill to a known runtime-owned source.",
        severity="attention",
        confidence="high",
        standards=(
            StandardRef(label="CIS Control 2", maturity="standard"),
            StandardRef(label="NIST AI RMF Map", maturity="standard"),
        ),
        what_next="Confirm which runtime or user owns this skill before organizing it.",
    ),
    "broken-skill-file": RuleSpec(
        id="broken-skill-file",
        title="Broken skill file",
        reason="The SKILL.md frontmatter could not be parsed reliably.",
        severity="attention",
        confidence="high",
        standards=(StandardRef(label="Runtime skill format", maturity="runtime_practice"),),
        what_next="Open the SKILL.md and fix the frontmatter before relying on it.",
    ),
    "path-escape": RuleSpec(
        id="path-escape",
        title="Path escape",
        reason="A symlink or path inside the skill points outside the skill folder.",
        severity="high",
        confidence="high",
        standards=(
            StandardRef(label="OWASP LLM06", maturity="standard"),
            StandardRef(label="NIST SSDF", maturity="standard"),
        ),
        what_next="Inspect the linked path and keep this skill out of automatic cleanup.",
    ),
    "dangerous-shell": RuleSpec(
        id="dangerous-shell",
        title="Dangerous shell",
        reason=(
            "A script contains shell patterns commonly used for destructive "
            "or remote execution."
        ),
        severity="high",
        confidence="high",
        standards=(
            StandardRef(label="OWASP LLM06", maturity="standard"),
            StandardRef(label="NIST SSDF", maturity="standard"),
        ),
        what_next="Inspect the script before using this skill.",
    ),
    "sensitive-content": RuleSpec(
        id="sensitive-content",
        title="Sensitive content",
        reason="The skill contains high-confidence credential or secret-like material.",
        severity="high",
        confidence="high",
        standards=(
            StandardRef(label="OWASP LLM02", maturity="standard"),
            StandardRef(label="NIST SSDF", maturity="standard"),
        ),
        what_next="Remove real secrets from the skill or confirm the match is only a test fixture.",
    ),
    "behavior-override": RuleSpec(
        id="behavior-override",
        title="Behavior override",
        reason=(
            "The skill appears to instruct the agent to ignore rules or reveal "
            "protected prompts."
        ),
        severity="attention",
        confidence="medium",
        standards=(
            StandardRef(label="OWASP LLM01", maturity="standard"),
            StandardRef(label="OWASP LLM07", maturity="standard"),
        ),
        what_next="Confirm this is not an instruction that changes the agent's behavior boundary.",
    ),
    "persistence-write": RuleSpec(
        id="persistence-write",
        title="Persistence write",
        reason=(
            "The skill appears to write identity, memory, shell profile, "
            "or runtime config files."
        ),
        severity="high",
        confidence="medium",
        standards=(
            StandardRef(label="OWASP LLM06", maturity="standard"),
            StandardRef(label="NIST SSDF", maturity="standard"),
        ),
        what_next="Review the write target and confirm the skill is allowed to persist changes.",
    ),
    "legacy-looking-folder": RuleSpec(
        id="legacy-looking-folder",
        title="Legacy-looking folder",
        reason="The folder name looks like a backup, copy, old version, or migration marker.",
        severity="info",
        confidence="medium",
        standards=(StandardRef(label="Product hygiene", maturity="product_hygiene"),),
        what_next="Shown as a visibility signal only; no file action is implied.",
    ),
}


def build_finding(
    rule_id: str,
    evidence: list[str],
    *,
    severity: FindingSeverity | None = None,
    confidence: FindingConfidence | None = None,
) -> Finding:
    spec = RULES[rule_id]
    return Finding(
        rule_id=spec.id,
        title=spec.title,
        reason=spec.reason,
        severity=severity or spec.severity,
        confidence=confidence or spec.confidence,
        evidence=evidence,
        standard_refs=list(spec.standards),
        what_next=spec.what_next,
    )


def standards_lens(finding: Finding) -> str:
    if not finding.standard_refs:
        return "Product hygiene"
    return ", ".join(ref.label for ref in finding.standard_refs)


def maturity_lens(finding: Finding) -> str:
    values = {ref.maturity for ref in finding.standard_refs}
    return ", ".join(sorted(values)) if values else "product_hygiene"
