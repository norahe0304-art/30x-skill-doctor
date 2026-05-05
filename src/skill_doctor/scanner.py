"""
[INPUT]: 依赖 ./models 的数据类型与 ./classify 的 categorize，依赖 yaml/hashlib/re/pathlib。
[OUTPUT]: 对外提供 scan_all(roots=None) -> (list[SkillInstance], list[JunkFile],
         list[BrokenLink])，以及 RUNTIME_ROOTS 路径白名单和 JUNK_PATTERNS regex 列表。
[POS]: 文件系统发现层。读 SKILL.md frontmatter，算 body hash，记录 symlink 链与 macOS 垃圾。
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

from .classify import categorize
from .config import user_extra_runtime_paths
from .models import BrokenLink, JunkFile, Runtime, SkillInstance

# 默认 runtime 根路径白名单。每条是 (root_dir, runtime_tag, glob_for_skill_dirs)。
HOME = Path.home()
RUNTIME_ROOTS: tuple[tuple[Path, Runtime, str], ...] = (
    (HOME / ".claude" / "skills", Runtime.CLAUDE, "*"),
    (HOME / ".codex" / "skills", Runtime.CODEX, "*"),
    (HOME / ".cursor" / "skills", Runtime.CURSOR, "*"),
    (HOME / ".openclaw" / "skills", Runtime.OPENCLAW, "*"),
    (HOME / ".agents" / "skills", Runtime.AGENTS, "*"),
    (HOME / ".config" / "opencode" / "skills", Runtime.OPENCODE, "*"),
    (HOME / ".codex" / "superpowers" / "skills", Runtime.PLUGIN_CODEX, "*"),
    # Claude marketplace plugins come in three layouts; cover all three.
    (HOME / ".claude" / "plugins" / "marketplaces", Runtime.PLUGIN_CLAUDE, "*/skills/*"),
    (HOME / ".claude" / "plugins" / "marketplaces", Runtime.PLUGIN_CLAUDE, "*/plugins/*/skills/*"),
    (
        HOME / ".claude" / "plugins" / "marketplaces",
        Runtime.PLUGIN_CLAUDE,
        "*/external_plugins/*/skills/*",
    ),
)


# Junk file detection (macOS / editor / iCloud copy artifacts).
# NEVER include patterns that overlap with iCloud offload placeholders (`*.icloud`).
# See anthropics/claude-code#32637 — a tool deleted real iCloud-offloaded files
# thinking they were empty. We hard-exclude that suffix below.
JUNK_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r" \d+\.md$"), "macos-copy"),
    (re.compile(r" \d+\.json$"), "macos-copy"),
    (re.compile(r" \d+\.py$"), "macos-copy"),
    (re.compile(r" \d+\.yaml$"), "macos-copy"),
    (re.compile(r" \d+\.toml$"), "macos-copy"),
    (re.compile(r" \d+$"), "macos-copy-dir"),
    (re.compile(r"^\.DS_Store$"), "ds-store"),
    (re.compile(r"^\._"), "apple-double"),
    (re.compile(r"^__MACOSX$"), "macosx-zip"),
    # Vim swap regex per github/gitignore canonical Global/Vim.gitignore.
    (re.compile(r"^[._].*\.s[a-v][a-z]$"), "vim-swap"),
    (re.compile(r"^[._].*\.sw[a-p]$"), "vim-swap"),
    (re.compile(r"\.swp$"), "vim-swap"),
    (re.compile(r"\.swo$"), "vim-swap"),
    (re.compile(r"~$"), "editor-backup"),
    (re.compile(r"\.un~$"), "vim-undo"),
)


# Paths to NEVER scan / NEVER flag — protected because they may contain
# user data masquerading as "junk" (iCloud offload placeholders, etc.).
JUNK_PROTECTED_PARENTS = (
    "/Library/CloudStorage/",     # macOS iCloud Drive / Dropbox / OneDrive
    "/Library/Mobile Documents/",  # legacy iCloud path
)
JUNK_PROTECTED_SUFFIXES = (
    ".icloud",   # iCloud Drive offload placeholder; deleting destroys real data
)


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def _runtime_from_string(s: str) -> Runtime:
    try:
        return Runtime(s)
    except ValueError:
        return Runtime.UNKNOWN


def _parse_skill_md(skill_md: Path) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_string). Empty dict on parse failure."""
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}, ""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    try:
        front = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        front = {}
    body = text[match.end():]
    return (front if isinstance(front, dict) else {}), body


def _normalize_body(body: str) -> str:
    """Strip whitespace variance so cosmetic diffs do not split dup groups."""
    return "\n".join(line.rstrip() for line in body.splitlines()).strip()


def _hash_body(body: str) -> str:
    return hashlib.sha256(_normalize_body(body).encode("utf-8")).hexdigest()


def _is_junk_protected(path: Path) -> bool:
    """True if `path` lives somewhere we must not flag as junk (iCloud, cloud sync)."""
    s = str(path)
    if any(p in s for p in JUNK_PROTECTED_PARENTS):
        return True
    if any(s.endswith(suf) for suf in JUNK_PROTECTED_SUFFIXES):
        return True
    return False


def _detect_junk(directory: Path, runtime: Runtime) -> list[JunkFile]:
    """Recursively find junk files in a skill directory (handles e.g. scripts/foo 2.py)."""
    found: list[JunkFile] = []
    if not directory.exists():
        return found
    try:
        entries = list(directory.rglob("*"))
    except OSError:
        return found
    for entry in entries:
        if _is_junk_protected(entry):
            continue
        for pattern, tag in JUNK_PATTERNS:
            if pattern.search(entry.name):
                found.append(JunkFile(path=entry, pattern=tag, runtime=runtime))
                break
    return found


def _max_mtime_in(directory: Path, default: float) -> float:
    """Latest mtime across the skill dir tree (so editing references/foo.md counts as activity)."""
    best = default
    try:
        for entry in directory.rglob("*"):
            try:
                mt = entry.stat().st_mtime
                if mt > best:
                    best = mt
            except OSError:
                continue
    except OSError:
        pass
    return best


def _build_instance(
    skill_dir: Path, runtime: Runtime
) -> tuple[SkillInstance | None, BrokenLink | None]:
    """Try to build a SkillInstance from a skill directory. Returns (instance, broken_link)."""
    if skill_dir.is_symlink() and not skill_dir.exists():
        intended = (
            Path(str(skill_dir.readlink())) if skill_dir.is_symlink() else skill_dir
        )
        return None, BrokenLink(
            path=skill_dir,
            runtime=runtime,
            intended_target=intended,
        )

    if not skill_dir.is_dir():
        return None, None

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None, None

    front, body = _parse_skill_md(skill_md)
    name = str(front.get("name") or skill_dir.name)
    description = str(front.get("description") or "").strip()
    metadata = front.get("metadata") or {}
    version = None
    if isinstance(metadata, dict):
        version = metadata.get("version")
    if version is not None:
        version = str(version)

    is_symlink = skill_dir.is_symlink()
    file_is_symlink = skill_md.is_symlink()
    try:
        target = Path(str(skill_dir.readlink())) if is_symlink else None
    except OSError:
        target = None

    try:
        real_path = skill_dir.resolve()
    except OSError:
        real_path = skill_dir

    try:
        mtime = skill_md.stat().st_mtime
    except OSError:
        mtime = 0.0
    # Use the latest mtime in the skill tree so edits to references/scripts also count.
    mtime = _max_mtime_in(skill_dir, mtime)

    instance = SkillInstance(
        path=skill_dir,
        skill_md=skill_md,
        runtime=runtime,
        name=name,
        dir_name=skill_dir.name,
        description=description,
        version=version,
        body_hash=_hash_body(body),
        body_lines=len(body.splitlines()),
        is_symlink=is_symlink,
        symlink_target=target,
        real_path=real_path,
        file_is_symlink=file_is_symlink,
        mtime=mtime,
    )
    instance.category = categorize(instance)
    return instance, None


def scan_all(
    roots: tuple[tuple[Path, Runtime, str], ...] | None = None,
) -> tuple[list[SkillInstance], list[JunkFile], list[BrokenLink]]:
    """Walk all known runtime directories. Return (instances, junk_files, broken_links).

    If `roots` is None, uses RUNTIME_ROOTS plus user's config.toml [extra_runtimes].
    """
    instances: list[SkillInstance] = []
    junk: list[JunkFile] = []
    broken: list[BrokenLink] = []
    seen_paths: set[Path] = set()

    effective_roots: tuple
    if roots is not None:
        effective_roots = roots
    else:
        extras = tuple(
            (path, _runtime_from_string(tag), pattern)
            for path, tag, pattern in user_extra_runtime_paths()
        )
        effective_roots = RUNTIME_ROOTS + extras

    for root, runtime, pattern in effective_roots:
        if not root.exists():
            continue
        for skill_dir in root.glob(pattern):
            # Dedup by skill_dir itself (the placement). Two different runtime
            # paths pointing at the same real_path are still TWO placements,
            # which is what cross-runtime visibility needs to see.
            if skill_dir in seen_paths:
                continue
            seen_paths.add(skill_dir)

            instance, broken_link = _build_instance(skill_dir, runtime)
            if instance is not None:
                instances.append(instance)
                junk.extend(_detect_junk(skill_dir, runtime))
            if broken_link is not None:
                broken.append(broken_link)

    return instances, junk, broken
