# Loop Configuration — VN3DS-CHARM

> Controls how the autonomous loop operates. The Orchestrator reads this
> at startup and respects these parameters throughout the session.

## Cycle Limits

- **Max Cycles Per Session**: 20
- **Max Consecutive Failures**: 3 (escalate to human after 3 reverts in a row)
- **Max Cycle Duration**: 30 minutes (per agent, per cycle)

## Agent Spawn Configuration

Four agents. No UI-Reviewer — VN3DS-CHARM has no traditional web frontend.
Visual/gameplay validation happens via Azahar (Old 3DS profile) at phase
boundaries, flagged by the Tester when a cycle plausibly warrants it, not
run automatically by an agent every cycle.

### Cycle Execution Order
```
1. PLAN       — Orchestrator plans the cycle, reads GAME-PLAN.md + relevant component
2. BUILD      — Developer implements the assigned task (Converter OR Engine, one per cycle)
3. VERIFY     — These agents run IN PARALLEL after Developer commits:
                 ├── Tester (pytest for Converter, busted for Engine; flags memory-budget review if warranted)
                 └── Security (archive/subprocess/dependency scan)
4. EVALUATE   — Orchestrator collects metrics from ALL agents
5. DECIDE     — KEEP or REVERT (see thresholds below)
6. DOCUMENT   — Documentation agent updates docs (ONLY if cycle was KEPT)
7. LOG        — Orchestrator updates METRICS-HISTORY.md + SKILLS-LOG.md
```

### Agent Activation Rules
| Agent         | When to Spawn | Condition |
|---------------|--------------|-----------|
| Developer     | Every cycle  | Always |
| Tester        | Every cycle  | Always |
| Security      | Every cycle  | Always — even converter-only changes can introduce archive-extraction or subprocess risk |
| Documentation | After every KEPT cycle | Skipped on REVERT |

### Spawn Prompts

```
Developer: "You are the Developer agent. Read agents/AGENT-DEVELOPER.md for
your complete instructions. Your task for this cycle is: [TASK]. Component:
[Converter | Engine | Triage-UI]. Read the matching stack file in /stack to
confirm technology and constraints — if Engine work, re-read the
authoring-vs-runtime table in STACK-ENGINE.md before writing any code. Commit
your work when complete and report back."
```

```
Tester: "You are the Tester agent. Read agents/AGENT-TESTER.md for your
complete instructions. The Developer just completed: [TASK] on [Converter |
Engine]. Write/run the appropriate test suite (pytest or busted), run the
relevant regression corpus check, and report results. Flag explicitly if this
change plausibly affects the Old 3DS memory budget."
```

```
Security: "You are the Security agent. Read agents/AGENT-SECURITY.md for your
complete instructions. Scan the Developer's changes for this cycle. Focus on
archive extraction path safety, subprocess invocation safety, and dependency
vulnerabilities — VN3DS-CHARM has no web/auth surface, so do not report on
categories that don't apply here. Write your report to /tests/security-reports/."
```

```
Documentation (post-KEEP): "You are the Documentation agent. Read
agents/AGENT-DOCUMENTATION.md for your complete instructions. Cycle [N] was
KEPT. Update CHANGELOG.md, update docs/vnds-command-reference.md or
docs/converter-support-status.md if the command set or conversion map changed,
and update README.md if phase/game completion status changed."
```

## Metric Thresholds

| Metric                        | Minimum to KEEP | Direction | Source Agent |
|--------------------------------|-----------------|-----------|-------------|
| Build/compile success          | true            | must pass | Developer/Tester |
| Test pass rate                 | ≥ 90%           | must not decrease | Tester |
| Access violations              | 0               | must be zero | Orchestrator |
| Language-boundary violations   | 0               | must be zero (e.g. hand-edited generated Lua, Python in src/engine) | Orchestrator |
| Regression corpus              | 100% pass       | existing VNDS scripts / "The Question" must keep working | Tester |
| Security critical              | 0               | must be zero | Security |
| Security high                  | ≤ 2             | must not exceed | Security |
| Old 3DS memory (when flagged)  | ≤ 70MB hard ceiling | must not regress past ceiling | Human/Azahar check |

**REVERT decision tree (in priority order):**
```
IF build/compile fails                   → REVERT
IF access violations > 0                 → REVERT
IF language-boundary violation > 0       → REVERT
IF security critical > 0                 → REVERT
IF test pass rate decreased              → REVERT
IF regression corpus broke               → REVERT
IF Azahar check shows budget exceeded    → REVERT
IF security high > 2                     → REVERT
IF all metrics hold or improve           → KEEP
```

## Metric Improvement Targets

| Metric                  | Target    |
|-------------------------|-----------|
| Current phase exit criteria (GAME-PLAN.md) | 100%      |
| Test pass rate          | ≥ 95%     |
| Security critical       | 0         |
| Security high           | 0         |
| Vulnerable dependencies | 0         |
| Old 3DS memory ceiling  | Never exceeded |

## Loop Behavior

- **On KEEP**: Documentation agent runs → merge feature branch to main → select next work item
- **On REVERT**: Reset feature branch, send ALL failure details (tests + security) to developer, retry same work item
- **On 3rd consecutive REVERT**: Pause loop, create `[HUMAN REQUIRED]` task
- **On phase exit criteria met**: Run final metric collection, final security scan,
  check whether this is the Phase 2 close (cutover evaluation point per
  `orchestrator/CUTOVER.md`), trigger phase retrospective
