"""
[INPUT]: 依赖 ./health.HealthBreakdown, ./models.AnalysisReport,
         ./apply._copy_to_clipboard 的多平台剪贴板支持。
[OUTPUT]: 对外提供 build_svg / build_ascii / build_markdown 三种渲染,
         write_share_card(...) 一站式 CLI 入口（写文件 + 复制路径 + 控制台预览）。
[POS]: 病毒分发层。把扫描结果包装成可截图 / 可分享的成绩单。
       不引入新依赖：SVG 纯字符串拼，ASCII 走 Rich。
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .config import CONFIG_DIR
from .health import HealthBreakdown
from .models import RUNTIME_LABEL, AnalysisReport

# ─── Theme tokens ───────────────────────────────────────────────────────────
# Held in one place so swapping the palette later is one diff, not a hunt.
# Deliberately desaturated — health cards are read; they're not party flyers.
_THEME = {
    "bg_top":      "#0f1419",
    "bg_bot":      "#1a1f2e",
    "fg_dim":      "#9ca3af",
    "fg_strong":   "#f3f4f6",
    "good":        "#10b981",
    "warn":        "#f59e0b",
    "bad":         "#ef4444",
    "mute":        "#6b7280",
    "card_radius": 16,
}


def _color_for_score(score: int) -> str:
    if score >= 85:
        return _THEME["good"]
    if score >= 65:
        return _THEME["warn"]
    return _THEME["bad"]


def _top_runtimes(report: AnalysisReport, k: int = 3) -> list[tuple[str, int]]:
    pairs = [(RUNTIME_LABEL[r], n) for r, n in report.by_runtime.items() if n > 0]
    pairs.sort(key=lambda kv: -kv[1])
    return pairs[:k]


# ─── SVG card ───────────────────────────────────────────────────────────────
def build_svg(report: AnalysisReport, breakdown: HealthBreakdown) -> str:
    """A 600×400 self-contained SVG. No external resources, no JS, embed-safe."""
    score_color = _color_for_score(breakdown.score)
    today = datetime.now().strftime("%Y-%m-%d")
    runtimes = _top_runtimes(report)

    # findings row — only render dimensions that have non-zero count.
    findings: list[tuple[str, int, str]] = []
    if breakdown.pending_dup_groups:
        findings.append(("duplicates", breakdown.pending_dup_groups, _THEME["warn"]))
    if breakdown.drift_groups:
        findings.append(("drift", breakdown.drift_groups, _THEME["warn"]))
    if breakdown.broken_links:
        findings.append(("broken", breakdown.broken_links, _THEME["bad"]))
    if breakdown.junk_files:
        findings.append(("junk", breakdown.junk_files, _THEME["mute"]))
    if breakdown.stale_skills:
        findings.append(("stale", breakdown.stale_skills, _THEME["mute"]))

    findings_svg = ""
    for i, (label, n, color) in enumerate(findings[:4]):
        x = 32 + i * 132
        findings_svg += (
            f'<text x="{x}" y="312" font-size="22" font-weight="600" '
            f'fill="{color}">{n}</text>'
            f'<text x="{x}" y="332" font-size="13" fill="{_THEME["fg_dim"]}">'
            f'{label}</text>'
        )
    if not findings:
        findings_svg = (
            f'<text x="32" y="320" font-size="16" fill="{_THEME["good"]}">'
            '✓ no actionable findings</text>'
        )

    runtimes_svg = ""
    for i, (label, n) in enumerate(runtimes):
        y = 220 + i * 22
        runtimes_svg += (
            f'<text x="364" y="{y}" font-size="13" '
            f'fill="{_THEME["fg_dim"]}">{label}</text>'
            f'<text x="555" y="{y}" font-size="13" text-anchor="end" '
            f'fill="{_THEME["fg_strong"]}">{n}</text>'
        )

    # Build as a list of lines so per-line width stays sane; SVG parsers
    # ignore the newlines inside the element. Coordinates form a 32px left
    # gutter and an 8-row vertical rhythm.
    fg_dim = _THEME["fg_dim"]
    fg_strong = _THEME["fg_strong"]
    mute = _THEME["mute"]
    font_family = (
        "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', "
        "sans-serif"
    )
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" '
        f'viewBox="0 0 600 400" font-family="{font_family}">',
        '  <defs>',
        '    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">',
        f'      <stop offset="0%" stop-color="{_THEME["bg_bot"]}"/>',
        f'      <stop offset="100%" stop-color="{_THEME["bg_top"]}"/>',
        '    </linearGradient>',
        '  </defs>',
        f'  <rect width="600" height="400" rx="{_THEME["card_radius"]}" '
        f'fill="url(#bg)"/>',
        f'  <text x="32" y="56" font-size="14" font-weight="500" '
        f'letter-spacing="2" fill="{fg_dim}">'
        f'🩺 SKILL LIBRARY HEALTH</text>',
        f'  <text x="32" y="80" font-size="13" fill="{mute}">'
        f'{today} · skill-doctor</text>',
        f'  <text x="32" y="180" font-size="96" font-weight="700" '
        f'fill="{fg_strong}">{breakdown.score}</text>',
        f'  <text x="195" y="180" font-size="42" font-weight="600" '
        f'fill="{score_color}">{breakdown.grade}</text>',
        f'  <text x="32" y="208" font-size="14" fill="{fg_dim}">'
        f'out of 100</text>',
        f'  <text x="364" y="180" font-size="48" font-weight="600" '
        f'fill="{fg_strong}">{breakdown.total_skills}</text>',
        f'  <text x="364" y="202" font-size="13" fill="{fg_dim}">'
        f'skills · {breakdown.total_runtimes} runtimes</text>',
        runtimes_svg,
        findings_svg,
        f'  <line x1="32" y1="356" x2="568" y2="356" stroke="{mute}" '
        f'stroke-opacity="0.2"/>',
        f'  <text x="32" y="378" font-size="12" fill="{mute}">'
        f'pipx install skill-doctor  ·  '
        f'github.com/norahe0304-art/30x-skill-doctor</text>',
        '</svg>',
    ]
    return "\n".join(lines) + "\n"


# ─── ASCII card ─────────────────────────────────────────────────────────────
# Inner box width. Box-drawing chars (│ ╭ etc.) are 1-col; emoji is 2-col.
# Pad helper accepts a `visual_len` hint when emoji are present, so we never
# rely on Python's len() (which counts codepoints, not terminal cells).
_INNER = 46


def _row(content: str, visual_len: int | None = None) -> str:
    pad = _INNER - (visual_len if visual_len is not None else len(content))
    pad = max(pad, 0)
    return f"│{content}{' ' * pad}│"


def build_ascii(report: AnalysisReport, breakdown: HealthBreakdown) -> str:
    """Box-drawing card that screenshots cleanly from a terminal."""
    runtimes = _top_runtimes(report)

    findings: list[tuple[str, int]] = []           # (content, visual_len)
    if breakdown.pending_dup_groups:
        s = f"  duplicates  🟠 {breakdown.pending_dup_groups}"
        findings.append((s, len(s) + 1))           # one emoji → +1 cell
    if breakdown.drift_groups:
        s = f"  drift       🟡 {breakdown.drift_groups}"
        findings.append((s, len(s) + 1))
    if breakdown.broken_links:
        s = f"  broken      ✗  {breakdown.broken_links}"
        findings.append((s, len(s)))
    if breakdown.junk_files:
        s = f"  junk        🗑 {breakdown.junk_files}"
        findings.append((s, len(s) + 1))
    if breakdown.stale_skills:
        s = f"  stale       🕰 {breakdown.stale_skills}"
        findings.append((s, len(s) + 1))
    if not findings:
        s = "  ✓ no actionable findings"
        findings = [(s, len(s))]

    bar  = "─" * _INNER
    sep  = f"├{bar}┤"
    top  = f"╭{bar}╮"
    bot  = f"╰{bar}╯"

    header = "  🩺  SKILL LIBRARY HEALTH"
    lines = [
        top,
        _row(header, visual_len=len(header) + 1),  # 🩺 → +1 cell
        sep,
        _row(f"   {breakdown.score:>3} / 100      Grade: {breakdown.grade:<3}"),
        _row(f"   {breakdown.total_skills} skills · {breakdown.total_runtimes} runtimes"),
        sep,
        _row("  Top runtimes:"),
    ]
    for label, n in runtimes:
        lines.append(_row(f"  {label:<20} {n:>3}"))
    lines.append(sep)
    lines.append(_row("  Findings:"))
    for content, vlen in findings:
        lines.append(_row(content, visual_len=vlen))
    lines.append(bot)
    lines.append("  pipx install skill-doctor")
    return "\n".join(lines)


# ─── Markdown (for Reddit / GitHub issue / chat) ────────────────────────────
def build_markdown(report: AnalysisReport, breakdown: HealthBreakdown) -> str:
    runtimes = _top_runtimes(report)
    rt_line = " · ".join(f"{lbl} {n}" for lbl, n in runtimes)
    rows = [
        f"## 🩺 Skill Library Health: **{breakdown.score}/100** ({breakdown.grade})",
        "",
        f"- **{breakdown.total_skills}** skills across **{breakdown.total_runtimes}** runtimes",
        f"- Top: {rt_line}" if runtimes else "",
    ]
    if breakdown.pending_dup_groups:
        rows.append(f"- 🟠 {breakdown.pending_dup_groups} duplicate groups still need cleanup")
    if breakdown.drift_groups:
        rows.append(f"- 🟡 {breakdown.drift_groups} drift groups")
    if breakdown.broken_links:
        rows.append(f"- ✗ {breakdown.broken_links} broken symlinks")
    if breakdown.junk_files:
        rows.append(f"- 🗑 {breakdown.junk_files} junk files")
    if breakdown.stale_skills:
        rows.append(f"- 🕰 {breakdown.stale_skills} stale skills (>90d)")
    if not breakdown.has_findings:
        rows.append("- ✓ Clean: nothing to auto-fix")
    rows += [
        "",
        "Audit yours: `pipx install skill-doctor && skill-doctor share`",
    ]
    return "\n".join(r for r in rows if r is not None)


# ─── CLI entrypoint ─────────────────────────────────────────────────────────
SHARE_DIR = CONFIG_DIR / "share"


def write_share_card(
    report: AnalysisReport,
    breakdown: HealthBreakdown,
    out_path: Path | None = None,
    fmt: str = "svg",
) -> Path:
    """Render and write a share card to disk. Returns the path written."""
    SHARE_DIR.mkdir(parents=True, exist_ok=True)
    if out_path is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_path = SHARE_DIR / f"skill-health-{stamp}.{fmt}"
    out_path = Path(out_path).expanduser()
    if fmt == "svg":
        out_path.write_text(build_svg(report, breakdown), encoding="utf-8")
    elif fmt == "md":
        out_path.write_text(build_markdown(report, breakdown), encoding="utf-8")
    elif fmt == "txt":
        out_path.write_text(build_ascii(report, breakdown), encoding="utf-8")
    else:
        raise ValueError(f"unknown share format: {fmt}")
    return out_path
