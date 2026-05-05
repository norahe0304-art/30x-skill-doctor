# skill_doctor/
> L2 | 父级: /Users/nora/Documents/Skill Housekeeping/AGENTS.md

成员清单
__init__.py: 包入口，暴露 __version__ = "0.2.0"。
cli.py: Typer 命令层 (default / apply / undo)，仅做参数解析与编排。
scanner.py: 文件系统遍历层。RUNTIME_ROOTS 路径白名单 + JUNK_PATTERNS regex；解析 SKILL.md frontmatter，算 body sha256，记录 symlink 链与 macOS 垃圾。
analyze.py: 5 维度纯函数检查 + master 选举。group_by_hash_and_name (重复) / group_by_name (漂移) / find_broken / find_junk + elect_master 加权评分。
classify.py: 用途分类层。路径前缀优先 (PATH_PREFIX_RULES) → description 关键词兜底 (KEYWORD_RULES)。10 类 + 未分类。
models.py: 领域模型层。Runtime / Category / IssueType / ActionType 枚举；SkillInstance / DupGroup / DriftGroup / BrokenLink / JunkFile / Action / FsOp / AnalysisReport dataclass。
report.py: 默认视图 + JSON 渲染。render_default 自适应一屏 (count=0 隐藏维度) + render_json + report_to_dict + 可选 quality 子块。
report_full.py: 大表渲染。render_full 按 dir_name 聚合后输出 Rich 表，可按 runtime/category 过滤。从 report.py 拆出以保持每文件 ≤200 行。
apply.py: 动作编排层。build_actions 把分析翻译成可逆 FsOp；apply_actions 逐条 y/N/q/a + 备份；undo_last 反向恢复最近一次 backup。
apply_ops.py: 文件系统执行细节。execute(action, backup_dir) 与 undo_op(op)。所有"动手"动作集中在这里，便于审计。
asm_bridge.py: 可选 enrichment 桥。has_asm 检测 + quality_sample subprocess 调 asm eval。装了就用，没装就回退提示。
config.py: 用户配置与 ~/.skill-doctor/ 目录管理。CONFIG_DIR / BACKUP_ROOT / DEFAULT_WEIGHTS。
legacy/: V0.1 历史快照 (14 个旧 Python 文件)。冻结，不被新代码 import。

法则: runtime 优先·读为主·写最小·命令薄·规则可解释·每文件 ≤200 行

[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
