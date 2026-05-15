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
    "health_headline": {
        "en": "🩺 Health: [bold {color}]{score}/100  {grade}[/bold {color}]",
        "zh": "🩺 健康分: [bold {color}]{score}/100  {grade}[/bold {color}]",
    },
    "health_clean": {
        "en": "🩺 [bold green]Library is clean — nothing to auto-fix[/bold green]",
        "zh": "🩺 [bold green]Skill 库很干净 — 没有可自动修的[/bold green]",
    },
    "share_intro": {
        "en": "[bold]Sharing card written:[/bold]",
        "zh": "[bold]健康卡片已生成:[/bold]",
    },
    "share_paths": {
        "en": "  SVG (drag into Twitter/Reddit): {svg}\n"
              "  Markdown snippet (copied to clipboard): {md}",
        "zh": "  SVG（拖到 Twitter/Reddit）: {svg}\n"
              "  Markdown 片段（已复制到剪贴板）: {md}",
    },
    "share_no_clip": {
        "en": "  Markdown snippet: {md}  [dim](clipboard copy failed; "
              "paste from the file)[/dim]",
        "zh": "  Markdown 片段: {md}  [dim]（剪贴板复制失败, 从文件粘贴）[/dim]",
    },
    "install_skill_header": {
        "en": "Installing skill-doctor as a Claude Code skill...",
        "zh": "把 skill-doctor 注册成 Claude Code skill...",
    },
    "install_skill_done": {
        "en": "  ✓ {label}: {dest}",
        "zh": "  ✓ {label}: {dest}",
    },
    "install_skill_skip": {
        "en": "  ↷ {label}: already installed (use --force to overwrite)",
        "zh": "  ↷ {label}: 已安装（加 --force 覆盖）",
    },
    "install_skill_overwrite": {
        "en": "  ↻ {label}: overwritten {dest}",
        "zh": "  ↻ {label}: 已覆盖 {dest}",
    },
    "install_skill_error": {
        "en": "  ✗ {label}: {detail}",
        "zh": "  ✗ {label}: {detail}",
    },
    "install_skill_none": {
        "en": "No supported runtime directories detected on this host.\n"
              "  Try --all to install into every runtime path regardless.",
        "zh": "未检测到任何支持的 runtime 目录。\n"
              "  加 --all 把 skill 装到所有 runtime（即使尚未创建）。",
    },
    "install_skill_next": {
        "en": "[dim]Next: in any Agent chat, say things like "
              "'audit my skills' or 'do I have duplicates?' — "
              "the Agent will invoke skill-doctor for you.[/dim]",
        "zh": "[dim]接下来: 在任何 Agent 对话里说 "
              "「帮我清理 skill」「我是不是装了重复 skill」之类的话, "
              "Agent 会自动调用 skill-doctor.[/dim]",
    },
    "categories": {
        "en": "  Categories:",
        "zh": "  用途分类:",
    },
    "header_dup": {
        "en": "[orange3]🟠 {n} duplicate groups still need cleanup[/orange3] "
              "({i} instances)",
        "zh": "[orange3]🟠 {n} 组重复待清理[/orange3]（{i} 份）",
    },
    "header_dup_aligned": {
        "en": "[green]✓ {n} duplicate groups already aligned[/green] "
              "[dim](non-master copies are already symlinks → master · "
              "no action needed)[/dim]",
        "zh": "[green]✓ {n} 组已对齐[/green] "
              "[dim]（副本已是软链指向主源 · 无需处理）[/dim]",
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
    "footer_clean":  {
        "en": "→ Run [bold]skill-doctor clean[/bold] "
              "[dim](auto-fixes raw dupes / broken / junk; offers AI handoff "
              "prompts for drift / stale / quality)[/dim]",
        "zh": "→ 跑 [bold]skill-doctor clean[/bold] "
              "[dim]（自动修原始副本 / 断链 / 垃圾；漂移 / 陈旧 / 写法质量"
              "会让你选择是否生成 AI handoff prompt）[/dim]",
    },
    "footer_ok": {
        "en": "[green]✓ Nothing to auto-fix.[/green] [dim]Drift / stale / "
              "low-quality items above (if any) need human + AI judgment — "
              "run [bold]skill-doctor clean[/bold] to get an AI handoff "
              "prompt for them.[/dim]",
        "zh": "[green]✓ 没有可自动修的。[/green] [dim]上面如还有漂移 / 陈旧 / "
              "写法低分, 跑 [bold]skill-doctor clean[/bold] 让它帮你"
              "生成 AI handoff prompt。[/dim]",
    },
    "footer_full":   {"en": "[dim]💡 Full per-skill table: skill-doctor --full[/dim]",
                      "zh": "[dim]💡 完整大表: skill-doctor --full[/dim]"},
    "footer_quality": {
        "en": "[dim]💡 Unlock the SKILL.md write-quality dimension: "
              "[bold]npm install -g agent-skill-manager[/bold][/dim]",
        "zh": "[dim]💡 解锁 SKILL.md 写法质量维度: "
              "[bold]npm install -g agent-skill-manager[/bold][/dim]",
    },
    "quality_header": {
        "en": "[bold cyan]📋 SKILL.md write quality[/bold cyan]",
        "zh": "[bold cyan]📋 SKILL.md 写法质量[/bold cyan]",
    },
    "quality_locked_header": {
        "en": "[bold yellow]📋 SKILL.md write quality — locked[/bold yellow] "
              "[yellow](asm not installed; this is the 7th dimension)[/yellow]",
        "zh": "[bold yellow]📋 SKILL.md 写法质量 — 未启用[/bold yellow] "
              "[yellow]（asm 未安装；这是第 7 维度）[/yellow]",
    },
    "quality_locked_install": {
        "en": "  Install once to unlock:  "
              "[bold]npm install -g agent-skill-manager[/bold]",
        "zh": "  装一次解锁:  "
              "[bold]npm install -g agent-skill-manager[/bold]",
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
    "drift_handoff_intro": {
        "en": "🟡 {n} drift groups remain — Skill Doctor doesn't auto-resolve "
              "these (intent is unknowable from files alone).",
        "zh": "🟡 还有 {n} 组 drift — Skill Doctor 不会自动处理它们"
              "（光看文件分不出是有意分叉还是忘了同步）。",
    },
    "drift_handoff_ask": {
        "en": "  Triage drift with AI? [y/N] ",
        "zh": "  让 AI 帮你判断保留 / 合并? [y/N] ",
    },
    "stale_handoff_intro": {
        "en": "🕰 {n} stale skills remain — could be obsolete or just stable.",
        "zh": "🕰 还有 {n} 个 stale skill — 可能没用了, 也可能只是稳定。",
    },
    "stale_handoff_ask": {
        "en": "  Triage stale with AI? [y/N] ",
        "zh": "  让 AI 帮你判断删 / 留? [y/N] ",
    },
    "quality_handoff_intro": {
        "en": "📋 Low-grade SKILL.md files exist — asm gave generic fixes; "
              "AI can translate them into concrete edits.",
        "zh": "📋 有低分 SKILL.md — asm 给了通用建议, AI 可以翻译成具体改写清单。",
    },
    "quality_handoff_no_asm": {
        "en": "📋 SKILL.md write-quality handoff requires `asm` (the SKILL.md "
              "evaluator).\n"
              "  Install it once:  npm install -g agent-skill-manager\n"
              "  Then rerun `skill-doctor clean` and pick this option to "
              "generate an AI fix-it prompt for low-grade skills.",
        "zh": "📋 SKILL.md 写法质量 handoff 需要 `asm` (SKILL.md 评估器)。\n"
              "  装一次:  npm install -g agent-skill-manager\n"
              "  装好后再跑 `skill-doctor clean`, 选这一项就能给低分 skill "
              "生成 AI 修法 prompt。",
    },
    "quality_handoff_ask": {
        "en": "  Triage quality fixes with AI? (runs asm — warm cache is fast) [y/N] ",
        "zh": "  让 AI 帮你给具体修法? (会跑一遍 asm, cache 暖很快) [y/N] ",
    },
    "quality_handoff_empty": {
        "en": "  asm returned no rows. Skipping.",
        "zh": "  asm 没返回数据, 已跳过。",
    },
    "quality_handoff_none_low": {
        "en": "  ✓ No D/F-grade skills. Quality is healthy.",
        "zh": "  ✓ 没有 D/F 等级的 skill. 写法质量没事。",
    },
    "handoff_skipped": {
        "en": "  Skipped.",
        "zh": "  已跳过。",
    },
    "handoff_clipboard": {
        "en": "  ✓ Prompt copied to clipboard.\n"
              "    Paste into Claude.ai / Cursor → follow the AI's table.\n"
              "    (Backup at {path})",
        "zh": "  ✓ Prompt 已复制到剪贴板。\n"
              "    粘到 Claude.ai / Cursor → 看 AI 给的 table。\n"
              "    (备份在 {path})",
    },
    "handoff_written": {
        "en": "  ✓ Wrote prompt to: {path}\n"
              "    Paste its content into Claude.ai / Cursor → "
              "follow the AI's table.",
        "zh": "  ✓ Prompt 已写入: {path}\n"
              "    把内容粘到 Claude.ai / Cursor → 看 AI 给的 table。",
    },
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
        "en": "  Apply? [y = yes / N = no (default) / a = yes to all of this type / q = quit] ",
        "zh": "  执行? [y = 是 / N = 否（默认）/ a = 同类型全部同意 / q = 退出] ",
    },
    "act_dedup_title":  {"en": "Merge {name} ({rt})",     "zh": "合并 {name}（{rt}）"},
    "act_dedup_detail": {"en": "{src} → symlink to {dst}", "zh": "{src} → 软链到 {dst}"},
    "act_junk_title":   {"en": "Remove junk file ({pattern})",
                         "zh": "清理垃圾文件（{pattern}）"},
    "act_broken_title": {"en": "Remove broken symlink ({rt})",
                         "zh": "移除断链（{rt}）"},
    # rationale lines (printed before each prompt)
    "rat_why_master": {
        "en": "Master picked by score across 3 signals "
              "(version · copies pointing here · last modified):",
        "zh": "主源按 3 个信号打分自动选出 "
              "（版本号 · 被几个副本指向 · 最近修改时间）：",
    },
    "rat_master_row":   {"en": "  ← master", "zh": "  ← 主源"},
    "rat_will_do":      {"en": "Will do:",        "zh": "动作："},
    "rat_reversible": {
        "en": "Reversible: skill-doctor undo restores everything above.",
        "zh": "可恢复：skill-doctor undo 一行还原以上所有变更。",
    },
    "rat_codex_warn": {
        "en": "Note: OpenAI closed Codex's file-level SKILL.md symlink support "
              "as not-planned (#15756, with #17344 as duplicate); they also "
              "closed CLI ≤ 0.98's bug where ~/.codex/skills being a symlink "
              "hides discovery entirely (#11314). skill-doctor creates "
              "directory-level symlinks at ~/.codex/skills/<skill>/, which "
              "sidesteps both — current Codex CLI handles these fine.",
        "zh": "提示：OpenAI 已把 Codex 文件级 SKILL.md 软链支持 closed as "
              "not-planned (#15756, #17344 是其 duplicate)；CLI ≤ 0.98 上 "
              "~/.codex/skills 本身是软链时整个发现失败 (#11314, 同样 closed). "
              "skill-doctor 创建的是目录级软链 ~/.codex/skills/<skill>/，"
              "刚好绕开以上两个 bug，当前 Codex CLI 能正常识别。",
    },
    "rat_cursor_warn": {
        "en": "Note: Cursor is known to not reliably follow directory symlinks "
              "for skills (see skills-hub README, which forces copy on Cursor "
              "targets). The link will be created, but Cursor may ignore it. "
              "If skills don't appear in Cursor, run `cp -R` from the master "
              "instead, or use --exclude cursor to skip this target.",
        "zh": "提示：Cursor 已知不可靠 follow skills 目录软链（参考 skills-hub "
              "README 对 Cursor target 强制 copy 的做法）。软链会被创建，"
              "但 Cursor 可能识别不出来。如果发现 skill 没在 Cursor 里出现，"
              "改用 cp -R 从 master 复制过去；或加 --exclude cursor 跳过该 target。",
    },
    "rat_junk_pattern": {
        "en": "Pattern '{pattern}' matched — see methodology in skill-doctor README.",
        "zh": "命中规则 '{pattern}' — 详见 skill-doctor README 方法论.",
    },
    "rat_broken_detect": {
        "en": "POSIX rule: path.is_symlink() and not path.exists() — target gone.",
        "zh": "POSIX 判定: path.is_symlink() 且 not path.exists() — 目标已不存在.",
    },
    "rat_broken_safe": {
        "en": "Safe: symlinks store no data; removing this loses nothing.",
        "zh": "无风险：软链不存数据，删它不丢任何东西。",
    },
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
