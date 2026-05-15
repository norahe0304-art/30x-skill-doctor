"""
[INPUT]: 依赖 importlib.resources 读包内 SKILL.md 模板, 依赖 ./i18n.t,
         依赖 pathlib.Path 操作 ~/.{claude,codex,cursor,openclaw}/skills/。
[OUTPUT]: 对外提供 SKILL_TARGETS 字典, install_skill_for(runtime, force) -> InstallResult,
         install_skill_all(force) -> list[InstallResult]。
[POS]: Adoption hack 层。把 skill-doctor 自身注册为 Claude Code / Codex / Cursor /
       OpenClaw 的可触发 skill, 让 Agent 在用户聊天时自然 invoke。
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

# ─── Target table ───────────────────────────────────────────────────────────
# (runtime_slug, label, destination dir relative to $HOME). Only runtimes whose
# `~/.{slug}/skills/` directory pattern is standard. The directory will be
# created if it doesn't exist — installing the skill into a brand-new runtime
# folder is exactly the point.
SKILL_TARGETS: dict[str, tuple[str, Path]] = {
    "claude":   ("Claude Code", Path.home() / ".claude"   / "skills" / "skill-doctor"),
    "codex":    ("Codex",       Path.home() / ".codex"    / "skills" / "skill-doctor"),
    "cursor":   ("Cursor",      Path.home() / ".cursor"   / "skills" / "skill-doctor"),
    "openclaw": ("OpenClaw",    Path.home() / ".openclaw" / "skills" / "skill-doctor"),
}


@dataclass(frozen=True)
class InstallResult:
    runtime: str             # slug
    label: str               # human label
    dest: Path               # SKILL.md target path
    status: str              # "installed" | "skipped_exists" | "overwritten" | "error"
    detail: str = ""         # error message if status == "error"


def _read_template() -> str:
    """Read the bundled SKILL.md template, with a graceful dev-mode fallback."""
    try:
        return (files("skill_doctor.templates") / "SKILL.md").read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError):
        # Editable installs without resources resolution — fall back to repo layout.
        candidate = Path(__file__).parent / "templates" / "SKILL.md"
        return candidate.read_text(encoding="utf-8")


def install_skill_for(runtime: str, force: bool = False) -> InstallResult:
    """Write SKILL.md into the runtime's skill directory. Idempotent unless --force."""
    if runtime not in SKILL_TARGETS:
        return InstallResult(
            runtime=runtime, label=runtime, dest=Path(""),
            status="error", detail=f"unknown runtime '{runtime}'",
        )
    label, dest_dir = SKILL_TARGETS[runtime]
    dest_file = dest_dir / "SKILL.md"

    if dest_file.exists() and not force:
        return InstallResult(
            runtime=runtime, label=label, dest=dest_file, status="skipped_exists"
        )

    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        existed = dest_file.exists()
        dest_file.write_text(_read_template(), encoding="utf-8")
        status = "overwritten" if existed else "installed"
        return InstallResult(runtime=runtime, label=label, dest=dest_file, status=status)
    except OSError as e:
        return InstallResult(
            runtime=runtime, label=label, dest=dest_file,
            status="error", detail=str(e),
        )


def detected_runtimes() -> list[str]:
    """Return runtime slugs whose root directory already exists on this host.

    Defines 'detected' as the parent .{slug} dir existing — that's the
    strongest signal the user actually uses this runtime, without us having
    to enumerate every skill they own.
    """
    out: list[str] = []
    for slug, (_label, dest_dir) in SKILL_TARGETS.items():
        # dest_dir = ~/.{slug}/skills/skill-doctor → walk two levels up to .{slug}
        runtime_root = dest_dir.parent.parent
        if runtime_root.exists():
            out.append(slug)
    return out


def install_skill_all(force: bool = False, only_detected: bool = True) -> list[InstallResult]:
    targets = detected_runtimes() if only_detected else list(SKILL_TARGETS.keys())
    return [install_skill_for(slug, force=force) for slug in targets]
