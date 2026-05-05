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
from .models import Category, Runtime
from .report import render_default, render_json
from .report_full import render_full
from .scanner import scan_all

app = typer.Typer(
    name="skill-doctor",
    help="跨 runtime skill 结构地图：看清你有什么，整理乱在哪。",
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
            f"未知 runtime '{value}'，可选: {', '.join(r.value for r in Runtime)}"
        ) from e


def _category_arg(value: str | None) -> Category | None:
    if not value:
        return None
    needle = value.lower()
    for cat in Category:
        if cat.value == value or cat.value.lower() == needle or cat.name.lower() == needle:
            return cat
    raise typer.BadParameter(
        f"未知 category '{value}'，可选: {', '.join(c.value for c in Category)}"
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
    full: bool = typer.Option(False, "--full", help="完整大表（每个 skill 一行）"),
    no_truncate: bool = typer.Option(False, "--no-truncate", help="--full 时不截断长路径"),
    json_out: bool = typer.Option(False, "--json", help="JSON 机读输出"),
    runtime: str | None = typer.Option(None, "--runtime", help="只看一个 runtime"),
    category: str | None = typer.Option(None, "--category", help="只看一个用途"),
    version: bool | None = typer.Option(
        None, "--version", "-V", callback=_version_callback, is_eager=True,
        help="显示版本",
    ),
    quality_n: int | None = typer.Option(
        None, "--quality-n", help="只评估前 N 个（不带缓存的快速抽样）"
    ),
    stale_days: int = typer.Option(
        STALE_DAYS_DEFAULT, "--stale-days",
        help="超过 N 天没改的 skill 标为陈旧 (默认 180, mtime 信号)"
    ),
) -> None:
    """默认命令：扫描 + 分析 + 自适应报告。"""
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
        typer.echo("⚠ 未检测到 asm CLI，请先装: npm install -g agent-skill-manager")

    render_default(report, quality_rows=quality_rows)


def _run_quality(instances, quality_n: int | None) -> list[QualityRow] | None:
    paths = [inst.path for inst in instances]
    console = Console()
    if quality_n is not None:
        typer.echo(f"⏳ 跑 asm eval 抽样 (前 {min(quality_n, len(paths))} 个 skill)...")
        return quality_sample(paths, n=quality_n)

    cache_status = _cache_status(paths)
    if cache_status == "miss":
        typer.echo(
            f"⏳ 首次评估 SKILL.md 写法质量 ({len(paths)} 个 skill, 约 40 秒, 之后走缓存)..."
        )

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
        typer.echo("⚠ --yes 会自动执行所有动作（仍走备份，可 undo）")
        typer.echo("   3 秒后开始，Ctrl+C 取消...")
        import time
        try:
            time.sleep(3)
        except KeyboardInterrupt:
            typer.echo("\n已取消")
            raise typer.Exit() from None
    instances, junk, broken = scan_all()
    report = analyze(instances, junk, broken)
    apply_actions(report, interactive=not yes)


@app.command("clean")
def clean_command(
    yes: bool = typer.Option(False, "--yes", "-y", help="非交互模式，全部执行（仍走备份）"),
) -> None:
    """逐条 y/N 点头来整理你机器上的 skill。删之前先备份，可 undo。"""
    _clean_impl(yes)


@app.command("apply", hidden=True)
def apply_command(
    yes: bool = typer.Option(False, "--yes", "-y"),
) -> None:
    """已重命名为 clean。本命令保留为别名以便肌肉记忆过渡。"""
    _clean_impl(yes)


@app.command("undo")
def undo_command(
    pick: bool = typer.Option(False, "--pick", help="列出所有备份让你选一个恢复"),
) -> None:
    """默认恢复最近一次 apply；--pick 让你从历史里选。"""
    if pick:
        backups = list_backups()
        if not backups:
            typer.echo("没有可撤销的 backup。")
            raise typer.Exit()
        typer.echo("可恢复的备份（最新在最下）:")
        for idx, bdir in enumerate(backups, 1):
            typer.echo(f"  [{idx}] {bdir.name}")
        typer.echo(f"输入编号 (1-{len(backups)}) 或回车默认最新:", nl=False)
        choice = (input(" ") or str(len(backups))).strip()
        try:
            picked = backups[int(choice) - 1]
        except (ValueError, IndexError):
            typer.echo("非法编号，取消")
            raise typer.Exit() from None
        undo_last(picked)
    else:
        undo_last()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
