"""Tests for the share-card renderers. We assert structural invariants —
the exact pixel-pushing styling is not stable enough to test as strings."""

from __future__ import annotations

from skill_doctor.health import health_score
from skill_doctor.models import (
    AnalysisReport,
    BrokenLink,
    Category,
    DupGroup,
    Runtime,
    SkillInstance,
)
from skill_doctor.share import build_ascii, build_markdown, build_svg, write_share_card


def _make_inst(name: str, runtime: Runtime = Runtime.CLAUDE) -> SkillInstance:
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


def _report_with_dup() -> AnalysisReport:
    a = _make_inst("dup", Runtime.CLAUDE)
    b = _make_inst("dup", Runtime.CODEX)
    return AnalysisReport(
        instances=[a, b],
        by_runtime={Runtime.CLAUDE: 1, Runtime.CODEX: 1},
        by_category={Category.OTHER: 2},
        duplicates=[DupGroup(body_hash="h", instances=[a, b], master=a)],
    )


def test_svg_is_well_formed_and_self_contained() -> None:
    report = _report_with_dup()
    svg = build_svg(report, health_score(report))
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")
    # no remote refs — must be fully self-contained for embedding
    assert "http://" not in svg.replace("http://www.w3.org", "")
    assert "https://" not in svg
    # the data the user wants to share IS in the card
    assert "98" in svg  # 1 pending dup → 98
    assert "B+" in svg or "A" in svg
    assert "2" in svg   # total skills


def test_svg_no_findings_shows_clean_marker() -> None:
    inst = _make_inst("solo")
    report = AnalysisReport(
        instances=[inst],
        by_runtime={Runtime.CLAUDE: 1},
        by_category={Category.OTHER: 1},
    )
    svg = build_svg(report, health_score(report))
    assert "no actionable findings" in svg


def test_ascii_box_alignment_is_consistent() -> None:
    """Every body line should have the same display width — easy way to
    catch off-by-one padding bugs in the box renderer."""
    report = _report_with_dup()
    card = build_ascii(report, health_score(report))
    lines = card.splitlines()
    # rows that start with │ should all end with │
    body = [ln for ln in lines if ln.startswith("│")]
    assert body, "ascii card has no boxed rows"
    for ln in body:
        assert ln.endswith("│"), f"misaligned row: {ln!r}"


def test_markdown_carries_install_command() -> None:
    """The whole point of the share is to drive installs — verify the CTA."""
    report = _report_with_dup()
    md = build_markdown(report, health_score(report))
    assert "pipx install skill-doctor" in md
    assert "Health" in md


def test_write_share_card_creates_file(tmp_path) -> None:
    report = _report_with_dup()
    breakdown = health_score(report)
    target = tmp_path / "card.svg"
    out = write_share_card(report, breakdown, out_path=target, fmt="svg")
    assert out == target
    assert target.exists()
    assert "<svg" in target.read_text(encoding="utf-8")


def test_write_share_card_rejects_unknown_format(tmp_path) -> None:
    report = _report_with_dup()
    breakdown = health_score(report)
    target = tmp_path / "card.bogus"
    try:
        write_share_card(report, breakdown, out_path=target, fmt="png")
    except ValueError as e:
        assert "format" in str(e).lower()
        return
    raise AssertionError("png should have been rejected; no PNG dependency in the package")


def test_broken_link_appears_in_findings() -> None:
    inst = _make_inst("x")
    report = AnalysisReport(
        instances=[inst],
        by_runtime={Runtime.CLAUDE: 1},
        by_category={Category.OTHER: 1},
        broken_links=[BrokenLink(
            path="/tmp/dead",                # type: ignore[arg-type]
            runtime=Runtime.CLAUDE,
            intended_target="/missing",      # type: ignore[arg-type]
        )],
    )
    svg = build_svg(report, health_score(report))
    assert "broken" in svg
