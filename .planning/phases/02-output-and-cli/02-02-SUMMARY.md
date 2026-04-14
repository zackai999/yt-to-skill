---
phase: 02-output-and-cli
plan: "02"
subsystem: cli
tags: [cli, resolver, batch-processing, argparse, tdd, yt-dlp, entry-point]

# Dependency graph
requires:
  - phase: 02-output-and-cli/02-01
    provides: SkillError hierarchy, run_skill(), render_skill_md()
  - phase: 01-text-pipeline
    provides: extract_video_id, run_pipeline, StageResult, PipelineConfig

provides:
  - yt_to_skill/resolver.py — resolve_urls() for single/playlist/channel URL expansion
  - yt_to_skill/cli.py — CLI entry point with argparse, batch loop, summary table
  - yt_to_skill/config.py (extended) — skills_dir field added to PipelineConfig
  - yt_to_skill/orchestrator.py (extended) — skill stage as 6th stage, force parameter
  - pyproject.toml (extended) — [project.scripts] entry point registration
  - tests/test_resolver.py — 8 URL resolver tests
  - tests/test_cli.py — 14 CLI and config tests

affects:
  - End users: yt-to-skill command now fully usable from CLI

# Tech tracking
tech-stack:
  added: []
  patterns:
    - TDD red-green cycle for all new modules
    - resolver.py fast-path: try extract_video_id() before yt-dlp call
    - Batch loop error isolation: SkillError caught per-video, loop continues
    - Non-strategy detection: last StageResult stage_name == 'filter' with no error
    - summary table: f-string aligned table with ✓/✗/⚠ markers

key-files:
  created:
    - yt_to_skill/resolver.py
    - yt_to_skill/cli.py
    - tests/test_resolver.py
    - tests/test_cli.py
  modified:
    - yt_to_skill/config.py
    - yt_to_skill/orchestrator.py
    - pyproject.toml
    - tests/test_orchestrator.py

key-decisions:
  - "resolve_urls() tries extract_video_id() first for zero-network single-video detection before falling back to yt-dlp"
  - "force parameter added to run_pipeline() signature (not to PipelineConfig) per plan research recommendation"
  - "Non-strategy detection in CLI: pipeline returns early at filter stage (last StageResult.stage_name == 'filter'), not a failure"
  - "Tests use monkeypatch.setenv('OPENROUTER_API_KEY') to satisfy PipelineConfig validation without polluting environment"
  - "test_orchestrator.py updated to mock run_skill — all 6 tests that ran through full pipeline now mock the new 6th stage"

patterns-established:
  - "Batch loop pattern: try/except SkillError per video, record (video_id, status, detail) tuples, print summary in finally"
  - "Resolver pattern: single-video fast path via extract_video_id(), playlist/channel via yt-dlp extract_flat"

requirements-completed: [OUTP-04, OUTP-05, OUTP-06]

# Metrics
duration: 8min
completed: 2026-04-14
---

# Phase 2 Plan 02: CLI Entry Point and Batch Processing Summary

**resolve_urls() URL resolver with yt-dlp playlist/channel expansion plus argparse CLI with batch loop, per-video error isolation, progress lines, summary table, and yt-to-skill entry point registration**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-14T06:13:57Z
- **Completed:** 2026-04-14
- **Tasks:** 2 (TDD — 4 commits: 2 test + 2 feat)
- **Files modified:** 8

## Accomplishments

- resolve_urls() resolves single videos via extract_video_id() fast path, expands playlists/channels via yt-dlp extract_flat mode — entries without 'id' filtered with loguru warning
- NetworkError raised on yt-dlp DownloadError or generic exception wrapping for clean caller interface
- PipelineConfig extended with skills_dir field (Path("skills") default), configurable via SKILLS_DIR env var
- run_pipeline extended with force=True keyword parameter, passed through to run_skill() as 6th pipeline stage
- cli.py: argparse entry point with url, --output-dir, --force, --verbose flags
- Batch loop processes all videos sequentially, catches SkillError and generic exceptions per-video, continues to next video
- Per-stage progress lines (✓ completed, ✗ error, - cached) printed as stages complete
- Summary table printed for batch runs (>1 video) using f-string column alignment with ✓/✗/⚠ markers
- Non-strategy videos (pipeline returned at filter stage) show as "skipped — not a strategy video", do not affect exit code
- Exit code 0 on all success/skipped, exit code 1 on any video failure
- yt-to-skill = "yt_to_skill.cli:main" registered in pyproject.toml [project.scripts]
- 22 new tests covering all behaviors; existing test_orchestrator.py updated to mock new 6th stage

## Task Commits

Each task was committed atomically following TDD:

1. **RED: URL resolver tests** - `748c0ea` (test)
2. **GREEN: URL resolver implementation** - `bad65d6` (feat)
3. **RED: CLI/config/orchestrator tests** - `64e1d5e` (test)
4. **GREEN: CLI/config/orchestrator implementation** - `dacec81` (feat)

## Files Created/Modified

- `yt_to_skill/resolver.py` — resolve_urls() with single-video fast path and yt-dlp expansion
- `yt_to_skill/cli.py` — argparse CLI with batch loop, progress display, summary table
- `yt_to_skill/config.py` — skills_dir: Path = Path("skills") field added
- `yt_to_skill/orchestrator.py` — run_skill imported and called as 6th stage; force parameter added to run_pipeline
- `pyproject.toml` — [project.scripts] yt-to-skill entry point added
- `tests/test_resolver.py` — 8 tests covering all resolver behaviors
- `tests/test_cli.py` — 14 tests covering config, orchestrator wiring, CLI flags, batch, summary
- `tests/test_orchestrator.py` — 6 existing tests updated to mock run_skill (new 6th stage)

## Decisions Made

- resolve_urls() calls extract_video_id() first to avoid a yt-dlp network call for single-video URLs — fast path is zero-network
- force stays CLI-only (not in PipelineConfig) — keeps config serializable and environment-clean as per research guidance
- Non-strategy pipeline stop detected by checking `results[-1].stage_name == "filter"` — no filter_result.json re-read needed in CLI
- test_cli.py uses `monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")` for config validation — avoids patching the entire PipelineConfig class

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_orchestrator.py to mock new 6th stage**
- **Found during:** Task 2 GREEN — full test suite run
- **Issue:** test_orchestrator.py tests didn't mock run_skill, causing 1 test failure after orchestrator gained the skill stage. test_run_pipeline_returns_list_of_stage_results asserted len(results) == 5 (now 6). test_run_pipeline_calls_stages_in_order asserted 5-element call_order list.
- **Fix:** Added `patch("yt_to_skill.orchestrator.run_skill")` to all 6 orchestrator tests that run through the full pipeline. Updated assertions from 5 to 6 where stage counts are checked.
- **Files modified:** `tests/test_orchestrator.py`
- **Commit:** `dacec81` (included in GREEN commit)

**2. [Rule 2 - Missing] Added OPENROUTER_API_KEY env setup to CLI tests**
- **Found during:** Task 2 GREEN — first test run
- **Issue:** CLI tests called `PipelineConfig()` without mocking it; validation failed with missing API key error, causing all CLI tests to exit(1).
- **Fix:** Added `monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")` to each CLI test that calls `main()`.
- **Files modified:** `tests/test_cli.py`
- **Commit:** `dacec81` (included in GREEN commit)

## Issues Encountered

None beyond the auto-fixed deviations above.

## User Setup Required

None — no external service configuration required for this plan.

## Next Phase Readiness

- yt-to-skill CLI is fully functional end-to-end from URL input to SKILL.md output
- All 175 tests pass including new and existing tests
- No blockers for Phase 3 (video/image pipeline)

## Self-Check: PASSED

All files verified present, all commits verified in git log.

---
*Phase: 02-output-and-cli*
*Completed: 2026-04-14*
