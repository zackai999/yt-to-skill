---
phase: 01-text-pipeline
plan: "04"
subsystem: pipeline
tags: [filter, translation, langdetect, llm, classify, glossary, tdd]

# Dependency graph
requires:
  - phase: 01-text-pipeline
    plan: "02"
    provides: "classify_content, translate_text, load_glossary via yt_to_skill/llm/client.py; trading_zh_en.json glossary"
  - phase: 01-text-pipeline
    plan: "03"
    provides: "raw_transcript.json (TranscriptArtifact), metadata.json (VideoMetadata) from ingest and transcript stages"
provides:
  - "run_filter: two-stage non-strategy filter — Stage 1 free metadata scoring, Stage 2 cheap LLM transcript classification"
  - "metadata_prefilter: keyword scoring with STRATEGY_KEYWORDS + NON_STRATEGY_KEYWORDS (English + Chinese)"
  - "run_translate: language detection + glossary-injected LLM translation; English passthrough"
  - "detect_language: langdetect wrapper with CJK normalization and graceful failure"
  - "extract_glossary_additions: parses GLOSSARY_ADDITIONS section from LLM translation response"
affects:
  - "01-05-PLAN.md (Extraction and Orchestrator — consumes filter_result.json and translated.txt)"

# Tech tracking
tech-stack:
  added:
    - "langdetect — language identification from transcript text (first 1000 chars for speed)"
  patterns:
    - "Two-stage gate: cheap metadata scoring before expensive LLM call"
    - "Conservative None client: when llm_client=None and Stage 1 passes, assume strategy (avoid false negatives)"
    - "GLOSSARY_ADDITIONS: section in LLM response allows the model to suggest new terms; extracted, logged, and stripped before saving"
    - "Any type hint for llm_client parameter (not OpenAI directly) to satisfy static analysis test banning openai imports in stages/"

key-files:
  created:
    - "yt_to_skill/stages/filter.py — metadata_prefilter + run_filter with two-stage non-strategy gate"
    - "yt_to_skill/stages/translate.py — detect_language, extract_glossary_additions, run_translate"
    - "tests/test_filter.py — 18 tests: metadata keyword scoring, run_filter flow, artifact guard, stage gating"
    - "tests/test_translate.py — 14 tests: language detection, glossary additions parsing, run_translate flow"
  modified: []

key-decisions:
  - "Any type hint for llm_client in stages instead of OpenAI: static analysis test bans 'from openai' in stages/ — using Any preserves type safety intent while passing enforcement"
  - "None llm_client conservatively passes Stage 2: better to extract a borderline video than to silently drop a strategy video"
  - "Chinese keyword matching works without lowercasing CJK: .lower() on mixed string leaves CJK unchanged; combined keyword set covers both Latin and Chinese terms"
  - "GLOSSARY_ADDITIONS section stripped from translated.txt: clean text for downstream extraction; additions logged via loguru for periodic glossary review"

patterns-established:
  - "Two-stage filter pattern: free/fast metadata pre-filter gates expensive LLM calls"
  - "Conservative LLM bypass: when client unavailable, assume positive (strategy) to avoid false negatives"
  - "LLM response augmentation: structured sections (GLOSSARY_ADDITIONS) for out-of-band communication from model to pipeline"

requirements-completed: [EXTR-01, EXTR-04]

# Metrics
duration: 8min
completed: 2026-04-14
---

# Phase 1 Plan 04: Filter and Translation Stages Summary

**Two-stage non-strategy filter (metadata keyword scoring + LLM transcript classification) and glossary-injected LLM translation with GLOSSARY_ADDITIONS extraction — 32 tests passing, both stages idempotent**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-04-13T20:23:37Z
- **Completed:** 2026-04-14
- **Tasks:** 2 (both TDD)
- **Files modified:** 4 created

## Accomplishments

- Two-stage filter with STRATEGY_KEYWORDS (11 English + 11 Chinese) and NON_STRATEGY_KEYWORDS scoring: Stage 1 free metadata check gates Stage 2 LLM call — avoids wasted extraction on vlogs/news
- Translation stage detects language (langdetect first 1000 chars), skips LLM entirely for English transcripts, and injects the 97-term trading glossary into the system prompt for Chinese-to-English translation
- GLOSSARY_ADDITIONS section in LLM response is extracted, each new term logged via loguru, then stripped from the output before writing clean translated.txt
- Both stages fully idempotent via artifact_guard pattern (filter_result.json / translated.txt)
- Static analysis constraint maintained: no direct openai imports in either stage module

## Task Commits

Each task was committed atomically:

1. **Task 1 TDD RED: Failing filter tests** — `672b311` (test)
2. **Task 1 TDD GREEN: Filter stage implementation** — `9821c09` (feat)
3. **Task 2 TDD RED: Failing translate tests** — `6e0aaea` (test)
4. **Task 2 TDD GREEN: Translate stage implementation** — `56e246d` (feat)

_Note: TDD tasks have separate commits for RED (failing tests) and GREEN (implementation)_

## Files Created/Modified

- `yt_to_skill/stages/filter.py` — STRATEGY_KEYWORDS + NON_STRATEGY_KEYWORDS sets; metadata_prefilter scoring function; run_filter with Stage 1 (free) + Stage 2 (LLM) gating
- `yt_to_skill/stages/translate.py` — detect_language (langdetect + CJK normalization); extract_glossary_additions parser; run_translate with English passthrough and glossary injection
- `tests/test_filter.py` — 18 tests: 12 metadata_prefilter (keyword scoring, Chinese terms, case-insensitivity), 6 run_filter (artifact guard, stage gating, LLM call, FilterResult JSON)
- `tests/test_translate.py` — 14 tests: 4 detect_language (zh/en, exception, 1000-char limit), 3 extract_glossary_additions (parse, empty, missing), 7 run_translate (artifact guard, English skip, LLM call, GLOSSARY_ADDITIONS, langdetect failure)

## Decisions Made

- **Any type hint for llm_client**: Static analysis test in test_llm_client.py scans stages/ for `from openai` and `import openai` and fails if found. Used `Any` type hint to avoid importing OpenAI class in stages while preserving intent.
- **Conservative None client**: When `llm_client=None` and Stage 1 passes, Stage 2 is skipped and `is_strategy=True` is assumed. This prevents false negatives (wrongly dropping strategy videos) at the cost of potentially passing a few edge cases to extraction.
- **langdetect unknown defaults to translation**: When langdetect throws LangDetectException (e.g., insufficient text), language is `"unknown"` and translation proceeds. Better to translate unnecessarily than skip translation on non-English content.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed openai imports from stages to satisfy static analysis test**
- **Found during:** Task 2 (translate stage — after initial GREEN commit)
- **Issue:** Both filter.py and translate.py initially imported `from openai import OpenAI` for type hints in function signatures. The static analysis test `test_stages_do_not_import_openai_directly` in test_llm_client.py scans all .py files under yt_to_skill/stages/ and fails on `from openai`.
- **Fix:** Replaced `OpenAI | None` type hint with `Any | None` from `typing`. No functional change — all mocking and runtime behavior unchanged.
- **Files modified:** yt_to_skill/stages/filter.py, yt_to_skill/stages/translate.py
- **Verification:** `uv run pytest tests/test_filter.py tests/test_translate.py tests/test_llm_client.py` — 45 tests pass including static analysis test
- **Committed in:** 56e246d (Task 2 GREEN commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug: openai import constraint)
**Impact on plan:** Necessary for correctness — the static analysis constraint is an enforced architectural invariant from Plan 02. No scope creep.

## Issues Encountered

None.

## User Setup Required

None — no new external service configuration required.

## Next Phase Readiness

- Filter stage complete: saves LLM extraction costs by rejecting obvious non-strategy content at metadata level (free) then transcript level (cheap)
- Translation stage complete: Chinese transcripts translated with 97-term glossary injection; unknown terms flagged for glossary review
- Ready for 01-05: Extraction and Orchestrator stage (consumes filter_result.json + translated.txt)
- No blockers for next plan

---
*Phase: 01-text-pipeline*
*Completed: 2026-04-14*

## Self-Check: PASSED

All created files and commits verified:
- FOUND: yt_to_skill/stages/filter.py
- FOUND: yt_to_skill/stages/translate.py
- FOUND: tests/test_filter.py
- FOUND: tests/test_translate.py
- FOUND: .planning/phases/01-text-pipeline/01-04-SUMMARY.md
- FOUND commit 672b311: test(01-04): add failing tests for filter stage
- FOUND commit 9821c09: feat(01-04): implement filter stage with two-stage non-strategy detection
- FOUND commit 6e0aaea: test(01-04): add failing tests for translate stage
- FOUND commit 56e246d: feat(01-04): implement translate stage with language detection and glossary injection
