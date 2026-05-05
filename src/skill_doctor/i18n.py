"""
[INPUT]: 依赖 os / locale 标准库.
[OUTPUT]: 对外提供 detect_lang() -> 'en'|'zh' 与 t(key, **kwargs) 翻译入口,
         以及 CATEGORY_LABEL 用于 Category 枚举的本地化展示.
[POS]: 输出层 i18n 单点入口. 算法/数据层一律用英文 keyword, 翻译只在渲染时发生.
[PROTOCOL]: 变更时更新此头部, 然后检查 AGENTS.md
"""

from __future__ import annotations

import locale
import os

from .models import Category

_CACHED_LANG: str | None = None


def detect_lang() -> str:
    """Return 'zh' for Chinese locale, else 'en'.

    Resolution order:
      1. ``SKILL_DOCTOR_LANG`` env var (``zh`` | ``en``) — explicit override.
      2. POSIX locale via ``locale.getlocale()`` / ``$LANG`` / ``$LC_ALL``.
    """
    global _CACHED_LANG
    if _CACHED_LANG is not None:
        return _CACHED_LANG
    forced = os.environ.get("SKILL_DOCTOR_LANG", "").strip().lower()
    if forced in {"zh", "en"}:
        _CACHED_LANG = forced
        return _CACHED_LANG
    sys_lang = ""
    try:
        sys_lang = (locale.getlocale()[0] or "")
    except Exception:
        sys_lang = ""
    if not sys_lang:
        sys_lang = os.environ.get("LANG", "") or os.environ.get("LC_ALL", "")
    _CACHED_LANG = "zh" if sys_lang.lower().startswith("zh") else "en"
    return _CACHED_LANG


CATEGORY_LABEL: dict[Category, dict[str, str]] = {
    Category.SEO:           {"en": "SEO",          "zh": "SEO"},
    Category.ADS:           {"en": "Ads",          "zh": "广告"},
    Category.MARKETING:     {"en": "Marketing",    "zh": "营销"},
    Category.DEV:           {"en": "Dev",          "zh": "开发"},
    Category.DEPLOY:        {"en": "Deploy",       "zh": "部署"},
    Category.DATA:          {"en": "Data",         "zh": "数据"},
    Category.DESIGN:        {"en": "Design",       "zh": "设计"},
    Category.AI_VIDEO:      {"en": "AI/Video",     "zh": "AI/视频"},
    Category.OTHER:         {"en": "Other",        "zh": "其他"},
    Category.UNCATEGORIZED: {"en": "Uncategorized", "zh": "未分类"},
}


def category_label(cat: Category) -> str:
    return CATEGORY_LABEL.get(cat, {}).get(detect_lang(), cat.value)


_TR: dict[str, dict[str, str]] = {
    "skills_across_runtimes": {
        "en": "📂 [bold]{n}[/bold] skills across [bold]{m}[/bold] runtimes:",
        "zh": "📂 [bold]{n}[/bold] 个 skill, 跨 [bold]{m}[/bold] 个 runtime:",
    },
    "categories": {
        "en": "  Categories:",
        "zh": "  用途分类:",
    },
    "header_dup": {
        "en": "[orange3]🟠 {n} duplicate groups[/orange3] ({i} instances)",
        "zh": "[orange3]🟠 {n} 组重复[/orange3]（{i} 份）",
    },
    "header_drift": {
        "en": "[yellow]🟡 {n} drift groups[/yellow] (same name, different content)",
        "zh": "[yellow]🟡 {n} 组漂移[/yellow]（同名不同内容）",
    },
    "header_broken": {
        "en": "[red]✗  {n} broken symlinks[/red]",
        "zh": "[red]✗  {n} 个断链[/red]",
    },
    "header_junk": {
        "en": "[grey50]🗑 {n} junk files[/grey50]",
        "zh": "[grey50]🗑 {n} 个垃圾文件[/grey50]",
    },
    "header_stale": {
        "en": "[grey62]🕰 {n} stale skills[/grey62] "
              "(oldest {oldest} days · could be unused or just stable)",
        "zh": "[grey62]🕰 {n} 个 stale skill[/grey62]"
              "（最久 {oldest} 天 · 可能没用, 也可能只是稳定）",
    },
    "tail_more": {
        "en": "  [dim]...{rest} more · run [bold]skill-doctor --all[/bold] "
              "for the full list[/dim]",
        "zh": "  [dim]...其余 {rest} 个 · 跑 [bold]skill-doctor --all[/bold] 看全部[/dim]",
    },
    "dup_copies": {"en": "({n} copies)",         "zh": "（{n} 份）"},
    "dup_master": {"en": "master:",              "zh": "主源:"},
    "dup_copy":   {"en": "copy:",                "zh": "副本:"},
    "drift_div":  {"en": "({n} copies, divergent)", "zh": "（{n} 份, 内容分叉）"},
    "no_version": {"en": "no version",           "zh": "无版本"},
    "broken_was": {"en": "→ was:",               "zh": "→ 原指向:"},
    "stale_idle": {"en": "{n} days idle ·",      "zh": "{n} 天没改 ·"},
    "footer_clean":  {"en": "→ Tidy up: [bold]skill-doctor clean[/bold]",
                      "zh": "→ 整理: [bold]skill-doctor clean[/bold]"},
    "footer_ok":     {"en": "[green]✓ Nothing to clean up. Library looks healthy.[/green]",
                      "zh": "[green]✓ 没有需要整理的, 库很干净。[/green]"},
    "footer_full":   {"en": "[dim]💡 Full per-skill table: skill-doctor --full[/dim]",
                      "zh": "[dim]💡 完整大表: skill-doctor --full[/dim]"},
    "footer_quality": {
        "en": "[dim]💡 Install the SKILL.md quality evaluator to unlock the "
              "write-quality dimension.[/dim]",
        "zh": "[dim]💡 装上 SKILL.md 质量评估器, 解锁写法质量维度.[/dim]",
    },
    "quality_header": {
        "en": "[bold cyan]📋 SKILL.md write quality[/bold cyan]",
        "zh": "[bold cyan]📋 SKILL.md 写法质量[/bold cyan]",
    },
    "quality_scored": {
        "en": "  {n} skills scored   [dim]{summary}[/dim]",
        "zh": "  {n} 个 skill 已评分   [dim]{summary}[/dim]",
    },
    "quality_lowest": {
        "en": "[dim]  Lowest 5 + suggestions:[/dim]",
        "zh": "[dim]  最低 5 个 + 修复建议（评估器输出英文）:[/dim]",
    },
    "no_actions":   {"en": "✓ Nothing to clean up.",     "zh": "✓ 没有需要整理的。"},
    "actions_queued": {
        "en": "{n} actions queued. Backup dir: {dir}",
        "zh": "{n} 个动作待执行. 备份目录: {dir}",
    },
    "stopped":      {"en": "Stopped.",                   "zh": "已停止。"},
    "act_done":     {"en": "  ✓ done",                    "zh": "  ✓ 完成"},
    "act_failed":   {"en": "  ✗ failed: {err}",          "zh": "  ✗ 失败: {err}"},
    "apply_sum": {
        "en": "\nSummary: ✓{done} done · {skipped} skipped · {failed} failed"
              "\nUndo: skill-doctor undo",
        "zh": "\n汇总: ✓{done} 完成 · {skipped} 跳过 · {failed} 失败"
              "\n撤销: skill-doctor undo",
    },
    "apply_prompt": {
        "en": "  Apply? [y/N/q/a (a = yes-to-all-of-this-type)] ",
        "zh": "  执行? [y/N/q/a (a = 同类型批量同意)] ",
    },
    "act_dedup_title":  {"en": "Merge {name} ({rt})",     "zh": "合并 {name}（{rt}）"},
    "act_dedup_detail": {"en": "{src} → symlink to {dst}", "zh": "{src} → 软链到 {dst}"},
    "act_junk_title":   {"en": "Remove junk file ({pattern})",
                         "zh": "清理垃圾文件（{pattern}）"},
    "act_broken_title": {"en": "Remove broken symlink ({rt})",
                         "zh": "移除断链（{rt}）"},
    "no_backups":       {"en": "No backups to undo.", "zh": "没有可撤销的备份。"},
    "no_manifest":      {"en": "backup {dir} is missing manifest.json",
                         "zh": "备份 {dir} 缺少 manifest.json"},
    "undo_starting":    {"en": "Reverting {name} ({n} actions)...",
                         "zh": "正在撤销 {name}（{n} 个动作）..."},
    "undo_op_failed":   {"en": "  ✗ undo failed {op}: {err}",
                         "zh": "  ✗ 撤销失败 {op}: {err}"},
    "undo_summary":     {"en": "Undo done: ✓{restored} restored · {failed} failed",
                         "zh": "撤销完成: ✓{restored} 恢复 · {failed} 失败"},
    "yes_warn": {
        "en": "⚠ --yes will run every action automatically (still backed up, undoable).",
        "zh": "⚠ --yes 会自动执行所有动作（仍走备份, 可 undo）",
    },
    "yes_countdown": {"en": "   Starting in 3 s. Ctrl+C to cancel...",
                       "zh": "   3 秒后开始, Ctrl+C 取消..."},
    "yes_cancelled": {"en": "\nCancelled.",  "zh": "\n已取消"},
    "no_eval": {
        "en": "⚠ No SKILL.md quality evaluator on PATH; quality dimension skipped.",
        "zh": "⚠ 未检测到 SKILL.md 质量评估器, 跳过写法质量维度.",
    },
    "quality_sample": {
        "en": "⏳ Quality sample on first {n} skills...",
        "zh": "⏳ 抽样评估前 {n} 个 SKILL.md 写法质量...",
    },
    "quality_first": {
        "en": "⏳ First-time quality scan over {n} skills "
              "(~40 s; subsequent runs use mtime cache)...",
        "zh": "⏳ 首次评估 {n} 个 SKILL.md 写法质量（约 40 秒, 之后走 mtime 缓存）...",
    },
    "undo_pick_header": {
        "en": "Available backups (most recent last):",
        "zh": "可恢复的备份（最新在最下）:",
    },
    "undo_pick_prompt": {
        "en": "Pick a number (1-{n}) or press Enter for the latest:",
        "zh": "输入编号（1-{n}）或回车默认最新:",
    },
    "undo_pick_invalid": {"en": "Invalid number, cancelled.", "zh": "非法编号, 取消。"},
}


def t(key: str, **kwargs) -> str:
    """Translate `key` to the user's locale; fall back to English then the key itself."""
    table = _TR.get(key)
    if not table:
        return key
    template = table.get(detect_lang()) or table.get("en") or key
    return template.format(**kwargs) if kwargs else template
