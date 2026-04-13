---
phase: 01-text-pipeline
verified: 2026-04-14T00:00:00Z
status: passed
score: 5/5 must-haves verified
re_verification: false
---

# Phase 1: Text Pipeline Verification Report

**Phase Goal:** Given a YouTube video URL, produce a validated `extracted_logic.json` on disk containing structured trading strategy data
**Verified:** 2026-04-14
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can point the pipeline at a YouTube video with captions and get a transcript extracted without downloading the video | VERIFIED | `transcript.py`: `fetch_captions()` calls `YouTubeTranscriptApi().list(video_id)` — no audio download on caption path. `ingest.py`: `skip_download=True` in ydl_opts. Caption path in `run_transcript()` never calls `download_audio()`. |
| 2 | User can point the pipeline at a caption-less Chinese YouTube video and get a transcript via Whisper (Belle-whisper-large-v3-zh) fallback | VERIFIED | `transcript.py`: `BELLE_WHISPER_MODEL_ID = "Huan69/Belle-whisper-large-v3-zh-punct-fasterwhisper"`. `get_whisper_model()` loads this model. `run_transcript()` falls back to `download_audio()` + `transcribe_audio()` when captions return `None` or fail quality check. `transcribe_audio()` passes `vad_filter=True`. |
| 3 | User can re-run the pipeline on the same video and have all completed stages skipped, with outputs served from disk artifacts in `work/<video_id>/` | VERIFIED | `artifact_guard()` in `stages/base.py` returns `True` if `output_path.exists()`. Every stage (`run_ingest`, `run_transcript`, `run_filter`, `run_translate`, `run_extract`) calls `artifact_guard()` at entry and returns `StageResult(skipped=True)` on hit. Orchestrator test `test_run_pipeline_all_skipped_on_rerun` confirms 5/5 stages report `skipped=True`. 118 tests pass. |
| 4 | The pipeline produces `extracted_logic.json` containing entry/exit criteria, indicators, timeframes, risk rules, and market conditions — with `REQUIRES_SPECIFICATION` markers on any unstated parameters | VERIFIED | `extraction.py`: `TradingLogicExtraction` has `strategies: list[StrategyObject]`. `StrategyObject` has `entry_criteria`, `exit_criteria`, `indicators`, `risk_rules`, `market_conditions`, `unspecified_params`. `model_validator(mode="after")` auto-populates `unspecified_params` with dotted paths (e.g., `entry_criteria[0].value`) for every `None` field in conditions. `extract_trading.txt` prompt instructs model to use `null` for unstated parameters. `run_extract()` serialises via `model_dump_json(indent=2)` to `extracted_logic.json`. |
| 5 | Non-strategy videos (vlogs, news, clickbait) are detected and skipped before LLM extraction calls are made | VERIFIED | `filter.py`: Stage 1 `metadata_prefilter()` scores title+description+tags using `STRATEGY_KEYWORDS` and `NON_STRATEGY_KEYWORDS` — returns early with `is_strategy=False` if score <= 0, skipping any LLM call. Stage 2 (LLM `classify_content`) only runs when Stage 1 passes. Orchestrator reads `FilterResult.is_strategy` and returns before `run_translate` + `run_extract` on rejection. |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `pyproject.toml` | Project metadata, all deps, pytest/ruff config | VERIFIED | Contains `faster-whisper>=1.0.0`, all core deps, `[tool.pytest.ini_options]` |
| `yt_to_skill/config.py` | PipelineConfig(BaseSettings) with env loading | VERIFIED | Exports `PipelineConfig`; `openrouter_api_key: str` required; `work_dir: Path`, model names, whisper settings present; `model_config = {"env_file": ".env"}` |
| `yt_to_skill/models/artifacts.py` | VideoMetadata, TranscriptArtifact, FilterResult dataclasses | VERIFIED | All three dataclasses present with `to_json`/`from_json`; `TranscriptArtifact.method` is `Literal["captions", "whisper"]`; `FilterResult.is_strategy: bool` |
| `yt_to_skill/models/extraction.py` | TradingLogicExtraction, StrategyObject, EntryCondition Pydantic models | VERIFIED | All three models present; `EntryCondition` has nullable `value`, `timeframe`, `confirmation`; `StrategyObject.model_validator` auto-populates `unspecified_params`; `TradingLogicExtraction.to_file()` and `from_file()` present |
| `yt_to_skill/stages/base.py` | Stage protocol with artifact guard | VERIFIED | `StageResult` dataclass (stage_name, artifact_path, skipped, error) and `artifact_guard(path) -> bool` both present; loguru logging on cache hit |
| `yt_to_skill/llm/client.py` | OpenRouter wrapper with translate, classify, extract functions | VERIFIED | Exports `make_openai_client`, `make_instructor_client`, `translate_text`, `classify_content`, `extract_trading_logic`, `load_glossary`; base_url `https://openrouter.ai/api/v1`; tenacity `_retry` wraps all API calls; `max_tokens` set on every call |
| `yt_to_skill/glossary/trading_zh_en.json` | 50-100 Chinese-English trading term pairs | VERIFIED | 97 terms confirmed; contains `多头` and crypto/futures terms |
| `yt_to_skill/llm/prompts/translate.txt` | Translation prompt with `{glossary}` injection slot | VERIFIED | `{glossary}` placeholder present; `GLOSSARY_ADDITIONS` instruction present |
| `yt_to_skill/llm/prompts/extract_trading.txt` | Extraction prompt with REQUIRES_SPECIFICATION instructions | VERIFIED | `REQUIRES_SPECIFICATION` named in rule #1; null-field policy explicitly stated: "you MUST return null for that field" |
| `yt_to_skill/stages/ingest.py` | yt-dlp metadata fetch + lazy audio download | VERIFIED | Exports `run_ingest` and `download_audio`; `skip_download=True` for metadata; `format="bestaudio/best"`, `fragment_retries=3` for audio; artifact guards on both functions |
| `yt_to_skill/stages/transcript.py` | Caption extraction + Whisper fallback with quality heuristics | VERIFIED | Exports `run_transcript`; `fetch_captions()`, `is_caption_quality_acceptable()`, `transcribe_audio()` present; Belle model ID hard-coded; `vad_filter=True` |
| `yt_to_skill/stages/filter.py` | Two-stage non-strategy filter | VERIFIED | Exports `run_filter`; `metadata_prefilter()` with bilingual keyword sets; Stage 2 LLM `classify_content` called only when Stage 1 passes |
| `yt_to_skill/stages/translate.py` | Language detection + glossary-injected LLM translation | VERIFIED | Exports `run_translate`; `detect_language()` using langdetect; English passthrough without LLM call; `load_glossary()` + `translate_text()` injection; `GLOSSARY_ADDITIONS` extracted and stripped |
| `yt_to_skill/stages/extract.py` | LLM extraction via instructor + Pydantic schema | VERIFIED | Exports `run_extract`; calls `extract_trading_logic()` with instructor client; writes `extracted_logic.json` via `model_dump_json(indent=2)`; artifact guard present |
| `yt_to_skill/orchestrator.py` | Pipeline orchestrator wiring all stages | VERIFIED | Exports `run_pipeline` and `extract_video_id`; stages called in order ingest -> transcript -> filter -> translate -> extract; non-strategy early termination; per-stage try/except; LLM clients created once |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `llm/client.py` | `config.py` | `PipelineConfig` parameter on all functions | VERIFIED | Every function signature accepts `config: PipelineConfig`; `config.openrouter_api_key`, `config.translation_model`, etc. used directly |
| `llm/client.py` | `models/extraction.py` | `response_model=TradingLogicExtraction` in `extract_trading_logic` | VERIFIED | Line 211: `response_model=TradingLogicExtraction` passed to instructor client |
| `stages/transcript.py` | `stages/ingest.py` | Whisper path calls `download_audio` | VERIFIED | `from yt_to_skill.stages.ingest import download_audio`; called at lines 305 and 319 in the Whisper fallback branches |
| `stages/ingest.py` | `models/artifacts.py` | Produces `VideoMetadata` | VERIFIED | `from yt_to_skill.models.artifacts import VideoMetadata`; instantiated and written to `metadata.json` |
| `stages/transcript.py` | `models/artifacts.py` | Produces `TranscriptArtifact` | VERIFIED | `from yt_to_skill.models.artifacts import TranscriptArtifact, VideoMetadata`; `TranscriptArtifact` built and serialized |
| `stages/filter.py` | `llm/client.py` | `classify_content` for Stage 2 | VERIFIED | `from yt_to_skill.llm.client import classify_content`; called when Stage 1 passes and `llm_client` is not None |
| `stages/translate.py` | `llm/client.py` | `translate_text` with glossary | VERIFIED | `from yt_to_skill.llm.client import load_glossary, translate_text`; both called in non-English path |
| `stages/translate.py` | `glossary/trading_zh_en.json` | `load_glossary` via `_DEFAULT_GLOSSARY_PATH` | VERIFIED | `_DEFAULT_GLOSSARY_PATH = Path(__file__).parent.parent / "glossary" / "trading_zh_en.json"`; `load_glossary()` called with this path |
| `stages/extract.py` | `llm/client.py` | `extract_trading_logic` | VERIFIED | `from yt_to_skill.llm.client import extract_trading_logic`; called with instructor client |
| `stages/extract.py` | `models/extraction.py` | `TradingLogicExtraction` as response type | VERIFIED | `from yt_to_skill.models.extraction import TradingLogicExtraction`; result typed as `TradingLogicExtraction` |
| `orchestrator.py` | `stages/` (all five) | Imports and calls all `run_*` functions | VERIFIED | Imports `run_extract`, `run_filter`, `run_ingest`, `run_transcript`, `run_translate`; all called in sequence |
| `orchestrator.py` | `config.py` | `PipelineConfig` drives all stage behavior | VERIFIED | `config: PipelineConfig` parameter; `config.work_dir` used; passed to every stage call |
| No direct openai imports in `stages/` | `llm/client.py` gateway enforced | Static analysis test | VERIFIED | Grep of `yt_to_skill/stages/*.py` finds zero matches for `from openai` or `import openai`; static analysis test `test_stages_do_not_import_openai_directly` in `test_llm_client.py` also confirms this at test runtime |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| INPT-01 | 01-03 | Caption extraction via youtube-transcript-api | SATISFIED | `fetch_captions()` in `transcript.py` uses `YouTubeTranscriptApi().list(video_id)` with zh language priority; 16 transcript tests pass |
| INPT-02 | 01-03 | Whisper fallback (Belle-whisper-large-v3-zh) | SATISFIED | `get_whisper_model()` loads `Huan69/Belle-whisper-large-v3-zh-punct-fasterwhisper`; `transcribe_audio()` uses `vad_filter=True`; fallback triggered automatically on missing/poor captions |
| INPT-03 | 01-03 | Audio download via yt-dlp | SATISFIED | `download_audio()` uses `format="bestaudio/best"`, `fragment_retries=3`; artifact guard prevents re-download |
| INPT-05 | 01-05 | Idempotent pipeline (skip processed videos) | SATISFIED | `artifact_guard()` in every stage; orchestrator test confirms all 5 stages report `skipped=True` on re-run; `extracted_logic.json` guard prevents re-extraction |
| EXTR-01 | 01-04 | Chinese transcript translation with glossary | SATISFIED | `run_translate()` detects language, injects 97-term glossary via `load_glossary()`; English passthrough; GLOSSARY_ADDITIONS captured and stripped |
| EXTR-02 | 01-01, 01-05 | Structured extraction (entry/exit, indicators, timeframes, risk rules, market conditions) | SATISFIED | `TradingLogicExtraction` / `StrategyObject` schema covers all fields; `extract_trading.txt` prompt instructs extraction of all categories; `run_extract()` writes complete JSON |
| EXTR-03 | 01-01, 01-05 | REQUIRES_SPECIFICATION markers for implicit parameters | SATISFIED | `StrategyObject.model_validator` auto-populates `unspecified_params` list with dotted paths for every `None` field; prompt says "you MUST return null" for unstated parameters |
| EXTR-04 | 01-04 | Non-strategy content filtered before extraction | SATISFIED | `metadata_prefilter()` gates Stage 2 LLM call; orchestrator stops pipeline before translate+extract when `filter_data.is_strategy` is False |
| INFR-01 | 01-02 | All LLM calls route through OpenRouter | SATISFIED | `make_openai_client()` uses `base_url="https://openrouter.ai/api/v1"`; static analysis test enforces no direct openai imports in `stages/`; all LLM calls channeled through `llm/client.py` |
| INFR-02 | 01-01 | Intermediate artifacts on disk for resumability | SATISFIED | Each stage writes a typed artifact: `metadata.json`, `raw_transcript.json`, `filter_result.json`, `translated.txt`, `extracted_logic.json`; all under `work/<video_id>/` |

**All 10 phase-1 requirement IDs accounted for. No orphaned requirements detected.**

---

### Anti-Patterns Found

No anti-patterns detected. Grep across all implementation files (`stages/`, `orchestrator.py`, `llm/client.py`, `models/`) found zero occurrences of:
- TODO / FIXME / XXX / HACK / PLACEHOLDER
- `return null` / `return {}` / `return []` as stub implementations
- Placeholder comments or "coming soon" text

---

### Human Verification Required

The following behaviors require real YouTube API access or live LLM calls and cannot be verified programmatically against this codebase alone:

#### 1. Caption Extraction — Live Caption Video

**Test:** Run `run_pipeline` with a Chinese trading video URL known to have captions (e.g., a video with confirmed zh captions)
**Expected:** `raw_transcript.json` written with `method="captions"`, `caption_quality="good"`, segments populated; no audio downloaded
**Why human:** Requires live YouTube network access; cannot mock in unit tests

#### 2. Whisper Fallback — Caption-Less Chinese Video

**Test:** Run `run_pipeline` with a Chinese trading video that has no captions or only auto-generated poor-quality captions
**Expected:** `raw_transcript.json` written with `method="whisper"`, Belle model invoked, audio file appears in `work/<video_id>/audio.*`
**Why human:** Requires live YouTube network access + HuggingFace model download on first run

#### 3. Non-Strategy Video Rejection — End-to-End

**Test:** Run `run_pipeline` on a Chinese vlog or news video (e.g., a daily life channel)
**Expected:** `filter_result.json` written with `is_strategy=false`; no `translated.txt` or `extracted_logic.json` created; pipeline terminates after filter stage
**Why human:** Requires live YouTube network access and real LLM classification call

#### 4. extracted_logic.json Quality — Real Trading Video

**Test:** Run `run_pipeline` on a Chinese trading strategy video with explicit entry/exit rules
**Expected:** `extracted_logic.json` contains `strategies` array with non-empty `entry_criteria`, `exit_criteria`, `indicators`, `risk_rules`; `unspecified_params` populated only for genuinely unstated fields
**Why human:** Requires live LLM extraction call; quality of structured output cannot be verified without real model response

---

## Gaps Summary

None. All five observable truths verified. All ten requirement IDs (INPT-01, INPT-02, INPT-03, INPT-05, EXTR-01, EXTR-02, EXTR-03, EXTR-04, INFR-01, INFR-02) are satisfied by substantive, wired implementations. 118 tests pass. No stubs or placeholder implementations found.

The phase delivers the stated goal: given a YouTube video URL, `run_pipeline(video_id, config)` produces a validated `extracted_logic.json` on disk containing structured trading strategy data, with all five intermediate artifacts checkpointed under `work/<video_id>/`.

---

_Verified: 2026-04-14_
_Verifier: Claude (gsd-verifier)_
