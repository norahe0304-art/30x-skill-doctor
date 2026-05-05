"""
[INPUT]: Depends on pathlib to derive local runtime roots from home and project paths.
[OUTPUT]: Provides runtime registry and source classification helpers.
[POS]: Runtime boundary layer; every scan decision starts here.
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

from pathlib import Path

from skill_doctor.models import AgentRuntime, LoadStatus, SourceKind


def build_runtime_registry(
    home: Path | None = None, project: Path | None = None
) -> list[AgentRuntime]:
    home = Path.home() if home is None else home
    project = Path.cwd() if project is None else project

    return [
        AgentRuntime(
            id="claude",
            name="Claude",
            roots=[
                home / ".claude" / "skills",
                home / ".claude" / "plugins" / "marketplaces",
                project / ".claude" / "skills",
            ],
            first_class=True,
            apply_enabled=True,
        ),
        AgentRuntime(
            id="codex",
            name="Codex",
            roots=[
                home / ".codex" / "skills",
                home / ".codex" / "plugins" / "cache",
                project / ".codex" / "skills",
            ],
            first_class=True,
            apply_enabled=True,
        ),
        AgentRuntime(
            id="shared",
            name="Agents shared",
            roots=[home / ".agents" / "skills", project / ".agents" / "skills"],
            first_class=True,
            apply_enabled=False,
        ),
        AgentRuntime(
            id="cursor",
            name="Cursor",
            roots=[
                home / ".cursor" / "skills",
                home / ".cursor" / "skills-cursor",
                project / ".cursor" / "skills",
            ],
        ),
        AgentRuntime(id="hermes", name="Hermes", roots=[home / ".hermes" / "skills"]),
        AgentRuntime(
            id="openclaw",
            name="OpenClaw",
            roots=[
                home / ".openclaw" / "skills",
                home / ".openclaw" / "workspace" / "skills",
                home / ".openclaw" / "workspace" / ".agents" / "skills",
            ],
        ),
    ]


def classify_source(path: Path, runtime_id: str) -> tuple[SourceKind, LoadStatus, bool]:
    parts = set(path.parts)
    path_text = str(path)

    if runtime_id == "shared":
        return "shared", "available", False
    if runtime_id == "openclaw":
        return "warehouse", "library", False
    if ".system" in parts:
        return "system", "bundled", True
    if "plugins" in parts and "cache" in parts:
        return "plugin_cache", "bundled", True
    if "plugins" in parts and "marketplaces" in parts:
        return "plugin_marketplace", "bundled", True
    nested_claude_skill = (
        "/.claude/skills/" in path_text
        and "/." in path_text.split("/.claude/skills/", 1)[-1]
    )
    if nested_claude_skill:
        return "migration_bundle", "imported", False
    if runtime_id == "cursor":
        return "user", "available", False
    if runtime_id == "hermes":
        return "user", "available", False
    if runtime_id in {"claude", "codex"}:
        return "user", "active", False
    return "unknown", "unknown", False
