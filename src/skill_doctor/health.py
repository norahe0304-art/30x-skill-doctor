"""
[INPUT]: 依赖 ./models 的 AnalysisReport。
[OUTPUT]: 对外提供 HealthBreakdown dataclass + health_score(report) 纯函数。
[POS]: 健康分数计算层。被 report.py（首屏 wow stat）与 share.py（SVG 卡片）共享，
       从一个地方调权重避免漂移。
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import AnalysisReport

# ─── Weights ────────────────────────────────────────────────────────────────
# Pure subtractive model: start at 100, deduct per finding.
# Calibrated so a brand-new clean library scores ≥ 95 and a 187-instance / 38-drift
# wreck (the maintainer's real machine pre-cleanup) lands at ≈ 0-30 — covering the
# whole "wow it's bad" spectrum without saturating at 0 on the typical user.
WEIGHTS = {
    "pending_dup": 2.0,    # actionable, auto-fixable by `clean`
    "broken_link": 3.0,    # symlinks are payload-free; fix is loss-free
    "junk_file":   0.5,    # nuisance, low signal
    "drift":       1.0,    # needs human judgment
    "stale":       0.2,    # weakest dimension (mtime != invocation)
}


@dataclass(frozen=True)
class HealthBreakdown:
    """Self-contained snapshot of a single scan's health. Passed to renderers."""

    score: int           # 0-100, clipped
    grade: str           # A / A- / B+ / B / B- / C+ / C / C- / D / F
    total_skills: int
    total_runtimes: int
    pending_dup_groups: int
    pending_dup_instances: int
    drift_groups: int
    broken_links: int
    junk_files: int
    stale_skills: int

    @property
    def headline(self) -> str:
        """A single human-friendly line: 'Health 73/100 (C+)' or 'Library is clean'."""
        if self.score >= 95 and not self.has_findings:
            return "Library is clean"
        return f"Health {self.score}/100 ({self.grade})"

    @property
    def has_findings(self) -> bool:
        return any(
            (self.pending_dup_groups, self.drift_groups, self.broken_links,
             self.junk_files, self.stale_skills)
        )


def _to_grade(score: int) -> str:
    # Bands match a typical US academic curve. Anchors:
    #   A (95)  spotless
    #   B (80)  a handful of fixable items
    #   C (65)  noticeable accumulation
    #   D (50)  needs a real cleanup pass
    #   F (<50) extensively cluttered
    if score >= 95:
        return "A"
    if score >= 90:
        return "A-"
    if score >= 85:
        return "B+"
    if score >= 80:
        return "B"
    if score >= 75:
        return "B-"
    if score >= 70:
        return "C+"
    if score >= 65:
        return "C"
    if score >= 60:
        return "C-"
    if score >= 50:
        return "D"
    return "F"


def health_score(report: AnalysisReport) -> HealthBreakdown:
    """Compute the 0-100 health score and structured breakdown."""
    pending_groups = [g for g in report.duplicates if not g.is_aligned]
    pending_instances = sum(len(g.instances) - 1 for g in pending_groups)
    drifts = len(report.drifts)
    broken = len(report.broken_links)
    junk = len(report.junk_files)
    stale = len(report.stale)

    raw = (
        100.0
        - len(pending_groups) * WEIGHTS["pending_dup"]
        - drifts                * WEIGHTS["drift"]
        - broken                * WEIGHTS["broken_link"]
        - junk                  * WEIGHTS["junk_file"]
        - stale                 * WEIGHTS["stale"]
    )
    score = max(0, min(100, int(round(raw))))

    return HealthBreakdown(
        score=score,
        grade=_to_grade(score),
        total_skills=report.total_skills,
        total_runtimes=report.total_runtimes,
        pending_dup_groups=len(pending_groups),
        pending_dup_instances=pending_instances,
        drift_groups=drifts,
        broken_links=broken,
        junk_files=junk,
        stale_skills=stale,
    )
