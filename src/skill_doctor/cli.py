"""
[INPUT]: 依赖 typer, 依赖 ./scanner.scan_all、./analyze.analyze、
         ./report 的三个 render 函数，以及 ./models 的枚举。
[OUTPUT]: 对外提供 main() 入口，以及 skill-doctor / apply / undo 三个命令。
[POS]: skill_doctor 包的命令层。极薄，只做参数解析与编排，业务在下层。
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

import typer
from rich.console import Console

from . import __version__
from .analyze import analyze
from .apply import apply_actions, list_backups, undo_last
from .asm_bridge import QualityRow, asm_version, has_asm, quality_full, quality_sample
from .config import STALE_DAYS_DEFAULT
from .i18n import t
from .models import Category, Runtime
from .report import render_default, render_json
from .report_full import render_full
from .scanner import scan_all

app = typer.Typer(
    name="skill-doctor",
    help="Cross-runtime skill housekeeping: see what you have, tidy what's messy.",
    no_args_is_help=False,
    add_completion=False,
)


def _runtime_arg(value: str | None) -> Runtime | None:
    if not value:
        return None
    try:
        return Runtime(value.lower())
    except ValueError as e:
        raise typer.BadParameter(
            f"unknown runtime '{value}'. Options: {', '.join(r.value for r in Runtime)}"
        ) from e


def _category_arg(value: str | None) -> Category | None:
    if not value:
        return None
    needle = value.lower()
    for cat in Category:
        if cat.value == value or cat.value.lower() == needle or cat.name.lower() == needle:
            return cat
    raise typer.BadParameter(
        f"unknown category '{value}'. Options: {', '.join(c.value for c in Category)}"
    )


def _version_callback(value: bool) -> None:
    if value:
        asm = asm_version()
        line = f"skill-doctor v{__version__}"
        if asm:
            line += f"  ({asm})"
        typer.echo(line)
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def default(
    ctx: typer.Context,
    full: bool = typer.Option(False, "--full", help="Full per-skill table (one row each)"),
    no_truncate: bool = typer.Option(
        False, "--no-truncate", help="Don't truncate long paths in --full"
    ),
    json_out: bool = typer.Option(False, "--json", help="Machine-readable JSON output"),
    runtime: str | None = typer.Option(None, "--runtime", help="Filter by runtime"),
    category: str | None = typer.Option(None, "--category", help="Filter by category"),
    version: bool | None = typer.Option(
        None, "--version", "-V", callback=_version_callback, is_eager=True,
        help="Show version",
    ),
    quality_n: int | None = typer.Option(
        None, "--quality-n", help="Quick uncached quality sample of first N skills"
    ),
    stale_days: int = typer.Option(
        STALE_DAYS_DEFAULT, "--stale-days",
        help="Stale threshold in days (default 90, mtime-only signal)"
    ),
    show_all: bool = typer.Option(
        False, "--all", "-a", help="List every issue (default shows top 30 per dimension)"
    ),
) -> None:
    """Scan + analyze + adaptive report."""
    if ctx.invoked_subcommand is not None:
        return

    instances, junk, broken = scan_all()
    report = analyze(instances, junk, broken, stale_days=stale_days)

    if json_out:
        render_json(report)
        return

    if full:
        runtime_enum = _runtime_arg(runtime)
        category_enum = _category_arg(category)
        render_full(
            report,
            runtime_filter=runtime_enum,
            category_filter=category_enum,
            no_truncate=no_truncate,
        )
        return

    quality_rows: list[QualityRow] | None = None
    if has_asm():
        quality_rows = _run_quality(instances, quality_n)
    elif quality_n is not None:
        typer.echo(t("no_eval"))

    render_default(report, quality_rows=quality_rows, show_all=show_all)


def _run_quality(instances, quality_n: int | None) -> list[QualityRow] | None:
    paths = [inst.path for inst in instances]
    console = Console()
    if quality_n is not None:
        typer.echo(t("quality_sample", n=min(quality_n, len(paths))))
        return quality_sample(paths, n=quality_n)

    cache_status = _cache_status(paths)
    if cache_status == "miss":
        typer.echo(t("quality_first", n=len(paths)))

    def progress(idx: int, total: int, name: str) -> None:
        if cache_status == "miss" and (idx == 1 or idx == total or idx % 10 == 0):
            pct = int(idx * 100 / total)
            console.print(f"  [{idx:>3}/{total}] {pct:>3}%  {name}", style="dim")

    return quality_full(paths, progress_cb=progress)


def _cache_status(paths: list) -> str:
    """Return 'hit' if quality cache likely covers most paths, else 'miss'."""
    from .config import QUALITY_CACHE_PATH
    if not QUALITY_CACHE_PATH.exists():
        return "miss"
    try:
        import json
        cache = json.loads(QUALITY_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "miss"
    covered = sum(1 for p in paths if str(p) in cache)
    return "hit" if covered > len(paths) * 0.8 else "miss"


def _clean_impl(yes: bool) -> None:
    if yes:
        typer.echo(t("yes_warn"))
        typer.echo(t("yes_countdown"))
        import time
        try:
            time.sleep(3)
        except KeyboardInterrupt:
            typer.echo(t("yes_cancelled"))
            raise typer.Exit() from None
    instances, junk, broken = scan_all()
    report = analyze(instances, junk, broken)
    apply_actions(report, interactive=not yes)


@app.command("clean")
def clean_command(
    yes: bool = typer.Option(
        False, "--yes", "-y",
        help="Non-interactive: run every queued action (still backed up).",
    ),
) -> None:
    """Walk through every fix interactively (y/N/q/a). Backed up + undoable."""
    _clean_impl(yes)


@app.command("apply", hidden=True)
def apply_command(
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """Renamed to `clean`. Kept as a hidden alias for muscle memory."""
    _clean_impl(yes)


@app.command("undo")
def undo_command(
    pick: bool = typer.Option(False, "--pick", help="Pick from any past backup"),
) -> None:
    """Restore the most recent `clean` apply; `--pick` selects from history."""
    if pick:
        backups = list_backups()
        if not backups:
            typer.echo(t("no_backups"))
            raise typer.Exit()
        typer.echo(t("undo_pick_header"))
        for idx, bdir in enumerate(backups, 1):
            typer.echo(f"  [{idx}] {bdir.name}")
        typer.echo(t("undo_pick_prompt", n=len(backups)), nl=False)
        choice = (input(" ") or str(len(backups))).strip()
        try:
            picked = backups[int(choice) - 1]
        except (ValueError, IndexError):
            typer.echo(t("undo_pick_invalid"))
            raise typer.Exit() from None
        undo_last(picked)
    else:
        undo_last()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
