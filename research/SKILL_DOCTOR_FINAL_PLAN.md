# Skill Doctor — Final Plan (拍板版)

> 第一性原理收敛后的终版。2026-05-04 冻结。
> 替代之前所有 V1/V2 计划。

---

## 一、定位（一句话）

**看清你机器上 skill 的结构地图，告诉你哪里乱了、怎么修。**

不是 lint（asm eval 做了，我们 Phase 1 调它）。
不是安全（asm audit security / vetter 做了）。
不是包管理器（asm install 做了）。
是**跨 runtime 结构地图 + 整理向导**。

---

## 二、用户主诉求（原话）

> "我主要就是要看看我有哪些 skill 然后可以整理好"

拆成 2 件事：

```
1. 看清     →  我有哪些 skill, 在哪, 是什么用途
2. 整理     →  乱的合并 / 错的修 / 垃圾清理
```

---

## 三、5 个维度（最终）

```
看清:
  📂 用途分类      Inventory 视图，按用途+runtime 分桶展示

整理:
  🟠 重复          同 hash 多副本，合并到单源
  🟡 漂移          同名但 hash 不同（版本不一致）
  ✗  断链          symlink 指向已删除文件
  🗑 垃圾          macOS '* 2' / .DS_Store / 编辑器临时文件
```

**砍掉的维度**（曾考虑过）：
- ~~孤儿~~ —— 误判多，没影响日常使用
- ~~主从乱~~ —— 融入「重复」的 master 选举
- ~~SKILL.md 写法质量~~ —— 调 asm eval
- ~~安全扫描~~ —— 调 asm audit security 或让用户自己跑 vetter

---

## 四、产品形态

**一个工具，两个命令**：

```bash
skill-doctor          # 看地图
skill-doctor apply    # 修地图
```

辅助 flag（不增加心智负担）：
```bash
skill-doctor --full              # 大表，每个 skill 一行
skill-doctor --runtime claude    # 只看一个 runtime
skill-doctor --category seo      # 只看一个用途
skill-doctor --json              # 喂下游工具
```

---

## 五、默认输出（一屏，自适应）

**核心原则：检查永远跑，显示自适应。** count = 0 的维度直接隐藏，不打扰。

清爽机器（无问题）只看到用途分类 + 一行 "✓ 一切正常"。
重度机器（你）才会看到完整 4 类整理建议。



```
$ skill-doctor

📂 你有 440 个 skill, 跨 8 个 runtime:

   Runtime          数量
   ────────────────────
   Claude Code      154
   OpenClaw         151
   Agents            44
   plugin            43
   Codex             31
   opencode           9
   codex-plugin       7
   gemini             1

   按用途分类 (基于 description + 路径前缀推断):
     SEO (32)   |  广告 (24)   |  营销 (18)
     开发 (45)  |  部署 (28)   |  数据 (12)
     设计 (15)  |  AI/视频 (9) |  其他 (220)
     未分类 (37)

   单类查看: skill-doctor --category <name>

🟠 47 组重复 / duplicates (合并后省 ~120 MB)
🟡 4 组漂移 / drift (同名不同版本)
✗  3 个断链 / broken (软链坏了)
🗑 12 个垃圾 / junk (macOS '* 2' 等)

→ 整理: skill-doctor apply

📋 想看 SKILL.md 写法质量? skill-doctor 自动调用 asm eval (若已装)
🛡️  想查安全? 跑: asm audit security <skill-name>
```

---

## 六、大表（`--full`）列定义

```
Name              Runtimes              Master Path                          Status
─────────────────────────────────────────────────────────────────────────────────────
ads-google        Claude / Codex        ~/.openclaw/skills/ads-google        🟠 dup
ab-test-setup     Claude / OpenClaw     ~/.openclaw/.../marketingskills/...  🟡 drift
copywriting       Claude / OpenClaw     ~/.openclaw/skills/copywriting       🟠 dup
some-skill        Claude                (broken)                              ✗ broken
seo-blog-writer   OpenClaw              ~/.openclaw/skills/seo-blog-writer   ✓
```

5 列：Name / Runtimes / Master Path / Status / 默认隐藏 Category（用 `--show-cat` 展开）。

---

## 七、`skill-doctor apply` 流程

```
$ skill-doctor apply

下面是要做的 47 + 4 + 3 + 12 = 66 件事。

[1/66] 合并重复: ads-google
       将 ~/.claude/skills/ads-google → 软链到 ~/.openclaw/skills/ads-google
       命令:  
         mv ~/.claude/skills/ads-google ~/.skill-doctor/backup/2026-05-04/ads-google.claude
         ln -sfn ~/.openclaw/skills/ads-google ~/.claude/skills/ads-google
       执行? [y/N/q/a]   (a = yes-to-all-of-this-type)
```

- 单条 y/N
- `q` 退出
- `a` 同类型批量同意（所有重复合并 / 所有垃圾删除）
- 删除前先 `mv` 到 `~/.skill-doctor/backup/<timestamp>/`
- 备份保留 30 天，过期清理
- 一行命令恢复：`skill-doctor undo`

---

## 八、5 类检查的具体逻辑

| 类 | 信号 | 算法 |
|---|---|---|
| **用途分类** | description 关键词 + 路径前缀 | `30x-seo-* → SEO`、`ads-* → 广告`、description 含 "SEO/blog/keyword" → SEO，未匹配 → 未分类 |
| **重复** | body hash 相同 | sha256(normalized SKILL.md body) 分组，同组 ≥2 即重复 |
| **漂移** | dirName 相同但 hash 不同 | 按 dirName 分组 → 各份 hash 不同 → 标 drift |
| **断链** | symlink 但 target 不存在 | `Path.is_symlink() and not Path.exists()` |
| **垃圾** | 4 类文件名模式 | 见下面规则 |

### 垃圾的具体定义（4 类）

```python
JUNK_PATTERNS = [
    # 1. macOS 副本污染（iCloud / Time Machine 留下）
    r" \d+\.md$",           # "FILENAME 2.md"
    r" \d+\.json$",
    r" \d+\.py$",
    r" \d+/$",              # "DIRNAME 2/"

    # 2. macOS 系统隐藏文件
    r"^\.DS_Store$",
    r"^\._",                # AppleDouble metadata
    r"^__MACOSX$",

    # 3. 编辑器临时文件
    r"\.swp$",              # vim swap
    r"\.swo$",
    r"~$",                  # editor backup
    r"\.un~$",              # vim undo

    # 4. SKILL.md 文件本身的多余副本（不是漂移，是 macOS 副本）
    r"^SKILL \d+\.md$",
    r"^README \d+\.md$",
]
```

**不算垃圾**（防止误判）：
- ❌ `v2.md` `v3.md` 这种语义版本号
- ❌ `step-2.md` `chapter-3.md` 这种内容编号
- ❌ 用户主动命名带数字的文件（如 `top-10-tips.md`）

判定规则：**必须是空格 + 纯数字 + 扩展名**，才算 macOS 副本。

### Master 选举算法（重复维度的核心）

```python
score = (
    version_rank      * 0.40 +   # 版本号 semver 比较，新的得分高
    incoming_links    * 0.30 +   # 入向 symlink 数（多少别的副本指向它）
    path_depth        * 0.15 +   # 路径深度（marketingskills/skills/x 比 skills/x 深 = 真源）
    mtime_freshness   * 0.15     # 修改时间（新的得分高）
)
master = group.instances.argmax(score)
```

权重在 `~/.skill-doctor/config.toml` 可改。

---

## 九、技术栈

Python 3.12+ / Typer / Rich / Pydantic / PyYAML / rapidfuzz / questionary。
保留现有 `pyproject.toml` 配置。

---

## 十、文件结构

```
src/skill_doctor/
  __init__.py
  cli.py            ~80 行   两个命令 + flag handling
  scanner.py        ~150 行  扫文件系统 + 解析 SKILL.md + symlink 链
  analyze.py        ~200 行  5 类检查 + master 选举
  classify.py       ~80 行   用途分类（路径前缀 + description 关键词）
  asm_bridge.py     ~80 行   subprocess 调 asm eval / audit security（可选）
  models.py         ~80 行   Skill / Group / Issue / Action
  report.py         ~150 行  rich 表格 + 双语摘要
  apply.py          ~120 行  逐条确认 + 备份 + 执行 + undo
  config.py         ~40 行   ~/.skill-doctor/config.toml

总计: ~980 行 / 9 文件
```

**所有文件 ≤200 行**。无子目录嵌套。

---

## 十一、要砍的旧文件

```
src/skill_doctor/
  cli.py              重写
  scanner.py          重写（保留 runtime 路径白名单）
  parser.py           重写并合进 scanner
  models.py           重写
  rules.py            删 (603 行 → asm eval 替代)
  rule_catalog.py     删
  report.py           重写 (850 → 150 行)
  compare.py          删
  organizer.py        删
  serialization.py    删
  index.py            删
  runtime_registry.py 保留（路径白名单复用）
  config.py           简化

旧文件 git mv 到 legacy/ 备份, 不直接删。
legacy/README.md 写一句"v1 历史快照, 已被 v0.2 取代"
```

---

## 十二、5 阶段实施（共 ~12 小时）

**Phase 0 · 清场（1 小时）**
- `git mv` 14 个旧文件到 `legacy/`
- 建 9 个新空文件 + 空 `__init__.py`
- pytest 跑通空架子（占位测试）

**Phase 1 · 扫描 + 分析（4 小时）**
- `scanner.py` 走 8 个 runtime 路径
- `analyze.py` 实现 4 类整理检查（重复 / 漂移 / 断链 / 垃圾）+ master 选举
- `classify.py` 用途分类（10 大类 + 未分类）
- 单元测试: fixture 模拟 5 种典型乱况

**Phase 2 · 报告 + CLI（3 小时）**
- `report.py` 默认一屏输出 + `--full` 大表 + `--json`
- `cli.py` 默认命令 + flags
- 在你机器上跑通，对照真实 440 个 skill / 47 dup groups

**Phase 3 · Apply（2 小时）**
- `apply.py` 逐条 y/N/q/a + 备份 + undo
- 在你机器上 dry-run 一遍

**Phase 4 · asm 集成（1 小时）**
- `asm_bridge.py` 检测 `which asm`
- 装了就在 footer 显示"想看质量? skill-doctor 已为你跑了 asm eval, 5 个最低分: ..."
- 没装就跳过

**Phase 5 · 收尾（1 小时）**
- README 重写
- AGENTS.md 文档同步（GEB 协议 L1/L2/L3）
- legacy/README.md

---

## 十三、Definition of Done

- [ ] `skill-doctor` 在你机器上跑出真实数字（应接近 440 skills / 47 dup groups / 4 drift / 3 broken / 12 junk）
- [ ] 用途分类至少识别出 9 大类（SEO/广告/营销/开发/部署/数据/设计/AI/其他）
- [ ] 默认输出 ≤ 60 行
- [ ] master 选举正确（ab-test-setup 应选 v1.1.0 深路径那份）
- [ ] `skill-doctor apply` 能正确处理 1 组重复 + 1 个 macOS 垃圾
- [ ] 备份在 `~/.skill-doctor/backup/<ts>/` 可恢复
- [ ] `skill-doctor undo` 一键恢复最近一次 apply
- [ ] 所有源文件 ≤ 200 行
- [ ] asm 装了就显示质量摘要，没装也能正常跑
- [ ] 文档同步（README + AGENTS.md L1/L2）

---

## 十四、不做的事（边界明确）

- ❌ SKILL.md 写法 lint（→ asm eval）
- ❌ 安全扫描（→ asm audit security / vetter）
- ❌ 评分（grade A/B/C/D）
- ❌ 安装 / 更新 / 卸载（→ asm install）
- ❌ catalog / search / publish（→ asm）
- ❌ TUI（v1 只 CLI）
- ❌ 运行历史 / cron / track（→ v2）
- ❌ 孤儿检测（误判多，砍掉）
- ❌ 主从乱（融进 master 选举，不是独立维度）
- ❌ "建议加 ## Prerequisites" 这类评论性 lint（asm 已做）

---

## 十五、定位标语（README 第一行）

> **Skill Doctor 看清你机器上 skill 的结构地图：哪些重复了、漂移了、断链了、是垃圾。给你修复方案，让你确认后执行。仅此而已。**

---

[PROTOCOL]: 变更时更新此头部，然后检查 AGENTS.md
