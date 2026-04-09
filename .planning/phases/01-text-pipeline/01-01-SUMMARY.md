---
phase: 01-text-pipeline
plan: "01"
subsystem: infra
tags: [pydantic, pydantic-settings, dataclasses, pytest, uv, python, faster-whisper, openai, instructor]

# Dependency graph
requires: []
provides:
  - "uv-managed Python project with all pipeline dependencies installed"
  - "PipelineConfig(BaseSettings) loading from OPENROUTER_API_KEY env var"
  - "VideoMetadata, TranscriptArtifact, FilterResult dataclasses with JSON serialization"
  - "EntryCondition, StrategyObject, TradingLogicExtraction Pydantic models with REQUIRES_SPECIFICATION semantics"
  - "StageResult dataclass and artifact_guard function for idempotent stage caching"
  - "pytest infrastructure with shared fixtures (tmp_work_dir, sample_video_id, sample_transcript_segments, mock_config)"
affects:
  - "01-02-PLAN.md (LLM client — uses PipelineConfig)"
  - "01-03-PLAN.md (Transcript stages — uses TranscriptArtifact, VideoMetadata, artifact_guard)"
  - "01-04-PLAN.md (Filter and Translation — uses FilterResult, TradingLogicExtraction)"
  - "01-05-PLAN.md (Extraction and Orchestrator — uses TradingLogicExtraction, StageResult)"

# Tech tracking
tech-stack:
  added:
    - "yt-dlp 2026.3.17 — YouTube video/audio downloading"
    - "youtube-transcript-api 1.2.4 — caption extraction"
    - "faster-whisper 1.2.1 — local speech-to-text transcription"
    - "openai 2.31.0 — OpenRouter API client"
    - "instructor 1.15.1 — structured LLM output extraction"
    - "pydantic 2.13.0 — data validation and serialization"
    - "pydantic-settings 2.13.1 — env var loading"
    - "tenacity 9.1.4 — retry logic"
    - "loguru 0.7.3 — structured logging"
    - "langdetect 1.0.9 — language detection"
    - "pytest 9.0.3 — test framework"
    - "ruff 0.15.10 — linter"
    - "mypy 1.20.1 — type checker"
  patterns:
    - "artifact_guard pattern: check Path.exists() before running stage, return cached StageResult with skipped=True"
    - "REQUIRES_SPECIFICATION: null fields in EntryCondition propagate paths to StrategyObject.unspecified_params via model_validator"
    - "dataclasses with to_json/from_json for pipeline artifact serialization"
    - "pydantic-settings with model_config env_file for environment-based configuration"

key-files:
  created:
    - "pyproject.toml — project metadata, all deps, pytest/ruff config"
    - "yt_to_skill/config.py — PipelineConfig(BaseSettings)"
    - "yt_to_skill/models/artifacts.py — VideoMetadata, TranscriptArtifact, FilterResult"
    - "yt_to_skill/models/extraction.py — EntryCondition, StrategyObject, TradingLogicExtraction"
    - "yt_to_skill/stages/base.py — StageResult, artifact_guard"
    - "tests/conftest.py — shared pytest fixtures"
    - "tests/test_config.py — 7 PipelineConfig tests"
    - "tests/test_models.py — 21 model tests"
    - ".env.example — OPENROUTER_API_KEY placeholder"
    - ".gitignore — work/, .env, __pycache__, etc."
  modified: []

key-decisions:
  - "Python >=3.11,<3.13 required for ctranslate2 wheel compatibility"
  - "uv as package/venv manager; dev deps in optional-dependencies.dev"
  - "pydantic-settings for config so OPENROUTER_API_KEY can be set via .env or shell env"
  - "StrategyObject uses model_validator(mode=after) to auto-populate unspecified_params — callers don't need to manually track null fields"
  - "Artifact dataclasses use to_json/from_json classmethods for JSON serialization; Pydantic models use to_file/from_file"

patterns-established:
  - "artifact_guard(path): check Path.exists() before running any stage — returns True on cache hit"
  - "REQUIRES_SPECIFICATION semantics: null value fields in EntryCondition automatically appear in StrategyObject.unspecified_params as dotted paths"
  - "Stage result always returns StageResult(stage_name, artifact_path, skipped, error)"

requirements-completed: [INFR-02, EXTR-02, EXTR-03]

# Metrics
duration: 20min
completed: 2026-04-14
---

# Phase 1 Plan 01: Project Scaffold, Config, and Data Models Summary

**uv-managed Python project scaffold with typed pipeline config, REQUIRES_SPECIFICATION extraction schema (Pydantic), and idempotent stage base protocol — 28 tests passing**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-04-14
- **Completed:** 2026-04-14
- **Tasks:** 2 (both TDD)
- **Files modified:** 12 created, 1 updated

## Accomplishments

- Project installs cleanly with `uv sync`; all 74 packages resolved and installed
- PipelineConfig(BaseSettings) loads OPENROUTER_API_KEY from env with typed validation and sensible defaults
- Full Pydantic extraction schema with automatic REQUIRES_SPECIFICATION propagation: null fields in EntryCondition automatically appear in StrategyObject.unspecified_params as dotted paths like `entry_criteria[0].value`
- Three pipeline artifact dataclasses (VideoMetadata, TranscriptArtifact, FilterResult) with to_json/from_json JSON serialization
- artifact_guard/StageResult protocol provides the idempotent caching contract all stages will implement
- 28 tests passing: 7 config tests + 21 model tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Project scaffold, dependencies, and config** — `fd9d8ee` (feat) + `fd9d8ee` (initial)
2. **Task 2 TDD RED: Failing model tests** — `569a12d` (test)
3. **Task 2 TDD GREEN: Data models implementation** — `d466ca9` (feat)

_Note: TDD tasks have separate commits for RED (failing tests) and GREEN (implementation)_

## Files Created/Modified

- `pyproject.toml` — Project metadata, all runtime and dev dependencies, pytest/ruff config
- `yt_to_skill/__init__.py` — Package root
- `yt_to_skill/config.py` — PipelineConfig(BaseSettings) with openrouter_api_key, work_dir, model names, whisper config
- `yt_to_skill/models/__init__.py` — Re-exports all key types
- `yt_to_skill/models/artifacts.py` — VideoMetadata, TranscriptArtifact, FilterResult dataclasses
- `yt_to_skill/models/extraction.py` — EntryCondition, StrategyObject, TradingLogicExtraction Pydantic models
- `yt_to_skill/stages/__init__.py` — Package root
- `yt_to_skill/stages/base.py` — StageResult dataclass, artifact_guard function
- `yt_to_skill/llm/__init__.py` — Package root
- `tests/__init__.py` — Package root
- `tests/conftest.py` — Shared fixtures: tmp_work_dir, sample_video_id, sample_transcript_segments, mock_config
- `tests/test_config.py` — 7 PipelineConfig tests
- `tests/test_models.py` — 21 model tests
- `.env.example` — OPENROUTER_API_KEY=your-key-here
- `.gitignore` — work/, .env, __pycache__, etc.
- `uv.lock` — Lockfile with all 74 resolved packages

## Decisions Made

- **Python >=3.11,<3.13**: ctranslate2 (faster-whisper dependency) has no Python 3.13 wheel; upper bound enforced in pyproject.toml
- **StrategyObject model_validator**: Auto-populates unspecified_params from null fields in entry/exit criteria — callers never manually track which fields are unspecified
- **Translation/extraction model**: Set to `anthropic/claude-sonnet-4-20250514` as the primary capable model; filter uses `mistralai/mistral-7b-instruct` (cheap classification)

## Deviations from Plan

None — plan executed exactly as written. The only minor adaptation was creating the package directory structure before running `uv sync` (hatchling couldn't build the editable package without the `yt_to_skill/` directory existing), which is expected for a new project.

## Issues Encountered

- **hatchling build error**: `uv sync` failed initially because the `yt_to_skill/` package directory didn't exist yet. Fixed by creating the directory structure before syncing. Not a deviation — standard greenfield setup sequence.

## User Setup Required

**External services require manual configuration:**

1. Copy `.env.example` to `.env`
2. Set `OPENROUTER_API_KEY=sk-or-your-key` in `.env`
3. Verify: `OPENROUTER_API_KEY=test uv run python -c "from yt_to_skill.config import PipelineConfig; PipelineConfig(); print('OK')"`

## Next Phase Readiness

- Project scaffold complete, all imports working, all tests passing
- Ready for 01-02: LLM client wrapper, prompt templates, and trading glossary
- No blockers for next plan

---
*Phase: 01-text-pipeline*
*Completed: 2026-04-14*
