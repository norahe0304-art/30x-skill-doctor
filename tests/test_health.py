"""Tests for the health-score subtractive model. Calibration tests check
that score bands correspond to the documented severity meaning."""

from __future__ import annotations

from skill_doctor.health import _to_grade, health_score
from skill_doctor.models import (
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


def _make_instance(name: str = "demo", runtime: Runtime = Runtime.CLAUDE) -> SkillInstance:
    return SkillInstance(
        path=f"/tmp/{name}",                      # type: ignore[arg-type]
        skill_md=None,
        runtime=runtime,
        name=name,
        dir_name=name,
        description="",
        version=None,
        body_hash="h",
        body_lines=0,
        is_symlink=False,
        symlink_target=None,
        real_path=f"/tmp/{name}",                 # type: ignore[arg-type]
        file_is_symlink=False,
        mtime=0,
        category=Category.OTHER,
    )


def _empty_report() -> AnalysisReport:
    inst = _make_instance()
    return AnalysisReport(
        instances=[inst],
        by_runtime={Runtime.CLAUDE: 1},
        by_category={Category.OTHER: 1},
    )


def test_clean_library_scores_100() -> None:
    breakdown = health_score(_empty_report())
    assert breakdown.score == 100
    assert breakdown.grade == "A"
    assert not breakdown.has_findings


def test_pending_dup_deducts_2() -> None:
    report = _empty_report()
    a = _make_instance("dup", Runtime.CLAUDE)
    b = _make_instance("dup", Runtime.CODEX)
    report.duplicates = [DupGroup(body_hash="h", instances=[a, b], master=a)]
    breakdown = health_score(report)
    # 1 pending group → 2 points off, score 98 → A
    assert breakdown.score == 98
    assert breakdown.grade == "A"
    assert breakdown.pending_dup_groups == 1


def test_aligned_dup_does_not_deduct() -> None:
    """Already-linked dup groups are noise, not a finding; they shouldn't penalize."""
    report = _empty_report()
    master = _make_instance("dup", Runtime.CLAUDE)
    follower = _make_instance("dup", Runtime.CODEX)
    follower.is_symlink = True
    follower.real_path = master.real_path
    report.duplicates = [
        DupGroup(body_hash="h", instances=[master, follower], master=master)
    ]
    breakdown = health_score(report)
    assert breakdown.score == 100
    assert breakdown.pending_dup_groups == 0


def test_broken_links_dominate_score() -> None:
    """Broken links are loss-free to fix and should weigh heaviest per finding."""
    report = _empty_report()
    report.broken_links = [
        BrokenLink(path=f"/tmp/x{i}", runtime=Runtime.CLAUDE, intended_target=f"/missing/{i}")  # type: ignore[arg-type]
        for i in range(5)
    ]
    breakdown = health_score(report)
    # 5 × 3 = 15 off → score 85 → B+
    assert breakdown.score == 85
    assert breakdown.grade == "B+"


def test_grade_band_anchors() -> None:
    assert _to_grade(100) == "A"
    assert _to_grade(95) == "A"
    assert _to_grade(94) == "A-"
    assert _to_grade(89) == "B+"
    assert _to_grade(80) == "B"
    assert _to_grade(65) == "C"
    assert _to_grade(50) == "D"
    assert _to_grade(49) == "F"
    assert _to_grade(0) == "F"


def test_extensive_clutter_floors_at_zero() -> None:
    """Real-world wreck should saturate at 0, not go negative."""
    report = _empty_report()
    # 200 pending dups + 100 broken = 700 deductions, way past 100
    instances = [_make_instance(f"x{i}") for i in range(2)]
    report.duplicates = [
        DupGroup(body_hash=f"h{i}", instances=instances, master=instances[0])
        for i in range(200)
    ]
    report.broken_links = [
        BrokenLink(path=f"/tmp/b{i}", runtime=Runtime.CLAUDE, intended_target=f"/x/{i}")  # type: ignore[arg-type]
        for i in range(100)
    ]
    breakdown = health_score(report)
    assert breakdown.score == 0
    assert breakdown.grade == "F"


def test_headline_message() -> None:
    clean = health_score(_empty_report())
    assert "clean" in clean.headline.lower()

    report = _empty_report()
    report.junk_files = [
        JunkFile(path=f"/tmp/j{i}", pattern=".DS_Store", runtime=Runtime.CLAUDE)  # type: ignore[arg-type]
        for i in range(40)
    ]
    breakdown = health_score(report)
    assert "Health" in breakdown.headline
    assert str(breakdown.score) in breakdown.headline


def test_stale_is_weakest_signal() -> None:
    """Stale dimension at 0.2 each — even 50 stales should keep score in A range."""
    report = _empty_report()
    inst = _make_instance()
    report.stale = [StaleSkill(instance=inst, days_ago=180) for _ in range(50)]
    breakdown = health_score(report)
    # 50 * 0.2 = 10 off → 90 → A-
    assert breakdown.score == 90
    assert breakdown.grade == "A-"


def test_drift_does_not_dominate() -> None:
    report = _empty_report()
    inst = _make_instance()
    report.drifts = [DriftGroup(name=f"d{i}", instances=[inst, inst]) for i in range(10)]
    breakdown = health_score(report)
    assert breakdown.score == 90
    assert breakdown.drift_groups == 10
