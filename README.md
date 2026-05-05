# 30x Skill Doctor

**Spring-cleaning for your AI agent skill library.**

If you use Claude Code, Codex, Cursor, OpenClaw, or any combination of them,
your `~/.claude/skills/`, `~/.codex/skills/`, `~/.cursor/skills/`, and plugin
directories are probably a graveyard. The same skill installed three times under
three different names. Old version in one runtime, newer version in another.
Symlinks pointing at deleted files.

`30x-skill-doctor` scans the lot, surfaces what's wrong, and walks you through
a fix — interactively, with a backup, and a one-line undo.

![Demo](./skill-doctor-demo.gif)

---

## Three steps

### 1. Install

```bash
pipx install 30x-skill-doctor
```

Or with uv:

```bash
uv tool install 30x-skill-doctor
```

Plain `pip` works too: `pip install 30x-skill-doctor`.

> Optional: install [`asm`](https://github.com/luongnv89/agent-skill-manager)
> (`npm install -g agent-skill-manager`) to unlock the SKILL.md write-quality
> dimension. Everything else works without it.

### 2. See what you have

```bash
skill-doctor
```

You'll get a one-screen report like this:

```
📂 You have 453 skills across 8 runtimes:

    Claude Code        154
    OpenClaw           151
    Plugin (Claude)     48
    Agents              44
    Codex               31
    Plugin (Codex)      14
    OpenCode             9
    Cursor               2

  Categories:
    Other (147) | SEO (91) | Marketing (59) | Dev (47) | Ads (41) | ...

🟠 70 duplicate groups (187 instances)
🟡 38 drift conflicts (same name, different content)
✗  25 broken symlinks

📋 SKILL.md write quality
   B:23 C:262 D:150 F:18

→ Clean up: skill-doctor clean
```

Dimensions with zero findings are hidden automatically. Clean machines just
see the inventory and a green checkmark.

### 3. Tidy up

```bash
skill-doctor clean
```

It walks through every issue interactively:

```
[1/48] Merge ads-google (claude)
  ~/.claude/skills/ads-google → symlink to ~/.openclaw/skills/ads-google
  Apply? [y/N/q/a (a = yes-to-all-of-this-type)]
```

- **y** — apply this one
- **N** — skip (default; bare Enter also skips)
- **q** — stop right here
- **a** — yes-to-all of this action type (no more prompts for it)

Anything destructive is `mv`'d to `~/.skill-doctor/backup/<timestamp>/` first,
not removed. Roll back the last apply with:

```bash
skill-doctor undo
```

Need to recover an older one? `skill-doctor undo --pick`.

---

## Seven dimensions it checks

| | What it catches | What `clean` does about it |
|---|---|---|
| 📂 **Categories** | Auto-tags every skill (SEO / Ads / Marketing / Dev / …) | — |
| 🟠 **Duplicates** | Identical SKILL.md (sha256) under multiple runtimes | Replace copies with symlinks to a smart-elected master |
| 🟡 **Drift** | Same name, different content (e.g. v1.1 in Claude, v1.0 in OpenClaw) | Surface only — you choose the source of truth |
| ✗ **Broken** | Symlink whose target doesn't exist anymore | Remove the dead link |
| 🗑 **Junk** | macOS `* 2.md`, `.DS_Store`, vim swap files, etc., anywhere in the tree | Backup and delete |
| 🕰 **Stale** | Skill directory untouched for > 180 days (mtime) | Just flagged — your call |
| 📋 **Write quality** | SKILL.md hygiene + suggested fixes (cached, near-instant after first scan) | — |

### Master election (the dedup heart)

When several copies of the same skill exist, one becomes the canonical source
the others symlink to. The election score is transparent:

```
score = version (40%) + inbound symlinks (30%) + path depth (15%) + mtime (15%)
```

Tweak weights in `~/.skill-doctor/config.toml`.

---

## Common flags

```bash
skill-doctor                       # default report
skill-doctor --full                # one row per skill
skill-doctor --full --no-truncate  # don't shorten long paths
skill-doctor --version             # version info
skill-doctor --runtime claude      # filter by runtime
skill-doctor --category seo        # filter by category
skill-doctor --json                # machine-readable
skill-doctor --stale-days 90       # change stale threshold
skill-doctor --quality-n 10        # quick uncached quality sample
skill-doctor clean                 # interactive tidy
skill-doctor clean --yes           # non-interactive (3-second cancel)
skill-doctor undo                  # roll back last apply
skill-doctor undo --pick           # pick a past backup
```

---

## Custom runtime paths

Have skills somewhere unusual? Drop them into `~/.skill-doctor/config.toml`:

```toml
[[extra_runtimes]]
path = "~/my-skills"
runtime = "unknown"   # or any known tag: claude / codex / openclaw / agents / ...
glob = "*"

[weights]
version = 0.40
incoming_links = 0.30
path_depth = 0.15
mtime_freshness = 0.15
```

---

## FAQ

**Will it auto-delete anything?**
No. Everything destructive is `mv`'d to `~/.skill-doctor/backup/` first. Run
`skill-doctor undo` and the last apply is fully reversible.

**Why no auto-fix for "drift"?**
Two divergent copies might be intentional (you tweaked one for a specific
runtime). The tool refuses to guess; it only flags.

**First run takes ~40 seconds — what's it doing?**
Scoring every SKILL.md for write quality. Subsequent runs hit a per-file mtime
cache and finish in < 1 second. Edit one SKILL.md and only that one is
re-scored.

**My skill folder isn't on the default list.**
Add it under `[[extra_runtimes]]` in `~/.skill-doctor/config.toml`.

**Where does the write-quality score come from?**
From `asm` (an open-source evaluator aligned with the Anthropic skill-creator
spec). If `asm` isn't installed, the column is simply omitted — the other six
dimensions don't depend on it.

---

## Developer quick-start

```bash
git clone https://github.com/norahe0304-art/30x-skill-doctor.git
cd 30x-skill-doctor
uv sync
uv run --no-editable pytest          # 32 tests
uv run --no-editable ruff check .
uv run --no-editable skill-doctor    # try it on your machine
```

Project layout in `AGENTS.md` (project doctrine) and
`src/skill_doctor/AGENTS.md` (module map).

License: MIT.
