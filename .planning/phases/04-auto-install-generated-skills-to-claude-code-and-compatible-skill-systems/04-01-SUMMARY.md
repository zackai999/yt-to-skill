---
phase: 04-auto-install-generated-skills-to-claude-code-and-compatible-skill-systems
plan: 01
subsystem: installer
tags: [installer, skill-management, agent-detection, provenance, yaml, questionary, shutil]

# Dependency graph
requires:
  - phase: 02-output-and-cli
    provides: render_skill_md() in stages/skill.py with YAML frontmatter — extended with source_video_id
  - phase: 03-visual-enrichment
    provides: full skill directory scaffold (assets/, scripts/, references/) — copied by installer

provides:
  - installer.py with detect_installed_agents, sanitize_skill_name, install_skill, list_installed_skills, uninstall_skill
  - source_video_id field in staging SKILL.md frontmatter
  - questionary dependency for interactive CLI prompts

affects:
  - 04-02 (CLI restructure — imports installer functions for process/list/uninstall subcommands)

# Tech tracking
tech-stack:
  added:
    - questionary==2.1.1 (interactive CLI prompts)
    - prompt-toolkit==3.0.52 (questionary dependency)
  patterns:
    - Path.home() evaluated at call time in get_global_paths() to support test monkeypatching
    - YAML frontmatter round-trip via yaml.safe_load + yaml.dump for provenance injection
    - shutil.copytree for full directory tree copy, shutil.rmtree for clean uninstall
    - Loguru debug logging for skipped/missing agent paths

key-files:
  created:
    - yt_to_skill/installer.py
    - tests/test_installer.py
  modified:
    - yt_to_skill/stages/skill.py (source_video_id added to frontmatter_dict)
    - pyproject.toml (questionary dependency)
    - tests/test_skill.py (2 new tests for source_video_id)

key-decisions:
  - "get_global_paths() and get_project_paths() are functions (not module-level constants) so Path.home() evaluates at call time, enabling test monkeypatching"
  - "source_video_id added to staging SKILL.md frontmatter; installer adds installed_at on copy — two-phase provenance"
  - "uninstall_skill only removes skills with source_video_id in frontmatter — protects manually created skills from accidental deletion"
  - "copilot uses .github/skills/ for project-local path (not .copilot/skills/) — follows GitHub Copilot conventions"

patterns-established:
  - "Call-time path evaluation pattern: functions returning dicts with Path.home() for testable agent detection"
  - "YAML frontmatter injection pattern: split on ---, parse, augment, re-serialize with yaml.dump"
  - "Source video ID as provenance marker: source_video_id field distinguishes yt-to-skill installs from manual installs"

requirements-completed: [INST-01, INST-02, INST-03, INST-04, INST-05]

# Metrics
duration: 2min
completed: 2026-04-15
---

# Phase 4 Plan 01: Installer Module Summary

**Agent detection + skill install/list/uninstall via installer.py with YAML provenance injection across 5 compatible agents (claude-code, codex, cursor, gemini, copilot)**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-15T09:59:57Z
- **Completed:** 2026-04-15T10:02:30Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- installer.py with 9 exported functions covering full skill lifecycle (detect, install, list, uninstall)
- TDD-driven with 27 tests in test_installer.py covering all edge cases
- source_video_id field added to staging SKILL.md frontmatter in skill.py
- questionary interactive prompt dependency added

## Task Commits

Each task was committed atomically with TDD RED→GREEN commits:

1. **Task 1: Create installer module with TDD (RED)** - `f86984a` (test)
2. **Task 1: Create installer module with TDD (GREEN)** - `1205546` (feat)
3. **Task 2: Extend skill.py source_video_id (RED)** - `11b584f` (test)
4. **Task 2: Extend skill.py source_video_id (GREEN)** - `7a7d1e9` (feat)

_Note: TDD tasks have separate RED (test) and GREEN (feat) commits._

## Files Created/Modified
- `yt_to_skill/installer.py` — Agent detection, install/list/uninstall, provenance injection, sanitization
- `tests/test_installer.py` — 27 unit tests for all installer functions
- `yt_to_skill/stages/skill.py` — Added source_video_id to frontmatter_dict in render_skill_md()
- `tests/test_skill.py` — Added 2 tests for source_video_id in staging frontmatter
- `pyproject.toml` — Added questionary dependency

## Decisions Made
- `get_global_paths()` and `get_project_paths()` are functions (not module-level constants): Path.home() evaluates at call time, enabling pytest monkeypatching without import side effects.
- Two-phase provenance: staging SKILL.md gets `source_video_id`; installer adds `installed_at` when copying to agent directories.
- `uninstall_skill` only removes directories where SKILL.md has `source_video_id` — protects manually created skills.
- Copilot uses `.github/skills/` for project-local path (not `.copilot/skills/`), following GitHub Copilot spec conventions.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
- 3 pre-existing failures in `tests/test_config.py` related to model name strings (`claude-sonnet-4.6` vs `claude-sonnet-4-20250514`) and env var validation — out of scope, logged as pre-existing and not touched.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- installer.py is complete and fully tested — ready for Plan 02 CLI restructure
- Plan 02 will call detect_installed_agents(), install_skill(), list_installed_skills(), uninstall_skill() from this module
- questionary available for interactive agent selection prompts

---
*Phase: 04-auto-install-generated-skills-to-claude-code-and-compatible-skill-systems*
*Completed: 2026-04-15*
