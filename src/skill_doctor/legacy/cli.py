"""
[INPUT]: Depends on Typer, Rich, questionary, and the Skill Doctor core engine.
[OUTPUT]: Provides the `skill-doctor` guided CLI and JSON-capable subcommands.
[POS]: Thin command layer for humans, agents, and scripts.
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import questionary
import typer
from rich.console import Console

from skill_doctor.compare import build_runtime_comparison
from skill_doctor.config import save_visibility_snapshot
from skill_doctor.report import (
    dump_json,
    render_check,
    render_comparison,
    render_organize,
    render_snapshot,
)
from skill_doctor.rules import build_visibility_snapshot, enrich_report
from skill_doctor.runtime_registry import build_runtime_registry
from skill_doctor.scanner import scan_skills

app = typer.Typer(invoke_without_command=True, no_args_is_help=False)
console = Console()
JsonOption = Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON.")]
AllOption = Annotated[bool, typer.Option("--all", help="Show all skills, not just issues.")]
LimitOption = Annotated[int | None, typer.Option("--limit", help="Limit rendered/JSON skills.")]
StandardsOption = Annotated[
    bool,
    typer.Option("--standards", help="Show standards and rule maturity mappings."),
]
DedupeOption = Annotated[
    bool,
    typer.Option("--dedupe", help="Inspect top duplicate and likely-overlap groups."),
]
OrganizeOption = Annotated[
    bool,
    typer.Option("--organize", help="Show visibility shelves and metadata categories."),
]
CategoryOption = Annotated[
    str | None,
    typer.Option("--category", help="Filter housekeeping details by use category."),
]
StatusOption = Annotated[
    str | None,
    typer.Option("--status", help="Filter housekeeping details by status shelf."),
]
RuntimeOption = Annotated[
    str | None,
    typer.Option("--runtime", help="Filter housekeeping details by runtime id."),
]
HomeOption = Annotated[Path | None, typer.Option("--home", help="Override home directory.")]
ProjectOption = Annotated[
    Path | None,
    typer.Option("--project", help="Override project directory."),
]
SaveOption = Annotated[bool, typer.Option("--save", help="Save visibility metadata.")]
YesOption = Annotated[bool, typer.Option("--yes", help="Confirm metadata-only save.")]


def _home_project(home: Path | None, project: Path | None) -> tuple[Path, Path]:
    return (Path.home() if home is None else home, Path.cwd() if project is None else project)


def _check_report(home: Path | None, project: Path | None):
    home_path, project_path = _home_project(home, project)
    registry = build_runtime_registry(home=home_path, project=project_path)
    return enrich_report(scan_skills(registry))


@app.callback()
def root(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return
    console.print("[bold]Skill Doctor[/bold]")
    report = _check_report(None, None)
    render_check(console, report, limit=12)
    choice = questionary.select(
        "Next step?",
        choices=[
            "Show visibility view",
            "Show visibility snapshot",
            "Exit",
        ],
    ).ask()
    if choice == "Show visibility view":
        render_organize(console, report, limit=12)
    elif choice == "Show visibility snapshot":
        render_snapshot(console, build_visibility_snapshot(report), limit=0)


@app.command()
def check(
    json_output: JsonOption = False,
    show_all: AllOption = False,
    limit: LimitOption = None,
    show_standards: StandardsOption = False,
    show_dedupe: DedupeOption = False,
    show_organize: OrganizeOption = False,
    category: CategoryOption = None,
    status: StatusOption = None,
    runtime: RuntimeOption = None,
    home: HomeOption = None,
    project: ProjectOption = None,
) -> None:
    report = _check_report(home, project)
    if json_output:
        typer.echo(dump_json(report, limit=limit))
        return
    if show_organize or category or status or runtime:
        render_organize(
            console,
            report,
            limit=limit or 50,
            category=category,
            status=status,
            runtime=runtime,
        )
        return
    render_check(
        console,
        report,
        show_all=show_all,
        limit=limit or 50,
        show_standards=show_standards,
        show_dedupe=show_dedupe,
    )


@app.command()
def snapshot(
    json_output: JsonOption = False,
    save: SaveOption = False,
    yes: YesOption = False,
    limit: LimitOption = None,
    home: HomeOption = None,
    project: ProjectOption = None,
) -> None:
    _, project_path = _home_project(home, project)
    report = _check_report(home, project)
    visibility_snapshot = build_visibility_snapshot(report)
    if save:
        manifest = save_visibility_snapshot(project_path, visibility_snapshot, yes=yes)
        if json_output:
            typer.echo(dump_json(manifest))
        else:
            console.print(f"Saved: {manifest.applied}")
        return
    if json_output:
        typer.echo(dump_json(visibility_snapshot))
        return
    render_snapshot(console, visibility_snapshot, limit=limit or 0)


@app.command()
def compare(
    source_runtime: str,
    target_runtime: str,
    json_output: JsonOption = False,
    home: HomeOption = None,
    project: ProjectOption = None,
) -> None:
    report = _check_report(home, project)
    comparison = build_runtime_comparison(report, source_runtime, target_runtime)
    if json_output:
        typer.echo(dump_json(comparison))
        return
    render_comparison(console, comparison)


def main() -> None:
    app()
