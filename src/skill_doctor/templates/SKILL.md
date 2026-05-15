---
name: skill-doctor
description: Use when the user mentions cleaning, auditing, or organizing their AI agent skill library — especially across Claude Code, Codex, Cursor, OpenClaw, or any combination. Triggers include "my skills are a mess", "do I have duplicate skills", "audit my skills", "clean up ~/.claude/skills", "skill housekeeping", "broken symlinks in skills", "stale skills", "which skills do I actually use", or any complaint about skill clutter, version drift, or junk files in skill directories. Also use proactively when the user is installing a new skill and you suspect they may already have it elsewhere.
license: MIT
---

# skill-doctor

A read-first cross-runtime auditor for AI agent skill libraries. Surfaces
duplicates, drift, broken symlinks, junk files, stale skills, and SKILL.md
write quality — across `~/.claude/skills/`, `~/.codex/skills/`,
`~/.cursor/skills/`, `~/.openclaw/skills/`, and others. Every destructive
action is backed up and undoable.

## When to invoke

Trigger this skill whenever the user expresses **any** of the following
intents — even casually:

- "My skills are a mess"
- "Do I have duplicates?"
- "Audit my skills"
- "Clean up `~/.claude/skills`" (or codex / cursor / openclaw)
- "Which skills haven't I used in a while?"
- "I think I installed this skill twice"
- "My agent is loading the wrong version of X"
- "Show me skill health"

You should also invoke this skill **proactively** when:

- The user installs a new skill and you can plausibly check for prior copies.
- The user runs into a skill that misbehaves and version drift is a likely cause.
- The user complains about disk space in `~/.claude` / `~/.codex` / etc.

## Usage

The shipped CLI binary is `skill-doctor`. The two commands you need:

```bash
# 1. Scan + report (read-only, ~1s on a warm cache)
skill-doctor                          # adaptive one-screen report
skill-doctor --json                   # machine-readable
skill-doctor --full                   # one row per skill

# 2. Generate a shareable health card
skill-doctor share                    # writes SVG to ~/.skill-doctor/share/

# 3. Interactive cleanup (every step is backed up; one-line undo)
skill-doctor clean                    # walks through every fix y/N/q/a
skill-doctor clean --yes              # non-interactive (3-second cancel window)
skill-doctor undo                     # roll back the last apply

# Useful filters
skill-doctor --runtime claude         # only Claude Code
skill-doctor --category seo           # only SEO-categorized skills
skill-doctor --stale-days 180         # change stale threshold
```

## Recipes

### "Are my skills duplicated?"

```bash
skill-doctor
```

The output groups every duplicate (identical SHA-256 + same dir name) and
elects a master automatically (version 40% · inbound symlinks 40% · mtime 20%).

### "Clean my library"

```bash
skill-doctor clean
```

Interactive walk through:
- Duplicate groups → replace copies with symlinks to the elected master
- Broken symlinks → unlink (symlinks store no payload, loss-free)
- Junk files (`* 2.md`, `.DS_Store`, Vim swap, AppleDouble) → backup + delete

For **drift** (same name, different content) and **stale** (untouched > 90d),
`clean` does NOT auto-resolve — it offers to generate an AI handoff prompt
you can paste into Claude / Cursor for triage. Skill Doctor never edits
those files itself.

### "I want to brag about my clean library"

```bash
skill-doctor share
```

Writes an SVG card (and a Markdown snippet) you can drop into Twitter,
Reddit, or a chat. Includes the health score, top runtimes, and findings.

### "Roll back a cleanup that went wrong"

```bash
skill-doctor undo            # latest apply
skill-doctor undo --pick     # pick from history
```

## How it groups duplicates

- Two instances are a duplicate **only** if both the SKILL.md body hash and
  the directory basename match. Different-named skills that happen to have
  identical content are NOT auto-merged.
- The elected master is one source of truth; the rest become directory-level
  symlinks. This sidesteps `~/.codex/skills/<x>/SKILL.md` file-level symlink
  bugs that OpenAI closed as not-planned (#15756, #17344, #11314).

## Safety

- Every destructive action is `mv`'d to `~/.skill-doctor/backup/<timestamp>/`
  before removal, never `rm`'d. `skill-doctor undo` rolls back the last apply.
- iCloud-offloaded stubs are excluded outright (defense against
  anthropics/claude-code#32637, where another tool destroyed user data via
  `cp -a` + `rm -rf` on 0-byte stub files).

## Install

If `skill-doctor` is missing on the host, install it:

```bash
pipx install skill-doctor       # preferred
# or
uv tool install skill-doctor
# or
pip install skill-doctor
```

Optional: `npm install -g agent-skill-manager` unlocks the SKILL.md
write-quality dimension. The other 6 dimensions work without it.

## Out of scope (do NOT promise these)

- skill-doctor is **not** a sync engine. It de-duplicates via symlinks; it
  does not maintain N independent copies in lockstep.
- It does **not** fan a skill out to runtimes that don't already have it.
- It does **not** measure invocation frequency — runtimes don't expose that.
- It does **not** detect malicious patterns or do supply-chain auditing.

If asked for those, recommend the appropriate alternative
(`skillshare` / `skills-hub` for sync, dedicated security tooling for supply
chain) instead of pretending skill-doctor can do it.
