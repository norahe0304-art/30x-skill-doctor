"""
[INPUT]: 依赖 shutil / subprocess / sys 标准库。
[OUTPUT]: 对外提供 copy_to_clipboard(text) -> bool。
[POS]: 跨平台剪贴板助手。被 ./apply (handoff) 与 ./cli (share 子命令) 共享，
       抽离的唯一理由：第二个调用点的出现。
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

import shutil
import subprocess
import sys


def copy_to_clipboard(text: str) -> bool:
    """Best-effort copy to system clipboard. Returns True on success.

    Platform-specific binaries we try, in order:
      macOS:    pbcopy           (always present)
      Linux:    wl-copy / xclip / xsel  (whichever is on PATH)
      Windows:  clip             (built-in since Windows Vista)
    Falls back to False so the caller can show the file path instead.
    """
    candidates: list[list[str]] = []
    if sys.platform == "darwin":
        candidates.append(["pbcopy"])
    elif sys.platform == "win32":
        if shutil.which("clip"):
            candidates.append(["clip"])
    else:
        if shutil.which("wl-copy"):
            candidates.append(["wl-copy"])
        if shutil.which("xclip"):
            candidates.append(["xclip", "-selection", "clipboard"])
        if shutil.which("xsel"):
            candidates.append(["xsel", "--clipboard", "--input"])
    for cmd in candidates:
        try:
            proc = subprocess.run(
                cmd, input=text.encode("utf-8"), check=False, capture_output=True
            )
            if proc.returncode == 0:
                return True
        except (OSError, subprocess.SubprocessError):
            continue
    return False
