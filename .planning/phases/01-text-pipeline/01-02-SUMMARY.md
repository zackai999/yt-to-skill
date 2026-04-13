---
phase: 01-text-pipeline
plan: "02"
subsystem: infra
tags: [openrouter, openai, instructor, tenacity, loguru, llm, glossary, prompts, retry]

# Dependency graph
requires:
  - phase: 01-text-pipeline-01
    provides: "PipelineConfig with openrouter_api_key, model names, max_tokens; TradingLogicExtraction Pydantic model"
provides:
  - "OpenRouter LLM client wrapper: make_openai_client, make_instructor_client, translate_text, classify_content, extract_trading_logic, load_glossary"
  - "Three LLM prompt templates: translate.txt (glossary injection), filter_content.txt (STRATEGY/NOT_STRATEGY), extract_trading.txt (REQUIRES_SPECIFICATION)"
  - "Trading glossary: 97 curated Chinese-English crypto/trading term pairs in trading_zh_en.json"
affects:
  - "01-03-PLAN.md (transcript stages — will call translate_text)"
  - "01-04-PLAN.md (filter stage — will call classify_content)"
  - "01-05-PLAN.md (extraction stage — will call extract_trading_logic)"

# Tech tracking
tech-stack:
  added:
    - "openai SDK — used via make_openai_client with custom base_url for OpenRouter routing"
    - "instructor — structured LLM output extraction via instructor.from_openai()"
    - "tenacity — retry logic with wait_exponential(min=2, max=60), stop_after_attempt(3)"
    - "loguru — logging model ID, stage name, token usage after each LLM call"
  patterns:
    - "Single LLM gateway: all model calls route through yt_to_skill/llm/client.py — no direct openai imports in stages/"
    - "Shared _retry decorator via tenacity applied to all API-calling functions"
    - "_parse_classification helper for parsing multi-line LLM filter responses"
    - "Prompt templates as .txt files loaded at call time via Path(__file__).parent / 'prompts'"

key-files:
  created:
    - "yt_to_skill/llm/client.py — OpenRouter wrapper with 6 exported functions"
    - "yt_to_skill/llm/prompts/translate.txt — translation prompt with {glossary} injection slot and GLOSSARY_ADDITIONS instruction"
    - "yt_to_skill/llm/prompts/filter_content.txt — classification prompt outputting STRATEGY/NOT_STRATEGY with confidence"
    - "yt_to_skill/llm/prompts/extract_trading.txt — extraction prompt with REQUIRES_SPECIFICATION null-field policy"
    - "yt_to_skill/glossary/trading_zh_en.json — 97-term Chinese-English trading glossary"
    - "tests/test_llm_client.py — 13 tests covering client, classification, extraction, and static analysis"
  modified: []

key-decisions:
  - "All LLM calls route through yt_to_skill/llm/client.py — enforced by static analysis test scanning stages/ for direct openai imports"
  - "Shared tenacity _retry decorator (module-level) avoids repeating retry config on each function"
  - "Prompt templates stored as .txt files alongside client.py — loaded at call time, not at import time, so tests can mock completions without file issues"
  - "classify_content parses multi-line response (STRATEGY/NOT_STRATEGY + confidence + reason) via _parse_classification helper"

patterns-established:
  - "LLM gateway pattern: import client functions, not openai SDK directly, in all stage files"
  - "Prompt injection: load template, replace {glossary} slot with formatted term list, pass as system message"
  - "Classification parsing: strip + splitlines pattern for multi-line structured LLM responses"

requirements-completed: [INFR-01]

# Metrics
duration: 3min
completed: 2026-04-14
---

# Phase 1 Plan 02: OpenRouter LLM Client, Prompts, and Trading Glossary Summary

**OpenRouter LLM gateway (6 functions) with tenacity retry, 3 domain-specific prompt templates, and 97-term Chinese-English crypto trading glossary — 13 tests passing**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-04-13T20:11:11Z
- **Completed:** 2026-04-14
- **Tasks:** 2 (Task 1 TDD, Task 2 content)
- **Files modified:** 6 created

## Accomplishments

- Single LLM gateway module centralizing all OpenRouter calls — static analysis test enforces no direct openai imports in stages/
- All three pipeline LLM functions (translate, classify, extract) have max_tokens, temperature, retry logic, and loguru logging
- Trading glossary with 97 curated Chinese-English crypto/futures term pairs (including critical terms: 多头/long, 止损/stop loss, 金叉/golden cross, 爆仓/liquidation)
- Three prompt templates encode domain-specific instructions: GLOSSARY_ADDITIONS for unknown terms, STRATEGY/NOT_STRATEGY classification format, REQUIRES_SPECIFICATION null-field extraction policy

## Task Commits

Each task was committed atomically:

1. **Task 1 TDD RED: Failing LLM client tests** — `25b7cef` (test)
2. **Task 1 TDD GREEN: LLM client implementation + prompt templates** — `9162435` (feat)
3. **Task 2: Trading glossary** — `a468e6b` (feat)

_Note: TDD tasks have separate commits for RED (failing tests) and GREEN (implementation)_

## Files Created/Modified

- `yt_to_skill/llm/client.py` — 6 exported functions: make_openai_client, make_instructor_client, translate_text, classify_content, extract_trading_logic, load_glossary
- `yt_to_skill/llm/prompts/translate.txt` — Translation system prompt with {glossary} injection and GLOSSARY_ADDITIONS instruction
- `yt_to_skill/llm/prompts/filter_content.txt` — Classification prompt with strict NOT_STRATEGY threshold
- `yt_to_skill/llm/prompts/extract_trading.txt` — Extraction prompt with REQUIRES_SPECIFICATION null-field policy and multiple strategy support
- `yt_to_skill/glossary/trading_zh_en.json` — 97-term Chinese-English trading glossary
- `tests/test_llm_client.py` — 13 tests: client factories, translate glossary injection, classify bool/float return, extract response_model/temperature, static analysis, load_glossary

## Decisions Made

- **All LLM calls through client.py**: Enforced via static analysis test that scans yt_to_skill/stages/ for direct openai imports — any future stage that imports openai directly will fail CI
- **Shared _retry decorator at module level**: Avoids copy-pasting tenacity config on each function; all API functions share the same retry policy
- **Prompt templates as .txt files loaded at call time**: Allows easy prompt editing without code changes; tests mock the completions layer so file reads succeed normally during testing
- **_parse_classification helper**: LLM filter response is multi-line (label + confidence + reason); helper isolates the parsing logic and is testable independently

## Deviations from Plan

None — plan executed exactly as written. Prompt templates were created as part of Task 1 GREEN commit (they were needed for client.py to work) rather than as a separate sub-step of Task 2, but both files and glossary are present as specified.

## Issues Encountered

None.

## User Setup Required

None — no new external service configuration required. OPENROUTER_API_KEY was already documented in 01-01.

## Next Phase Readiness

- LLM gateway is complete and tested; stages can call translate_text, classify_content, extract_trading_logic
- Trading glossary blocker from STATE.md is resolved (trading glossary authored before first extraction run)
- Ready for 01-03: Transcript stages (ingest, captions, Whisper fallback)

---
*Phase: 01-text-pipeline*
*Completed: 2026-04-14*
