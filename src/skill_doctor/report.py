"""
[INPUT]: 依赖 rich.console.Console / rich.table.Table，依赖 ./asm_bridge 的 QualityRow，
         依赖 ./models 的 AnalysisReport 与 RUNTIME_LABEL。
[OUTPUT]: 对外提供 render_default / render_json / report_to_dict。
         render_full 在 ./report_full.py，便于按文件 ≤200 行的边界拆分。
[POS]: 视图渲染层（默认 + JSON）。无业务逻辑，纯展示。
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .asm_bridge import QualityRow, has_asm
from .i18n import category_label, t
from .models import (
    RUNTIME_LABEL,
    AnalysisReport,
    SkillInstance,
)

_console = Console()


# ─── default view ────────────────────────────────────────────────────────────
def render_default(
    report: AnalysisReport,
    quality_rows: list[QualityRow] | None = None,
    console: Console | None = None,
    show_all: bool = False,
) -> None:
    c = console or _console
    c.print()
    c.print(t("skills_across_runtimes", n=report.total_skills, m=report.total_runtimes))
    c.print()

    table = Table(show_header=False, show_edge=False, padding=(0, 2), box=None)
    table.add_column("Runtime", style="cyan")
    table.add_column("count", justify="right")
    for runtime, count in sorted(report.by_runtime.items(), key=lambda kv: -kv[1]):
        if count > 0:
            table.add_row(f"  {RUNTIME_LABEL[runtime]}", str(count))
    c.print(table)
    c.print()

    _render_categories(report, c)
    _render_issues(report, c, show_all=show_all)
    _render_quality(quality_rows, c)
    _render_footer(report, c)


def _render_categories(report: AnalysisReport, c: Console) -> None:
    cats = [(cat, n) for cat, n in report.by_category.items() if n > 0]
    if not cats:
        return
    cats.sort(key=lambda kv: -kv[1])
    c.print(t("categories"))
    chunks = [f"[bold]{category_label(cat)}[/bold] ({n})" for cat, n in cats]
    line = "    " + " | ".join(chunks)
    c.print(line)
    c.print()


def _render_issues(report: AnalysisReport, c: Console, show_all: bool = False) -> None:
    has_any = False
    if report.duplicates:
        instances = sum(len(g.instances) for g in report.duplicates)
        c.print(t("header_dup", n=len(report.duplicates), i=instances))
        _render_dup_list(report, c, show_all)
        has_any = True
    if report.drifts:
        c.print(t("header_drift", n=len(report.drifts)))
        _render_drift_list(report, c, show_all)
        has_any = True
    if report.broken_links:
        c.print(t("header_broken", n=len(report.broken_links)))
        _render_broken_list(report, c, show_all)
        has_any = True
    if report.junk_files:
        c.print(t("header_junk", n=len(report.junk_files)))
        _render_junk_list(report, c, show_all)
        has_any = True
    if report.stale:
        oldest = report.stale[0].days_ago
        c.print(t("header_stale", n=len(report.stale), oldest=oldest))
        _render_stale_list(report, c, show_all)
        has_any = True
    if has_any:
        c.print()


def _short(p) -> str:
    home = str(Path.home())
    s = str(p)
    return s.replace(home, "~", 1) if s.startswith(home) else s


DEFAULT_LIMIT = 30


def _list_tail(shown: int, total: int, method_lines: list[str], c: Console) -> None:
    if total > shown:
        c.print(t("tail_more", rest=total - shown))
    for line in method_lines:
        c.print(f"  [dim italic]{line}[/dim italic]")
    c.print()


def _render_dup_list(report: AnalysisReport, c: Console, show_all: bool) -> None:
    limit = len(report.duplicates) if show_all else DEFAULT_LIMIT
    for g in report.duplicates[:limit]:
        name = g.instances[0].dir_name
        c.print(f"  [bold]{name}[/bold]  [dim]{t('dup_copies', n=len(g.instances))}[/dim]")
        c.print(
            f"    [orange3]{t('dup_master')}[/orange3] [dim]{_short(g.master.path)}[/dim]"
        )
        for inst in g.instances:
            if inst is g.master:
                continue
            c.print(f"    [dim]{t('dup_copy')}[/dim]   [dim]{_short(inst.path)}[/dim]")
    _list_tail(
        limit, len(report.duplicates),
        [
            "Detection: same dir_name + SHA-256(normalized SKILL.md body) match",
            "Master election: version 40% · inbound symlinks 30% · "
            "path depth 15% · mtime 15%",
            "Provenance: NIST FIPS 180-4 (SHA-256) · git content-addressable model",
        ],
        c,
    )


def _render_drift_list(report: AnalysisReport, c: Console, show_all: bool) -> None:
    limit = len(report.drifts) if show_all else DEFAULT_LIMIT
    for g in report.drifts[:limit]:
        c.print(f"  [bold]{g.name}[/bold]  [dim]{t('drift_div', n=len(g.instances))}[/dim]")
        for inst in g.instances:
            ver = f"v{inst.version}" if inst.version else t("no_version")
            c.print(
                f"    [yellow]{inst.runtime.value:13}[/yellow] "
                f"[dim]{ver:12}[/dim] [dim]{_short(inst.path)}[/dim]"
            )
    _list_tail(
        limit, len(report.drifts),
        [
            "Detection: same dir_name but SHA-256 differs",
            "Policy: never auto-resolved — divergence may be intentional",
            "Version (if any) follows: SemVer 2.0.0 (semver.org)",
        ],
        c,
    )


def _render_broken_list(report: AnalysisReport, c: Console, show_all: bool) -> None:
    limit = len(report.broken_links) if show_all else DEFAULT_LIMIT
    for b in report.broken_links[:limit]:
        c.print(f"  [red]{_short(b.path)}[/red]")
        c.print(f"    [dim]{t('broken_was')} {_short(b.intended_target)}[/dim]")
    _list_tail(
        limit, len(report.broken_links),
        [
            "Detection: Path.is_symlink() and not Path.exists()",
            "Equivalent to: find <root> -xtype l (POSIX find(1))",
            "Provenance: POSIX.1-2017 symlink semantics · macOS BSD lstat(2)",
        ],
        c,
    )


def _render_junk_list(report: AnalysisReport, c: Console, show_all: bool) -> None:
    limit = len(report.junk_files) if show_all else DEFAULT_LIMIT
    for j in report.junk_files[:limit]:
        c.print(f"  [grey50]{_short(j.path)}[/grey50] [dim]({j.pattern})[/dim]")
    _list_tail(
        limit, len(report.junk_files),
        [
            r"Patterns: ' \d+\.(md|json|py)' · '.DS_Store' · '^._' · '*.swp' · '*~'",
            "Scan: Path.rglob (recursive across each skill tree)",
            "Provenance: macOS Finder/iCloud collision renaming · Vim ':help swap-file'",
        ],
        c,
    )


def _render_stale_list(report: AnalysisReport, c: Console, show_all: bool) -> None:
    limit = len(report.stale) if show_all else DEFAULT_LIMIT
    for s in report.stale[:limit]:
        idle = t("stale_idle", n=s.days_ago)
        c.print(
            f"  [grey62]{s.instance.dir_name:30}[/grey62] "
            f"[dim]{idle} {_short(s.instance.path)}[/dim]"
        )
    _list_tail(
        limit, len(report.stale),
        [
            "Detection: max mtime across skill tree > threshold (default 90 days)",
            "Limit: mtime != invocation. Threshold tunable via --stale-days N",
            "Provenance: POSIX stat(2) st_mtime · not atime (noatime mount default)",
        ],
        c,
    )


def _render_quality(rows: list[QualityRow] | None, c: Console) -> None:
    if rows is None or not rows:
        return
    grades = Counter(r.grade for r in rows)
    summary = " ".join(f"{g}:{n}" for g, n in sorted(grades.items()))
    c.print(t("quality_header"))
    c.print(t("quality_scored", n=len(rows), summary=summary))
    c.print(t("quality_lowest"))
    for row in rows[:5]:
        c.print(f"  [cyan]{row.name}[/cyan]  [bold]{row.score}/100  {row.grade}[/bold]")
        for suggestion in row.suggestions[:3]:
            c.print(f"    [dim]• {suggestion}[/dim]")
    c.print()


def _render_footer(report: AnalysisReport, c: Console) -> None:
    c.print(t("footer_clean") if report.has_issues else t("footer_ok"))
    c.print(t("footer_full"))
    if not has_asm():
        c.print(t("footer_quality"))
    c.print()


# ─── JSON ────────────────────────────────────────────────────────────────────
def render_json(report: AnalysisReport, console: Console | None = None) -> None:
    c = console or _console
    c.print_json(json.dumps(report_to_dict(report), default=str))


def report_to_dict(report: AnalysisReport) -> dict:
    return {
        "totals": {
            "skills": report.total_skills,
            "runtimes": report.total_runtimes,
        },
        "by_runtime": {r.value: n for r, n in report.by_runtime.items() if n > 0},
        "by_category": {c.value: n for c, n in report.by_category.items() if n > 0},
        "duplicates": [
            {
                "name": g.instances[0].dir_name,
                "body_hash": g.body_hash,
                "instances": [_inst_to_dict(i) for i in g.instances],
                "master": _inst_to_dict(g.master),
            }
            for g in report.duplicates
        ],
        "drifts": [
            {"name": d.name, "instances": [_inst_to_dict(i) for i in d.instances]}
            for d in report.drifts
        ],
        "broken_links": [
            {
                "path": str(b.path),
                "runtime": b.runtime.value,
                "intended_target": str(b.intended_target),
            }
            for b in report.broken_links
        ],
        "junk_files": [
            {"path": str(j.path), "pattern": j.pattern, "runtime": j.runtime.value}
            for j in report.junk_files
        ],
    }


def _inst_to_dict(i: SkillInstance) -> dict:
    return {
        "name": i.name,
        "dir_name": i.dir_name,
        "runtime": i.runtime.value,
        "path": str(i.path),
        "real_path": str(i.real_path),
        "is_symlink": i.is_symlink,
        "version": i.version,
        "category": i.category.value,
    }
