"""
[INPUT]: Depends on pathlib and yaml to parse SKILL.md files.
[OUTPUT]: Provides parse_skill_file with frontmatter, body, and parser diagnostics.
[POS]: File-format boundary between raw markdown and SkillRecord construction.
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from skill_doctor.models import Diagnostic


def parse_skill_file(path: Path) -> tuple[dict[str, Any], str, list[Diagnostic]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    diagnostics: list[Diagnostic] = []

    if not text.startswith("---"):
        diagnostics.append(
            Diagnostic(
                code="missing-frontmatter",
                severity="warning",
                message="SKILL.md does not start with YAML frontmatter.",
                evidence=[str(path)],
                source_rule="parser.frontmatter",
            )
        )
        return {}, text, diagnostics

    lines = text.splitlines()
    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break

    if end_index is None:
        diagnostics.append(
            Diagnostic(
                code="unterminated-frontmatter",
                severity="error",
                message="YAML frontmatter is not closed.",
                evidence=[str(path)],
                source_rule="parser.frontmatter",
            )
        )
        return {}, text, diagnostics

    raw_frontmatter = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :])
    try:
        frontmatter = yaml.safe_load(raw_frontmatter) or {}
    except yaml.YAMLError as error:
        diagnostics.append(
            Diagnostic(
                code="invalid-frontmatter",
                severity="error",
                message="YAML frontmatter could not be parsed.",
                evidence=[str(error)],
                source_rule="parser.yaml",
            )
        )
        return {}, body, diagnostics

    if not isinstance(frontmatter, dict):
        diagnostics.append(
            Diagnostic(
                code="invalid-frontmatter-type",
                severity="error",
                message="YAML frontmatter must be a mapping.",
                evidence=[str(path)],
                source_rule="parser.yaml",
            )
        )
        return {}, body, diagnostics

    return frontmatter, body, diagnostics
