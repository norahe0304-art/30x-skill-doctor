"""
[INPUT]: 依赖 pathlib.Path 与 tomllib (3.11+) 读 ~/.skill-doctor/config.toml。
[OUTPUT]: 对外提供 BACKUP_ROOT / CONFIG_PATH / QUALITY_CACHE_PATH 路径常量，
         DEFAULT_WEIGHTS / STALE_DAYS_DEFAULT，load_config() -> dict，
         user_extra_runtime_paths() -> 用户在 config.toml 里加的额外 runtime 根。
[POS]: 用户配置与本工具自有目录管理。
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

import tomllib
from pathlib import Path

CONFIG_DIR = Path.home() / ".skill-doctor"
CONFIG_PATH = CONFIG_DIR / "config.toml"
BACKUP_ROOT = CONFIG_DIR / "backup"
QUALITY_CACHE_PATH = CONFIG_DIR / "quality_cache.json"

DEFAULT_WEIGHTS = {
    # Master-election weights. Path depth was dropped in v0.4.0 — searching the
    # community turned up zero citations for "deeper path = canonical source".
    # The opposite intuition (root-level = canonical, scoped = override) is
    # implied by Claude Code's enterprise > personal > project precedence.
    # Removing the unverified 15% and redistributing prevents a fake authority.
    "version": 0.40,
    "incoming_links": 0.40,
    "path_depth": 0.0,
    "mtime_freshness": 0.20,
}

STALE_DAYS_DEFAULT = 90  # Skills with mtime older than this are flagged. mtime-only signal.
# 3 months feels right — agent skills are a fast-evolving space, anything
# untouched for that long deserves at least a glance.


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """Read config.toml; return dict with sensible defaults filled in."""
    cfg: dict = {"weights": dict(DEFAULT_WEIGHTS), "extra_runtimes": []}
    if not CONFIG_PATH.exists():
        return cfg
    try:
        data = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return cfg
    if isinstance(data.get("weights"), dict):
        cfg["weights"].update(data["weights"])
    if isinstance(data.get("extra_runtimes"), list):
        cfg["extra_runtimes"] = list(data["extra_runtimes"])
    return cfg


def user_extra_runtime_paths() -> list[tuple[Path, str, str]]:
    """User-defined extra runtime roots from config.toml.

    Each entry: { path = "~/...", runtime = "...", glob = "*" }
    Returns list of (Path, runtime_tag_str, glob_pattern).
    """
    cfg = load_config()
    out: list[tuple[Path, str, str]] = []
    for item in cfg.get("extra_runtimes", []):
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        runtime = item.get("runtime") or "unknown"
        glob_pat = item.get("glob") or "*"
        if not path:
            continue
        out.append((Path(path).expanduser(), str(runtime), str(glob_pat)))
    return out
