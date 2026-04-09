# Project Research Summary

**Project:** yt-to-skill — YouTube video-to-structured-skill extraction pipeline
**Domain:** Python CLI / LLM-powered video processing / Chinese-language trading content
**Researched:** 2026-04-13
**Confidence:** HIGH

## Executive Summary

`yt-to-skill` is a local Python CLI pipeline that ingests YouTube videos (primarily Chinese-language crypto trading content), extracts transcripts, translates them to English, applies structured LLM extraction, and emits SKILL.md files conforming to the Agent Skills specification. Experts build this class of tool as a multi-stage pipeline where each stage is independently cacheable on disk — not a monolithic process function — enabling resumption, testability, and selective re-runs. The recommended approach uses `youtube-transcript-api` as the primary transcript source (zero-cost, no download), `faster-whisper` with Belle-whisper-large-v3-zh as a mandatory fallback (significant fraction of Chinese channels have no captions), and OpenRouter via the `openai` SDK with `instructor` for Pydantic-validated structured LLM output.

The single greatest quality risk in this pipeline is the Chinese-to-English translation step. Trading terminology in Mandarin does not map literally to standard English equivalents, and a general-purpose translation will silently corrupt strategy semantics — producing SKILL.md files that look complete but encode wrong rules. This must be addressed from the start with a curated bilingual glossary injected into the translation prompt. A secondary risk is LLM hallucination of specific trading parameters not stated in the source; the `REQUIRES_SPECIFICATION` mechanism must be a first-class feature of the extraction schema, not an afterthought.

The architecture research identifies a clear build order driven by dependencies: config and data contracts first, then the text extraction path (ingest → transcript → translate → extract → render), then visual enrichment (keyframes), then CLI orchestration wiring everything together. Python 3.11 with `uv` for dependency management is the well-justified toolchain. The full stack has been verified against PyPI and official sources with HIGH confidence.

---

## Key Findings

### Recommended Stack

The stack is built around a small set of purpose-fit libraries that avoid heavy runtimes like PyTorch. `faster-whisper` (CTranslate2 backend) delivers the same accuracy as the original Whisper at 4x the speed with a fraction of the memory footprint. The `openai` SDK is used directly against OpenRouter's OpenAI-compatible endpoint — no additional SDK or abstraction layer is needed. `instructor` wraps that client to enforce Pydantic schema validation on LLM responses with automatic retry-on-parse-error. Python 3.11 is the required version: 3.13 has no `ctranslate2` wheels.

**Core technologies:**
- **Python 3.11:** Runtime — required for faster-whisper/ctranslate2 wheel compatibility
- **yt-dlp 2026.3.17:** Video download + metadata — de facto standard, supports playlists/channels
- **youtube-transcript-api 1.2.4:** Caption extraction — zero-download path for videos with captions
- **faster-whisper 1.2.1 + Belle-whisper-large-v3-zh-punct:** Chinese ASR fallback — 4x faster than openai/whisper, no PyTorch
- **PySceneDetect 0.6.7.1:** Keyframe extraction — 94.7% scene detection accuracy, production-proven
- **openai SDK 2.31.0:** OpenRouter client — OpenAI-compatible, no extra dependency
- **instructor 1.15.1:** Structured LLM output — Pydantic validation with retry-on-schema-failure
- **Pydantic 2.13.0:** Data schemas — powers instructor and all inter-stage data contracts
- **Typer 0.24.1 + Rich 14.1.0:** CLI + terminal output — type-hint-driven arg parsing, multi-stage progress display
- **uv:** Dependency management — 10-100x faster than pip, lockfile semantics

See `.planning/research/STACK.md` for full version table, alternatives considered, and what to avoid.

### Expected Features

The core pipeline value chain has no optional steps: if any of transcript extraction, translation, or structured extraction is absent, the output is useless. Features divide cleanly into a validated v1 core and a v1.x batch/visual layer.

**Must have (v1 table stakes):**
- Transcript extraction via captions API + Whisper fallback — both paths required; Chinese channels frequently lack captions
- Chinese-to-English translation with trading terminology glossary — quality gate for all downstream steps
- Trading logic extraction with `REQUIRES_SPECIFICATION` flags — distinguishes stated rules from hallucinated ones
- SKILL.md generation following Agent Skills spec — the deliverable format
- CLI interface (single video URL) — minimum invocation surface
- Idempotent processing via download archive — required even for small playlists
- Error reporting with failure codes and stage-level messages — pipeline has too many failure modes for silent behavior

**Should have (v1.x differentiators):**
- Batch processing (playlists and full channels) — amplifies value significantly once single-video is stable
- Video content filtering (skip non-strategy videos) — prevents wasted LLM calls at scale
- Keyframe extraction via PySceneDetect — visual context anchors chart-based strategy references
- SKILL.md validation via `skills-ref` — catches format regressions in CI-style fashion

**Defer (v2+):**
- Domain-extensible YAML config architecture — defer until Chinese crypto trading is validated end-to-end
- Multi-platform support (Bilibili, TikTok) — defer until YouTube pipeline is mature
- Skill versioning / diff tracking — requires persistent state design

See `.planning/research/FEATURES.md` for full dependency graph, prioritization matrix, and competitor analysis.

### Architecture Approach

The pipeline follows a stage-as-function pattern with filesystem-backed artifact guards. Each of the seven stages (Ingest, Transcript, Translation, Vision, Extraction, Render, and the Orchestrator that drives them) is an independent module writing a typed artifact to `work/<video_id>/`. A stage is skipped if its output artifact already exists — this is the cheapest possible resumption mechanism and is critical for iterative development where LLM calls are expensive. All LLM calls route through a single `llm/client.py` wrapper, all Pydantic models live in `models/extraction.py` decoupled from stage logic, and all prompts are plain-text files in `llm/prompts/` to enable fast iteration without Python changes.

**Major components:**
1. **CLI Entry Point (`cli.py`)** — URL parsing, URL-type resolution (single/playlist/channel), config building; no business logic
2. **Pipeline Orchestrator (`orchestrator.py`)** — stage sequencing, cache checking, retry logic, batch loop with per-video error isolation
3. **Ingest Stage** — yt-dlp metadata + video download; lazy (only downloads video if Whisper fallback is needed)
4. **Transcript Stage** — youtube-transcript-api with automatic Belle-whisper fallback; VAD filter enabled by default
5. **Translation Stage** — language detection + OpenRouter LLM translation with injected trading glossary
6. **Vision Stage** — PySceneDetect AdaptiveDetector + pHash deduplication; capped at configurable max-frames
7. **Extraction Stage** — OpenRouter LLM + instructor + `TradingLogicExtraction` Pydantic schema; REQUIRES_SPECIFICATION-aware
8. **Renderer Stage** — Jinja2 template assembly from `extracted_logic.json`; pure function, no LLM calls

See `.planning/research/ARCHITECTURE.md` for full data flow diagrams, anti-patterns, scaling considerations, and integration boundaries.

### Critical Pitfalls

1. **Chinese captions frequently absent** — Design Whisper fallback as a first-class path from day one. Catch the full `youtube-transcript-api` exception hierarchy (`TranscriptsDisabled`, `NoTranscriptAvailable`, `VideoUnavailable`). Enable `vad_filter=True` on all Whisper calls to suppress hallucination on intro jingles and music.

2. **Trading terminology mistranslation** — Build the Chinese-English trading glossary before the first extraction run. Inject it into the translation prompt. High `REQUIRES_SPECIFICATION` rates are often a symptom of bad translation, not vague source content. This is the highest-leverage quality investment in the entire project.

3. **LLM hallucinating specific parameters** — Make every numeric field in `TradingLogicExtraction` explicitly nullable with `REQUIRES_SPECIFICATION` as the sentinel. Prompt temperature must be 0. Run post-extraction verification on sample outputs before trusting the pipeline for real use.

4. **OpenRouter structured output silently dropped** — Maintain an explicit allowlist of model IDs confirmed to support `json_schema` (Claude 3.x, GPT-4o, Gemini 2.x). Always validate LLM output via Pydantic/instructor regardless of response_format setting. Always set `max_tokens` on all calls to avoid unbounded billing.

5. **PySceneDetect keyframe explosion on screen-recording videos** — Use `AdaptiveDetector` (not `ContentDetector`), raise threshold to ~3.0, apply pHash deduplication, and cap maximum frames per video. Calibrate on real target-channel videos before any batch run.

See `.planning/research/PITFALLS.md` for full prevention strategies, integration gotchas, performance traps, and recovery costs.

---

## Implications for Roadmap

Based on combined research, the pipeline's dependency structure strongly suggests a five-phase build where the text extraction path is completed and validated before adding visual enrichment or batch orchestration. The Architecture research provides an explicit build order (reproduced below) that this phase structure follows.

### Phase 1: Foundation and Text Pipeline

**Rationale:** Every other capability depends on the text extraction chain. Config, data contracts, and LLM client must exist before any stage is implemented. Whisper fallback must be wired in the same phase as captions — not deferred — because Chinese caption availability is poor on the target channel. The translation glossary must be authored before extraction runs.

**Delivers:** Working single-video pipeline from URL to `extracted_logic.json`. CLI accepts a URL, downloads if needed, extracts/transcribes/translates, and produces validated structured trading logic on disk.

**Addresses (from FEATURES.md):** Transcript extraction (captions + Whisper), Chinese-to-English translation, trading logic extraction, `REQUIRES_SPECIFICATION` flags, idempotent stage caching, error reporting.

**Avoids (from PITFALLS.md):** Chinese captions absent (Whisper fallback), Whisper hallucination (VAD filter), trading term mistranslation (glossary), LLM hallucination (nullable schema + temperature 0), OpenRouter structured output drop (allowlist + validation), yt-dlp bot detection (jitter + cookie support).

**Stack used:** yt-dlp, youtube-transcript-api, faster-whisper + Belle model, openai SDK, instructor, Pydantic, pydantic-settings, tenacity, loguru.

**Research flag:** LOW — patterns are well-established; standard stage-as-function pipeline with artifact guards.

---

### Phase 2: SKILL.md Generation and CLI

**Rationale:** Depends on Phase 1 producing valid `extracted_logic.json`. The Renderer and CLI are the final layer that converts extracted data into the deliverable format and makes the pipeline user-invocable. Building CLI last (after stages are tested individually) is the architecture recommendation.

**Delivers:** Working end-to-end pipeline invocable as `yt-to-skill <url>` that produces a valid `skills/<video_id>/SKILL.md` with correct Agent Skills spec frontmatter and directory structure.

**Addresses (from FEATURES.md):** SKILL.md generation (Agent Skills spec), CLI interface, skill output directory structure (`assets/`, `scripts/`, `references/` scaffold).

**Avoids (from PITFALLS.md):** Silent success on empty SKILL.md (quality gate — require at least one entry criterion, one exit criterion, one risk rule), SKILL.md format non-compliance (validate output before writing).

**Stack used:** Typer, Rich, Jinja2.

**Research flag:** LOW — well-documented patterns; SKILL.md spec is authoritative with validation tooling.

---

### Phase 3: Batch Processing and Content Filtering

**Rationale:** Depends on Phase 1-2 single-video pipeline being stable and reliable. Batch amplifies value significantly but also amplifies every bug — processing 200 videos with a bad translation glossary means 200 bad skills. Content filtering gates LLM cost at scale.

**Delivers:** `yt-to-skill <channel-or-playlist-url>` processes all videos in a channel/playlist with per-video error isolation, progress reporting, download archive (idempotency), jitter-rate-limited downloads, and a summary report (N processed / M skipped / K failed).

**Addresses (from FEATURES.md):** Batch processing (playlists and channels), video content filtering (non-strategy skip).

**Avoids (from PITFALLS.md):** yt-dlp IP blocking at batch scale (authenticated cookies, jitter delays, lowered fragment-retries), batch abort on single failure (log-and-continue pattern), performance trap of sequential download without I/O parallelism.

**Stack used:** yt-dlp batch/archive flags, concurrent.futures for I/O-bound stages, tenacity exponential backoff.

**Research flag:** MEDIUM — batch error isolation and rate-limiting patterns are well-documented, but yt-dlp bot detection behavior is actively changing (2025-2026 enforcement tightening noted); may need validation of cookie-auth approach.

---

### Phase 4: Visual Enrichment (Keyframes)

**Rationale:** Structurally independent of the text path — Vision Stage can read from the same `work/<video_id>/video.mp4` that Ingest already downloads. Deferred until text pipeline is validated because keyframe quality is hard to assess without real sample videos from the target channel, and threshold calibration is required before batch use.

**Delivers:** `assets/frame_NNN.png` keyframes written to `skills/<video_id>/assets/`, keyframe context optionally injected into the extraction prompt with timestamps.

**Addresses (from FEATURES.md):** Keyframe extraction for chart screenshots, SKILL.md `assets/` populated with visual references.

**Avoids (from PITFALLS.md):** Keyframe explosion on screen-recording videos (AdaptiveDetector, threshold calibration, pHash dedup, frame cap), video download bandwidth waste (resize to 360p for scene detection, use `bestaudio` format when only audio needed).

**Stack used:** PySceneDetect 0.6.7.1, OpenCV (PySceneDetect backend), ffmpeg system binary.

**Research flag:** HIGH — requires threshold calibration on actual Trader Feng Ge videos; PySceneDetect `AdaptiveDetector` behavior on screen-recording content is less documented than film detection; recommend a dedicated spike on 5-10 sample videos before committing to production implementation.

---

### Phase 5: Hardening and Extensibility

**Rationale:** Post-validation polish. Domain-extensible YAML config, SKILL.md validation via `skills-ref`, cost tracking, and multi-domain architecture refactoring are high-value but depend on the pipeline having proven itself on the primary use case (Chinese crypto, single domain).

**Delivers:** Domain config profiles (trading YAML), language config profiles (zh YAML), SKILL.md validation as a post-generation gate, per-call cost logging to OpenRouter, `skills-ref validate` integrated as CLI post-step.

**Addresses (from FEATURES.md):** SKILL.md validation, domain-extensible architecture, OpenRouter as unified LLM gateway.

**Avoids (from PITFALLS.md):** Hardcoded domain logic in stage code (ARCHITECTURE anti-pattern 3), single hardcoded OpenRouter model (model allowlist + fallback).

**Stack used:** PyYAML, skills-ref CLI, existing stack; refactoring existing Python, not new libraries.

**Research flag:** LOW — standard YAML-config extensibility pattern; skills-ref validator is authoritative; straightforward refactor once pipeline is working.

---

### Phase Ordering Rationale

- **Text path first, visuals second:** The value chain is `transcript → translate → extract → render`. Keyframes enhance but do not unlock the core value. Building visuals before the text path is stable would mask quality issues.
- **Single video before batch:** Bugs in extraction quality are cheap to fix on one video; expensive to fix across a 200-video channel run. The pitfalls research shows re-extraction costs are HIGH when hallucination or mistranslation is discovered late.
- **Glossary in Phase 1, not a later phase:** The pitfalls research is explicit: "build glossary before first extraction run." This is not optional polish — a pipeline run without a glossary produces systematically corrupted output that must be discarded entirely.
- **Orchestrator and CLI after stages:** The architecture research recommends wiring stages together last. Each stage should be independently testable before the Orchestrator exists.

### Research Flags

Phases needing deeper research during planning:
- **Phase 3 (Batch):** yt-dlp YouTube bot detection is actively evolving; verify cookie-auth approach and rate-limiting behavior against current yt-dlp version before implementing
- **Phase 4 (Keyframes):** PySceneDetect `AdaptiveDetector` threshold calibration on screen-recording trading content requires a spike with real sample videos; default values will not work

Phases with standard patterns (safe to skip research-phase):
- **Phase 1 (Text Pipeline):** stage-as-function with artifact guards is a documented, stable pattern; stack is fully verified
- **Phase 2 (SKILL.md / CLI):** Agent Skills spec is authoritative with validation tooling; Typer/Rich patterns are well-documented
- **Phase 5 (Hardening):** YAML config extensibility and validation integration are standard; no novel patterns

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified against PyPI and official sources; compatibility matrix explicitly documented |
| Features | HIGH | Features derived from PROJECT.md requirements + Agent Skills spec (authoritative); competitor analysis validated against known implementations |
| Architecture | HIGH | Stage-as-function pattern is well-documented; build order is logically derived from dependencies; all integration points verified |
| Pitfalls | MEDIUM-HIGH | Most pitfalls verified via official docs or multiple sources; Belle-whisper dialect limits are LOW confidence (single vendor description); yt-dlp bot detection behavior verified via GitHub issues but is an evolving target |

**Overall confidence:** HIGH

### Gaps to Address

- **Trading glossary scope:** Research identifies that a glossary is mandatory but does not enumerate the full term list. During Phase 1 planning, author the glossary from verified bilingual sources (OKX/Binance Chinese docs, Investopedia Chinese) targeting 50+ term pairs. Validate against at least 5 real Trader Feng Ge transcripts before the translation stage is considered complete.

- **Target channel caption availability rate:** Research estimates "significant fraction" of Chinese trading videos lack captions but does not give a channel-specific number. During Phase 1 implementation, probe 10-20 Trader Feng Ge videos before committing to the caption-first vs. Whisper-first decision in the Transcript Stage.

- **OpenRouter model allowlist:** Research identifies that structured output support is model-specific but the list may change as new models are added to OpenRouter. The allowlist should be an editable config value, not hardcoded, so it can be maintained without code changes.

- **PySceneDetect threshold for target channel:** The pitfalls research is explicit that default thresholds will cause keyframe explosion on screen-recording content. Actual calibrated values for Trader Feng Ge videos cannot be determined until Phase 4 implementation begins with real sample videos.

---

## Sources

### Primary (HIGH confidence)
- [Agent Skills Specification — agentskills.io](https://agentskills.io/specification) — SKILL.md format, frontmatter schema, validation tooling
- [youtube-transcript-api 1.2.4 — PyPI](https://pypi.org/project/youtube-transcript-api/) — transcript extraction capabilities and exception hierarchy
- [faster-whisper 1.2.1 — PyPI](https://pypi.org/project/faster-whisper/) — version, compatibility, CTranslate2 backend
- [yt-dlp 2026.3.17 — PyPI](https://pypi.org/project/yt-dlp/) — version, Python requirements
- [openai SDK 2.31.0 — PyPI](https://pypi.org/project/openai/) — OpenRouter-compatible base_url pattern
- [instructor 1.15.1 — PyPI](https://pypi.org/project/instructor/) + [integration guide](https://python.useinstructor.com/integrations/openrouter/) — Pydantic validation with OpenRouter
- [OpenRouter Structured Outputs documentation](https://openrouter.ai/docs/guides/features/structured-outputs) — json_schema support per model
- [PySceneDetect 0.6.7.1 Python API](https://www.scenedetect.com/docs/latest/api.html) — AdaptiveDetector, ContentDetector
- [Belle-whisper-large-v3-zh-punct — HuggingFace](https://huggingface.co/BELLE-2/Belle-whisper-large-v3-zh-punct) — Chinese ASR model

### Secondary (MEDIUM confidence)
- [How to Tackle yt-dlp Challenges in AI-Scale Scraping — Medium](https://medium.com/@DataBeacon/how-to-tackle-yt-dlp-challenges-in-ai-scale-scraping-8b78242fedf0) — rate limiting, bot detection mitigations
- [yt-dlp GitHub issues #15899, #13067](https://github.com/yt-dlp/yt-dlp/issues/15899) — fragment-retries bot detection behavior
- [Data Pipeline Design Patterns — Start Data Engineering](https://www.startdataengineering.com/post/code-patterns/) — stage-as-function artifact guard pattern
- [Structured Data Extraction with LLMs — PyCon 2025](https://building-with-llms-pycon-2025.readthedocs.io/en/latest/structured-data-extraction.html) — Pydantic + instructor patterns
- [yfe404/AI-anything GitHub](https://github.com/yfe404/AI-anything) — reference implementation for YouTube-to-skill pipeline
- [Towards reducing hallucination in extracting information from financial reports — arXiv](https://arxiv.org/html/2310.10760) — LLM hallucination in structured financial extraction

### Tertiary (LOW confidence)
- Belle-whisper dialect limit descriptions — from single vendor/model card; actual performance on target channel content needs empirical validation
- [Chinese Financial Localization — 1-StopAsia](https://www.1stopasia.com/blog/chinese-financial-terminology-orange-book/) — glossary scope guidance; should be validated against OKX/Binance official docs

---
*Research completed: 2026-04-13*
*Ready for roadmap: yes*
