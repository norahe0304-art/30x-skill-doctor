"""
[INPUT]: Depends on CheckReport and filesystem paths for JSON cache persistence.
[OUTPUT]: Provides metadata-only index writes under `.skill-doctor/index.json`.
[POS]: Large-installation cache layer; it never writes source skill directories.
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

import json
from pathlib import Path

from skill_doctor.models import CheckReport
from skill_doctor.serialization import compact_model


def write_index(project: Path, report: CheckReport) -> Path:
    path = project / ".skill-doctor" / "index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(compact_model(report), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return path
