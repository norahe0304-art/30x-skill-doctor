"""
[INPUT]: 依赖 ./models 的 Action/FsOp/AnalysisReport, 依赖 ./config 的 BACKUP_ROOT,
         依赖 ./apply_ops 的 execute / undo_op 实施层。
[OUTPUT]: 对外提供 build_actions(report) -> list[Action]、
         apply_actions(report, interactive=True) -> ApplySummary、
         undo_last() -> UndoSummary。
[POS]: 整理动作的编排层。先 mv 到 backup/<ts>/，再创建 symlink 或删除（由 apply_ops 真正执行）。
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .apply_ops import execute, undo_op
from .clipboard import copy_to_clipboard
from .config import BACKUP_ROOT, ensure_config_dir
from .i18n import t
from .models import Action, ActionType, AnalysisReport, FsOp


@dataclass
class ApplySummary:
    completed: int = 0
    skipped: int = 0
    failed: int = 0
    backup_dir: Path | None = None
    manifest_path: Path | None = None


@dataclass
class UndoSummary:
    restored: int = 0
    failed: int = 0
    backup_dir: Path | None = None


@dataclass
class _Plan:
    actions: list[Action] = field(default_factory=list)
    _next_id: int = 0

    def add(
        self,
        action_type: ActionType,
        title: str,
        detail: str,
        ops: list[FsOp],
        rationale: list[str] | None = None,
    ) -> None:
        self._next_id += 1
        self.actions.append(
            Action(
                id=self._next_id,
                type=action_type,
                title=title,
                detail=detail,
                ops=ops,
                rationale=rationale or [],
            )
        )


def build_actions(
    report: AnalysisReport, force_master_runtime: str | None = None
) -> list[Action]:
    """Translate analysis findings into reversible action plans.

    `force_master_runtime`: when set, override smart election and prefer that
    runtime as master in every duplicate group (skillshare-style "designate
    the source"). Falls back to elected master if the requested runtime is
    not present in the group.
    """
    plan = _Plan()
    _plan_dedup(report, plan, force_master_runtime)
    _plan_junk(report, plan)
    _plan_broken(report, plan)
    return plan.actions


def _short(p: Path) -> str:
    home = str(Path.home())
    s = str(p)
    return s.replace(home, "~", 1) if s.startswith(home) else s


def _plan_dedup(
    report: AnalysisReport, plan: _Plan, force_master_runtime: str | None = None
) -> None:
    all_instances = report.instances
    for group in report.duplicates:
        master = group.master
        if force_master_runtime:
            override = next(
                (i for i in group.instances if i.runtime.value == force_master_runtime),
                None,
            )
            if override is not None:
                master = override
        master_real = master.real_path
        rationale_for_group = _build_dedup_rationale(group, all_instances, master)
        for inst in group.instances:
            if inst is master:
                continue
            if inst.is_symlink and inst.real_path == master_real:
                continue
            plan.add(
                ActionType.DEDUP,
                t("act_dedup_title", name=inst.dir_name, rt=inst.runtime.value),
                t("act_dedup_detail", src=_short(inst.path), dst=_short(master_real)),
                [
                    FsOp("move_to_backup", inst.path),
                    FsOp("symlink", master_real, inst.path),
                ],
                rationale=rationale_for_group,
            )


def _build_dedup_rationale(group, all_instances: list, master=None) -> list[str]:
    """Build per-action rationale lines explaining the master election."""
    from datetime import datetime
    chosen_master = master if master is not None else group.master
    lines = [t("rat_why_master")]
    for inst in group.instances:
        ver = inst.version or "-"
        try:
            mt = datetime.fromtimestamp(inst.mtime).strftime("%Y-%m-%d %H:%M")
        except (OSError, ValueError):
            mt = "?"
        inbound = sum(
            1 for o in all_instances
            if o is not inst and o.is_symlink and o.real_path == inst.real_path
        )
        marker = t("rat_master_row") if inst is chosen_master else ""
        lines.append(
            f"  {inst.runtime.value:14}  v={ver:6}  "
            f"inbound={inbound}  mtime={mt}{marker}"
        )
    lines.append("")
    lines.append(t("rat_will_do"))
    return lines


def _plan_junk(report: AnalysisReport, plan: _Plan) -> None:
    for junk in report.junk_files:
        plan.add(
            ActionType.DELETE_JUNK,
            t("act_junk_title", pattern=junk.pattern),
            f"{_short(junk.path)}",
            [FsOp("move_to_backup", junk.path)],
            rationale=[
                t("rat_junk_pattern", pattern=junk.pattern),
                "",
                t("rat_will_do"),
            ],
        )


def _plan_broken(report: AnalysisReport, plan: _Plan) -> None:
    for broken in report.broken_links:
        plan.add(
            ActionType.REMOVE_BROKEN,
            t("act_broken_title", rt=broken.runtime.value),
            f"{_short(broken.path)} (was → {_short(broken.intended_target)})",
            [FsOp("remove_symlink", broken.path)],
            rationale=[
                t("rat_broken_detect"),
                t("rat_broken_safe"),
                "",
                t("rat_will_do"),
            ],
        )


def apply_actions(
    report: AnalysisReport,
    interactive: bool = True,
    force_master_runtime: str | None = None,
) -> ApplySummary:
    actions = build_actions(report, force_master_runtime=force_master_runtime)
    summary = ApplySummary()
    if not actions:
        print(t("no_actions"))
        _maybe_offer_handoffs(report, interactive)
        return summary

    ensure_config_dir()
    backup_dir = BACKUP_ROOT / datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"timestamp": datetime.now().isoformat(), "actions": []}
    summary.backup_dir = backup_dir
    summary.manifest_path = backup_dir / "manifest.json"

    auto_yes_for: set[ActionType] = set()

    print()
    print(t("actions_queued", n=len(actions), dir=_short(backup_dir)))
    print()

    for action in actions:
        print(f"[{action.id}/{len(actions)}] {action.title}")
        for line in action.rationale:
            print(f"  {line}" if line and not line.startswith(" ") else line)
        has_symlink = False
        has_cursor_target = False
        for op in action.ops:
            if op.kind == "move_to_backup":
                print(f"    backup  {_short(op.src)}  →  {_short(backup_dir)}/")
            elif op.kind == "symlink" and op.dst is not None:
                print(f"    symlink {_short(op.dst)}  →  {_short(op.src)}")
                has_symlink = True
                if ".cursor" in op.dst.parts:
                    has_cursor_target = True
            elif op.kind == "remove_symlink":
                print(f"    unlink  {_short(op.src)}")
        if has_symlink:
            print(f"  {t('rat_codex_warn')}")
        if has_cursor_target:
            print(f"  {t('rat_cursor_warn')}")
        print(f"  {t('rat_reversible')}")
        choice = "y" if (not interactive or action.type in auto_yes_for) else _ask_choice()

        if choice == "q":
            print(t("stopped"))
            break
        if choice == "n":
            summary.skipped += 1
            continue
        if choice == "a":
            auto_yes_for.add(action.type)

        try:
            ops_done = execute(action, backup_dir)
            manifest["actions"].append(
                {
                    "id": action.id,
                    "type": action.type.value,
                    "title": action.title,
                    "ops_done": ops_done,
                }
            )
            summary.completed += 1
            print(t("act_done"))
        except OSError as e:
            summary.failed += 1
            print(t("act_failed", err=str(e)))

    summary.manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        t(
            "apply_sum",
            done=summary.completed,
            skipped=summary.skipped,
            failed=summary.failed,
        )
    )
    _maybe_offer_handoffs(report, interactive)
    return summary


def _maybe_offer_handoffs(report: AnalysisReport, interactive: bool) -> None:
    """Offer AI handoff prompts for drift / stale / quality, one at a time.

    Handoffs require an explicit user yes — `--yes` (non-interactive) skips
    them entirely, since handoff is fundamentally a user-driven choice
    (which AI to use, when to act on its recommendations) that can't be
    safely automated.
    """
    if not interactive:
        return
    _ask_drift_handoff(report)
    _ask_stale_handoff(report)
    _ask_quality_handoff(report)


def _ask_drift_handoff(report: AnalysisReport) -> None:
    if not report.drifts:
        return
    print()
    print(t("drift_handoff_intro", n=len(report.drifts)))
    if not _yes_no(t("drift_handoff_ask")):
        print(t("handoff_skipped"))
        return
    from .handoff import write_drift_handoff
    out_path = write_drift_handoff(report)
    _emit_handoff_result(out_path)


def _ask_stale_handoff(report: AnalysisReport) -> None:
    if not report.stale:
        return
    print()
    print(t("stale_handoff_intro", n=len(report.stale)))
    if not _yes_no(t("stale_handoff_ask")):
        print(t("handoff_skipped"))
        return
    from .handoff import write_stale_handoff
    out_path = write_stale_handoff(report)
    _emit_handoff_result(out_path)


def _ask_quality_handoff(report: AnalysisReport) -> None:
    """Quality is lazy: ask first, then run asm (uses mtime cache so warm cache is fast).

    When asm is not installed, surface install instructions instead of silently
    skipping — quality is the third pillar of the handoff feature and a missing
    evaluator should be visible, not invisible.
    """
    from .asm_bridge import has_asm, quality_full
    print()
    if not has_asm():
        print(t("quality_handoff_no_asm"))
        return
    print(t("quality_handoff_intro"))
    if not _yes_no(t("quality_handoff_ask")):
        print(t("handoff_skipped"))
        return
    paths = [inst.path for inst in report.instances]
    rows = quality_full(paths)
    if not rows:
        print(t("quality_handoff_empty"))
        return
    low_grade = [r for r in rows if r.grade in {"D", "F"}]
    if not low_grade:
        print(t("quality_handoff_none_low"))
        return
    from .handoff import write_quality_handoff
    out_path = write_quality_handoff(low_grade)
    _emit_handoff_result(out_path)


def _yes_no(prompt_text: str) -> bool:
    sys.stdout.write(prompt_text)
    sys.stdout.flush()
    try:
        raw = (sys.stdin.readline() or "").strip().lower()
    except KeyboardInterrupt:
        return False
    return raw in {"y", "yes"}


def _emit_handoff_result(out_path: Path) -> None:
    content = out_path.read_text(encoding="utf-8")
    if copy_to_clipboard(content):
        print(t("handoff_clipboard", path=_short(out_path)))
    else:
        print(t("handoff_written", path=_short(out_path)))


def _ask_choice() -> str:
    while True:
        sys.stdout.write(t("apply_prompt"))
        sys.stdout.flush()
        try:
            raw = (sys.stdin.readline() or "").strip().lower()
        except KeyboardInterrupt:
            return "q"
        if raw in {"y", "n", "q", "a", ""}:
            return raw or "n"


def list_backups() -> list[Path]:
    """All backup directories sorted oldest → newest."""
    if not BACKUP_ROOT.exists():
        return []
    return sorted([p for p in BACKUP_ROOT.iterdir() if p.is_dir()])


def undo_last(picked: Path | None = None) -> UndoSummary:
    """Undo the most recent backup, or the one at `picked` if given."""
    summary = UndoSummary()
    if picked is None:
        backups = list_backups()
        target = backups[-1] if backups else None
    else:
        target = picked
    if target is None:
        print(t("no_backups"))
        return summary
    manifest_path = target / "manifest.json"
    if not manifest_path.exists():
        print(t("no_manifest", dir=str(target)))
        return summary

    summary.backup_dir = target
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    print(t("undo_starting", name=target.name, n=len(manifest["actions"])))
    for action in reversed(manifest["actions"]):
        for op in reversed(action["ops_done"]):
            try:
                undo_op(op)
                summary.restored += 1
            except OSError as e:
                summary.failed += 1
                print(t("undo_op_failed", op=op, err=str(e)))
    print(t("undo_summary", restored=summary.restored, failed=summary.failed))
    return summary
