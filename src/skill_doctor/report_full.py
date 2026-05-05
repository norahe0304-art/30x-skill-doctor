"""
[INPUT]: 依赖 rich.console.Console / rich.table.Table，依赖 ./models 的数据类型。
[OUTPUT]: 对外提供 render_full(report, runtime_filter, category_filter, console)。
[POS]: 大表渲染层。报告默认视图在 ./report.py，full 大表单独切到这里以保持每文件 ≤200 行。
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .models import (
    RUNTIME_LABEL,
    AnalysisReport,
    Category,
    DupGroup,
    Runtime,
    SkillInstance,
)

_STATUS_ORDER = {"broken": 0, "drift": 1, "dup": 2, "ok": 3}


def render_full(
    report: AnalysisReport,
    runtime_filter: Runtime | None = None,
    category_filter: Category | None = None,
    console: Console | None = None,
    no_truncate: bool = False,
) -> None:
    c = console or Console()
    rows = _aggregate_by_name(report)
    if runtime_filter is not None:
        rows = [r for r in rows if runtime_filter in r["runtimes"]]
    if category_filter is not None:
        rows = [r for r in rows if r["category"] == category_filter]

    rows.sort(key=lambda r: (_STATUS_ORDER.get(r["status"], 99), r["name"]))

    table = Table(
        title=f"Skill Map ({len(rows)} skills shown)",
        show_lines=False,
        title_style="bold",
        expand=no_truncate,
    )
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Runtimes", style="white")
    table.add_column("Master", style="dim", no_wrap=no_truncate, overflow="fold")
    table.add_column("Cat", style="magenta")
    table.add_column("Status", style="white")

    for row in rows:
        runtimes_str = " / ".join(RUNTIME_LABEL[r] for r in row["runtimes"])
        master = _shorten_path(row["master_path"]) if row["master_path"] else "—"
        table.add_row(
            row["name"],
            runtimes_str,
            master,
            row["category"].value,
            row["status_label"],
        )
    c.print(table)


def _aggregate_by_name(report: AnalysisReport) -> list[dict]:
    """Group instances by dir_name; tag with worst status across the group."""
    by_name: dict[str, list[SkillInstance]] = defaultdict(list)
    for inst in report.instances:
        by_name[inst.dir_name].append(inst)

    dup_names = {g.instances[0].dir_name for g in report.duplicates}
    drift_names = {g.name for g in report.drifts}
    broken_paths = {b.path for b in report.broken_links}

    rows: list[dict] = []
    for name, members in by_name.items():
        status, label = _pick_status(name, members, dup_names, drift_names, broken_paths)
        master_path = _master_path_for(name, members, report.duplicates)
        rows.append(
            {
                "name": name,
                "runtimes": tuple(m.runtime for m in members),
                "category": members[0].category,
                "master_path": master_path,
                "status": status,
                "status_label": label,
            }
        )
    return rows


def _pick_status(
    name: str,
    members: list[SkillInstance],
    dup_names: set[str],
    drift_names: set[str],
    broken_paths: set[Path],
) -> tuple[str, str]:
    if any(m.path in broken_paths for m in members):
        return "broken", "[red]✗ broken[/red]"
    if name in drift_names:
        return "drift", "[yellow]🟡 drift[/yellow]"
    if name in dup_names:
        return "dup", "[orange3]🟠 dup[/orange3]"
    return "ok", "[green]✓[/green]"


def _master_path_for(
    name: str, members: list[SkillInstance], dups: list[DupGroup]
) -> Path | None:
    for g in dups:
        if g.instances[0].dir_name == name:
            return g.master.path
    if len(members) == 1:
        return members[0].path
    return None


def _shorten_path(p: Path) -> str:
    home = str(Path.home())
    s = str(p)
    return s.replace(home, "~", 1) if s.startswith(home) else s
