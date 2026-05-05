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

from rich.console import Console
from rich.table import Table

from .asm_bridge import QualityRow, has_asm
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
) -> None:
    c = console or _console
    c.print()
    c.print(
        f"📂 你有 [bold]{report.total_skills}[/bold] 个 skill, "
        f"跨 [bold]{report.total_runtimes}[/bold] 个 runtime:"
    )
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
    _render_issues(report, c)
    _render_quality(quality_rows, c)
    _render_footer(report, c)


def _render_categories(report: AnalysisReport, c: Console) -> None:
    cats = [(cat, n) for cat, n in report.by_category.items() if n > 0]
    if not cats:
        return
    cats.sort(key=lambda kv: -kv[1])
    c.print("  按用途分类:")
    chunks = [f"[bold]{cat.value}[/bold] ({n})" for cat, n in cats]
    line = "    " + " | ".join(chunks)
    c.print(line)
    c.print()


def _render_issues(report: AnalysisReport, c: Console) -> None:
    has_any = False
    if report.duplicates:
        instances = sum(len(g.instances) for g in report.duplicates)
        c.print(
            f"[orange3]🟠 {len(report.duplicates)} 组重复[/orange3] / duplicates "
            f"({instances} instances)"
        )
        has_any = True
    if report.drifts:
        c.print(
            f"[yellow]🟡 {len(report.drifts)} 组漂移[/yellow] / drift "
            f"(同名不同版本)"
        )
        has_any = True
    if report.broken_links:
        c.print(f"[red]✗  {len(report.broken_links)} 个断链[/red] / broken links")
        has_any = True
    if report.junk_files:
        c.print(f"[grey50]🗑 {len(report.junk_files)} 个垃圾文件[/grey50] / junk")
        has_any = True
    if report.stale:
        oldest = report.stale[0].days_ago
        c.print(
            f"[grey62]🕰 {len(report.stale)} 个 skill 长时间未改动[/grey62] / stale "
            f"(最久 {oldest} 天，可能过时也可能稳定)"
        )
        has_any = True
    if has_any:
        c.print()


def _render_quality(rows: list[QualityRow] | None, c: Console) -> None:
    if rows is None or not rows:
        return
    grades = Counter(r.grade for r in rows)
    summary = " ".join(f"{g}:{n}" for g, n in sorted(grades.items()))
    c.print("[bold cyan]📋 SKILL.md write quality[/bold cyan]")
    c.print(f"  {len(rows)} skills scored   [dim]{summary}[/dim]")
    c.print("[dim]  Lowest 5 + suggestions:[/dim]")
    for row in rows[:5]:
        c.print(f"  [cyan]{row.name}[/cyan]  [bold]{row.score}/100  {row.grade}[/bold]")
        for suggestion in row.suggestions[:3]:
            c.print(f"    [dim]• {suggestion}[/dim]")
    c.print("[dim]💡 单 skill 详细诊断: asm eval <skill 路径>[/dim]")
    c.print()


def _render_footer(report: AnalysisReport, c: Console) -> None:
    if report.has_issues:
        c.print("→ 整理: [bold]skill-doctor clean[/bold]")
    else:
        c.print("[green]✓ 一切正常, 没有需要整理的。[/green]")
    c.print("[dim]💡 完整大表: skill-doctor --full[/dim]")
    if not has_asm():
        c.print(
            "[dim]💡 装 asm 后会自动加 SKILL.md 写法质量评估: "
            "npm i -g agent-skill-manager[/dim]"
        )
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
