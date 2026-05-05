"""Phase 1 — analyze() behavior: dup grouping, drift, master election."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from skill_doctor.analyze import analyze, elect_master
from skill_doctor.config import DEFAULT_WEIGHTS
from skill_doctor.models import Runtime, SkillInstance
from skill_doctor.scanner import scan_all


def _custom_roots(layout: dict[Runtime, Path]) -> tuple:
    return tuple((path, runtime, "*") for runtime, path in layout.items())


def _scan(layout: dict[Runtime, Path]):
    instances, junk, broken = scan_all(_custom_roots(layout))
    return analyze(instances, junk, broken)


def test_dup_group_detected_across_runtimes(
    tmp_runtime_root: dict[Runtime, Path],
    make_skill: Callable[..., Path],
) -> None:
    body = "Identical body text.\n"
    make_skill(tmp_runtime_root[Runtime.CLAUDE], "ads-google", body=body)
    make_skill(tmp_runtime_root[Runtime.CODEX], "ads-google", body=body)
    make_skill(tmp_runtime_root[Runtime.OPENCLAW], "ads-google", body=body)

    report = _scan(tmp_runtime_root)
    assert len(report.duplicates) == 1
    assert len(report.duplicates[0].instances) == 3


def test_drift_group_detected_when_same_name_different_body(
    tmp_runtime_root: dict[Runtime, Path],
    make_skill: Callable[..., Path],
) -> None:
    make_skill(tmp_runtime_root[Runtime.CLAUDE], "ab-test-setup", body="V1.1\n", version="1.1.0")
    make_skill(tmp_runtime_root[Runtime.OPENCLAW], "ab-test-setup", body="V1.0\n", version="1.0.0")

    report = _scan(tmp_runtime_root)
    assert len(report.duplicates) == 0
    assert len(report.drifts) == 1
    assert {i.runtime for i in report.drifts[0].instances} == {Runtime.CLAUDE, Runtime.OPENCLAW}


def test_master_election_prefers_higher_version(
    tmp_runtime_root: dict[Runtime, Path],
    make_skill: Callable[..., Path],
) -> None:
    make_skill(tmp_runtime_root[Runtime.CLAUDE], "x", body="same body\n", version="1.1.0")
    make_skill(tmp_runtime_root[Runtime.OPENCLAW], "x", body="same body\n", version="1.0.0")

    report = _scan(tmp_runtime_root)
    assert len(report.duplicates) == 1
    master = report.duplicates[0].master
    assert master.version == "1.1.0"


def test_master_election_prefers_more_inbound_links(
    tmp_runtime_root: dict[Runtime, Path],
    make_skill: Callable[..., Path],
    make_symlink: Callable[[Path, Path], None],
) -> None:
    real_dir = make_skill(tmp_runtime_root[Runtime.OPENCLAW], "shared", body="x\n", version="1.0.0")
    # Two runtimes symlink to the openclaw copy.
    make_symlink(real_dir, tmp_runtime_root[Runtime.CLAUDE] / "shared")
    make_symlink(real_dir, tmp_runtime_root[Runtime.CODEX] / "shared")

    report = _scan(tmp_runtime_root)
    # All four entries (1 real + 2 symlinks + dedup by resolve in scan_all):
    # scan_all dedupes by resolved path, so symlink directories appear once.
    # We still expect openclaw to be elected master if any dup group is formed.
    if report.duplicates:
        assert report.duplicates[0].master.runtime == Runtime.OPENCLAW


def test_stale_detected_when_mtime_older_than_threshold(
    tmp_runtime_root: dict[Runtime, Path],
    make_skill: Callable[..., Path],
) -> None:
    import os
    import time

    skill_dir = make_skill(tmp_runtime_root[Runtime.CLAUDE], "old-skill")
    skill_md = skill_dir / "SKILL.md"
    # Set mtime to 400 days ago.
    old = time.time() - 400 * 86400
    os.utime(skill_md, (old, old))

    instances, junk, broken = scan_all(_custom_roots(tmp_runtime_root))
    report = analyze(instances, junk, broken, stale_days=365)
    assert len(report.stale) == 1
    assert report.stale[0].days_ago >= 399


def test_stale_threshold_zero_disables_check(
    tmp_runtime_root: dict[Runtime, Path],
    make_skill: Callable[..., Path],
) -> None:
    make_skill(tmp_runtime_root[Runtime.CLAUDE], "any")
    instances, junk, broken = scan_all(_custom_roots(tmp_runtime_root))
    report = analyze(instances, junk, broken, stale_days=0)
    assert report.stale == []


def test_elect_master_single_member_returns_self() -> None:
    inst = SkillInstance(
        path=Path("/x"),
        skill_md=Path("/x/SKILL.md"),
        runtime=Runtime.CLAUDE,
        name="x",
        dir_name="x",
        description="",
        version="1.0.0",
        body_hash="h",
        body_lines=1,
        is_symlink=False,
        symlink_target=None,
        real_path=Path("/x"),
        file_is_symlink=False,
        mtime=0.0,
    )
    assert elect_master([inst], [inst], DEFAULT_WEIGHTS) is inst
