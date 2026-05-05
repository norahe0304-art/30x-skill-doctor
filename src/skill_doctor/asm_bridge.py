"""
[INPUT]: 依赖 shutil.which 检测 asm CLI, 依赖 subprocess.run 调 `asm eval --json`,
         依赖 ./config 的 QUALITY_CACHE_PATH 做 mtime-keyed 缓存。
[OUTPUT]: 对外提供 has_asm() / quality_sample() / quality_full() / QualityRow。
[POS]: 可选 enrichment 桥。asm 未装时函数返回 None；装了就以 mtime 为 key 增量评估，
       第一次慢一次, 后续命中缓存几乎零延迟。
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import QUALITY_CACHE_PATH, ensure_config_dir


@dataclass
class QualityRow:
    name: str
    score: int
    grade: str
    suggestions: list[str]
    path: Path


def has_asm() -> bool:
    return shutil.which("asm") is not None


def asm_version() -> str | None:
    """Return short 'asm vX.Y.Z' or None if asm absent / errors."""
    if not has_asm():
        return None
    try:
        proc = subprocess.run(
            ["asm", "--version"], capture_output=True, text=True, timeout=3, check=False
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    text = (proc.stdout or proc.stderr or "").strip()
    # asm prints e.g. "agent-skill-manager (asm) v2.6.1 (9ba9e7c)"; keep only "asm vX.Y.Z".
    import re
    match = re.search(r"v\d+\.\d+\.\d+", text)
    return f"asm {match.group(0)}" if match else "asm"


def quality_sample(
    skill_paths: list[Path], n: int = 10, timeout: float = 10.0
) -> list[QualityRow] | None:
    """Quick taste — eval first n skills without caching. Returns sorted ascending by score."""
    if not has_asm():
        return None
    rows = [r for p in skill_paths[:n] if (r := _eval_one(p, timeout)) is not None]
    rows.sort(key=lambda r: r.score)
    return rows


def quality_full(
    skill_paths: list[Path],
    timeout: float = 10.0,
    progress_cb=None,
) -> list[QualityRow] | None:
    """Eval ALL skills with mtime-keyed cache. Cache invalidates per-skill on SKILL.md change."""
    if not has_asm():
        return None
    cache = _load_cache()
    rows: list[QualityRow] = []
    total = len(skill_paths)
    for idx, path in enumerate(skill_paths, 1):
        if progress_cb is not None:
            progress_cb(idx, total, path.name)
        row = _cached_or_eval(path, cache, timeout)
        if row is not None:
            rows.append(row)
    _save_cache(cache)
    rows.sort(key=lambda r: r.score)
    return rows


def _cached_or_eval(path: Path, cache: dict, timeout: float) -> QualityRow | None:
    skill_md = path / "SKILL.md"
    try:
        mtime = skill_md.stat().st_mtime if skill_md.exists() else 0.0
    except OSError:
        mtime = 0.0
    key = str(path)
    cached = cache.get(key)
    if cached and abs(cached.get("mtime", 0.0) - mtime) < 1e-3:
        return QualityRow(
            name=cached["name"],
            score=cached["score"],
            grade=cached["grade"],
            suggestions=cached.get("suggestions", []),
            path=Path(cached["path"]),
        )
    row = _eval_one(path, timeout)
    if row is not None:
        cache[key] = {**asdict(row), "path": str(row.path), "mtime": mtime}
    return row


def _load_cache() -> dict:
    if not QUALITY_CACHE_PATH.exists():
        return {}
    try:
        return json.loads(QUALITY_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict) -> None:
    ensure_config_dir()
    try:
        QUALITY_CACHE_PATH.write_text(
            json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


def _eval_one(path: Path, timeout: float) -> QualityRow | None:
    try:
        proc = subprocess.run(
            ["asm", "eval", str(path), "--json"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None

    if proc.returncode != 0 or not proc.stdout.strip():
        return None

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None

    score = int(data.get("overallScore") or 0)
    grade = str(data.get("grade") or "?")
    suggestions = list(data.get("topSuggestions") or [])
    return QualityRow(
        name=path.name,
        score=score,
        grade=grade,
        suggestions=suggestions[:3],
        path=path,
    )
