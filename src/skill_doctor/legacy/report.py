"""
[INPUT]: Depends on Rich, compact serialization, rule_catalog, and report models.
[OUTPUT]: Provides quiet health reports, standards views, visibility snapshots,
runtime comparisons.
[POS]: Presentation layer kept separate from scan/rule visibility logic.
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

import json
from collections import Counter

from rich.console import Console
from rich.markup import escape
from rich.table import Table

from skill_doctor.models import (
    CheckReport,
    DuplicateGroup,
    Finding,
    RuntimeComparison,
    VisibilitySnapshot,
)
from skill_doctor.rule_catalog import RULES, maturity_lens, standards_lens
from skill_doctor.serialization import compact_model


def dump_json(model, limit: int | None = None) -> str:
    return json.dumps(compact_model(model, limit=limit), indent=2, sort_keys=True)


def render_check(
    console: Console,
    report: CheckReport,
    show_all: bool = False,
    limit: int = 50,
    show_standards: bool = False,
    show_dedupe: bool = False,
) -> None:
    attention = _attention_skills(report)
    no_cleanup = _no_cleanup_skills(report)
    runtime_order = _attention_runtime_order(report)
    runtime_count = len(report.runtime_counts)

    console.print("[bold]Verdict[/bold]")
    console.print(f"{len(report.skills)} skills checked across {runtime_count} runtimes.")
    if attention:
        console.print(
            f"{len(attention)} need attention before this setup can be considered organized."
        )
        console.print(f"Start with {_start_here_text(runtime_order)}.")
    else:
        console.print("No attention items found. This setup looks organized for cleanup.")
    console.print("No skill files will be changed.")
    console.print()

    _render_start_here(console, runtime_order)
    _render_attention(console, attention, limit=limit)
    _render_looks_organized(console, no_cleanup)
    _render_optional_dedupe(console, report, limit=limit, expanded=show_dedupe)
    _render_runtime_summary(console, report)
    _render_standards(console, expanded=show_standards)

    if show_all:
        _render_all_skills(console, report, limit=limit)


def render_organize(
    console: Console,
    report: CheckReport,
    limit: int = 50,
    category: str | None = None,
    status: str | None = None,
    runtime: str | None = None,
) -> None:
    skills = _filtered_housekeeping_skills(report, category, status, runtime)
    attention = _attention_skills(report)
    console.print("[bold]Visibility[/bold]")
    console.print(f"{len(report.skills)} skills checked.")
    console.print(f"{len(attention)} need attention.")
    console.print(f"{_status_count(report, 'active_candidate')} active-looking skills.")
    console.print(
        f"{_status_count(report, 'background') + _status_count(report, 'runtime_managed')} "
        "background/runtime/library skills."
    )
    exact_groups = len(_duplicate_groups(report, "same-content-copy"))
    console.print(f"{exact_groups} exact-copy groups found.")
    console.print("No skill files will be changed.")
    console.print()

    _render_housekeeping_start(console, report)
    _render_housekeeping_shelves(console, report)
    _render_housekeeping_insights(console, report, limit, category, status, runtime)
    _render_housekeeping_filtered(console, skills, limit, category, status, runtime)


def _render_housekeeping_start(console: Console, report: CheckReport) -> None:
    console.print("[bold]Start here[/bold]")
    rows = _housekeeping_start_rows(report)
    if not rows:
        console.print("No high-priority visibility finding right now.")
        console.print()
        return
    for index, row in enumerate(rows[:3], start=1):
        console.print(f"{index}. {row}")
    console.print()


def _render_housekeeping_shelves(console: Console, report: CheckReport) -> None:
    console.print("[bold]Use shelves[/bold]")
    table = Table(show_header=True)
    table.add_column("Category")
    table.add_column("Skills", justify="right")
    for category, count in _category_counts(report).most_common():
        table.add_row(category, str(count))
    console.print(table)
    console.print()

    console.print("[bold]Status shelves[/bold]")
    status_table = Table(show_header=True)
    status_table.add_column("Status")
    status_table.add_column("Skills", justify="right")
    for status, count in _status_counts(report).most_common():
        status_table.add_row(_status_label(status), str(count))
    console.print(status_table)
    console.print()


def _render_housekeeping_filtered(
    console: Console,
    skills: list,
    limit: int,
    category: str | None,
    status: str | None,
    runtime: str | None,
) -> None:
    if not any([category, status, runtime]):
        console.print("Use --category, --status, or --runtime to inspect a shelf.")
        console.print()
        return

    console.print("[bold]Shelf details[/bold]")
    if not skills:
        console.print("No skills match this shelf.")
        console.print()
        return
    table = Table()
    table.add_column("Runtime")
    table.add_column("Skill")
    table.add_column("Category")
    table.add_column("Status")
    table.add_column("Path")
    for skill in sorted(skills, key=lambda item: (item.runtime_id, item.name.lower()))[:limit]:
        housekeeping = skill.housekeeping
        table.add_row(
            _runtime_name(skill.runtime_id),
            skill.name,
            housekeeping.use_category if housekeeping else "unknown",
            _status_label(housekeeping.housekeeping_status if housekeeping else "unknown"),
            _short_path(skill.path),
        )
    console.print(table)
    if len(skills) > limit:
        console.print(f"{len(skills) - limit} more skills hidden. Use --limit.")
    console.print()


def _render_housekeeping_insights(
    console: Console,
    report: CheckReport,
    limit: int,
    category: str | None,
    status: str | None,
    runtime: str | None,
) -> None:
    insight_groups = _housekeeping_duplicate_groups(report, category, status, runtime)
    cross_runtime_groups = _housekeeping_cross_runtime_groups(
        report, category, status, runtime
    )
    legacy = _housekeeping_legacy_candidates(report, category, status, runtime)

    console.print("[bold]Visibility insights[/bold]")
    if not insight_groups and not cross_runtime_groups and not legacy:
        console.print("No duplicate or cross-runtime relationships in this shelf.")
        console.print()
        return

    for group in insight_groups[: min(limit, 5)]:
        console.print(
            f"- Exact copy: {escape(_group_name(group))} "
            f"({len(group.skills)} copies) -> identical content in multiple locations."
        )
        console.print(f"  Members: {escape(_inline_members(group.skills, limit=4))}")
    for name, skills in cross_runtime_groups[: min(limit, 5)]:
        console.print(
            f"- Cross-runtime pair: {escape(name)} "
            f"({len(skills)} installs) -> same-name skill across runtimes."
        )
        console.print(f"  Members: {escape(_inline_members(skills, limit=4))}")
    if legacy:
        console.print(
            f"- Legacy-looking folders: {len(legacy)} -> review whether they should stay visible."
        )
        console.print(f"  Examples: {escape(_inline_members(legacy[:5], limit=5))}")
    console.print()


def _render_start_here(console: Console, runtime_order: list[tuple[str, int]]) -> None:
    console.print("[bold]Start here[/bold]")
    if not runtime_order:
        console.print("No runtime needs immediate review.")
        console.print()
        return
    table = Table(show_header=True)
    table.add_column("Step", justify="right")
    table.add_column("Runtime")
    table.add_column("Attention items", justify="right")
    for index, (runtime_id, count) in enumerate(runtime_order[:3], start=1):
        table.add_row(str(index), _runtime_name(runtime_id), str(count))
    console.print(table)
    console.print()


def _render_attention(console: Console, skills: list, limit: int) -> None:
    console.print("[bold]Needs attention[/bold]")
    if not skills:
        console.print("No skills need attention.")
        console.print()
        return
    console.print("Each item shows why, where, confidence, standards lens, and next step.")
    rows = _attention_rows(skills)

    for index, (skill, finding, count) in enumerate(rows[:limit], start=1):
        console.print(
            f"{index}. [bold]{escape(_runtime_name(skill.runtime_id))} / "
            f"{escape(_attention_skill_label(skill, count))}[/bold] - "
            f"{escape(finding.title)} ({finding.severity}/{finding.confidence})"
        )
        console.print(f"   Evidence: {escape(_short_evidence(finding, limit=140))}")
        console.print(f"   Standards: {escape(standards_lens(finding))}")
        console.print(f"   Next: {escape(_short_text(finding.what_next, limit=140))}")
    if len(rows) > limit:
        console.print(f"{len(rows) - limit} more attention rows hidden. Use --limit.")
    console.print()


def _render_looks_organized(console: Console, skills: list) -> None:
    console.print("[bold]Looks organized[/bold]")
    console.print(
        f"{len(skills)} skills have no cleanup action. "
        "Skill Doctor found no organizing work for them; this is not a security audit result."
    )
    if not skills:
        console.print()
        return
    table = Table(show_header=True)
    table.add_column("Reason")
    table.add_column("Skills", justify="right")
    for reason, count in _no_cleanup_reasons(skills).items():
        table.add_row(reason, str(count))
    console.print(table)
    console.print()


def _render_optional_dedupe(
    console: Console, report: CheckReport, limit: int, expanded: bool
) -> None:
    exact = _duplicate_groups(report, "same-content-copy")
    likely = _top_likely_overlap_groups(report)
    console.print("[bold]Optional dedupe[/bold]")
    console.print(f"{len(exact)} exact-copy groups found.")
    console.print(f"{len(likely[:3])} likely overlap groups worth reviewing.")
    if not expanded:
        console.print("Run with --dedupe to inspect the top groups.")
        console.print()
        return

    groups = [*exact, *likely]
    if not groups:
        console.print("No duplicate groups to inspect.")
        console.print()
        return

    table = Table()
    table.add_column("Kind")
    table.add_column("Members")
    table.add_column("Reason")
    table.add_column("Confidence")
    for group in groups[:limit]:
        table.add_row(
            _duplicate_kind_label(group),
            _duplicate_members(group),
            group.reason,
            str(group.confidence),
        )
    console.print(table)
    if len(groups) > limit:
        console.print(f"{len(groups) - limit} more groups hidden. Use --limit.")
    console.print()


def _render_runtime_summary(console: Console, report: CheckReport) -> None:
    console.print("[bold]Runtime summary[/bold]")
    table = Table()
    table.add_column("Runtime")
    table.add_column("Skills", justify="right")
    table.add_column("Needs attention", justify="right")
    table.add_column("No cleanup action", justify="right")
    for runtime_id, skills in _skills_by_runtime(report).items():
        table.add_row(
            _runtime_name(runtime_id),
            str(len(skills)),
            str(sum(1 for skill in skills if _is_attention(skill))),
            str(sum(1 for skill in skills if _is_no_cleanup(skill))),
        )
    console.print(table)
    console.print()


def _render_standards(console: Console, expanded: bool) -> None:
    console.print("[bold]Standards lens[/bold]")
    console.print(
        "Standards-aligned references: OWASP LLM Top 10, NIST SSDF, "
        "NIST AI RMF, CIS Control 2, runtime docs, and product hygiene."
    )
    console.print("This is a local health check, not a compliance result.")
    if not expanded:
        console.print("Run with --standards to inspect rule details.")
        console.print()
        return

    table = Table()
    table.add_column("Rule")
    table.add_column("Severity")
    table.add_column("Confidence")
    table.add_column("References")
    table.add_column("Maturity")
    for rule in RULES.values():
        finding = rule_to_finding(rule.id)
        table.add_row(
            rule.title,
            rule.severity,
            rule.confidence,
            standards_lens(finding),
            maturity_lens(finding),
        )
    console.print(table)
    console.print()


def _render_all_skills(console: Console, report: CheckReport, limit: int) -> None:
    table = Table(title="All Skills")
    table.add_column("Runtime")
    table.add_column("Skill")
    table.add_column("Bucket")
    table.add_column("Path")
    for skill in report.skills[:limit]:
        bucket = skill.judgment.primary_bucket if skill.judgment else "unknown"
        table.add_row(_runtime_name(skill.runtime_id), skill.name, bucket, str(skill.path))
    console.print(table)
    if len(report.skills) > limit:
        console.print(f"{len(report.skills) - limit} more skills hidden. Use --limit.")


def render_snapshot(console: Console, snapshot: VisibilitySnapshot, limit: int = 20) -> None:
    console.print(
        "This saves Skill Doctor visibility metadata only. It does not clean skill files."
    )
    summary = Table(title="Visibility Snapshot Summary")
    summary.add_column("Runtime")
    summary.add_column("Visibility records", justify="right")
    for runtime, counts in _snapshot_counts_by_runtime(snapshot).items():
        summary.add_row(
            runtime,
            str(counts.get("record_visibility", 0)),
        )
    console.print(summary)
    if limit <= 0:
        console.print("Run with --limit to preview metadata records, or --json for full data.")
        return

    table = Table(title="Visibility Records")
    table.add_column("Runtime")
    table.add_column("Skill")
    table.add_column("Category")
    table.add_column("Status")
    table.add_column("Path")
    visible_records = sorted(snapshot.records, key=_snapshot_display_key)
    for record in visible_records[:limit]:
        table.add_row(
            _runtime_label(record.path),
            record.skill_name,
            _record_category(record),
            _record_status(record),
            str(record.path),
        )
    console.print(table)
    if len(snapshot.records) > limit:
        console.print(f"{len(snapshot.records) - limit} more records hidden. Use --json.")


def rule_to_finding(rule_id: str) -> Finding:
    rule = RULES[rule_id]
    return Finding(
        rule_id=rule.id,
        title=rule.title,
        reason=rule.reason,
        severity=rule.severity,
        confidence=rule.confidence,
        evidence=[],
        standard_refs=list(rule.standards),
        what_next=rule.what_next,
    )


def _skills_by_runtime(report: CheckReport) -> dict[str, list]:
    groups: dict[str, list] = {}
    for skill in report.skills:
        groups.setdefault(skill.runtime_id, []).append(skill)
    return dict(sorted(groups.items()))


def _filtered_housekeeping_skills(
    report: CheckReport,
    category: str | None,
    status: str | None,
    runtime: str | None,
) -> list:
    skills = []
    for skill in report.skills:
        housekeeping = skill.housekeeping
        if not housekeeping:
            continue
        if category and housekeeping.use_category != category:
            continue
        if status and housekeeping.housekeeping_status != status:
            continue
        if runtime and skill.runtime_id != runtime:
            continue
        skills.append(skill)
    return skills


def _housekeeping_duplicate_groups(
    report: CheckReport,
    category: str | None,
    status: str | None,
    runtime: str | None,
) -> list[DuplicateGroup]:
    groups: list[DuplicateGroup] = []
    for group in _duplicate_groups(report, "same-content-copy"):
        skills = _filter_skills(list(group.skills), category, status, runtime)
        if len(skills) < 2:
            continue
        groups.append(
            DuplicateGroup(
                id=group.id,
                kind=group.kind,
                skills=skills,
                reason=group.reason,
                confidence=group.confidence,
            )
        )
    return sorted(groups, key=lambda group: (-len(group.skills), _group_name(group)))


def _housekeeping_cross_runtime_groups(
    report: CheckReport,
    category: str | None,
    status: str | None,
    runtime: str | None,
) -> list[tuple[str, list]]:
    groups: dict[str, list] = {}
    for skill in _filter_skills(report.skills, category, status, runtime):
        if (
            skill.housekeeping
            and skill.housekeeping.housekeeping_status == "cross_runtime_pair"
        ):
            groups.setdefault(skill.name.lower(), []).append(skill)
    return sorted(
        [(name, skills) for name, skills in groups.items() if len(skills) > 1],
        key=lambda item: (-len(item[1]), item[0]),
    )


def _housekeeping_legacy_candidates(
    report: CheckReport,
    category: str | None,
    status: str | None,
    runtime: str | None,
) -> list:
    return [
        skill
        for skill in _filter_skills(report.skills, category, status, runtime)
        if skill.housekeeping
        and skill.housekeeping.housekeeping_status == "legacy_candidate"
    ]


def _filter_skills(
    skills: list,
    category: str | None,
    status: str | None,
    runtime: str | None,
) -> list:
    filtered = []
    for skill in skills:
        housekeeping = skill.housekeeping
        if not housekeeping:
            continue
        if category and housekeeping.use_category != category:
            continue
        if status and housekeeping.housekeeping_status != status:
            continue
        if runtime and skill.runtime_id != runtime:
            continue
        filtered.append(skill)
    return filtered


def _housekeeping_start_rows(report: CheckReport) -> list[str]:
    rows: list[str] = []
    broken = _skills_with_housekeeping_lens(report, "broken_metadata")
    dangerous = [
        skill
        for skill in _attention_skills(report)
        if skill.housekeeping and "broken_metadata" not in skill.housekeeping.quality_lens
    ]
    backups = [
        skill
        for skill in report.skills
        if skill.housekeeping
        and skill.housekeeping.housekeeping_status == "legacy_candidate"
    ]
    duplicates = _status_count(report, "exact_copy")
    if broken:
        rows.append(f"Fix {len(broken)} broken skill metadata files.")
    if dangerous:
        rows.append(f"Review {len(dangerous)} execution/path/behavior findings.")
    if backups:
        rows.append(f"Decide whether {len(backups)} legacy-looking skills should remain visible.")
    if duplicates:
        rows.append(
            f"Notice {duplicates} exact-copy skills; no action required unless visible "
            "clutter bothers you."
        )
    return rows


def _group_name(group: DuplicateGroup) -> str:
    names = Counter(skill.name for skill in group.skills)
    return names.most_common(1)[0][0] if names else group.id


def _inline_members(skills: list, limit: int) -> str:
    members = [
        f"{_runtime_name(skill.runtime_id)} / {skill.name} / {_short_path(skill.path)}"
        for skill in skills[:limit]
    ]
    if len(skills) > limit:
        members.append(f"+{len(skills) - limit} more")
    return "; ".join(members)


def _category_counts(report: CheckReport) -> Counter:
    counts: Counter[str] = Counter()
    for skill in report.skills:
        if skill.housekeeping:
            counts[skill.housekeeping.use_category] += 1
    return counts


def _status_counts(report: CheckReport) -> Counter:
    counts: Counter[str] = Counter()
    for skill in report.skills:
        if skill.housekeeping:
            counts[skill.housekeeping.housekeeping_status] += 1
    return counts


def _status_count(report: CheckReport, status: str) -> int:
    return _status_counts(report).get(status, 0)


def _status_label(status: str) -> str:
    labels = {
        "active_candidate": "active-looking",
        "background": "background",
        "runtime_managed": "runtime managed",
        "exact_copy": "exact copy",
        "cross_runtime_pair": "cross-runtime",
        "needs_attention": "needs attention",
        "legacy_candidate": "legacy-looking",
    }
    return labels.get(status, status.replace("_", " "))


def _skills_with_housekeeping_lens(report: CheckReport, lens: str) -> list:
    return [
        skill
        for skill in report.skills
        if skill.housekeeping and lens in skill.housekeeping.quality_lens
    ]


def _attention_skills(report: CheckReport) -> list:
    return sorted(
        [skill for skill in report.skills if _is_attention(skill)],
        key=_attention_display_key,
    )


def _no_cleanup_skills(report: CheckReport) -> list:
    return [skill for skill in report.skills if _is_no_cleanup(skill)]


def _is_attention(skill) -> bool:
    return bool(skill.judgment and skill.judgment.primary_bucket == "needs_attention")


def _is_no_cleanup(skill) -> bool:
    return bool(skill.judgment and skill.judgment.primary_bucket == "no_cleanup_action")


def _attention_display_key(skill) -> tuple[int, int, str, str]:
    finding = _primary_finding(skill)
    severity = {"high": 0, "attention": 1, "info": 2}
    confidence = {"high": 0, "medium": 1, "low": 2}
    return (
        severity.get(finding.severity, 9),
        confidence.get(finding.confidence, 9),
        skill.runtime_id,
        skill.name.lower(),
    )


def _attention_rows(skills: list) -> list[tuple[object, Finding, int]]:
    groups: dict[tuple[str, str, str], list] = {}
    for skill in skills:
        finding = _primary_finding(skill)
        key = (skill.runtime_id, skill.name, finding.rule_id)
        groups.setdefault(key, []).append(skill)
    rows: list[tuple[object, Finding, int]] = []
    for grouped in groups.values():
        first = sorted(grouped, key=lambda skill: str(skill.path))[0]
        rows.append((first, _primary_finding(first), len(grouped)))
    return sorted(rows, key=lambda row: _attention_display_key(row[0]))


def _attention_skill_label(skill, count: int) -> str:
    if count <= 1:
        return skill.name
    return f"{skill.name} (+{count - 1})"


def _primary_finding(skill) -> Finding:
    if skill.judgment and skill.judgment.findings:
        return sorted(skill.judgment.findings, key=_finding_sort_key)[0]
    return rule_to_finding("unknown-owner")


def _finding_sort_key(finding: Finding) -> tuple[int, int, str]:
    severity = {"high": 0, "attention": 1, "info": 2}
    confidence = {"high": 0, "medium": 1, "low": 2}
    return (
        severity.get(finding.severity, 9),
        confidence.get(finding.confidence, 9),
        finding.rule_id,
    )


def _short_evidence(finding: Finding, limit: int = 90) -> str:
    if not finding.evidence:
        return "See skill file."
    first = finding.evidence[0]
    return _short_text(_compact_evidence(first), limit=limit)


def _short_text(value: str, limit: int = 90) -> str:
    compact = " ".join(value.split())
    return compact if len(compact) <= limit else f"{compact[: limit - 3]}..."


def _compact_evidence(value: str) -> str:
    parts = value.rsplit(":", 2)
    if len(parts) == 3 and parts[1].strip().isdigit() and parts[0].startswith("/"):
        return f"{_short_path(parts[0])}:{parts[1]}: {parts[2].strip()}"
    if value.startswith("/") and ": " in value:
        path, detail = value.split(": ", 1)
        return f"{_short_path(path)}: {detail}"
    return value


def _start_here_text(runtime_order: list[tuple[str, int]]) -> str:
    if not runtime_order:
        return "no runtime"
    names = [_runtime_name(runtime_id) for runtime_id, _ in runtime_order[:2]]
    return ", then ".join(names)


def _attention_runtime_order(report: CheckReport) -> list[tuple[str, int]]:
    counts = Counter(skill.runtime_id for skill in _attention_skills(report))
    return sorted(counts.items(), key=lambda item: (-item[1], _runtime_name(item[0])))


def _no_cleanup_reasons(skills: list) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for skill in skills:
        counts[_no_cleanup_reason(skill)] += 1
    return dict(sorted(counts.items()))


def _no_cleanup_reason(skill) -> str:
    if skill.protected or skill.source_kind in {"system", "plugin_cache", "plugin_marketplace"}:
        return "Runtime-managed"
    if skill.source_kind == "warehouse":
        return "Warehouse/imported"
    if skill.source_kind == "shared":
        return "Shared background"
    if skill.load_status in {"library", "imported", "bundled"}:
        return "Installed/library"
    return "No cleanup action"


def _duplicate_groups(report: CheckReport, kind: str) -> list[DuplicateGroup]:
    return [group for group in report.duplicate_groups if group.kind == kind]


def _top_likely_overlap_groups(report: CheckReport) -> list[DuplicateGroup]:
    groups = _duplicate_groups(report, "near-duplicate")
    return sorted(groups, key=lambda group: (-group.confidence, _group_runtime_key(group)))[:3]


def _group_runtime_key(group: DuplicateGroup) -> str:
    runtimes = sorted({skill.runtime_id for skill in group.skills})
    names = sorted(skill.name.lower() for skill in group.skills)
    return ":".join([",".join(runtimes), ",".join(names)])


def _duplicate_kind_label(group: DuplicateGroup) -> str:
    return "Exact copy" if group.kind == "same-content-copy" else "Likely overlap"


def _duplicate_members(group: DuplicateGroup) -> str:
    members = [
        f"{_runtime_name(skill.runtime_id)} / {skill.name} / {_short_path(skill.path)}"
        for skill in group.skills[:4]
    ]
    if len(group.skills) > 4:
        members.append(f"+{len(group.skills) - 4} more")
    return "\n".join(members)


def _short_path(path) -> str:
    text = str(path)
    parts = text.split("/")
    if len(parts) <= 4:
        return text
    return "/".join(["...", *parts[-3:]])


def _snapshot_display_key(record) -> tuple[int, str, str]:
    priority = {"record_visibility": 0}
    return (
        priority.get(record.kind, 9),
        _runtime_label(record.path),
        record.skill_name.lower(),
        str(record.path),
    )


def _snapshot_counts_by_runtime(snapshot: VisibilitySnapshot) -> dict[str, Counter]:
    counts: dict[str, Counter] = {}
    for record in snapshot.records:
        runtime = _runtime_label(record.path)
        counts.setdefault(runtime, Counter())[record.kind] += 1
    return dict(sorted(counts.items()))


def _runtime_label(path) -> str:
    text = str(path)
    if "/.claude/" in text:
        return "Claude"
    if "/.codex/" in text:
        return "Codex"
    if "/.cursor/" in text:
        return "Cursor"
    if "/.openclaw/" in text:
        return "OpenClaw"
    if "/.agents/" in text:
        return "Shared"
    if "/.hermes/" in text:
        return "Hermes"
    return "Unknown"


def _runtime_name(runtime_id: str) -> str:
    names = {
        "claude": "Claude",
        "codex": "Codex",
        "cursor": "Cursor",
        "hermes": "Hermes",
        "openclaw": "OpenClaw",
        "shared": "Shared",
    }
    return names.get(runtime_id, runtime_id)


def _record_category(record) -> str:
    housekeeping = record.metadata.get("housekeeping")
    if isinstance(housekeeping, dict):
        return str(housekeeping.get("use_category", "unknown"))
    return "unknown"


def _record_status(record) -> str:
    housekeeping = record.metadata.get("housekeeping")
    if isinstance(housekeeping, dict):
        return _status_label(str(housekeeping.get("housekeeping_status", "unknown")))
    return "unknown"


def render_comparison(console: Console, comparison: RuntimeComparison) -> None:
    table = Table(
        title=f"Runtime Comparison: {comparison.source_runtime} -> {comparison.target_runtime}"
    )
    table.add_column("Relation")
    table.add_column("Skill")
    table.add_column("Source paths")
    table.add_column("Target paths")
    table.add_column("Reason")
    for item in comparison.items:
        table.add_row(
            item.relation.replace("_", " "),
            item.skill_name,
            _inline_paths(item.source_paths),
            _inline_paths(item.target_paths),
            item.reason,
        )
    console.print(table)


def _inline_paths(paths: list) -> str:
    if not paths:
        return ""
    values = [str(path) for path in paths[:3]]
    if len(paths) > 3:
        values.append(f"+{len(paths) - 3} more")
    return "; ".join(values)
