"""Phase 0 占位测试：确认包能 import、CLI 入口可加载。Phase 1 起换成真实行为测试。"""

from __future__ import annotations


def test_package_imports() -> None:
    import skill_doctor

    assert skill_doctor.__version__ == "0.5.0"


def test_cli_module_imports() -> None:
    from skill_doctor import cli

    assert cli.app is not None


def test_core_modules_present() -> None:
    from skill_doctor import (
        analyze,
        apply,
        asm_bridge,
        classify,
        clipboard,
        config,
        handoff,
        health,
        install_skill,
        models,
        report,
        scanner,
        share,
    )

    assert all(
        m is not None
        for m in (
            analyze, apply, asm_bridge, classify, clipboard, config,
            handoff, health, install_skill, models, report, scanner, share,
        )
    )
