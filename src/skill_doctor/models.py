"""
[INPUT]: 依赖 dataclasses / enum / pathlib 标准库。
[OUTPUT]: 对外提供 Runtime / Category / IssueType / Status 枚举，
         SkillInstance / JunkFile / DupGroup / DriftGroup / BrokenLink / AnalysisReport 数据类。
[POS]: skill_doctor 的领域模型层，所有 scanner/analyze/report/apply 都基于这些类型流通。
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class Runtime(StrEnum):
    CLAUDE = "claude"
    CODEX = "codex"
    CURSOR = "cursor"
    OPENCLAW = "openclaw"
    AGENTS = "agents"
    OPENCODE = "opencode"
    GEMINI = "gemini"
    PLUGIN_CLAUDE = "plugin"
    PLUGIN_CODEX = "codex-plugin"
    UNKNOWN = "unknown"


RUNTIME_LABEL = {
    Runtime.CLAUDE: "Claude Code",
    Runtime.CODEX: "Codex",
    Runtime.CURSOR: "Cursor",
    Runtime.OPENCLAW: "OpenClaw",
    Runtime.AGENTS: "Agents",
    Runtime.OPENCODE: "OpenCode",
    Runtime.GEMINI: "Gemini",
    Runtime.PLUGIN_CLAUDE: "Plugin (Claude)",
    Runtime.PLUGIN_CODEX: "Plugin (Codex)",
    Runtime.UNKNOWN: "Unknown",
}


class Category(StrEnum):
    SEO = "SEO"
    ADS = "广告"
    MARKETING = "营销"
    DEV = "开发"
    DEPLOY = "部署"
    DATA = "数据"
    DESIGN = "设计"
    AI_VIDEO = "AI/视频"
    OTHER = "其他"
    UNCATEGORIZED = "未分类"


class IssueType(StrEnum):
    DUPLICATE = "duplicate"
    DRIFT = "drift"
    BROKEN_LINK = "broken_link"
    JUNK = "junk"


class ActionType(StrEnum):
    DEDUP = "dedup"
    DELETE_JUNK = "delete_junk"
    REMOVE_BROKEN = "remove_broken"


@dataclass
class FsOp:
    """A single reversible filesystem operation."""

    kind: str                      # "move_to_backup" | "symlink" | "remove_symlink"
    src: Path                      # source path being acted on
    dst: Path | None = None        # target path (for symlink/move)


@dataclass
class Action:
    id: int
    type: ActionType
    title: str                     # one-line summary
    detail: str                    # what will happen
    ops: list[FsOp]                # ordered fs operations


@dataclass
class SkillInstance:
    """One physical placement of a skill on disk."""

    path: Path                       # the skill directory
    skill_md: Path | None            # SKILL.md path (None if missing)
    runtime: Runtime
    name: str                        # frontmatter.name or dirName
    dir_name: str                    # always parent dir basename
    description: str
    version: str | None              # frontmatter.metadata.version
    body_hash: str                   # sha256 of normalized SKILL.md body
    body_lines: int
    is_symlink: bool                 # the directory is a symlink
    symlink_target: Path | None      # raw target (may be relative)
    real_path: Path                  # resolved absolute path
    file_is_symlink: bool            # SKILL.md itself is a symlink (Codex bug)
    mtime: float
    category: Category = Category.UNCATEGORIZED


@dataclass
class JunkFile:
    path: Path
    pattern: str                     # which regex matched
    runtime: Runtime


@dataclass
class DupGroup:
    """Skills with identical body_hash across runtimes."""

    body_hash: str
    instances: list[SkillInstance]
    master: SkillInstance


@dataclass
class DriftGroup:
    """Skills sharing dir_name but with different body_hash (version drift)."""

    name: str
    instances: list[SkillInstance]


@dataclass
class BrokenLink:
    path: Path                       # the broken symlink itself
    runtime: Runtime
    intended_target: Path            # what it tried to point to


@dataclass
class StaleSkill:
    """Skill whose SKILL.md has not been modified recently. mtime-only — does NOT mean unused."""

    instance: SkillInstance
    days_ago: int


@dataclass
class AnalysisReport:
    instances: list[SkillInstance]
    by_runtime: dict[Runtime, int] = field(default_factory=dict)
    by_category: dict[Category, int] = field(default_factory=dict)
    duplicates: list[DupGroup] = field(default_factory=list)
    drifts: list[DriftGroup] = field(default_factory=list)
    broken_links: list[BrokenLink] = field(default_factory=list)
    junk_files: list[JunkFile] = field(default_factory=list)
    stale: list[StaleSkill] = field(default_factory=list)

    @property
    def total_skills(self) -> int:
        return len(self.instances)

    @property
    def total_runtimes(self) -> int:
        return len([k for k, v in self.by_runtime.items() if v > 0])

    @property
    def has_issues(self) -> bool:
        return bool(self.duplicates or self.drifts or self.broken_links or self.junk_files)
