"""Phase 1 — categorize() correctness across path-prefix and keyword paths."""

from __future__ import annotations

from pathlib import Path

from skill_doctor.classify import categorize
from skill_doctor.models import Category, Runtime, SkillInstance


def _make_instance(name: str, description: str = "") -> SkillInstance:
    return SkillInstance(
        path=Path(f"/tmp/{name}"),
        skill_md=Path(f"/tmp/{name}/SKILL.md"),
        runtime=Runtime.CLAUDE,
        name=name,
        dir_name=name,
        description=description,
        version=None,
        body_hash="x" * 64,
        body_lines=10,
        is_symlink=False,
        symlink_target=None,
        real_path=Path(f"/tmp/{name}"),
        file_is_symlink=False,
        mtime=0.0,
    )


def test_path_prefix_seo() -> None:
    assert categorize(_make_instance("30x-seo-keywords")) == Category.SEO


def test_path_prefix_ads() -> None:
    assert categorize(_make_instance("ads-google")) == Category.ADS


def test_path_prefix_deploy() -> None:
    assert categorize(_make_instance("vercel:deploy")) == Category.DEPLOY


def test_keyword_marketing() -> None:
    instance = _make_instance("copy-tool", description="When the user wants copywriting help.")
    assert categorize(instance) == Category.MARKETING


def test_keyword_data() -> None:
    instance = _make_instance("track-it", description="Sets up GA4 analytics tracking.")
    assert categorize(instance) == Category.DATA


def test_uncategorized_when_empty_description() -> None:
    instance = _make_instance("mystery", description="")
    assert categorize(instance) == Category.UNCATEGORIZED


def test_other_when_description_unmatched() -> None:
    instance = _make_instance("mystery", description="A philosophical skill about nothing.")
    assert categorize(instance) == Category.OTHER
