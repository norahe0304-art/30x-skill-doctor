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
pipx install skill-doctor
```

Or with uv:

```bash
uv tool install skill-doctor
```

Plain `pip` works too: `pip install skill-doctor`.

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
| 🕰 **Stale** | Skill directory untouched for > 90 days (mtime) | Just flagged — your call |
| 📋 **Write quality** | SKILL.md hygiene + suggested fixes (cached, near-instant after first scan) | — |

### Master election (the dedup heart)

When several copies of the same skill exist, one becomes the canonical source
the others symlink to. The election score is transparent:

```
score = version (40%) + inbound symlinks (40%) + mtime (20%)
```

When no instance in a duplicate group declares a `metadata.version`, the
version weight is redistributed evenly to the remaining two signals — the
algorithm doesn't pretend a 40% lever is doing work it isn't. Weights are
tunable in `~/.skill-doctor/config.toml`. Path-depth weight (`path_depth`)
is recognised but defaults to `0.0` — it was dropped in v0.4.0 because no
community convention supports "deeper path = more canonical."

---

## Methodology

Each diagnostic dimension is documented as a four-part contract: **definition**
(what is being asserted), **detection** (the algorithm that produces the
assertion), **provenance** (the standards or specifications the algorithm
relies on), and **failure modes** (where the assertion can be wrong, and the
direction of error). Objective facts derived from formal specifications are
kept separate from heuristics calibrated by the maintainer.

### 📂 Categories

**Definition.** Every discovered skill receives a single label from a closed
set: `SEO`, `Marketing`, `Dev`, `Ads`, `Deploy`, `Data`, `Design`, `AI/Video`,
`Other`, `Uncategorized`.

**Detection.** Two-pass classifier evaluated in priority order:

1. Path-prefix match against a hand-curated lookup table (`30x-seo-*` → SEO,
   `ads-*` → Ads, etc.).
2. Description-keyword match against a per-category bag of substrings.
3. Fallback to `Other` if at least one keyword fires; `Uncategorized` if the
   skill has no description.

**Provenance.** No external specification governs categorization. The lookup
table lives in `src/skill_doctor/classify.py` and is the canonical authority.
This dimension is a *viewer convenience*, not a correctness check.

**Failure modes.** Skills with bespoke naming and no domain keywords land in
`Other`. On a 453-skill library, ~32% currently fall into `Other`; this is a
classifier-coverage limit, not a user error.

### 🟠 Duplicates

**Definition.** A *duplicate group* is a set of two or more SKILL.md files
with byte-identical normalized bodies AND identical directory basenames.

**Detection.**

```
key  = ( sha256( normalize(body) ), basename(skill_dir) )
dup  = { key | |instances(key)| ≥ 2 }
```

Body normalization strips trailing whitespace per line and collapses leading
and trailing blank lines. Identical basenames are required to prevent
unrelated skills with coincidentally-identical content from being merged.

**Master election.** For each duplicate group, exactly one instance is
elected as the canonical source by a weighted score across four signals:

| Signal             | Weight | Rationale                                                                     |
|--------------------|-------:|-------------------------------------------------------------------------------|
| `metadata.version` |   40%  | Higher declared SemVer is the strongest signal of "newest writeable copy". When no instance in the group has a version, this 40% redistributes equally to the other two axes. |
| Inbound symlinks   |   40%  | If *N* sibling instances already resolve to this path, it is in fact the source. Strongest empirical signal in practice. |
| `mtime` recency    |   20%  | Tiebreaker for instances with otherwise equal provenance.                     |

All weights are configurable via `~/.skill-doctor/config.toml`. A
`path_depth` weight is recognised by the loader but defaults to `0.0`;
earlier versions of skill-doctor used a 15% path-depth weight on the
intuition that "deeper paths are monorepo sources," but a community survey
found no published convention to support this — the inverse intuition
(root-level = canonical) is implied by Claude Code's enterprise > personal >
project precedence — so the weight was removed in v0.4.0. Set it back if
your project has a clear deeper-is-source convention.

### Designating a master manually

For projects with a clear canonical source convention (skillshare-style),
override the elected master per run:

```bash
skill-doctor clean --master openclaw   # OpenClaw wins every duplicate group
```

**Provenance.** SHA-256 is specified in NIST FIPS PUB 180-4 (August 2015).
The content-addressable equivalence model follows Git's object model (Chacon
& Straub, *Pro Git*, 2nd ed., ch. 10).

**Failure modes.** Detection is exact: SHA-256 collision probability is
bounded at ≈ 2⁻²⁵⁶ and is treated as zero. Master election, by contrast, is a
heuristic and may diverge from a user's project-specific source-of-truth
convention; manual override is supported by editing the resulting plan
before applying.

### 🟡 Drift

**Definition.** Two or more instances share a directory basename but differ
in SHA-256 hash — i.e., the same skill identity has divergent content across
runtimes.

**Detection.** Group by `basename`; emit a drift group whenever the set of
distinct hashes inside that group has cardinality ≥ 2.

**Policy.** Drift is **never** auto-resolved. Divergence is frequently
intentional — for example, when a user customizes a skill for a specific
runtime — and silent merging risks data loss. The tool surfaces drift; the
user designates the source of truth.

**Provenance.** Detection follows the same content-addressable model as
duplicate detection. The non-resolution policy is a maintainer-chosen safety
invariant, not derived from an external spec.

**Failure modes.** A single-byte difference (e.g., a trailing space) is
sufficient to register drift. False-positive risk is non-trivial; this is a
deliberate trade against the larger risk of silent data loss.

### ✗ Broken symlinks

**Definition.** A path that is itself a symlink, but whose target does not
resolve to an existing filesystem entry.

**Detection.** `path.is_symlink() and not path.exists()`. Equivalent to
POSIX `find <root> -xtype l`.

**Policy.** `clean` calls `unlink(path)`. Symlinks store no payload, so
removal is loss-free.

**Provenance.** POSIX.1-2017 (IEEE Std 1003.1™-2017) §4.1.7 (symbolic link
resolution) and §`lstat`. Confirmed by macOS `lstat(2)`.

**Failure modes.** None at the detection layer. The relation is exact under
POSIX semantics.

### 🗑 Junk files

**Definition.** Files inside a skill tree that are not user content but
rather artefacts of the host filesystem, sync layer, or editor.

**Detection.** Filename matches against a curated regex catalog:

| Pattern                                  | Source                                            |
|------------------------------------------|---------------------------------------------------|
| `* \d+\.(md\|json\|py\|...)`             | iCloud Drive filename-collision suffixing         |
| `.DS_Store`                              | macOS Finder metadata                             |
| `._*` (AppleDouble)                      | macOS extended-attribute side-files               |
| `[._]*.s[a-v][a-z]`, `[._]*.sw[a-p]`     | Vim swap, per github/gitignore Global/Vim.gitignore (canonical, 173k stars) |
| `[._]s[a-rt-v][a-z]`, `[._]ss[a-gi-z]`   | Vim swap (root-level), same source                |
| `[._]*.un~`, `*~`                        | Vim persistent undo / Emacs backup                |
| `__MACOSX/`                              | macOS-injected zip metadata directory             |

Excluded outright (defense-in-depth against
[anthropics/claude-code#32637](https://github.com/anthropics/claude-code/issues/32637),
where another tool destroyed user data via `cp -a` + `rm -rf` on 0-byte
iCloud-offloaded stubs):
- File suffix `.icloud`
- Any path under `~/Library/CloudStorage/` or `~/Library/Mobile Documents/`

Scan is recursive across the entire skill directory tree (`Path.rglob`).

**Provenance.** Each entry corresponds to a documented behavior of the
producing system. The set is curated against observed pollution on real
machines, not generated from a single spec.

**Failure modes.** Deliberately-named files matching the patterns (e.g.,
`top-10 2.md`) will be flagged. Mitigated by mandatory pre-deletion backup
under `~/.skill-doctor/backup/<timestamp>/` and one-command `undo`.

### 🕰 Stale

**Definition.** A skill whose tree has not received any modification within a
configurable time window — flagged for review, **not** declared obsolete.

**Detection.** `max(stat.st_mtime for f in tree)` compared against
`now - threshold`. Default threshold is 90 days; override with
`--stale-days N`.

**Provenance.** POSIX `stat(2)` modification time. The 90-day default is a
maintainer-chosen heuristic, not specification-derived.

**Failure modes.** This is the **weakest** dimension epistemologically.
Modification time is not invocation time; the tool has no access to runtime
telemetry. A skill that is stable, correct, and invoked daily will be flagged
stale if its files have not been edited in 90 days. The output should be
treated as a "consider reviewing" prompt, never as a deletion recommendation.

### 📋 Write quality

**Definition.** A per-skill score (B/C/D/F) and ordered list of concrete
rewrite suggestions, evaluating SKILL.md hygiene against the canonical
agent-skill authoring specification.

**Detection.** Aligned with Anthropic's official `skill-creator`
specification — the source of truth for what constitutes a well-formed
SKILL.md. Results are cached per file by `mtime`; first run on a 453-skill
library takes ≈ 40 s, subsequent runs ≈ 0.4 s with no edits.

**Provenance.** [Anthropic skill-creator skill](https://github.com/anthropics/skills/tree/main/skills/skill-creator)
defines the rule set (frontmatter required fields, body length, description
format, naming conventions, progressive-disclosure structure).

**Failure modes.** Quality scoring is opt-in: requires the underlying
evaluator to be available on `PATH`. When unavailable, the dimension is
silently elided and the remaining six dimensions function unchanged.

---

## Out of scope

Skill Doctor explicitly does **not**:

- **Measure invocation frequency.** Runtimes do not expose skill-level
  telemetry; modification time is not a substitute.
- **Score overall "skill quality"** beyond the SKILL.md hygiene captured
  above. Behavioral evaluation belongs to runtime-specific tooling.
- **Detect malicious or adversarial patterns.** For supply-chain or prompt-
  injection concerns, use a dedicated security auditor.
- **Modify your filesystem without consent.** Every state-changing operation
  is interactive (`clean`), backed up to `~/.skill-doctor/backup/<timestamp>/`,
  and reversible via `skill-doctor undo`.

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
