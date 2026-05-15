# skill_doctor/
> L2 | 父级: /Users/nora/Documents/Skill Housekeeping/AGENTS.md

成员清单
__init__.py: 包入口，暴露 __version__ = "0.5.0"。
cli.py: Typer 命令层 (skill-doctor / clean / share / install-skill / undo)，仅做参数解析与编排。
scanner.py: 文件系统遍历层。RUNTIME_ROOTS 路径白名单 + JUNK_PATTERNS regex；解析 SKILL.md frontmatter，算 body sha256，记录 symlink 链与 macOS 垃圾。
analyze.py: 7 维度纯函数检查 + master 选举。group_by_hash_and_name (重复) / group_by_name (漂移) / find_broken / find_junk / find_stale + elect_master 加权评分 (version 40% + 入链 40% + mtime 20%)。
classify.py: 用途分类层。路径前缀优先 (PATH_PREFIX_RULES) → description 关键词兜底 (KEYWORD_RULES)。10 类 + 未分类。
models.py: 领域模型层。Runtime / Category / IssueType / ActionType 枚举；SkillInstance / DupGroup (含 is_aligned property) / DriftGroup / BrokenLink / JunkFile / StaleSkill / Action / FsOp / AnalysisReport dataclass。
health.py: 健康分数计算层。0-100 减扣模型 + 字母 grade (A/A-/B+/.../F)。被 report.py 首屏 wow stat 和 share.py SVG 卡片共用。
report.py: 默认视图 + JSON 渲染。render_default 顶部插 _render_health_headline (首屏震撼数字) + 自适应一屏 (count=0 隐藏维度, duplicates 拆 pending/aligned 两段) + render_json + report_to_dict + 可选 quality 子块。
report_full.py: 大表渲染。render_full 按 dir_name 聚合后输出 Rich 表，可按 runtime/category 过滤。从 report.py 拆出以保持每文件 ≤200 行。
apply.py: 动作编排层。build_actions 把分析翻译成可逆 FsOp；apply_actions 逐条 y/N/q/a + 备份 + 跑完后 _maybe_offer_handoffs 询问 drift/stale/quality 三个 AI handoff；undo_last 反向恢复最近一次 backup。剪贴板已抽到 clipboard.py。
apply_ops.py: 文件系统执行细节。execute(action, backup_dir) 与 undo_op(op)。所有"动手"动作集中在这里，便于审计。
asm_bridge.py: 可选 enrichment 桥。has_asm 检测 + quality_sample / quality_full subprocess 调 asm eval (mtime 缓存)。装了就用，没装就显示 npm install 安装指引。
handoff.py: AI handoff prompt 生成层。write_drift_handoff (unified diff, 50 行 cap) / write_stale_handoff (frontmatter + 60 行) / write_quality_handoff (asm 建议 + 60 行)。三个分别生成可粘到 Claude/Codex/Cursor 的 markdown。skill-doctor 自身从不动 drift/stale/quality 文件。
clipboard.py: 跨平台剪贴板助手。copy_to_clipboard(text) -> bool。pbcopy / wl-copy / xclip / xsel / clip 多平台 fallback。被 apply (handoff) 与 cli (share 子命令) 共享。
share.py: 病毒分发层。build_svg / build_ascii / build_markdown 三种载体 + write_share_card 一站式 CLI 入口。无新增依赖，纯字符串拼 SVG。
install_skill.py: Adoption hack 层。SKILL_TARGETS 字典 + install_skill_for/install_skill_all 把 templates/SKILL.md 写到 ~/.{claude,codex,cursor,openclaw}/skills/skill-doctor/。让 AI Agent 在用户聊天时自然 invoke skill-doctor。
templates/SKILL.md: Claude Code / Codex / Cursor / OpenClaw 通用的 skill 触发描述。description 字段穷举用户的自然语言意图（清理 / 重复 / 审计 / 断链 / stale），让 Agent 命中率最大化。
i18n.py: 双语 (zh/en) 字符串与 detect_lang。按 SKILL_DOCTOR_LANG 环境变量优先, 否则按 locale.getlocale() 自动切换。
config.py: 用户配置与 ~/.skill-doctor/ 目录管理。CONFIG_DIR / BACKUP_ROOT / HANDOFF_ROOT / QUALITY_CACHE_PATH / DEFAULT_WEIGHTS / STALE_DAYS_DEFAULT。share 子命令的输出目录 SHARE_DIR = CONFIG_DIR / "share"。
legacy/: V0.1 历史快照 (14 个旧 Python 文件)。冻结，不被新代码 import。

法则: runtime 优先·读为主·写最小·命令薄·规则可解释·每文件 ≤200 行·skill-doctor 不做 sync 引擎也不做 fan-out·adoption 优先（让 Agent 触发, 让卡片可分享, 让首屏震撼）

[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
