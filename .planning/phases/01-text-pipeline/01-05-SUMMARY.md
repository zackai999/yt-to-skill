---
phase: 01-text-pipeline
plan: "05"
subsystem: pipeline
tags: [extraction, orchestrator, instructor, pydantic, tdd]

# Dependency graph
requires:
  - phase: 01-text-pipeline
    plan: "04"
    provides: "run_filter (filter_result.json), run_translate (translated.txt)"
  - phase: 01-text-pipeline
    plan: "02"
    provides: "extract_trading_logic, make_openai_client, make_instructor_client via yt_to_skill/llm/client.py"
  - phase: 01-text-pipeline
    plan: "01"
    provides: "TradingLogicExtraction, StrategyObject, EntryCondition models with unspecified_params auto-population"
provides:
  - "run_extract: instructor-patched LLM extraction to TradingLogicExtraction -> extracted_logic.json"
  - "run_pipeline: orchestrator wiring ingest -> transcript -> filter -> translate -> extract"
  - "extract_video_id: YouTube URL parser for watch?v=, youtu.be, /shorts/ formats"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Orchestrator creates LLM clients once and passes to relevant stages (openai_client -> filter/translate, instructor_client -> extract)"
    - "Non-strategy early termination: orchestrator reads FilterResult.is_strategy and stops pipeline before expensive translate+extract"
    - "Stage error isolation: each stage wrapped in try/except; error logged, partial results returned, pipeline continues"

key-files:
  created:
    - "yt_to_skill/stages/extract.py — run_extract: artifact guard, loads translated.txt + raw_transcript.json, calls extract_trading_logic, writes extracted_logic.json"
    - "yt_to_skill/orchestrator.py — run_pipeline, extract_video_id"
    - "tests/test_extract.py — 7 tests: correct params, artifact guard, unspecified_params, raw_text, source_language, JSON round-trip"
    - "tests/test_orchestrator.py — 15 tests: directory creation, stage order, non-strategy skip, StageResult list, idempotency, single client creation, error handling, URL parsing"
  modified: []

key-decisions:
  - "Orchestrator reads FilterResult.from_json after filter stage to determine is_strategy — avoids passing filter state through function return values"
  - "Error handling per-stage: ingest/transcript failure causes early return (downstream stages cannot run); filter failure also returns early (no data to continue); translate/extract errors logged but pipeline returns collected results"
  - "extract_video_id uses urllib.parse for reliable URL parsing rather than regex"

patterns-established:
  - "Complete pipeline: video_id -> extracted_logic.json via run_pipeline"
  - "Client creation once pattern: factories called at pipeline start, injected into stages"

requirements-completed: [EXTR-02, EXTR-03, INPT-05]

# Metrics
duration: 3min
completed: 2026-04-14
---

# Phase 1 Plan 05: Extraction and Orchestrator Summary

**Instructor-patched LLM extraction to TradingLogicExtraction with REQUIRES_SPECIFICATION paths, plus orchestrator wiring all 5 stages — 22 new tests, 118 total passing**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-04-13T20:30:18Z
- **Completed:** 2026-04-13T20:33:24Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 4 created

## Accomplishments

- Extraction stage loads translated.txt + raw_transcript.json source_language, calls extract_trading_logic (instructor client, temperature=0), serializes TradingLogicExtraction to extracted_logic.json via model_dump_json
- StrategyObject.model_validator auto-populates unspecified_params paths for any None fields in entry_criteria/exit_criteria (REQUIRES_SPECIFICATION)
- Orchestrator creates openai_client and instructor_client once, runs all 5 stages in order, skips translate+extract when filter rejects the video, and wraps each stage in try/except for graceful partial results
- extract_video_id handles watch?v=, youtu.be, and /shorts/ YouTube URL formats using urllib.parse
- All 118 tests pass across the full suite

## Task Commits

Each task was committed atomically:

1. **Task 1 TDD RED: Failing extraction tests** — `9d476bd` (test)
2. **Task 1 TDD GREEN: Extraction stage implementation** — `0a730cb` (feat)
3. **Task 2 TDD RED: Failing orchestrator tests** — `822554e` (test)
4. **Task 2 TDD GREEN: Orchestrator implementation** — `07a756f` (feat)

_Note: TDD tasks have separate commits for RED (failing tests) and GREEN (implementation)_

## Files Created/Modified

- `yt_to_skill/stages/extract.py` — run_extract with artifact guard, loads translated.txt + raw_transcript.json, calls extract_trading_logic, writes extracted_logic.json, logs strategies and unspecified_params count
- `yt_to_skill/orchestrator.py` — run_pipeline (5-stage sequence, non-strategy early termination, error isolation), extract_video_id (urllib.parse-based YouTube URL parser)
- `tests/test_extract.py` — 7 tests: correct params to extract_trading_logic, artifact guard skips, unspecified_params populated for nulls, raw_text preserved, source_language from transcript, JSON round-trip
- `tests/test_orchestrator.py` — 15 tests: directory creation, stage order, non-strategy filter skip, StageResult list, idempotency, single LLM client creation, error handling, URL formats

## Decisions Made

- **Orchestrator reads FilterResult.from_json**: After filter stage, orchestrator reads the written filter_result.json to determine is_strategy. This decouples filter stage return value from orchestration logic — any stage can be re-run independently.
- **Error handling tiers**: ingest and transcript failure cause immediate return (downstream stages have no artifacts to work with); filter failure also returns early; translate/extract errors are captured in StageResult.error but remaining results are returned.
- **urllib.parse for URL parsing**: More robust than regex for handling query params, path segments, and edge cases like extra params (e.g., &list=).

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no new external service configuration required.

## Phase 1 Completion

Phase 1 Text Pipeline is now complete end-to-end:

```
YouTube URL -> extract_video_id -> run_pipeline(video_id, config)
  -> run_ingest     -> work/<id>/metadata.json
  -> run_transcript -> work/<id>/raw_transcript.json
  -> run_filter     -> work/<id>/filter_result.json
  -> run_translate  -> work/<id>/translated.txt
  -> run_extract    -> work/<id>/extracted_logic.json  ← primary output
```

All 5 plans in Phase 1 complete. 118 tests passing.

---
*Phase: 01-text-pipeline*
*Completed: 2026-04-14*

## Self-Check: PASSED

All created files and commits verified:
- FOUND: yt_to_skill/stages/extract.py
- FOUND: yt_to_skill/orchestrator.py
- FOUND: tests/test_extract.py
- FOUND: tests/test_orchestrator.py
- FOUND: .planning/phases/01-text-pipeline/01-05-SUMMARY.md
- FOUND commit 9d476bd: test(01-05): add failing tests for extraction stage
- FOUND commit 0a730cb: feat(01-05): implement extraction stage with instructor + Pydantic
- FOUND commit 822554e: test(01-05): add failing tests for orchestrator
- FOUND commit 07a756f: feat(01-05): implement orchestrator wiring all 5 stages into pipeline
