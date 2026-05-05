# Skill Doctor - 跨 runtime skill 结构分析器

Python 3.12+ + Typer + Rich + Pydantic + PyYAML + rapidfuzz + questionary。

<directory>
src/ - 包源码 (1 子目录: skill_doctor)
tests/ - fixture 驱动的行为测试 (1 子目录: legacy)
research/ - 产品与市场调研笔记 + 终版计划
</directory>

<config>
pyproject.toml - 包元数据 / CLI 入口 / 依赖 / pytest 与 ruff 配置
README.md - 用户视角的产品契约与 quickstart
.gitignore - 排除虚拟环境、缓存、构建产物、`.skill-doctor` 运行时元数据
uv.lock - 已解析的依赖图，保证 uv 可重现运行
</config>

法则: 全量扫描·5 维度自适应·只读分析·先备份再动手

变更日志:
- 2026-05-04: 播种 L1 项目宪法，建立 Skill Doctor V1 架构边界。
- 2026-05-04: 升级 Reduced V2 体检报告，规则目录集中化，默认只展开证据驱动的 attention 项。
- 2026-05-04: 增加 visibility organizer，提供用途分类、状态 shelf、snapshot 和 runtime compare。
- 2026-05-04: V0.2 重构 — 砍到两命令 (skill-doctor / apply / undo), 5 维度 (用途分类 / 重复 / 漂移 / 断链 / 垃圾), 自适应输出。旧 14 个文件冻结到 src/skill_doctor/legacy/。集成 asm 作为质量增强。
- 2026-05-04: V0.2.1 加陈旧维度 (mtime-based) + asm eval 走 mtime 缓存。
- 2026-05-04: V0.2.2 把 eval 升为默认开的第 7 维（asm 装了就跑），保留 --no-quality 关闭。
- 2026-05-04: V0.2.3 霹雳无敌全修：--version / 进度日志加密 / apply --yes 倒计时 / undo --pick 历史选 / 垃圾深扫 / 陈旧用整目录 mtime / config.toml 加 [[extra_runtimes]] / 大表 --no-truncate / categorize 减少"其他" 占比。
- 2026-05-04: V0.2.4 apply 重命名为 clean (apply 保留为隐藏 alias) + 陈旧默认阈值 365 → 180 天 (agent skills 概念整体也才几个月)。

[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
