# tests/
> L2 | 父级: /Users/nora/Documents/Skill Housekeeping/AGENTS.md

成员清单
conftest.py: 共享 fixture: tmp_runtime_root (4 个 runtime 临时目录)、make_skill 工厂、make_symlink 工厂。
test_skeleton.py: 包能 import + 9 个核心模块在场 + CLI 入口可加载。
test_classify.py: categorize() 在路径前缀与关键词两条路径上的正确性 (7 case)。
test_scanner.py: scan_all 行为：基础发现、macOS 垃圾、断链、symlink 链解析、版本与描述提取、空目录 (6 case)。
test_analyze.py: 重复分组 / 漂移分组 / master 选举 (按 version + 入链数) (5 case)。
test_apply.py: build_actions / apply_actions / undo_last 端到端 (含 dedup→undo round-trip / 垃圾清理 / 断链移除) (5 case)。
test_asm_bridge.py: asm 缺失返回 None / 全错返回 [] / 按 score 升序 (3 case)。
legacy/: V0.1 旧测试，pytest norecursedirs 跳过。

法则: 夹具真实·断言行为·禁止触碰用户 skills·monkeypatch BACKUP_ROOT 隔离

[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
