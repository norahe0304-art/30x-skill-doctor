"""
[INPUT]: 依赖 ./models 与 ./config 的 DEFAULT_WEIGHTS。
[OUTPUT]: 对外提供 analyze(instances, junk, broken, weights=None) -> AnalysisReport。
         核心子函数: group_by_hash / group_by_name / elect_master。
[POS]: 5 维度检查 + master 选举的纯函数层。无 I/O。
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

import time
from collections import Counter, defaultdict

from .config import DEFAULT_WEIGHTS, STALE_DAYS_DEFAULT
from .models import (
    AnalysisReport,
    BrokenLink,
    Category,
    DriftGroup,
    DupGroup,
    JunkFile,
    Runtime,
    SkillInstance,
    StaleSkill,
)


def _parse_semver(version: str | None) -> tuple[int, int, int]:
    """Best-effort semver tuple. Missing or junk → (0, 0, 0)."""
    if not version:
        return (0, 0, 0)
    parts = version.lstrip("v").split(".")[:3]
    out: list[int] = []
    for part in parts:
        digits = "".join(c for c in part if c.isdigit())
        out.append(int(digits) if digits else 0)
    while len(out) < 3:
        out.append(0)
    return (out[0], out[1], out[2])


def _normalize(values: list[float]) -> list[float]:
    """Min-max normalize to [0, 1]. All-equal collapses to 0.5 to avoid bias."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def _count_incoming_links(target: SkillInstance, all_instances: list[SkillInstance]) -> int:
    """How many other instances resolve to this instance's real_path."""
    return sum(
        1 for other in all_instances
        if other is not target and other.is_symlink and other.real_path == target.real_path
    )


def elect_master(
    group: list[SkillInstance],
    all_instances: list[SkillInstance],
    weights: dict[str, float],
) -> SkillInstance:
    """Score each instance and return the highest. Algorithm is documented in the README.

    When no instance in a group declares a version, the version axis adds no
    signal and its weight is *redistributed* to inbound + mtime so we don't
    pretend a 40% lever is doing work it isn't.
    """
    if len(group) == 1:
        return group[0]

    semvers = [_parse_semver(inst.version) for inst in group]
    incoming = [float(_count_incoming_links(inst, all_instances)) for inst in group]
    depths = [float(len(inst.real_path.parts)) for inst in group]
    mtimes = [inst.mtime for inst in group]

    semver_floats = [v[0] * 10000 + v[1] * 100 + v[2] for v in semvers]
    has_any_version = any(v > 0 for v in semver_floats)

    n_semver = _normalize(semver_floats)
    n_incoming = _normalize(incoming)
    n_depth = _normalize(depths)
    n_mtime = _normalize(mtimes)

    # Redistribute version weight to (inbound, mtime) when no instance has a version.
    w = dict(weights)
    if not has_any_version and w.get("version", 0):
        share = w["version"] / 2.0
        w["incoming_links"] = w.get("incoming_links", 0) + share
        w["mtime_freshness"] = w.get("mtime_freshness", 0) + share
        w["version"] = 0.0

    best_idx = 0
    best_score = float("-inf")
    for i, _inst in enumerate(group):
        score = (
            n_semver[i] * w["version"]
            + n_incoming[i] * w["incoming_links"]
            + n_depth[i] * w.get("path_depth", 0)
            + n_mtime[i] * w["mtime_freshness"]
        )
        if score > best_score:
            best_score = score
            best_idx = i
    return group[best_idx]


def _group_by_hash_and_name(
    instances: list[SkillInstance],
) -> dict[tuple[str, str], list[SkillInstance]]:
    """Dup groups require BOTH identical body hash AND identical dir_name.

    Different-named skills that happen to share content are NOT a safe dedup
    target — they might intentionally be registered under separate identities.
    """
    by_key: dict[tuple[str, str], list[SkillInstance]] = defaultdict(list)
    for inst in instances:
        if inst.body_hash:
            by_key[(inst.body_hash, inst.dir_name)].append(inst)
    return by_key


def _group_by_name(instances: list[SkillInstance]) -> dict[str, list[SkillInstance]]:
    by_name: dict[str, list[SkillInstance]] = defaultdict(list)
    for inst in instances:
        by_name[inst.dir_name].append(inst)
    return by_name


def _build_dup_groups(
    instances: list[SkillInstance], weights: dict[str, float]
) -> list[DupGroup]:
    groups: list[DupGroup] = []
    for (body_hash, _name), members in _group_by_hash_and_name(instances).items():
        if len(members) < 2:
            continue
        master = elect_master(members, instances, weights)
        groups.append(DupGroup(body_hash=body_hash, instances=members, master=master))
    return groups


def _build_drift_groups(
    instances: list[SkillInstance], dup_groups: list[DupGroup]
) -> list[DriftGroup]:
    """Same dir_name but different body_hash AND not already covered by a dup group."""
    dup_member_ids = {id(inst) for g in dup_groups for inst in g.instances}
    drifts: list[DriftGroup] = []
    for name, members in _group_by_name(instances).items():
        if len(members) < 2:
            continue
        hashes = {inst.body_hash for inst in members}
        if len(hashes) < 2:
            continue
        # Filter out members that are already in dup groups (they're handled there).
        remaining = [m for m in members if id(m) not in dup_member_ids]
        if len(remaining) < 2:
            continue
        # Only include if at least 2 distinct hashes remain.
        if len({m.body_hash for m in remaining}) < 2:
            continue
        drifts.append(DriftGroup(name=name, instances=remaining))
    return drifts


def _find_stale(instances: list[SkillInstance], days_threshold: int) -> list[StaleSkill]:
    """Skills whose SKILL.md mtime is older than the threshold. mtime-only signal."""
    if days_threshold <= 0:
        return []
    now = time.time()
    cutoff_seconds = days_threshold * 86400.0
    out: list[StaleSkill] = []
    for inst in instances:
        if inst.mtime <= 0:
            continue
        age_seconds = now - inst.mtime
        if age_seconds > cutoff_seconds:
            out.append(StaleSkill(instance=inst, days_ago=int(age_seconds / 86400)))
    out.sort(key=lambda s: -s.days_ago)
    return out


def analyze(
    instances: list[SkillInstance],
    junk_files: list[JunkFile],
    broken_links: list[BrokenLink],
    weights: dict[str, float] | None = None,
    stale_days: int = STALE_DAYS_DEFAULT,
) -> AnalysisReport:
    weights = weights or DEFAULT_WEIGHTS

    by_runtime = Counter[Runtime](inst.runtime for inst in instances)
    by_category = Counter[Category](inst.category for inst in instances)

    dup_groups = _build_dup_groups(instances, weights)
    drift_groups = _build_drift_groups(instances, dup_groups)
    stale = _find_stale(instances, stale_days)

    return AnalysisReport(
        instances=instances,
        by_runtime=dict(by_runtime),
        by_category=dict(by_category),
        duplicates=dup_groups,
        drifts=drift_groups,
        broken_links=broken_links,
        junk_files=junk_files,
        stale=stale,
    )
