# Phase 1: Text Pipeline - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Given a YouTube video URL, produce a validated `extracted_logic.json` on disk containing structured trading strategy data. Covers transcript extraction (captions + Whisper fallback), Chinese-to-English translation with trading glossary, structured logic extraction, non-strategy filtering, and idempotent artifact caching in `work/<video_id>/`.

</domain>

<decisions>
## Implementation Decisions

### Caption vs Whisper routing
- Caption-first approach: try youtube-transcript-api first, fall back to Whisper only when captions are missing or unusable
- Quality heuristics on fetched captions: detect garbled auto-captions (high ratio of short/repeated segments, excessive [Music] tags) and trigger Whisper fallback
- Accept any available language, not just Chinese — translate all non-English transcripts to English
- Language-agnostic caption selection: prioritize Chinese (zh/zh-Hans/zh-Hant) but use whatever is available

### Trading glossary design
- LLM-augmented approach: start with a curated base glossary, LLM identifies unknown trading terms during translation and suggests additions
- Starter glossary of 50-100 core Chinese crypto/trading terms before first pipeline run
- New term handling: Claude's discretion on auto-add vs queue-for-review approach
- Glossary location/structure: Claude's discretion (single file vs per-domain)

### Extraction schema shape
- Hybrid granularity: structured fields where possible (indicator, condition, value, timeframe, confirmation), with `raw_text` fallback for criteria the LLM can't cleanly structure
- Multiple strategies per video: schema is an array of strategy objects — some videos present variations (aggressive vs conservative entries)
- REQUIRES_SPECIFICATION markers: both inline in the field value AND in a top-level `unspecified_params` array listing paths to fields needing user specification
- Video metadata in extracted_logic.json: Claude's discretion on what's useful for downstream SKILL.md generation

### Non-strategy filtering
- Two-stage filtering: quick metadata pre-filter (title, description, tags), then transcript-based confirmation before LLM extraction
- Strict threshold: aggressively filter anything that doesn't clearly present a trading strategy — save LLM costs, accept risk of missing edge cases
- Filtered video handling: Claude's discretion on log-only vs minimal artifact approach
- Filter implementation (LLM call vs keyword heuristics): Claude's discretion

### Claude's Discretion
- Audio-only vs full video download when Whisper fallback triggers
- Glossary new-term handling (auto-add vs queue-for-review)
- Glossary file structure (single vs per-domain)
- Video metadata fields in extracted_logic.json
- Filtered video artifact handling
- Filter implementation approach (LLM vs heuristics)

</decisions>

<specifics>
## Specific Ideas

- Belle-whisper-large-v3-zh is the designated Whisper model for Chinese audio
- OpenRouter is the sole LLM gateway — all model calls route through it
- Primary test channel: Trader Feng Ge (Chinese crypto trading, BTC-focused)
- STATE.md blocker: trading glossary must be authored before first extraction run
- STATE.md note: probe 10-20 Trader Feng Ge videos to determine caption availability rate

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project, no existing code

### Established Patterns
- None yet — Phase 1 establishes the foundational patterns

### Integration Points
- Pipeline outputs to `work/<video_id>/` directory structure
- `extracted_logic.json` is the primary artifact consumed by Phase 2 (SKILL.md generation)
- Glossary file will be shared across all pipeline runs

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-text-pipeline*
*Context gathered: 2026-04-14*
