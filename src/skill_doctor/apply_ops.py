"""
[INPUT]: 依赖 ./models 的 Action / FsOp，依赖 os/shutil/pathlib 标准库。
[OUTPUT]: 对外提供 execute(action, backup_dir) -> list[dict]，与 undo_op(op) 反向恢复。
[POS]: 文件系统执行细节。从 ./apply.py 拆出来以保持每文件 ≤200 行。所有"动手"动作都集中在这里。
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .models import Action


def execute(action: Action, backup_dir: Path) -> list[dict]:
    """Run an Action's ordered FsOps. Return ops_done manifest entries for undo."""
    done: list[dict] = []
    for op in action.ops:
        if op.kind == "move_to_backup":
            done.append(_move_to_backup(op.src, backup_dir, action.id))
        elif op.kind == "symlink":
            assert op.dst is not None
            done.append(_make_symlink(op.src, op.dst))
        elif op.kind == "remove_symlink":
            done.append(_remove_symlink(op.src))
        else:
            raise ValueError(f"unknown op: {op.kind}")
    return done


def _move_to_backup(src: Path, backup_dir: Path, action_id: int) -> dict:
    target = backup_dir / f"a{action_id}-{src.name}"
    if src.is_symlink():
        link_target = os.readlink(src)
        src.unlink()
        return {"op": "removed_symlink", "src": str(src), "was_target": link_target}
    shutil.move(str(src), str(target))
    return {"op": "moved", "src": str(src), "backup": str(target)}


def _make_symlink(src: Path, dst: Path) -> dict:
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    os.symlink(src, dst)
    return {"op": "symlinked", "src": str(src), "dst": str(dst)}


def _remove_symlink(src: Path) -> dict:
    link_target = os.readlink(src) if src.is_symlink() else None
    src.unlink()
    return {"op": "removed_symlink", "src": str(src), "was_target": link_target}


def undo_op(op: dict) -> None:
    """Inverse of execute() for one ops_done entry. Idempotent where possible."""
    kind = op["op"]
    if kind == "moved":
        src = Path(op["src"])
        backup = Path(op["backup"])
        if src.exists() or src.is_symlink():
            src.unlink() if src.is_symlink() else shutil.rmtree(src)
        shutil.move(str(backup), str(src))
    elif kind == "symlinked":
        link = Path(op["dst"])
        if link.is_symlink():
            link.unlink()
    elif kind == "removed_symlink":
        link = Path(op["src"])
        target = op.get("was_target")
        if target and not link.exists() and not link.is_symlink():
            os.symlink(target, link)
