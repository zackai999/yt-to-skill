---
phase: 03-visual-enrichment
plan: 02
subsystem: pipeline
tags: [keyframes, gallery, skill-md, cli, orchestrator, tdd]

# Dependency graph
requires:
  - phase: 03-visual-enrichment
    provides: run_keyframes stage, PipelineConfig.max_keyframes/keyframes_enabled, sentinel guard pattern
  - phase: 02-output-and-cli
    provides: render_skill_md, run_skill, run_pipeline, CLI with argparse

provides:
  - render_gallery_section() in skill.py — timestamp-sorted ## Chart References gallery section
  - render_skill_md(extraction, keyframe_paths=) — backward-compatible gallery extension
  - run_skill(video_id, work_dir, skills_dir, keyframe_paths=) — gallery forwarding
  - Stage 7 in orchestrator: run_keyframes -> copy PNGs to assets/ -> re-render SKILL.md with gallery
  - CLI --no-keyframes flag (disables keyframe extraction via keyframes_enabled=False)
  - CLI --max-keyframes N flag (overrides config.max_keyframes)

affects:
  - End-to-end pipeline runs now produce SKILL.md with ## Chart References gallery
  - All tests patching run_pipeline now need run_keyframes mock

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Optional gallery extension: render_skill_md accepts keyframe_paths=None for backward compatibility"
    - "Pipeline continuation on keyframe error: Stage 7 uses try/except, errors logged but pipeline continues"
    - "re-render pattern: run_skill called twice — initial render (Stage 6) + gallery re-render after keyframes (Stage 7)"

key-files:
  created: []
  modified:
    - yt_to_skill/stages/skill.py
    - yt_to_skill/orchestrator.py
    - yt_to_skill/cli.py
    - tests/test_skill.py
    - tests/test_cli.py
    - tests/test_orchestrator.py

key-decisions:
  - "render_gallery_section(paths) returns '' for empty list — callers check truthiness before appending"
  - "Keyframe stage error does NOT abort pipeline — keyframes are nice-to-have visual enrichment"
  - "SKILL.md rendered twice: initial (Stage 6) + re-render with gallery (Stage 7) using force=True"
  - "Gallery entries sorted by filename (keyframe_MMSS) ensuring chronological order"
  - "Pre-existing orchestrator tests updated to mock run_keyframes — added Stage 7 changes count of results from 6 to 7"

patterns-established:
  - "Optional parameter extension: add param with default=None, check truthiness before use — preserves backward compat"
  - "Non-blocking stage: wrap in try/except, log error, append error StageResult, continue return"

requirements-completed:
  - INPT-04

# Metrics
duration: 8min
completed: 2026-04-14
---

# Phase 3 Plan 02: Pipeline Integration and Gallery Summary

**Keyframe gallery wired into SKILL.md: render_gallery_section with M:SS timestamps, Stage 7 orchestrator with PNG copying and re-render, --no-keyframes and --max-keyframes CLI flags**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-14T06:58:51Z
- **Completed:** 2026-04-14T07:09:00Z
- **Tasks:** 1 of 2 (Task 2 awaiting human calibration checkpoint)
- **Files modified:** 6

## Accomplishments
- Added `render_gallery_section(keyframe_paths)` to `skill.py` — converts `keyframe_MMSS.png` paths to sorted `## Chart References` gallery with `M:SS` timestamp links
- Extended `render_skill_md()` and `run_skill()` with optional `keyframe_paths=None` — fully backward compatible, no callers break
- Added Stage 7 to `orchestrator.py`: runs `run_keyframes`, copies PNGs from `work/<id>/keyframes/` to `skills/<id>/assets/`, re-renders SKILL.md with gallery; keyframe errors log and continue (do not abort pipeline)
- Added `--no-keyframes` and `--max-keyframes N` flags to `cli.py` argparse with proper config override via `model_copy`
- Updated 6 pre-existing orchestrator/CLI tests to mock `run_keyframes` (needed after Stage 7 addition); added 13 new tests across 3 test classes; 200 total tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Gallery section in skill.py and pipeline integration** - `9f2b38c` (feat)

_Note: TDD task — tests written first (RED), then implementation (GREEN)_

**Task 2 is a human calibration checkpoint — awaiting verification.**

## Files Created/Modified
- `yt_to_skill/stages/skill.py` - Added render_gallery_section(), extended render_skill_md(keyframe_paths=), extended run_skill(keyframe_paths=)
- `yt_to_skill/orchestrator.py` - Added shutil import, run_keyframes import, Stage 7 (keyframe extraction + PNG copy + gallery re-render)
- `yt_to_skill/cli.py` - Added --no-keyframes and --max-keyframes argparse flags with config overrides
- `tests/test_skill.py` - Added TestGallerySection (6 tests: renders_gallery, empty_returns_empty, gallery_in_full_render, no_gallery_by_default, gallery_at_bottom, gallery_sorted)
- `tests/test_cli.py` - Added TestNoKeyframesFlag (2 tests) and TestMaxKeyframesFlag (2 tests); fixed 2 orchestrator tests to mock run_keyframes
- `tests/test_orchestrator.py` - Added 3 keyframe tests (enabled calls, disabled skips, error continues); fixed 5 tests to mock run_keyframes and updated stage count to 7

## Decisions Made
- `render_gallery_section` returns `""` for empty list — callers check truthiness before appending to body, keeping the no-keyframes path clean
- Keyframe errors do NOT abort the pipeline — logged as warning, appended as error StageResult, pipeline returns normally
- SKILL.md is rendered twice when keyframes are present: initial render in Stage 6 (fast, no I/O dependency on video download), then re-rendered in Stage 7 after PNGs are in assets/
- Gallery entries sorted by filename (lexicographic on `keyframe_MMSS`) which gives chronological order
- Pre-existing tests that count pipeline stage results updated from `== 6` to `== 7`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-existing orchestrator tests failed after Stage 7 addition**
- **Found during:** Task 1 (GREEN phase — running full test suite)
- **Issue:** 5 tests in `test_orchestrator.py` and 2 in `test_cli.py` didn't mock `run_keyframes`. With `keyframes_enabled=True` (default config), Stage 7 ran for real and tried to download a fake video, producing errors and wrong result counts
- **Fix:** Added `patch("yt_to_skill.orchestrator.run_keyframes")` mock to each affected test; updated `len(results) == 6` to `== 7`; updated stage order assertion to include `"keyframes"` after `"skill"`
- **Files modified:** `tests/test_orchestrator.py`, `tests/test_cli.py`
- **Verification:** All 200 tests pass
- **Committed in:** `9f2b38c` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in test assumptions after pipeline extension)
**Impact on plan:** The fix was necessary for correct test isolation — no production code changes, no scope creep.

## Issues Encountered
None — implementation followed the plan exactly; the only issue was the pre-existing tests that needed updating due to Stage 7 addition.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Full pipeline now produces `## Chart References` gallery in SKILL.md when keyframes are extracted
- `--no-keyframes` and `--max-keyframes` CLI flags functional
- Task 2 (human calibration checkpoint) pending: user should run on 2-3 real Trader Feng Ge videos and verify threshold=8.0 produces 5-15 distinct keyframes per video
- If threshold needs tuning, `yt_to_skill/stages/keyframe.py` `AdaptiveDetector(adaptive_threshold=8.0)` value should be adjusted

---
*Phase: 03-visual-enrichment*
*Completed: 2026-04-14 (Task 1; Task 2 pending human verify)*

## Self-Check: PASSED
- skill.py: FOUND
- orchestrator.py: FOUND
- cli.py: FOUND
- 03-02-SUMMARY.md: FOUND
- Commit 9f2b38c: FOUND
