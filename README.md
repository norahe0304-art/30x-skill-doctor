# Skill Doctor

**给 AI agent skill 做大扫除的工具。**

你机器上 skill 太多 —— Claude 装了一堆，Codex 装了一堆，OpenClaw 又一堆，互相重复、互相打架，软链坏了不知道，一年没改的 skill 还在那躺着。

Skill Doctor 帮你看清现状 + 给你具体的清理方案。**永远不替你瞎删**，每个动作你点头才执行，删之前先备份，一行命令能撤回。

---

## 三步上手

### 第 1 步：装

```bash
pipx install skill-doctor
```

或者用 uv：

```bash
uv tool install skill-doctor
```

没有 pipx？跑 `pip install pipx && pipx ensurepath` 装一下，或者直接 `pip install skill-doctor`。

> **可选**：装 [`asm`](https://github.com/luongnv89/agent-skill-manager) 可以解锁 SKILL.md 写法质量评估那一块（`npm install -g agent-skill-manager`）。不装也能用其他 6 个维度。

### 第 2 步：看你有什么

```bash
skill-doctor
```

你会看到这样一份报告：

```
📂 你有 453 个 skill, 跨 8 个 runtime:

    Claude Code        154
    OpenClaw           151
    Plugin (Claude)     48
    Agents              44
    Codex               31
    Plugin (Codex)      14
    OpenCode             9
    Cursor               2

  按用途分类:
    SEO (91) | 营销 (59) | 开发 (47) | 广告 (41) | 设计 (19) | ...

🟠 70 组重复 / duplicates (187 instances)
🟡 38 组漂移 / drift (同名不同版本)
✗  25 个断链 / broken links

📋 写法质量评估 (附送, 来源: asm v2.6.1)
  453 个 skill 评分   B:23 C:262 D:150 F:18
  最低 5 个 + 修复建议:
  humanizer-zh  23/100  F
    • Write a one-sentence description that says specifically what...
    • Add a "## Acceptance Criteria" section with testable statements...

→ 整理: skill-doctor clean
```

### 第 3 步：整理（动手扫除）

```bash
skill-doctor clean
```

`clean` 就是"开扫"。它会**逐条问你**：

```
[1/48] 合并 ads-google (claude)
  ~/.claude/skills/ads-google → 软链到 ~/.openclaw/skills/ads-google
  执行? [y/N/q/a (a=同类型批量同意)]
```

按键说明：
- **y** 确认这一条
- **N** 跳过这一条（直接回车也是跳过）
- **q** 立即停止
- **a** 这种类型后面全部同意（不再问）

**不放心？打 N 全跳过**，看完所有建议再决定。

整理过程中删任何东西**先备份**到 `~/.skill-doctor/backup/<时间戳>/`，撤回一行命令：

```bash
skill-doctor undo
```

---

## 七个维度（这工具会查啥）

| 是啥 | 干嘛的 |
|---|---|
| 📂 **用途分类** | 自动给 skill 贴标签：SEO / 广告 / 营销 / 开发 …… |
| 🟠 **重复** | 同一份 skill 在多个 runtime 都有副本 → 建议软链合并到一份 |
| 🟡 **漂移** | 同名 skill 但内容不一样了（比如 Claude 是 v1.1，OpenClaw 是 v1.0）→ 让你手动决定哪份是对的 |
| ✗ **断链** | 软链指向已删除的文件，这 skill 用不了 → 帮你移除死链 |
| 🗑 **垃圾** | macOS 自动留下的 `* 2.md` / `.DS_Store` 等垃圾文件 → 删 |
| 🕰 **陈旧** | 整个 skill 目录超过半年没动 → 提醒你看一眼，不一定要删（默认 180 天，agent skills 这个概念整体也才几个月）|
| 📋 **写法质量** | SKILL.md 写得规不规范 → 给分数 + 修复建议 |

**自适应显示**：如果某个维度查出来 0 条，那一项就不会出现在报告里。清爽机器只看到分类 + 一句"一切正常"。

---

## 常用命令

```bash
# 看（最常用）
skill-doctor                       # 默认报告
skill-doctor --full                # 完整大表（每个 skill 一行）
skill-doctor --full --no-truncate  # 路径太长？这样不截断
skill-doctor --version             # 看 skill-doctor + asm 版本

# 整理
skill-doctor clean                 # 逐条 y/N 确认整理
skill-doctor undo                  # 撤销最近一次 apply

# 进阶
skill-doctor --stale-days 90       # 改陈旧阈值（默认 180 天）
skill-doctor --runtime claude      # 只看 Claude Code
skill-doctor --category seo        # 只看 SEO 类
skill-doctor --json                # 喂给别的工具
skill-doctor clean --yes           # 自动全跑（3 秒倒计时给 Ctrl+C）
skill-doctor undo --pick           # 从历史 backup 选一个恢复
```

---

## 一些常见疑问

**Q: 它会自动删我的 skill 吗？**
不会。所有删除前先 mv 到 `~/.skill-doctor/backup/`。一行 `skill-doctor undo` 完全恢复。

**Q: "重复"怎么判定？**
两个 skill 名字相同 + SKILL.md 内容 sha256 一致才算重复。不同名字的就算内容一样也不动你。

**Q: "漂移"为什么不自动改？**
两个版本不一样意味着可能是有意改的（比如你在 Claude 下手动调过）。我们不替你决定哪份对，只列出来你看。

**Q: 第一次跑 `skill-doctor` 等了 40 秒？**
首次会把每个 SKILL.md 跑一遍写法质量评估。**有缓存**，第二次跑就 0.4 秒。改了 SKILL.md 之后只重评那一个。

**Q: 我有自己的 skill 路径，工具没扫到？**
编辑 `~/.skill-doctor/config.toml`：

```toml
[[extra_runtimes]]
path = "~/my-skills"
runtime = "unknown"
glob = "*"
```

**Q: 跑 `apply` 之后我后悔了？**
```bash
skill-doctor undo
```

或者从所有历史里选一个：
```bash
skill-doctor undo --pick
```

**Q: 写法质量评估的分数从哪来？**
调用一个独立的开源评估器（[asm](https://github.com/luongnv89/agent-skill-manager)，对齐 Anthropic skill-creator 规范）。装了就自动用，没装也不影响其他 6 个核心维度。

---

## 开发者向（你不需要看）

```bash
uv run --no-editable pytest                  # 跑测试
uv run --no-editable ruff check .            # lint
```

文件结构在 `AGENTS.md`（项目宪法）和 `src/skill_doctor/AGENTS.md`（模块清单）。
