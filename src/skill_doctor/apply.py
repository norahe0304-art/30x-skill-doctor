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
from .config import BACKUP_ROOT, ensure_config_dir
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

    def add(self, action_type: ActionType, title: str, detail: str, ops: list[FsOp]) -> None:
        self._next_id += 1
        self.actions.append(Action(self._next_id, action_type, title, detail, ops))


def build_actions(report: AnalysisReport) -> list[Action]:
    """Translate analysis findings into reversible action plans."""
    plan = _Plan()
    _plan_dedup(report, plan)
    _plan_junk(report, plan)
    _plan_broken(report, plan)
    return plan.actions


def _short(p: Path) -> str:
    home = str(Path.home())
    s = str(p)
    return s.replace(home, "~", 1) if s.startswith(home) else s


def _plan_dedup(report: AnalysisReport, plan: _Plan) -> None:
    for group in report.duplicates:
        master_real = group.master.real_path
        for inst in group.instances:
            if inst is group.master:
                continue
            if inst.is_symlink and inst.real_path == master_real:
                continue
            plan.add(
                ActionType.DEDUP,
                f"合并 {inst.dir_name} ({inst.runtime.value})",
                f"{_short(inst.path)} → 软链到 {_short(master_real)}",
                [
                    FsOp("move_to_backup", inst.path),
                    FsOp("symlink", master_real, inst.path),
                ],
            )


def _plan_junk(report: AnalysisReport, plan: _Plan) -> None:
    for junk in report.junk_files:
        plan.add(
            ActionType.DELETE_JUNK,
            f"清理垃圾文件 ({junk.pattern})",
            f"{_short(junk.path)}",
            [FsOp("move_to_backup", junk.path)],
        )


def _plan_broken(report: AnalysisReport, plan: _Plan) -> None:
    for broken in report.broken_links:
        plan.add(
            ActionType.REMOVE_BROKEN,
            f"移除断链 ({broken.runtime.value})",
            f"{_short(broken.path)} (was → {_short(broken.intended_target)})",
            [FsOp("remove_symlink", broken.path)],
        )


def apply_actions(report: AnalysisReport, interactive: bool = True) -> ApplySummary:
    actions = build_actions(report)
    summary = ApplySummary()
    if not actions:
        print("✓ 没有需要整理的事项")
        return summary

    ensure_config_dir()
    backup_dir = BACKUP_ROOT / datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"timestamp": datetime.now().isoformat(), "actions": []}
    summary.backup_dir = backup_dir
    summary.manifest_path = backup_dir / "manifest.json"

    auto_yes_for: set[ActionType] = set()

    print(f"\n下面是要做的 {len(actions)} 件事 (备份目录: {_short(backup_dir)})\n")

    for action in actions:
        print(f"[{action.id}/{len(actions)}] {action.title}")
        print(f"  {action.detail}")
        choice = "y" if (not interactive or action.type in auto_yes_for) else _ask_choice()

        if choice == "q":
            print("已停止。")
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
            print("  ✓ 已执行")
        except OSError as e:
            summary.failed += 1
            print(f"  ✗ 失败: {e}")

    summary.manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(
        f"\n完成: ✓{summary.completed} 跳过 {summary.skipped} 失败 {summary.failed}"
        f"\n后悔了? skill-doctor undo"
    )
    return summary


def _ask_choice() -> str:
    while True:
        sys.stdout.write("  执行? [y/N/q/a (a=同类型批量同意)] ")
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
        print("没有可撤销的 backup。")
        return summary
    manifest_path = target / "manifest.json"
    if not manifest_path.exists():
        print(f"backup {target} 缺少 manifest.json")
        return summary

    summary.backup_dir = target
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    print(f"撤销 {target.name} 中 {len(manifest['actions'])} 个动作...")
    for action in reversed(manifest["actions"]):
        for op in reversed(action["ops_done"]):
            try:
                undo_op(op)
                summary.restored += 1
            except OSError as e:
                summary.failed += 1
                print(f"  ✗ 撤销失败 {op}: {e}")
    print(f"撤销完成: ✓{summary.restored} 失败 {summary.failed}")
    return summary
