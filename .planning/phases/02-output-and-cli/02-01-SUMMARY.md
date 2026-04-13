---
phase: 02-output-and-cli
plan: "01"
subsystem: pipeline
tags: [errors, skill-generation, yaml-frontmatter, pydantic, tdd]

# Dependency graph
requires:
  - phase: 01-text-pipeline
    provides: TradingLogicExtraction model, StageResult, artifact_guard pattern

provides:
  - yt_to_skill/errors.py — SkillError base + NetworkError, ExtractionError, LLMError, FormatError
  - yt_to_skill/stages/skill.py — render_skill_md() and run_skill() for SKILL.md generation
  - tests/test_errors.py — full error hierarchy test coverage
  - tests/test_skill.py — full SKILL.md generation test coverage

affects:
  - 02-02 (CLI entry point consumes run_skill and SkillError subclasses)
  - 02-03 (batch processing consumes run_skill)

# Tech tracking
tech-stack:
  added: [pyyaml (yaml.dump for frontmatter serialization)]
  patterns:
    - TDD red-green cycle for all new modules
    - Typed error hierarchy with category prefix and actionable suggestion
    - Four-section SKILL.md body structure per Agent Skills specification
    - REQUIRES_SPECIFICATION inline callouts within relevant body sections

key-files:
  created:
    - yt_to_skill/errors.py
    - yt_to_skill/stages/skill.py
    - tests/test_errors.py
    - tests/test_skill.py
  modified: []

key-decisions:
  - "SkillError uses class-level category/suggestion attributes so subclasses are zero-boilerplate"
  - "REQUIRES_SPECIFICATION markers placed inline within Entry/Exit Criteria section for entry/exit params — not as a top-level section"
  - "render_skill_md uses yaml.dump for frontmatter to ensure valid YAML regardless of special characters in strategy names"
  - "run_skill wraps both FileNotFoundError and pydantic ValidationError as FormatError for consistent caller interface"

patterns-established:
  - "Error pattern: [CATEGORY] message — suggestion format for all pipeline errors"
  - "SKILL.md structure: YAML frontmatter + Strategy Overview / Entry/Exit Criteria / Risk Management / Market Regime Filters"

requirements-completed: [OUTP-01, OUTP-02, OUTP-03, OUTP-06]

# Metrics
duration: 2min
completed: 2026-04-14
---

# Phase 2 Plan 01: Error Hierarchy and SKILL.md Generation Stage Summary

**Typed SkillError hierarchy with four category-prefixed subclasses and a render_skill_md renderer producing valid YAML frontmatter with four-section body and inline REQUIRES_SPECIFICATION callouts**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-13T23:08:34Z
- **Completed:** 2026-04-13T23:10:28Z
- **Tasks:** 1 (TDD — 2 commits: test + feat)
- **Files modified:** 4

## Accomplishments

- Typed error hierarchy: SkillError base class + NetworkError, ExtractionError, LLMError, FormatError — each with category prefix and actionable suggestion in formatted message string
- render_skill_md() converts TradingLogicExtraction to SKILL.md with valid YAML frontmatter (name, description, metadata block) and four canonical body sections
- REQUIRES_SPECIFICATION markers appear as inline blockquote callouts within the Entry/Exit Criteria section, not as a separate top-level section
- run_skill() creates skills/{video_id}/ scaffold (assets/, scripts/, references/), respects artifact_guard for caching, supports force flag, raises FormatError on missing/malformed extraction
- 35 tests covering all behaviors: error categories, suggestions, message format, frontmatter fields, body structure, inline markers, scaffold creation, stage result, artifact guard, force flag, missing extraction

## Task Commits

Each task was committed atomically following TDD:

1. **RED: Failing tests** - `6c79236` (test)
2. **GREEN: Implementation** - `31abe64` (feat)

## Files Created/Modified

- `yt_to_skill/errors.py` — SkillError base + four typed subclasses with category/suggestion
- `yt_to_skill/stages/skill.py` — render_skill_md() renderer and run_skill() stage function
- `tests/test_errors.py` — 16 tests for error hierarchy
- `tests/test_skill.py` — 19 tests for SKILL.md generation and run_skill behavior

## Decisions Made

- SkillError uses class-level `category` and `suggestion` attributes — subclasses need no `__init__` override, just two class variables
- REQUIRES_SPECIFICATION markers placed inline within Entry/Exit Criteria body section (not a separate top-level section), satisfying the must_have truth from the plan
- `yaml.dump` used for frontmatter serialization to guarantee valid YAML regardless of special characters in strategy names or descriptions
- `run_skill` wraps both `FileNotFoundError` and pydantic `ValidationError` as `FormatError` — callers get a single typed exception for extraction file problems

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- errors.py exports are ready for CLI and batch processing stages to import
- run_skill() and render_skill_md() are ready for orchestrator integration
- No blockers

---
*Phase: 02-output-and-cli*
*Completed: 2026-04-14*
