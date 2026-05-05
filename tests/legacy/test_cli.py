from __future__ import annotations

import json

from typer.testing import CliRunner

from skill_doctor.cli import app

runner = CliRunner()


def test_check_json_returns_runtime_first_report(skill_world):
    result = runner.invoke(
        app,
        [
            "check",
            "--json",
            "--home",
            str(skill_world["home"]),
            "--project",
            str(skill_world["project"]),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["runtime_counts"]["codex"] == 2
    assert payload["runtime_counts"]["shared"] == 5
    assert payload["skills"][0]["housekeeping"]


def test_check_human_output_is_runtime_first_health_report(skill_world):
    result = runner.invoke(
        app,
        [
            "check",
            "--limit",
            "5",
            "--home",
            str(skill_world["home"]),
            "--project",
            str(skill_world["project"]),
        ],
    )

    assert result.exit_code == 0
    assert "Verdict" in result.output
    assert "Start here" in result.output
    assert "Needs attention" in result.output
    assert "Looks organized" in result.output
    assert "Optional dedupe" in result.output
    assert "Runtime summary" in result.output
    assert "next step" in result.output
    assert "Skill Health by Runtime" not in result.output
    assert "Need decision" not in result.output
    assert "ignore" not in result.output.lower()
    assert "pin" not in result.output.lower()
    assert "migrate" not in result.output.lower()
    assert "copy decision" not in result.output.lower()
    assert "Migration Plan" not in result.output
    assert "skill-vetter" not in result.output.lower()


def test_snapshot_save_yes_writes_metadata_only(skill_world):
    result = runner.invoke(
        app,
        [
            "snapshot",
            "--save",
            "--yes",
            "--json",
            "--home",
            str(skill_world["home"]),
            "--project",
            str(skill_world["project"]),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["applied"] is True
    assert (skill_world["project"] / ".skill-doctor" / "config.toml").exists()
    assert (skill_world["shared"] / "30x-image.backup-1777235615597").exists()
    config_text = (skill_world["project"] / ".skill-doctor" / "config.toml").read_text(
        encoding="utf-8"
    )
    assert "[housekeeping]" in config_text


def test_plan_commands_do_not_write_metadata(skill_world):
    commands = [
        ["check", "--json"],
        ["snapshot", "--json"],
        ["compare", "codex", "claude", "--json"],
    ]

    for command in commands:
        result = runner.invoke(
            app,
            [
                *command,
                "--home",
                str(skill_world["home"]),
                "--project",
                str(skill_world["project"]),
            ],
        )
        assert result.exit_code == 0

    assert not (skill_world["project"] / ".skill-doctor").exists()


def test_check_json_limit_does_not_truncate_scan(skill_world):
    result = runner.invoke(
        app,
        [
            "check",
            "--json",
            "--limit",
            "1",
            "--home",
            str(skill_world["home"]),
            "--project",
            str(skill_world["project"]),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert len(payload["skills"]) == 1
    assert payload["runtime_counts"]["codex"] == 2
    assert payload["runtime_counts"]["shared"] == 5
    assert payload["skills_total"] == 10
    attention_queue = next(
        queue for queue in payload["review_queues"] if queue["name"] == "needs_attention"
    )
    assert attention_queue["total"] >= 1
    assert len(attention_queue["skills"]) == 1


def test_check_dedupe_expanded_output_has_actionable_members(skill_world):
    result = runner.invoke(
        app,
        [
            "check",
            "--dedupe",
            "--limit",
            "5",
            "--home",
            str(skill_world["home"]),
            "--project",
            str(skill_world["project"]),
        ],
    )

    assert result.exit_code == 0
    assert "Members" in result.output
    assert "Shared / duplicate-a" in result.output
    assert "Shared / duplicate-b" in result.output


def test_check_organize_outputs_visibility_shelves(skill_world):
    result = runner.invoke(
        app,
        [
            "check",
            "--organize",
            "--limit",
            "5",
            "--home",
            str(skill_world["home"]),
            "--project",
            str(skill_world["project"]),
        ],
    )

    assert result.exit_code == 0
    assert "Visibility" in result.output
    assert "Use shelves" in result.output
    assert "Status shelves" in result.output
    assert "Visibility insights" in result.output
    assert "Use --category, --status, or --runtime" in result.output


def test_check_organize_status_filter_outputs_shelf_details(skill_world):
    result = runner.invoke(
        app,
        [
            "check",
            "--organize",
            "--status",
            "exact_copy",
            "--home",
            str(skill_world["home"]),
            "--project",
            str(skill_world["project"]),
        ],
    )

    assert result.exit_code == 0
    assert "Shelf details" in result.output
    assert "Exact copy:" in result.output
    assert "duplicate-a" in result.output
    assert "identical content in multiple locations" in result.output


def test_snapshot_json_uses_compact_skill_refs(skill_world):
    result = runner.invoke(
        app,
        [
            "snapshot",
            "--json",
            "--home",
            str(skill_world["home"]),
            "--project",
            str(skill_world["project"]),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    queue_skill = payload["review_queues"][0]["skills"][0]
    assert payload["records"][0]["kind"] == "record_visibility"
    assert set(queue_skill) == {"id", "name", "path"}
    assert len(result.stdout) < 20000


def test_snapshot_human_output_accepts_limit(skill_world):
    result = runner.invoke(
        app,
        [
            "snapshot",
            "--limit",
            "3",
            "--home",
            str(skill_world["home"]),
            "--project",
            str(skill_world["project"]),
        ],
    )

    assert result.exit_code == 0
    assert "This saves Skill Doctor visibility metadata only" in result.output
    assert "more records hidden" in result.output


def test_snapshot_human_output_defaults_to_summary_only(skill_world):
    result = runner.invoke(
        app,
        [
            "snapshot",
            "--home",
            str(skill_world["home"]),
            "--project",
            str(skill_world["project"]),
        ],
    )

    assert result.exit_code == 0
    assert "Visibility Snapshot Summary" in result.output
    assert "Visibility Records" not in result.output
    assert "Run with --limit" in result.output


def test_snapshot_save_refuses_to_write_inside_skill_folder(skill_world):
    skill_project = skill_world["shared"] / "risky-shell"

    result = runner.invoke(
        app,
        [
            "snapshot",
            "--save",
            "--yes",
            "--json",
            "--home",
            str(skill_world["home"]),
            "--project",
            str(skill_project),
        ],
    )

    assert result.exit_code != 0
    assert not (skill_project / ".skill-doctor").exists()


def test_snapshot_save_refuses_to_write_below_skill_folder(skill_world):
    skill_project = skill_world["shared"] / "risky-shell" / "scripts"

    result = runner.invoke(
        app,
        [
            "snapshot",
            "--save",
            "--yes",
            "--json",
            "--home",
            str(skill_world["home"]),
            "--project",
            str(skill_project),
        ],
    )

    assert result.exit_code != 0
    assert not (skill_project / ".skill-doctor").exists()


def test_compare_codex_claude_json_is_visibility_only(skill_world):
    result = runner.invoke(
        app,
        [
            "compare",
            "codex",
            "claude",
            "--json",
            "--home",
            str(skill_world["home"]),
            "--project",
            str(skill_world["project"]),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["source_runtime"] == "codex"
    assert payload["target_runtime"] == "claude"
    assert payload["items"]
    assert {item["relation"] for item in payload["items"]} <= {
        "same_name",
        "source_only",
        "target_only",
    }
    assert "actions" not in payload


def test_compare_any_runtime_pair_is_visibility_only(skill_world):
    result = runner.invoke(
        app,
        [
            "compare",
            "codex",
            "cursor",
            "--json",
            "--home",
            str(skill_world["home"]),
            "--project",
            str(skill_world["project"]),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["source_runtime"] == "codex"
    assert payload["target_runtime"] == "cursor"
    assert payload["items"]
