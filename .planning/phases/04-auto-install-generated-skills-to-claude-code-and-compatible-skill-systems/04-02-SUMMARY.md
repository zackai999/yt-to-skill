---
phase: 04-auto-install-generated-skills-to-claude-code-and-compatible-skill-systems
plan: 02
subsystem: cli
tags: [cli, argparse, subcommands, questionary, installer, interactive, tdd]

# Dependency graph
requires:
  - phase: 04-auto-install-generated-skills-to-claude-code-and-compatible-skill-systems
    plan: 01
    provides: installer.py with detect_installed_agents, install_skill, list_installed_skills, uninstall_skill, sanitize_skill_name

provides:
  - Subcommand CLI (process/list/uninstall) in yt_to_skill/cli.py
  - Backward compat shim for bare URL usage
  - _run_install_flow() interactive install via questionary
  - --install flag for non-interactive batch installs
  - Conflict resolution (overwrite or custom name)
  - list subcommand showing all yt-to-skill installed skills
  - uninstall subcommand removing skills from all agents

affects:
  - End users: all yt-to-skill invocations go through the new subcommand CLI

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Backward compat shim: sys.argv.insert(1, "process") when first arg is URL-like
    - TDD (RED/GREEN) for CLI restructure — existing tests updated, new tests added
    - questionary interactive prompts for agent selection + scope + conflict resolution
    - _run_install_flow() centralizes all install logic, called once after batch loop

key-files:
  created: []
  modified:
    - yt_to_skill/cli.py
    - tests/test_cli.py

key-decisions:
  - "Backward compat shim inserts 'process' into sys.argv when first arg is URL-like (startswith http/www.) — existing tests work without modification"
  - "Batch runs collect all successful skill entries, then call _run_install_flow once — single prompt for all videos"
  - "Conflict resolution: overwrite=True or custom name (sanitized) or skip (None/empty cancel)"
  - "--install flag parses comma-separated agent IDs, validates against known agents, installs without prompt"
  - "Non-TTY detection: sys.stdin.isatty() False skips interactive prompt with informational message"

patterns-established:
  - "Single install prompt pattern: collect all skill entries during batch loop, run install flow once at end"
  - "Conflict resolution pattern: confirm->overwrite | decline->custom_name->sanitize->install or skip"

requirements-completed: [CLI-01, CLI-02, CLI-03]

# Metrics
duration: 20min
completed: 2026-04-15
---

# Phase 4 Plan 02: CLI Subcommand Refactor Summary

**Argparse subcommand CLI (process/list/uninstall) with backward-compat shim, questionary install flow, --install flag, and conflict resolution prompting custom name or overwrite**

## Performance

- **Duration:** 20 min
- **Started:** 2026-04-15T10:37:41Z
- **Completed:** 2026-04-15T10:57:00Z
- **Tasks:** 1 (Task 2 is checkpoint:human-verify, paused for verification)
- **Files modified:** 2

## Accomplishments
- cli.py refactored to process/list/uninstall subcommand pattern with argparse.add_subparsers
- Backward compat shim: bare URL (http/www.) auto-inserts "process" before routing — all existing tests pass unchanged
- _run_install_flow() with full interactive/non-interactive/--install-flag paths
- Conflict resolution: questionary.confirm -> overwrite OR questionary.text -> custom name -> sanitize -> install; cancel = skip
- 34 CLI tests pass (15 new tests + 19 existing tests all green)

## Task Commits

TDD RED->GREEN commits:

1. **Task 1 (RED): Add failing tests for CLI subcommand refactor** - `5bc4aff` (test)
2. **Task 1 (GREEN): Refactor CLI to subcommand pattern with install flow** - `0ed1d5c` (feat)

_Task 2 is a checkpoint:human-verify — pending human approval of end-to-end flow._

## Files Created/Modified
- `yt_to_skill/cli.py` — Subcommand CLI with process/list/uninstall, backward compat shim, _run_install_flow, _cmd_process, _cmd_list, _cmd_uninstall
- `tests/test_cli.py` — Added 15 new tests for subcommand routing, install flow, conflict resolution, backward compat

## Decisions Made
- Backward compat shim inserts "process" into sys.argv at position 1 when first arg starts with "http" or "www." — zero changes required in existing tests.
- Single prompt for batch runs: all skill entries accumulated during the batch loop, then _run_install_flow called once at the end (not per-video).
- On --install flag with unknown agent: print warning and skip that agent; continue with valid agents.
- Non-TTY mode: print "(skipping install prompt in non-interactive mode)" and return — no interactive prompts attempted.
- Conflict resolution: questionary.confirm first; if declined, questionary.text for custom name; if custom is None or empty string, skip and print "Skipping {name} for {agent}."

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
- 3 pre-existing failures in tests/test_config.py (model name strings and env var validation) — out of scope, not touched.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

Task 2 (checkpoint:human-verify) requires human to run end-to-end verification:
1. Process a test video URL
2. Confirm skill summary prints
3. Select agent interactively, verify skill installed
4. Run `yt-to-skill list` to see installed skill
5. Test conflict: decline overwrite, enter custom name
6. Run `yt-to-skill uninstall <name>` to remove skill
7. Verify backward compat: bare URL still works
8. Verify `yt-to-skill` (no args) shows help

---
*Phase: 04-auto-install-generated-skills-to-claude-code-and-compatible-skill-systems*
*Completed: 2026-04-15*
