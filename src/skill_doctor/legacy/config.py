"""
[INPUT]: Depends on VisibilitySnapshot and filesystem paths for metadata-only persistence.
[OUTPUT]: Provides config load/write and snapshot manifest creation.
[POS]: Sole write boundary; source skill directories are never mutated here.
[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from skill_doctor.models import RunManifest, VisibilitySnapshot


class SkillDoctorConfig(BaseModel):
    housekeeping: dict[str, dict[str, object]] = Field(default_factory=dict)


def save_visibility_snapshot(
    project: Path, snapshot: VisibilitySnapshot, yes: bool = False
) -> RunManifest:
    if not yes:
        return RunManifest(run_id=_run_id(), kind="snapshot", applied=False)

    _ensure_safe_state_root(project)
    tool_dir = project / ".skill-doctor"
    runs_dir = tool_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    config = load_config(project)

    for record in snapshot.records:
        value = str(record.path)
        housekeeping = record.metadata.get("housekeeping")
        if isinstance(housekeeping, dict):
            config.housekeeping[value] = housekeeping

    config_path = tool_dir / "config.toml"
    _write_config(config_path, config)
    run_id = _run_id()
    manifest_path = runs_dir / f"{run_id}.json"
    manifest = RunManifest(
        run_id=run_id,
        kind="snapshot",
        applied=True,
        written_files=[str(config_path), str(manifest_path)],
        records=[record.model_dump(mode="json") for record in snapshot.records],
    )
    manifest_path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest


def load_config(project: Path) -> SkillDoctorConfig:
    path = project / ".skill-doctor" / "config.toml"
    if not path.exists():
        return SkillDoctorConfig()
    housekeeping: dict[str, dict[str, object]] = {}
    current = None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "[housekeeping]":
            current = "housekeeping"
        elif stripped.startswith("items ="):
            values = _parse_list(stripped.split("=", 1)[1].strip())
            if current == "housekeeping":
                housekeeping = _parse_housekeeping(values)
    return SkillDoctorConfig(
        housekeeping=housekeeping,
    )


def _ensure_safe_state_root(project: Path) -> None:
    resolved = project.resolve()
    for candidate in (resolved, *resolved.parents):
        if (candidate / "SKILL.md").exists():
            raise ValueError(
                "Refusing to write .skill-doctor metadata inside or below a skill folder."
            )


def _write_config(path: Path, config: SkillDoctorConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(
        [
            "[housekeeping]",
            f"items = {_format_list(_format_housekeeping(config.housekeeping))}",
            "",
        ]
    )
    path.write_text(text, encoding="utf-8")


def _format_list(values: list[str]) -> str:
    return "[" + ", ".join(json.dumps(value) for value in values) + "]"


def _parse_list(value: str) -> list[str]:
    parsed = json.loads(value)
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _format_housekeeping(values: dict[str, dict[str, object]]) -> list[str]:
    records: list[str] = []
    for path, payload in sorted(values.items()):
        record = {"path": path, **payload}
        records.append(json.dumps(record, sort_keys=True))
    return records


def _parse_housekeeping(values: list[str]) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    for value in values:
        try:
            record = json.loads(value)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            continue
        path = record.pop("path")
        records[path] = record
    return records


def _run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
