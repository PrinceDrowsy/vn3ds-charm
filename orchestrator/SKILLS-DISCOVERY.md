# SKILLS-DISCOVERY.md — Pre-Project Skills Discovery Protocol (VN3DS-CHARM)

> Before any coding begins, the Orchestrator runs a skills discovery phase.
> This finds and installs relevant community and official skills that can
> improve agent performance for VN3DS-CHARM's specific tech stack: Python
> (converter), MoonScript/Lua (engine), LÖVE Potion, and 3DS homebrew.
>
> **This is a HARD GATE.** The Orchestrator cannot plan Cycle 1 until this
> protocol has been executed and the "Installed Skills" section below has been
> updated with results — even if the result is "no relevant skills found."

## Why This Matters

Skills provide procedural knowledge — battle-tested patterns, scripts, and
references — that make agents dramatically more effective. A MoonScript skill
might include LÖVE Potion 3DS packaging gotchas. A Python skill might include
subprocess-safety or archive-extraction patterns directly relevant to this
project's actual risk surface (see `agents/AGENT-SECURITY.md`).

## Planning Skills (already used — Phase P is complete)

Phase P for this project is already done (`base/PROJECT.md`, `base/ARCHITECTURE.md`,
ADR-001 through ADR-003, `GAME-PLAN.md` all exist). These planning skills were
used to get there and remain relevant for any future re-planning:

| Skill | Purpose | Source |
|---|---|---|
| `grill-with-docs` | Relentless planning interview that emits durable planning docs, ADRs, and a domain glossary | Hermes / Matt Pocock skills |
| `grill-me` | Lighter planning interview when durable docs aren't needed | Hermes / Matt Pocock skills |
| `to-issues` / `prd-to-issues` | Slice a plan/PRD into vertical GitHub issues (used at and after the cutover) | Hermes / Matt Pocock skills |

## Skills Registries (Search Priority Order)

### 1. Anthropic Official Skills
- **URL**: https://github.com/anthropics/skills
- **Install**: `/plugin marketplace add anthropics/skills`

### 2. Skills.sh Directory
- **URL**: https://skills.sh
- **Install**: `npx skills add <owner>/<skill-name>`

### 3. SkillHub / SkillsMP
- **URL**: https://skillsmp.com / https://skillhub.club

### 4. Claude Code Plugin Marketplace
- **Install**: `/plugin marketplace add <owner>/<repo>`

### 5. GitHub Direct Search
- **Search**: `SKILL.md in:path language:markdown` + stack keywords
- Per the agent-factory template's own discovery history, GitHub direct search
  has proven the most reliable method — most marketplace sites are JS-rendered,
  behind auth, or 404 for individual skill pages. Prioritize this.

## Discovery Protocol

### Step 1: Identify Skill Needs from Stack Files

```
From STACK-CONVERTER.md → "Python", "subprocess", "archive extraction", "zip-slip", "pytest"
From STACK-ENGINE.md    → "MoonScript", "Lua", "LÖVE2D"/"LÖVE Potion", "3DS homebrew", "devkitPro", "busted"
From STACK-TESTING.md   → "pytest", "busted", "Lua testing"
```

### Step 2: Search Each Registry

```
1. GitHub search: "SKILL.md moonscript" / "SKILL.md love2d" / "SKILL.md python subprocess security"
2. npx skills search "moonscript" / "lua" / "python archive extraction" (if CLI available)
3. Browse skills.sh for matching skills
4. Check anthropics/skills for generic Python/security capabilities
```

### Step 3: Evaluate Found Skills

| Criterion                | Minimum Acceptable          |
|--------------------------|------------------------------|
| Last updated             | Within 6 months (be lenient for niche MoonScript/3DS-homebrew skills — this ecosystem moves slowly; a 2-year-old MoonScript skill may still be the best available) |
| Has SKILL.md             | Required                    |
| Description specificity  | Must describe when to use   |
| Compatibility            | Claude Code compatible      |
| Security scan            | No hardcoded secrets/paths  |
| Size                     | SKILL.md under 200 lines    |

**Note:** MoonScript/LÖVE Potion/3DS-homebrew skills are a niche ecosystem —
expect fewer, older results than a mainstream stack like .NET or React would
return. Absence of a skill in this category is expected and should be
documented as such, not treated as a discovery failure.

### Step 4: Install Approved Skills

The Orchestrator installs skills autonomously via bash:

```bash
mkdir -p .claude/skills
git clone --depth 1 https://github.com/{owner}/{repo} /tmp/{repo}
find /tmp/{repo} -name "SKILL.md" -exec sh -c \
  'cp -r "$(dirname "$1")" .claude/skills/"$(basename "$(dirname "$1")")"/' _ {} \;
rm -rf /tmp/{repo}
ls .claude/skills/
```

**Fallback**: If git clone fails, ask the human to run
`/plugin marketplace add {owner}/{repo}` and flag `[HUMAN REQUIRED]`.

**Scope guidance:**
- **Project scope** (`.claude/skills/`): default, contained to this project.
- **User scope** (`~/.claude/skills/`): only if useful across all of Scott/PrinceDrowsy's projects.

### Step 5: Document Installed Skills

Append findings under "Installed Skills" below, replacing the sentinel.

## Recommended Skills by Stack

### For Python (Converter)
Search for:
- `python` general-purpose coding skills
- `subprocess` / `command-injection-prevention` security skills
- `archive-extraction` / `zip-slip` / `path-traversal` security skills
- `pytest` / `testing` skills

### For MoonScript / Lua / LÖVE Potion (Engine)
Search for:
- `moonscript` skills (expect very few — niche language)
- `lua` / `love2d` skills (LÖVE2D skills often transfer conceptually even
  though LÖVE Potion is 3DS-specific)
- `3ds-homebrew` / `devkitpro` / `libctru` skills
- `busted` / `lua-testing` skills

### For Security Scanning (this project's actual risk surface)
Search for:
- `archive-extraction-security` / `zip-slip` skills
- `subprocess-security` / `command-injection` skills
- `dependency-audit` / `pip-audit` / `luarocks` skills

### For Documentation
Search for:
- `markdown` / `technical-writing` skills
- `adr` / `architecture-decision-record` skills

## Skills Refresh Policy

- **Per phase**: re-run discovery if the phase introduces a new sub-stack (e.g.
  Phase 5.5 Triage UI framework, Phase 6 archive formats like `.xp3`/`.nsa`)
- **On failure pattern**: if agents struggle with MoonScript or LÖVE Potion
  specifics, search again — this ecosystem is under-documented compared to
  mainstream stacks, so a second, more targeted search sometimes surfaces
  something the first pass missed

---

## Installed Skills

**Discovery run:** 2026-07-04
**Status:** COMPLETE — Phase 0 skills discovery gate is unblocked.
**Scope:** project-local installs only. No user-global skills were added.

### Installed

| Skill | Source | Installed paths | Why approved | Notes / limits |
|---|---|---|---|---|
| `love2d-core` | `gamedev-skills/awesome-gamedev-agent-skills`, Apache-2.0 | `.claude/skills/love2d-core`, `.hermes/skills/love2d-core`, `.agents/skills/love2d-core`, `.continue/skills/love2d-core` | Best available LÖVE-family skill from skills.sh. Meets size criterion (146 lines) and had CLI-reported security status `Safe`, Socket `0 alerts`, Snyk `Low Risk`. | Targets desktop LÖVE 11.5/Lua, not LÖVE Potion/3DS directly. Use for transferable `love.load/update/draw`, `dt`, input, drawing state, and screen-state patterns only. Project docs remain authoritative for MoonScript source, LÖVE Potion constraints, `.t3x`, Old 3DS memory budget, and no-shader limitations. |
| `pytest-coverage` | `github/awesome-copilot`, GitHub skill collection | `.claude/skills/pytest-coverage`, `.hermes/skills/pytest-coverage`, `.agents/skills/pytest-coverage`, `.continue/skills/pytest-coverage` | Compact pytest coverage workflow. Meets size criterion (28 lines) and had CLI-reported security status `Safe`, Socket `0 alerts`, Snyk `Low Risk`. | Coverage-focused, not a full pytest architecture guide. Use when Phase 1+ converter tests exist and coverage gaps need to be found. |

`skills-lock.json` records the installed skill sources and hashes.

### Searched but not installed

| Area | Result | Decision |
|---|---|---|
| MoonScript | No skills found via `npx skills find moonscript`; GitHub code search was attempted but hit API rate limiting after initial empty responses. | No install. Treat MoonScript knowledge as project-local stack guidance plus upstream VNDS-LOVE source study. |
| LÖVE Potion / 3DS homebrew / devkitPro / libctru | No relevant skills found via skills.sh searches (`love2d` found generic desktop LÖVE only; `devkitpro` found none). Anthropic official skills repo cloned successfully but had no project-specific LÖVE Potion/3DS skill. | No install. `STACK-ENGINE.md`, `base/RULES.md`, upstream `ajusa/VNDS-LOVE`, LovePotion/lovebrew/devkitPro docs, and empirical Azahar/O3DS checks remain authoritative. |
| Lua `busted` testing | `npx skills find busted` returned no skills. Generic `lua` search results were unrelated evaluation/finance skills. | No install. Use upstream VNDS-LOVE's existing `busted` harness and add project notes if the Tester agent discovers repeatable patterns. |
| Python subprocess security | `npx skills find subprocess` surfaced `davidlee/doctrine@dispatch-subprocess`, but `skills use` failed on Windows checkout because of path-too-long filenames. | No install. Security agent must rely on project rules: no shell-string subprocesses for untrusted data, pass argv arrays, validate tool paths, timeouts, and capture errors. Create a project skill later if repeated subprocess pitfalls appear. |
| Archive extraction / zip-slip | `npx skills find "archive extraction"` surfaced archive/zip skills, but inspected candidates were generic archive handling or plan archival rather than secure extraction for untrusted VN/DLC archives. | No install. Phase 6+ needs explicit secure-extraction design before archive tooling lands: destination sandbox, path normalization, symlink/device rejection, size/count limits, and zip-slip/path-traversal tests. |
| Pytest general patterns | `manutej/luxor-claude-marketplace@pytest-patterns` was inspected but not kept because its `SKILL.md` is 1802 lines, exceeding the discovery criterion. | Rejected/replaced by compact `pytest-coverage`. If Phase 1 needs richer pytest guidance, create a smaller project-specific skill from observed patterns. |
| Official Anthropic skills | `https://github.com/anthropics/skills` cloned successfully. Available official skills are mostly document, webapp, API, and artifact-oriented; no Python converter, MoonScript, LÖVE, 3DS, or busted skill was found. | No install. |
| GitHub direct code search | Attempted stack-keyword `SKILL.md` searches. The GitHub Search API returned initial empty results, then HTTP 403 rate-limit responses for follow-up searches. | Partial coverage only. Skills.sh CLI and direct repository inspection were sufficient to unblock Phase 0; rerun GitHub search later if a niche failure pattern emerges. |

### Carry-forward guidance for agents

- Engine agents may load `love2d-core` for generic LÖVE loop/render/input patterns, but must translate implementation to **MoonScript source** and respect `STACK-ENGINE.md`/ADR-003.
- Converter/tester agents may load `pytest-coverage` only once converter code and tests exist; Phase 0.1 bootstrap does not require it.
- Do not assume any installed skill knows LÖVE Potion, Old 3DS memory constraints, `.t3x`, `lovebrew`, or MoonScript. Those remain project-specific knowledge in `base/`, `stack/`, `docs/adr/`, and upstream code.
- If a phase introduces a new stack, rerun this discovery protocol before implementation work for that phase.
