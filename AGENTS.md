# Skill Doctor - 跨 runtime skill 结构分析器

Python 3.12+ + Typer + Rich + Pydantic + PyYAML + rapidfuzz + questionary。

<directory>
src/ - 包源码 (1 子目录: skill_doctor)
tests/ - fixture 驱动的行为测试 (1 子目录: legacy)
</directory>

法则: research/ 与 marketing/ 为内部调研与素材，已移出公开仓库(仍在 git 历史中)，不在此地图追踪

<config>
pyproject.toml - 包元数据 / CLI 入口 / 依赖 / pytest 与 ruff 配置
README.md - 用户视角的产品契约与 quickstart
.gitignore - 排除虚拟环境、缓存、构建产物、`.skill-doctor` 运行时元数据
uv.lock - 已解析的依赖图，保证 uv 可重现运行
</config>

法则: 全量扫描·7 维度自适应·只读分析·先备份再动手·人为决策维度走 AI handoff 出口

变更日志:
- 2026-05-04: 播种 L1 项目宪法，建立 Skill Doctor V1 架构边界。
- 2026-05-04: 升级 Reduced V2 体检报告，规则目录集中化，默认只展开证据驱动的 attention 项。
- 2026-05-04: 增加 visibility organizer，提供用途分类、状态 shelf、snapshot 和 runtime compare。
- 2026-05-04: V0.2 重构 — 砍到两命令 (skill-doctor / apply / undo), 5 维度 (用途分类 / 重复 / 漂移 / 断链 / 垃圾), 自适应输出。旧 14 个文件冻结到 src/skill_doctor/legacy/。集成 asm 作为质量增强。
- 2026-05-04: V0.2.1 加陈旧维度 (mtime-based) + asm eval 走 mtime 缓存。
- 2026-05-04: V0.2.2 把 eval 升为默认开的第 7 维（asm 装了就跑），保留 --no-quality 关闭。
- 2026-05-04: V0.2.3 霹雳无敌全修：--version / 进度日志加密 / apply --yes 倒计时 / undo --pick 历史选 / 垃圾深扫 / 陈旧用整目录 mtime / config.toml 加 [[extra_runtimes]] / 大表 --no-truncate / categorize 减少"其他" 占比。
- 2026-05-04: V0.2.4 apply 重命名为 clean (apply 保留为隐藏 alias) + 陈旧默认阈值 365 → 180 天 (agent skills 概念整体也才几个月)。
- 2026-05-05: V0.4.0 清理 master 选举：删 path_depth 权重 (社区 0 引用)，version 40 + 入链 40 + mtime 20。修 Codex 警告 #11314/#17344 引用错误。修 Vim swap regex 与 macOS junk 分类。
- 2026-05-05: V0.4.1 加双语 i18n / asm cache / dedup rationale。
- 2026-05-05: V0.4.2 修 Codex issue 描述 (#15756 not-planned, #17344 dup, #11314 是目录级 bug)。加 Cursor symlink 警告。README 加 "Why directory-level symlinks" + "Out of scope"。
- 2026-05-05: V0.4.3 修报告语义谎言：duplicate 拆 pending/aligned (DupGroup.is_aligned property)；footer 改成"Nothing to auto-fix"诚实指向。
- 2026-05-06: V0.4.4 加 AI handoff 出口：clean 末尾询问 drift/stale/quality 是否生成 AI prompt → 写文件 + 自动复制到剪贴板。新增 src/skill_doctor/handoff.py。drift 用 unified diff (50 行 cap)，stale/quality 用 frontmatter + 60 行截断。asm 没装时显示 npm install 安装指引而非静默跳过。
- 2026-05-15: V0.5.0 病毒套件三连发（adoption sprint）：
  1. **首屏震撼数字**：scan 顶部新增 `🩺 Health: 73/100 (C+)` 一行 wow stat。新增 health.py 纯函数计算 0-100 健康分 + 字母 grade（A/A-/.../F），由减扣模型驱动。
  2. **share 健康卡片**：新增 `skill-doctor share` 子命令 → 输出 SVG（推到 Twitter/Reddit）+ ASCII（直接截图）+ Markdown（自动复制到剪贴板）。SVG 600×400 无外部依赖，自包含。新增 share.py。
  3. **install-skill 命令**：新增 `skill-doctor install-skill` 把 templates/SKILL.md 写到 ~/.{claude,codex,cursor,openclaw}/skills/skill-doctor/，让 AI Agent 在用户聊天时（"我感觉 skill 重了" / "audit my skills"）自然 invoke skill-doctor。新增 install_skill.py + templates/SKILL.md。
  附加：剪贴板助手从 apply.py 抽到独立 clipboard.py，消除模块耦合。
  实测：install-skill 在维护者机器 dogfood 验证，Claude Code 立刻识别 skill-doctor 为可触发 skill。

[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
