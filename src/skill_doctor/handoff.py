"""
[INPUT]: 依赖 ./models 的 AnalysisReport / DriftGroup / StaleSkill / SkillInstance,
         依赖 ./asm_bridge 的 QualityRow,
         依赖 ./config 的 HANDOFF_ROOT, 依赖 difflib (stdlib)。
[OUTPUT]: 对外提供
            write_drift_handoff(report) -> Path
            write_stale_handoff(report) -> Path
            write_quality_handoff(rows) -> Path
         三个分别生成 drift / stale / quality 维度的 AI prompt 文件。
         核心: 各维度用各自最少必要信息 (drift 用 unified diff;
         stale 用 frontmatter + 前 60 行; quality 用 asm 建议 + 前 60 行)。
[POS]: clean 流程在自动 actions 跑完后调用本模块, 把"需要人 review"的
         维度交给 AI 做初筛 + 用户拍板的中转层。skill-doctor 自身从不动
         这些文件 (Non-goal: not a sync engine)。
[PROTOCOL]: 变更时更新此头部, 然后检查 AGENTS.md
"""

from __future__ import annotations

import difflib
from datetime import datetime
from pathlib import Path

from .asm_bridge import QualityRow
from .config import HANDOFF_ROOT, ensure_config_dir
from .models import AnalysisReport, DriftGroup, SkillInstance, StaleSkill

# Diff caps: when a unified diff exceeds this many lines we declare the two
# sides "structurally divergent" and stop quoting the diff. Beyond ~50 lines
# the diff stops being legible faster than reading the two files anyway, and
# the only honest verdict for that case is "needs human review or
# keep_divergent" — which the AI can decide from frontmatter alone.
DIFF_LINE_CAP = 50


def write_drift_handoff(report: AnalysisReport) -> Path:
    """Generate a drift-triage prompt and persist it. Returns the file path."""
    ensure_config_dir()
    HANDOFF_ROOT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = HANDOFF_ROOT / f"drift-{ts}.md"
    out_path.write_text(_render_prompt(report.drifts), encoding="utf-8")
    return out_path


def _render_prompt(drifts: list[DriftGroup]) -> str:
    parts: list[str] = [_disclaimer(), _task(len(drifts)), _drifts_section(drifts)]
    return "\n".join(parts)


def _disclaimer() -> str:
    return (
        "> ⚠️ This file is for an AI, not a human. Don't read it.\n"
        "> Paste the whole thing into Claude / Codex / Cursor. The AI will\n"
        "> return a recommendation table — that's what you read.\n"
    )


def _task(n: int) -> str:
    return (
        "# Drift triage\n"
        f"\n{n} skills share a name across runtimes but their SKILL.md "
        "content has diverged. For each one, decide whether to keep the "
        "divergence or merge to one canonical version.\n"
        "\n## Output (one row per skill)\n"
        "\n```\n"
        "| skill | recommendation | confidence | reason | command |\n"
        "|---|---|---|---|---|\n"
        "```\n"
        "\n- `recommendation`: `merge_to_<runtime>` | `keep_divergent` | "
        "`needs_more_context`\n"
        "- `confidence`: `high` | `medium` | `low`\n"
        "- `reason`: ≤ 12 words\n"
        "- `command`: shell to apply your recommendation, or `#` for noop. "
        "When merging, use `cp -R <src>/. <dst>/` (note the trailing `/.`)\n"
        "\nNever modify files. Output the table only."
    )


def _drifts_section(drifts: list[DriftGroup]) -> str:
    parts = ["\n## Drifted skills\n"]
    for i, group in enumerate(drifts, start=1):
        parts.append(_render_group(i, group))
    return "\n".join(parts)


def _render_group(idx: int, group: DriftGroup) -> str:
    name = group.name
    instances = group.instances
    head = [f"### {idx}. {name}"]
    for inst in instances:
        head.append(_one_line_summary(inst))

    if len(instances) == 2:
        body = _render_pair(instances[0], instances[1])
    else:
        body = _render_multi(instances)
    return "\n".join(head) + "\n\n" + body + "\n"


def _one_line_summary(inst: SkillInstance) -> str:
    ver = inst.version or "no-version"
    desc = inst.description or ""
    if len(desc) > 90:
        desc = desc[:87].rstrip() + "..."
    return (
        f"- **{inst.runtime.value}** ({ver}, {inst.body_lines} lines, "
        f"hash `{inst.body_hash[:8]}`): {desc}"
    )


def _render_pair(a: SkillInstance, b: SkillInstance) -> str:
    a_text = _read_md(a)
    b_text = _read_md(b)
    if a_text is None or b_text is None:
        return "*(SKILL.md missing on one side; recommend `needs_more_context`)*"
    diff_lines = list(
        difflib.unified_diff(
            a_text.splitlines(),
            b_text.splitlines(),
            fromfile=f"{a.runtime.value} ({a.version or 'no-version'})",
            tofile=f"{b.runtime.value} ({b.version or 'no-version'})",
            n=3,
        )
    )
    if not diff_lines:
        return "*(diff is empty — files match exactly; this group should not be drift)*"
    if len(diff_lines) > DIFF_LINE_CAP:
        return (
            f"*Structural divergence — unified diff is {len(diff_lines)} "
            f"lines (cap {DIFF_LINE_CAP}). Recommend `keep_divergent` or "
            "`needs_more_context` based on the descriptions above; merging "
            "blind is unsafe.*"
        )
    body = "\n".join(diff_lines)
    return f"```diff\n{body}\n```"


def _render_multi(instances: list[SkillInstance]) -> str:
    """3+ instances: pairwise diffs are noisy; let AI decide from summaries."""
    return (
        "*3+ divergent instances — pairwise diff omitted. Recommend "
        "`needs_more_context` unless the summaries above make one version "
        "obviously canonical.*"
    )


def _read_md(inst: SkillInstance) -> str | None:
    if inst.skill_md is None or not inst.skill_md.exists():
        return None
    try:
        return inst.skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _short(p: Path) -> str:
    home = str(Path.home())
    s = str(p)
    return s.replace(home, "~", 1) if s.startswith(home) else s


# Stale handoff
# -----------------------------------------------------------------------------
# AI can't see usage logs, only SKILL.md content. The honest task is "given
# this skill's described purpose, does anything in the rest of the list
# (or in mainstream tooling) supersede it?" We embed only the frontmatter +
# first 60 lines per stale skill — beyond that, content rarely changes the
# obsolescence verdict.

STALE_BODY_LINE_CAP = 60


def write_stale_handoff(report: AnalysisReport) -> Path:
    ensure_config_dir()
    HANDOFF_ROOT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = HANDOFF_ROOT / f"stale-{ts}.md"
    out_path.write_text(_render_stale_prompt(report.stale), encoding="utf-8")
    return out_path


def _render_stale_prompt(stales: list[StaleSkill]) -> str:
    parts = [
        _disclaimer(),
        _stale_task(len(stales)),
        "\n## Stale skills\n",
    ]
    for i, s in enumerate(stales, start=1):
        parts.append(_render_stale_item(i, s))
    return "\n".join(parts)


def _stale_task(n: int) -> str:
    return (
        "# Stale skill triage\n"
        f"\n{n} skills haven't been modified in 90+ days. Decide whether each "
        "is abandoned (delete) or just stable (leave alone).\n"
        "\n## Output\n"
        "\n```\n"
        "| skill | verdict | confidence | reason | command |\n"
        "|---|---|---|---|---|\n"
        "```\n"
        "\n- `verdict`: `likely_obsolete` | `still_useful` | `uncertain`\n"
        "- `confidence`: `high` | `medium` | `low`\n"
        "- `reason`: ≤ 12 words. If obsolete, name what supersedes it.\n"
        "- `command`: `rm -rf <path>` only when verdict is `likely_obsolete` "
        "AND confidence is `high`. Otherwise `#`.\n"
        "\nYou cannot see usage logs — only SKILL.md content. Default to "
        "`still_useful` when uncertain. Output the table only."
    )


def _render_stale_item(idx: int, s: StaleSkill) -> str:
    inst = s.instance
    text = _read_md(inst)
    if text is None:
        body = "*(SKILL.md unreadable)*"
    else:
        lines = text.splitlines()
        truncated = lines[:STALE_BODY_LINE_CAP]
        body = "```markdown\n" + "\n".join(truncated) + "\n```"
        if len(lines) > STALE_BODY_LINE_CAP:
            body += f"\n*[truncated · {len(lines) - STALE_BODY_LINE_CAP} more lines]*"
    return (
        f"### {idx}. {inst.dir_name} ({s.days_ago} days idle)\n"
        f"- runtime: {inst.runtime.value}\n"
        f"- path: `{_short(inst.path)}`\n"
        f"- description: {inst.description or '*(none)*'}\n"
        f"\n{body}\n"
    )


# Quality handoff
# -----------------------------------------------------------------------------
# asm already produced generic suggestions ("add Acceptance Criteria"). The
# AI's job here is to translate those into concrete, skill-specific edits
# the user can apply by hand. We don't ask the AI to rewrite the file —
# 18 × full SKILL.md rewrites would explode the response — only a punch list.

QUALITY_BODY_LINE_CAP = 60


def write_quality_handoff(rows: list[QualityRow], top_n: int = 10) -> Path:
    """Generate quality-fix punch list for the lowest-scoring skills.

    `top_n` caps the number of skills included so the prompt stays under
    Claude.ai's comfortable context. Default 10 covers the F-grade tail.
    """
    ensure_config_dir()
    HANDOFF_ROOT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = HANDOFF_ROOT / f"quality-{ts}.md"
    selected = rows[:top_n]
    out_path.write_text(_render_quality_prompt(selected), encoding="utf-8")
    return out_path


def _render_quality_prompt(rows: list[QualityRow]) -> str:
    parts = [
        _disclaimer(),
        _quality_task(len(rows)),
        "\n## Low-quality skills\n",
    ]
    for i, row in enumerate(rows, start=1):
        parts.append(_render_quality_item(i, row))
    return "\n".join(parts)


def _quality_task(n: int) -> str:
    return (
        "# Quality fix triage\n"
        f"\n{n} skills got the lowest write-quality scores from asm (the "
        "SKILL.md evaluator). For each, asm flagged generic issues. "
        "Translate them into concrete edits tailored to *this* skill's "
        "domain.\n"
        "\n## Output\n"
        "\n```\n"
        "| skill | top 3 fixes | command |\n"
        "|---|---|---|\n"
        "```\n"
        "\n- `top 3 fixes`: bulleted list, written specifically for this "
        "skill's purpose (not generic). Example: instead of 'add "
        "Acceptance Criteria', write 'add: Output is a JSON report with "
        "fields {url, score, issues}'.\n"
        "- `command`: always `#` (the user edits SKILL.md by hand using "
        "your fixes as a punch list).\n"
        "\nDo not rewrite the file. Output the table only."
    )


def _render_quality_item(idx: int, row: QualityRow) -> str:
    text = _read_md_path(row.path / "SKILL.md")
    if text is None:
        body = "*(SKILL.md unreadable)*"
    else:
        lines = text.splitlines()
        truncated = lines[:QUALITY_BODY_LINE_CAP]
        body = "```markdown\n" + "\n".join(truncated) + "\n```"
        if len(lines) > QUALITY_BODY_LINE_CAP:
            body += f"\n*[truncated · {len(lines) - QUALITY_BODY_LINE_CAP} more lines]*"
    suggestions = "\n".join(f"  - {s}" for s in row.suggestions[:5])
    return (
        f"### {idx}. {row.name} ({row.score}/100, {row.grade})\n"
        f"- path: `{_short(row.path)}`\n"
        f"- asm flagged:\n{suggestions}\n"
        f"\n{body}\n"
    )


def _read_md_path(p: Path) -> str | None:
    if not p.exists():
        return None
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
