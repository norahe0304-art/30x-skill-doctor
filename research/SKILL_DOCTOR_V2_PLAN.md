# Skill Doctor v2 — Cross-Runtime Structural Curator

> Single source of truth for the v2 redesign. Frozen 2026-05-04.

---

## 1. Vision

**Skill Doctor 是你机器上 skill 文件的跨 runtime 结构分析器。它读、它分类、它指出冲突、它给 consolidate plan。它从不假装知道你用没用过。**

我们不是 sync 引擎（`runkids/skillshare` 是），不是单 runtime curator（Hermes 是），不是安全网关（`skill-vetter` 是）。我们填的是空位 ——

> **"在你按下任何 sync 按钮之前，让你看清你机器上 skill 的真实结构图与最佳合并路径。"**

输出供下游消费：人类读报告、`skillshare` 读 plan、agents 读 JSON。

---

## 2. Non-Goals（明确不做）

1. ❌ 不修改用户 skill 文件（不 ln/不 mv/不 rm）
2. ❌ 不基于使用频次评分（我们没有遥测数据，假装就是骗）
3. ❌ 不做安全扫描（aguara/skill-vetter 已成熟）
4. ❌ 不生成 skill（skill-creator 已成熟）
5. ❌ 不做包管理（marketplace plugin 自有机制）
6. ❌ 不与单 runtime curator 竞争（Hermes 在它的领域已经强）
7. ❌ 不在 v1 做 grade letter / prune / track —— 留给 v2

---

## 3. 第一性原理（五公理）

| # | 公理 | 落地约束 |
|---|---|---|
| P1 | 工具是镜子，不是手术刀 | 只写 `.skill-doctor/`，绝不写其他路径 |
| P2 | 没有跨 runtime 的"标准答案" | 每 skill 必带 portability tag，规则按 tag 分支 |
| P3 | 一个问题 = 一个命令 | CLI 三动词清晰映射用户脑中提问 |
| P4 | 数据单向流动 | 6 层管道，每层只读上层 |
| P5 | Source-of-truth 由 symlink 图自己说话 | Provenance = 多信号加权计算，不靠人工配置 |

---

## 4. 架构（6 层 / `src/skill_doctor/`）

```
DISCOVERY    scanner.py            ≤150 行   遍历 runtime 路径，解析 symlink 图
PARSING      parser.py             ≤120 行   frontmatter + body 容错解析
NORMALIZE    models.py             ≤200 行   Skill / SkillInstance / SkillGroup / Plan
ENRICH       analyzers/                       纯函数，每个维度一个文件:
               portability.py      ≤150 行     → portable / degrades / locked
               category.py         ≤150 行     → SEO / Ads / Dev / Marketing ...
               quality.py          ≤200 行     → 13 条 canon 规则
               placement.py        ≤180 行     → 跨 runtime 分布健康度
               provenance.py       ≤150 行     → 0-100 多信号置信度
               relations.py        ≤200 行     → exact / near / overlap
               election.py         ≤150 行     → consolidate 源选举算法
VIEWS        views/                            视图组装层（出口收窄到两个）:
               inventory_view.py   ≤200 行     → 大表（状态）
               clean_view.py       ≤220 行     → 统一清理表（lint findings + consolidate plans 排序合并）
PRESENT      cli.py                ≤180 行   Typer 命令入口
             report.py             ≤200 行   Rich/JSON 双 renderer
             rule_catalog.py       ≤180 行   规则定义 + 官方文档 URL
             config.py             ≤120 行   `.skill-doctor/` 元数据读写
             runtime_registry.py   ≤120 行   runtime 路径与默认源
             serialization.py      ≤120 行   index/plan JSON 编解码
             index.py              ≤80 行    扫描快照缓存
```

**所有文件 ≤200 行**（GEB 红线 800 严守）。当前 `report.py`(850) / `rules.py`(603) 必须爆破。

---

## 5. 数据模型

```python
# models.py
class SkillInstance:
    path: Path
    runtime: Runtime  # claude / codex / cursor / openclaw / agents / marketplace
    format: Format    # SKILL_MD / AGENTS_MD / CURSORRULES
    is_symlink: bool
    symlink_target: Path | None
    file_is_symlink: bool       # ⚠️ Codex 反模式：SKILL.md 自身是软链
    frontmatter: dict
    body_hash: str              # sha256 of normalized body
    body_lines: int
    mtime: datetime
    git_remote: str | None
    parse_diagnostics: list[Diagnostic]

class Skill:                    # 逻辑实体（同 identity 的副本群）
    identity: str               # frontmatter.name 或路径推断
    instances: list[SkillInstance]
    portability: Literal["portable", "degrades", "locked"]
    category: str               # 自动分类
    quality_score: int          # 0-100, A 轴
    placement_score: int        # 0-100, B 轴
    structural_score: int       # 0-100 = 0.5*Q + 0.5*P
    provenance_score: int       # 0-100, 独立维度
    findings: list[Finding]

class Finding:
    rule_id: str                # e.g. "Q01_NAME_REGEX"
    severity: Literal["BLOCK", "ATTENTION", "NOTE", "OK"]
    evidence: str               # 一句话事实
    citation_url: str           # 官方文档链接
    skill_id: str
    instance_path: Path | None  # 落到具体副本（如 file_is_symlink）

class ConsolidatePlan:
    group_id: str
    skill_identity: str
    elected_source: SkillInstance
    election_rationale: str     # "openclaw + 入向 20 链 + git remote"
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    actions: list[PlanAction]   # ln / skip / warn
    notes: list[str]
```

---

## 6. 规则目录（v1 共 14 条 / `rule_catalog.py`）

每条规则带官方 URL 引用。Severity: BLOCK > ATTENTION > NOTE > OK。

### Quality 轴（A 轴，共 8 条）

| ID | 规则 | Severity | 引用 |
|---|---|---|---|
| Q01 | `name` 必须匹配 `^[a-z0-9-]+$` 且 ≤64 chars | BLOCK | platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices |
| Q02 | `description` 非空且 ≤1024 chars | BLOCK | 同上 |
| Q03 | `description` 应包含 trigger 信号词（"use when", "when user"） | NOTE | skill-creator/SKILL.md |
| Q04 | SKILL.md body ≤500 行 | ATTENTION | 同上 |
| Q05 | `references/*.md` 单文件 >300 行须含 TOC | NOTE | 同上 |
| Q06 | `description` 与正文主题一致（Lack of Surprise） | NOTE | 同上 |
| Q07 | 正文 ALL-CAPS MUST/NEVER ≥3 次 → 建议改为 "Why: ..." | NOTE | 同上 |
| Q08 | 跨引用 `@/path` / `references/foo.md` 必须存在 | ATTENTION | agentskills.io/specification |

### Placement 轴（B 轴，共 4 条）

| ID | 规则 | Severity | 触发条件 |
|---|---|---|---|
| P01 | SKILL.md 文件本身是 symlink → Codex 静默忽略 | ATTENTION | github.com/openai/codex/issues/17344 |
| P02 | 同 hash 多副本但无入向 symlink 关系 | NOTE | 应 consolidate |
| P03 | 跨 runtime 同名但 hash 不同（漂移） | ATTENTION | 哪份是真？ |
| P04 | Portable skill 仅在单 runtime 出现 | NOTE | 可镜像 |

### 卫生（共 2 条）

| ID | 规则 | Severity | 触发条件 |
|---|---|---|---|
| H01 | macOS `* 2` 副本污染（CHANGELOG 2.md 等） | NOTE | iCloud/TimeMachine 残留 |
| H02 | frontmatter YAML 解析失败 | BLOCK | runtime 加载会失败 |

---

## 7. Portability 判定（`analyzers/portability.py`）

```
🟢 portable     frontmatter 仅含 name + description + metadata.version
                正文无 mcp__plugin_*, .claude/hooks/, .codex/ 路径
                → 跨 runtime 完全等价

🟡 degrades     frontmatter 含 allowed-tools / model / effort（Claude 专属）
                其他 runtime 静默忽略，能跑但缩水
                → 可同步，告知用户会缩水

🔴 locked       含 hooks / disable-model-invocation / context: fork
                或正文出现 "in Claude Code" / plugin: 命名空间硬编码
                → 跨 runtime 会错乱，不建议同步
```

判定信号在 `portability.py` 里硬编码，每条信号带原因注释。

---

## 8. Provenance 模型（`analyzers/provenance.py`）

**0-100 多信号叠加，不一票否决。**

| 信号 | 加分 |
|---|---|
| 在 git 仓且有 remote | +30 |
| frontmatter 含 `audit:` block（vetter 风格） | +25 |
| 入向 symlink ≥ 2 | +20 |
| 在已知目录树（openclaw/marketplace/anthropics） | +20 |
| frontmatter 含 `metadata.author` 或 `metadata.source` | +15 |
| 内容 hash 在已知 catalog（agentskills.io API，可选异步） | +15 |
| README.md 含 source URL | +10 |
| git log 真实人名提交 ≥ 3 次 | +5 |

**最大 100，截断**。HIGH ≥70 / MED 40-69 / LOW <40。

Provenance **绝不**作为闸门 —— 只影响 consolidate plan 的 confidence 标签。

---

## 9. Consolidate 算法（`analyzers/election.py` + `views/consolidate_view.py`）

### 9.1 分组

按 `body_hash` 分组得 exact-dup 集合。near-dup（相似度 ≥0.9）单独分组、只标记不出 plan。

### 9.2 源选举（每组）

```
1. 是否任一副本在 marketplace plugin 路径？
   → 是 → 跳过整组（plugin 自管），输出 SKIP 状态
   
2. 否则，按 provenance_score 降序排
   平票 → 入向 symlink 数降序 → mtime 升序 → path 字典序

3. 选 rank=1 当 source
```

### 9.3 Plan 生成

```python
for other in group.instances:
    if other == source: continue
    if other.is_symlink and resolves_to(source):
        action = SKIP_ALREADY_LINKED
    elif source.is_in_marketplace:
        action = SKIP_MARKETPLACE_OWNS
    else:
        action = REPLACE_WITH_SYMLINK   # 输出命令文本
        commands.append(f"rm -rf {other.path}")
        commands.append(f"ln -s {source.path} {other.path}")
        # ⚠️ rm 命令仅打印，不执行
```

### 9.4 Confidence 标签

| Source 特征 | Confidence |
|---|---|
| Marketplace（已跳过） | N/A |
| git-tracked + 公开 remote | HIGH |
| git-tracked + 私有/无 remote | MEDIUM |
| 无 git，但 provenance ≥40 | MEDIUM |
| 无 git，provenance <40 | LOW（提示手动核源） |
| 全组 provenance <40 + 内容不一致 | NO_PLAN（仅列证据） |

---

## 10. CLI 表面（`cli.py`）—— 两个动词，到此为止

**用户 JTBD 只有两件事**：(1) 我有什么 → `inventory`，(2) 该清理什么 → `clean`。
`lint` / `consolidate` 是**内部模块名**，绝不暴露成命令。

```bash
skill-doctor                          # 交互菜单 (questionary)

skill-doctor inventory                # 大表：状态
skill-doctor inventory --runtime claude
skill-doctor inventory --category seo
skill-doctor inventory --json

skill-doctor clean                    # 统一清理表：行动
skill-doctor clean --type dedup            # 只看去重类
skill-doctor clean --type metadata         # 只看 SKILL.md 写法问题
skill-doctor clean --type structure        # 只看结构类（如 SKILL.md-as-symlink）
skill-doctor clean --type noise            # 只看 macOS 副本污染
skill-doctor clean --confidence HIGH       # 只看高置信
skill-doctor clean --severity BLOCK        # 只看致命
skill-doctor clean --skill ads-google      # 单 skill 聚焦
skill-doctor clean --json > plan.json      # 喂下游工具
skill-doctor clean --emit-script > apply.sh  # 生成可粘贴 bash（不自动执行）
```

**v1 砍掉**：`check` / `snapshot` / `compare`（语义模糊，被两动词替代）。
**也不暴露**：`lint` / `consolidate` / `audit`（内部模块，不是用户脑里的词）。

---

## 11. 大表列定义（inventory）

```
Name | Cat | Runtimes | Source | Port | Prov | Score | Findings | Dup | Updated
─────┼─────┼──────────┼────────┼──────┼──────┼───────┼──────────┼─────┼─────────
ads-google | Ads | C X O | ~/.openclaw/skills/ads-google | 🟢 | HIGH(85) | 92 | – | unique | 26d
skill-vetter | Sec | C X O +18 | ~/.openclaw/.../skill-vetter | 🟢 | HIGH(95) | 88 | NOTE×1 | 21 copies | 47d
copywriting | Mkt | C O | ~/.openclaw/skills/copywriting | 🟡 | MED(55) | 72 | ATTN×2 | overlap | 3d
```

**默认排序**：findings 倒序 → runtime 数倒序 → name。

**列说明**：
- `Cat` = 自动分类（路径前缀 `30x-seo-*` `ads-*` + description 关键词）
- `Runtimes` = 用一字母 chip 显示（C=Claude, X=Codex, U=Cursor, O=Openclaw, A=Agents, M=Marketplace）
- `Port` = 🟢portable / 🟡degrades / 🔴locked
- `Prov` = HIGH/MED/LOW (score)
- `Score` = structural_score (0.5*Q + 0.5*P)

---

## 12. 输出文件结构

```
.skill-doctor/
  index.json                    # 当前全量快照
  history/
    2026-05-04T14-22.json       # 每次运行的快照（diff 用）
  plans/
    consolidate-2026-05-04.json # 最近一次 consolidate plan
  REPORT.md                     # 人类可读的最近报告
```

`history/` 启用 v2 的 `track` 命令做 diff，v1 已经写但不读。

---

## 13. 测试计划

### 13.1 现有测试保留
`test_scan.py` / `test_dedupe.py` 重构后内容不变，验证扫描 + dedupe 行为。

### 13.2 新增 fixtures
`tests/fixtures/` 加：
- `cross_runtime_symlinks/` — openclaw 风格扇出，验证源选举
- `codex_symlink_bug/` — SKILL.md 自身是软链，验证 P01 规则
- `marketplace_owned/` — `.claude/plugins/marketplaces/*/skills/`，验证 SKIP
- `provenance_signals/` — 8 种 provenance 信号的最小样本

### 13.3 新增测试文件
```
test_portability.py    # 三档判定
test_provenance.py     # 8 信号叠加
test_election.py       # 源选举算法
test_consolidate.py    # plan 生成 + confidence 标签
test_lint.py           # 14 条规则
test_inventory_view.py # 大表渲染
```

每个测试 ≤30 行，fixture-driven。

---

## 14. 迁移路线（B 路线 / 增量绞杀）

**总原则**：旧 `rules.py` 不一次性删，规则一条条迁过去。中途任何时刻 `pytest` 必须绿。

### Phase 0 · 准备（半天，不引入新功能）
- [ ] 建 `analyzers/` 目录 + 空 `__init__.py`
- [ ] 建 `views/` 目录 + 空 `__init__.py`
- [ ] 建 `tests/fixtures/` 子目录占位
- [ ] 在 `models.py` 补 `Finding.citation_url` / `Skill.portability` / `Skill.provenance_score` / `ConsolidatePlan` 字段
- [ ] CI 跑通

**交付**：仓库结构就绪，行为不变。

### Phase 1 · Inventory 大表（1 天）
- [ ] `analyzers/portability.py`（含 3 档判定逻辑 + 单测）
- [ ] `analyzers/category.py`（路径前缀 + description 关键词）
- [ ] `analyzers/provenance.py`（8 信号 + 单测）
- [ ] `views/inventory_view.py`（Rich 表 + JSON）
- [ ] `cli.py` 加 `inventory` 子命令
- [ ] 拆 `report.py` 中 inventory 相关代码到 `views/`，原 `report.py` 收缩

**交付**：`skill-doctor inventory` 跑通，你第一次看到全机器 skill 大表。

### Phase 2 · Clean（2.5 天）—— lint + consolidate 内部模块同期建，外部出口统一

子任务并行：
- [ ] `analyzers/quality.py`（Q01-Q08，每条带 citation URL）
- [ ] `analyzers/placement.py`（P01-P04）
- [ ] `analyzers/relations.py`（exact/near/overlap 分组）
- [ ] `analyzers/election.py`（源选举）
- [ ] `rule_catalog.py` 重写为规则注册表 + URL
- [ ] `views/clean_view.py`（统一表：lint findings + consolidate plans 合并 + 排序）
- [ ] `cli.py` 加 `clean` 子命令 + 各类 filter（`--type` / `--confidence` / `--severity` / `--skill` / `--emit-script`）
- [ ] 接 `~/.skill-doctor/plans/` 落盘
- [ ] 旧 `rules.py` 中已迁规则删除

**交付**：`skill-doctor clean` 跑通 —— 一张统一排序表，混合 14 条 lint 规则的 findings + 跨 runtime dedup plans，按严重度+置信度排序。`--json` 出机读 plan，`--emit-script` 出可粘贴 bash。

### Phase 4 · 收尾（半天）
- [ ] 删旧命令 `check` / `snapshot` / `compare`（或保留别名 1 个版本后移除）
- [ ] `report.py` 拆完，剩余代码 ≤200 行
- [ ] `rules.py` 清空 / 删除
- [ ] 跑全量验证命令（README.md "Development verification" 那一段）
- [ ] AGENTS.md 三层全部更新（L1 + L2 src/ + L2 tests/ + L2 research/）父级链接修齐
- [ ] L3 头部按 GEB 协议加到所有新增文件

**交付**：v0.2.0，三动词全部就绪，文档与代码同构。

**总工时估**：3.5 天纯写代码 + 0.5 天文档/收尾 = 4 天。

---

## 15. Definition of Done（v1 验收）

- [ ] `pytest` 全绿，新增 ≥40 个测试用例
- [ ] `ruff check .` 无 warning
- [ ] 所有源文件 ≤200 行（无单文件 >800）
- [ ] `skill-doctor inventory` 在你机器上跑通，输出 ≥250 行 skill 大表
- [ ] `skill-doctor clean` 输出统一表 —— 至少识别出 skill-vetter 跨 20 runtime 副本组的 HIGH-conf DEDUP 行 + ≥1 条 BLOCK + ≥10 条 NOTE 的 metadata/structure findings，全部按严重度+置信度排序
- [ ] `skill-doctor clean --type dedup` 只显示去重类
- [ ] `skill-doctor clean --json | head` 是合法 JSON
- [ ] `skill-doctor clean --emit-script` 生成的 bash 在干净环境下 dry-run 安全
- [ ] L1/L2/L3 GEB 文档全部就绪
- [ ] README.md 重写：定位句 + 三动词示例

---

## 16. Open Questions（动手前最后确认）

1. **L1 文件名**：当前是 `AGENTS.md`，你要改 `CLAUDE.md` 还是保持 `AGENTS.md`？（agents.md 标准 + Codex 一等公民支持，建议保 `AGENTS.md`）
2. **runtime 路径白名单**：`runtime_registry.py` 默认扫描列表是否覆盖完整？我列的：
   ```
   ~/.claude/skills, ~/.codex/skills, ~/.cursor/skills,
   ~/.openclaw/workspace/{.claude,.codex,.cursor,.agents,...}/skills,
   ~/.openclaw/skills, ~/.agents/skills,
   ~/.claude/plugins/marketplaces/*/skills,
   ~/.codex/superpowers, ~/.codex/plugins/*/skills
   ```
   还有要加的吗？
3. **provenance "已知 catalog 查询" 是否启用？** 需要异步 HTTP 调 agentskills.io。默认 `--no-network`，加 flag `--enrich-online` 才查。OK？

---

## 17. 引用清单

- agentskills.io 标准 — https://agentskills.io/
- Claude Code skills — https://code.claude.com/docs/en/skills
- Codex skills — https://developers.openai.com/codex/skills
- skill-creator canon — https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md
- best-practices — https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- Codex symlink bug — github.com/openai/codex/issues/17344, /8369, /11314
- runkids/skillshare — https://github.com/runkids/skillshare
- ariccb/sync-claude-skills-to-codex — https://github.com/ariccb/sync-claude-skills-to-codex
- obra/superpowers-marketplace — https://github.com/obra/superpowers-marketplace
- Hermes Curator — https://github.com/NousResearch/hermes-agent
- skill-vetter — https://github.com/app-incubator-xyz/skill-vetter
- aguara — https://github.com/garagon/aguara

---

[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
