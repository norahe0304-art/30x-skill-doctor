"""Phase 1 — scanner.scan_all behavior against synthetic runtime trees."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from skill_doctor.models import Runtime
from skill_doctor.scanner import scan_all


def _custom_roots(layout: dict[Runtime, Path]) -> tuple:
    return tuple((path, runtime, "*") for runtime, path in layout.items())


def test_scan_finds_basic_skill(
    tmp_runtime_root: dict[Runtime, Path],
    make_skill: Callable[..., Path],
) -> None:
    make_skill(tmp_runtime_root[Runtime.CLAUDE], "ads-google")
    instances, _, _ = scan_all(_custom_roots(tmp_runtime_root))
    assert len(instances) == 1
    assert instances[0].name == "ads-google"
    assert instances[0].runtime == Runtime.CLAUDE


def test_scan_detects_macos_junk(
    tmp_runtime_root: dict[Runtime, Path],
    make_skill: Callable[..., Path],
) -> None:
    skill_dir = make_skill(tmp_runtime_root[Runtime.CLAUDE], "ads-google")
    (skill_dir / "CHANGELOG 2.md").write_text("junk", encoding="utf-8")
    (skill_dir / ".DS_Store").write_text("", encoding="utf-8")

    _, junk, _ = scan_all(_custom_roots(tmp_runtime_root))
    pattern_tags = {j.pattern for j in junk}
    assert "macos-copy" in pattern_tags
    assert "ds-store" in pattern_tags


def test_scan_detects_broken_symlink(
    tmp_runtime_root: dict[Runtime, Path],
    make_symlink: Callable[[Path, Path], None],
) -> None:
    target = tmp_runtime_root[Runtime.OPENCLAW] / "nonexistent"
    link = tmp_runtime_root[Runtime.CLAUDE] / "broken"
    make_symlink(target, link)

    _, _, broken = scan_all(_custom_roots(tmp_runtime_root))
    assert len(broken) == 1
    assert broken[0].path == link


def test_scan_resolves_symlink_chain(
    tmp_runtime_root: dict[Runtime, Path],
    make_skill: Callable[..., Path],
    make_symlink: Callable[[Path, Path], None],
) -> None:
    real_dir = make_skill(tmp_runtime_root[Runtime.OPENCLAW], "ab-test-setup")
    link = tmp_runtime_root[Runtime.CLAUDE] / "ab-test-setup"
    make_symlink(real_dir, link)

    instances, _, _ = scan_all(_custom_roots(tmp_runtime_root))
    by_runtime = {inst.runtime for inst in instances}
    # Both runtimes saw the skill; symlink resolves to the same real_path.
    assert {Runtime.CLAUDE, Runtime.OPENCLAW} == by_runtime
    real_paths = {inst.real_path for inst in instances}
    # symlink resolves to openclaw real_dir; openclaw entry resolves to itself.
    assert real_dir.resolve() in real_paths


def test_scan_records_version_and_description(
    tmp_runtime_root: dict[Runtime, Path],
    make_skill: Callable[..., Path],
) -> None:
    make_skill(
        tmp_runtime_root[Runtime.CLAUDE],
        "copywriting",
        description="When the user wants copywriting help.",
        version="1.2.3",
    )
    instances, _, _ = scan_all(_custom_roots(tmp_runtime_root))
    inst = instances[0]
    assert inst.version == "1.2.3"
    assert "copywriting" in inst.description.lower()


def test_scan_skips_directory_without_skill_md(
    tmp_runtime_root: dict[Runtime, Path],
) -> None:
    (tmp_runtime_root[Runtime.CLAUDE] / "no-skill").mkdir()
    instances, _, _ = scan_all(_custom_roots(tmp_runtime_root))
    assert instances == []
