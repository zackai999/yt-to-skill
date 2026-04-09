# Phase 1: Text Pipeline - Research

**Researched:** 2026-04-14
**Domain:** YouTube transcript extraction, Chinese-to-English translation, structured LLM extraction, idempotent artifact pipeline (Python CLI)
**Confidence:** HIGH — all stack components verified against PyPI/official sources in prior project research (2026-04-13); phase-specific decisions confirmed against CONTEXT.md

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Caption vs Whisper routing:**
- Caption-first approach: try youtube-transcript-api first, fall back to Whisper only when captions are missing or unusable
- Quality heuristics on fetched captions: detect garbled auto-captions (high ratio of short/repeated segments, excessive [Music] tags) and trigger Whisper fallback
- Accept any available language, not just Chinese — translate all non-English transcripts to English
- Language-agnostic caption selection: prioritize Chinese (zh/zh-Hans/zh-Hant) but use whatever is available

**Trading glossary design:**
- LLM-augmented approach: start with a curated base glossary, LLM identifies unknown trading terms during translation and suggests additions
- Starter glossary of 50-100 core Chinese crypto/trading terms before first pipeline run

**Extraction schema shape:**
- Hybrid granularity: structured fields where possible (indicator, condition, value, timeframe, confirmation), with `raw_text` fallback for criteria the LLM can't cleanly structure
- Multiple strategies per video: schema is an array of strategy objects
- REQUIRES_SPECIFICATION markers: both inline in the field value AND in a top-level `unspecified_params` array listing paths to fields needing user specification
- Video metadata in extracted_logic.json: Claude's discretion on what's useful

**Non-strategy filtering:**
- Two-stage filtering: quick metadata pre-filter (title, description, tags), then transcript-based confirmation before LLM extraction
- Strict threshold: aggressively filter anything that doesn't clearly present a trading strategy

**Specific directives:**
- Belle-whisper-large-v3-zh is the designated Whisper model for Chinese audio
- OpenRouter is the sole LLM gateway — all model calls route through it
- Primary test channel: Trader Feng Ge (Chinese crypto trading, BTC-focused)
- Pipeline must be idempotent — completed stages skipped, outputs served from `work/<video_id>/`

### Claude's Discretion
- Audio-only vs full video download when Whisper fallback triggers
- Glossary new-term handling (auto-add vs queue-for-review)
- Glossary file structure (single vs per-domain)
- Video metadata fields in extracted_logic.json
- Filtered video artifact handling
- Filter implementation approach (LLM vs heuristics)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INPT-01 | User can extract transcript from any YouTube video with captions via youtube-transcript-api | youtube-transcript-api 1.2.4 covers this; language priority list `['zh', 'zh-Hans', 'zh-Hant', 'en']`; no API key required |
| INPT-02 | User can extract transcript from caption-less videos via Whisper (Belle-whisper-large-v3-zh) | faster-whisper 1.2.1 + `Huan69/Belle-whisper-large-v3-zh-punct-fasterwhisper` HuggingFace model; `vad_filter=True` required |
| INPT-03 | User can download video locally via yt-dlp for audio extraction | yt-dlp 2026.3.17; use `--format bestaudio` when only audio needed; lazy download (only when captions fail) |
| INPT-05 | Pipeline skips already-processed videos using download archive (idempotent) | Stage-as-function with artifact guard pattern — each stage checks for its output file before executing; `work/<video_id>/` directory as artifact store |
| EXTR-01 | User can translate Chinese transcripts to English via OpenRouter LLM with trading terminology glossary | openai SDK 2.31.0 with `base_url="https://openrouter.ai/api/v1"`; glossary injected into system prompt; `langdetect` or LLM for language detection |
| EXTR-02 | User can extract structured trading logic (entry/exit criteria, indicators, timeframes, risk rules, market conditions) from translated transcripts | instructor 1.15.1 + Pydantic 2.13.0; `TradingLogicExtraction` schema with array of strategy objects; temperature=0 |
| EXTR-03 | Extracted strategies flag implicit/unstated parameters with REQUIRES_SPECIFICATION markers | Nullable schema fields + `unspecified_params` top-level array; explicit prompt instruction "if not stated, return REQUIRES_SPECIFICATION" |
| EXTR-04 | Pipeline filters out non-strategy content before full extraction | Two-stage: metadata pre-filter (title/description heuristics) → transcript-sample confirmation (LLM or keyword score on first 500 words) |
| INFR-01 | All LLM calls route through OpenRouter as unified gateway | Single `llm/client.py` wrapper using `openai` SDK with `base_url`; all model calls go through it; `max_tokens` cap on every call |
| INFR-02 | Pipeline uses intermediate artifacts on disk (work/<video_id>/) for resumability and debugging | `work/<video_id>/` directory structure; `metadata.json`, `raw_transcript.json`, `translated.txt`, `extracted_logic.json`; stage skips on artifact presence |
</phase_requirements>

---

## Summary

Phase 1 builds the complete text extraction chain: from a YouTube URL to a validated `extracted_logic.json` on disk. This is the foundational phase — every subsequent phase (SKILL.md generation, batch processing) depends on this output. The pipeline must handle two transcript acquisition paths (captions via `youtube-transcript-api`, Whisper transcription via `faster-whisper` with Belle model), Chinese-to-English translation with a trading terminology glossary, structured LLM extraction via `instructor` + Pydantic, and non-strategy content filtering — all with artifact-guarded idempotency.

The architecture is a stage-as-function pipeline where each of six stages (Ingest, Transcript, Filter, Translate, Extract) writes a typed artifact to `work/<video_id>/`. A stage is skipped if its artifact already exists. This is the cheapest resumption mechanism possible and is critical for iterative development where LLM calls and Whisper transcription are expensive. All LLM calls route through a single `llm/client.py` wrapper pointing at OpenRouter's OpenAI-compatible endpoint.

The single greatest quality risk in this phase is the Chinese-to-English translation step. Trading terminology in Mandarin does not map literally to English equivalents, and a general-purpose translation silently corrupts strategy semantics. The trading glossary (50-100 term pairs) must be authored and validated before the first extraction run — this is not optional polish. A secondary risk is LLM hallucination of specific numeric parameters not stated in the source video; the `REQUIRES_SPECIFICATION` mechanism is the mitigation and must be a first-class feature of the extraction schema.

**Primary recommendation:** Build in this order: (1) project scaffold + config + data contracts, (2) OpenRouter LLM client wrapper, (3) trading glossary file, (4) Ingest stage (yt-dlp), (5) Transcript stage (captions + Whisper fallback wired together), (6) Filter stage, (7) Translation stage, (8) Extraction stage. Wire stages into minimal orchestrator last.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.11 | Runtime | Required: ctranslate2 (faster-whisper backend) has no Python 3.13 wheels; 3.11 is the sweet spot across all deps |
| yt-dlp | 2026.3.17 | Video metadata + audio download | De facto standard for YouTube; programmatic `YoutubeDL` Python API; playlist/channel support; Python 3.10+ required |
| youtube-transcript-api | 1.2.4 | Caption extraction | Zero-download path; fetches YouTube's own captions; supports `zh`/`zh-Hans`/`zh-Hant`; no API key |
| faster-whisper | 1.2.1 | Whisper ASR fallback | 4x faster than openai/whisper; CTranslate2 backend (no PyTorch); works CPU and CUDA 12 GPU |
| openai (SDK) | 2.31.0 | OpenRouter API client | OpenRouter is OpenAI-API-compatible; `base_url="https://openrouter.ai/api/v1"`; full async support |
| instructor | 1.15.1 | Structured LLM output | Pydantic-validated LLM output with retry-on-schema-failure; works with OpenRouter via openai SDK |
| Pydantic | 2.13.0 | Data validation + schemas | Powers instructor; defines `TradingLogicExtraction`, `TranscriptArtifact` dataclasses; V2 required (instructor uses V2) |
| pydantic-settings | 2.11.0 | Config + env management | Typed settings class loading `OPENROUTER_API_KEY`, model names from `.env`; replaces raw python-dotenv |
| uv | latest | Dependency management | 10-100x faster than pip; lockfile semantics via `uv.lock`; `pyproject.toml` with Python version pinning |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tenacity | latest | Retry logic for API calls | Wrap all OpenRouter calls with `@retry(wait=wait_exponential(...))`; handles 429 and transient errors |
| loguru | 0.7.x | Structured logging | Per-stage log output to file; audit trail for batch debugging; simpler than stdlib logging |
| langdetect | latest | Source language detection | Detect transcript language before deciding whether to translate; use before translation stage |

### Model

| Asset | Identifier | Purpose | Notes |
|-------|-----------|---------|-------|
| Belle-whisper (faster-whisper) | `Huan69/Belle-whisper-large-v3-zh-punct-fasterwhisper` | Chinese ASR | CTranslate2-converted variant; downloaded from HuggingFace on first use (~3 GB); punctuation variant reduces hallucination |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| youtube-transcript-api | yt-dlp `--write-subs` | transcript-api returns structured Python objects directly; yt-dlp writes SRT files to disk — more steps, no benefit for this use case |
| faster-whisper | openai/whisper | Never: openai/whisper requires PyTorch (~2 GB), is 4x slower, same accuracy |
| instructor | LangChain structured output | instructor is lighter and more reliable for pure extraction; LangChain adds abstraction layers for no gain |
| langdetect | LLM language detection | langdetect is free, instant, no API call; use LLM only if langdetect fails on a specific transcript |
| deepl/googletrans | Translation MT tools | MT tools mangle trading idioms; LLM translation with glossary injection is required for accuracy |

**Installation:**
```bash
# Create project
uv init yt-to-skill
cd yt-to-skill

# Core phase 1 dependencies
uv add yt-dlp youtube-transcript-api faster-whisper openai instructor pydantic pydantic-settings
uv add tenacity loguru langdetect

# Dev dependencies
uv add --dev pytest ruff mypy

# System dependency (not pip) — yt-dlp muxing requires system ffmpeg
brew install ffmpeg  # macOS

# Belle-whisper downloads on first faster-whisper use — no manual install needed
```

---

## Architecture Patterns

### Recommended Project Structure (Phase 1 scope)

```
yt_to_skill/
├── cli.py                      # Typer entry point (Phase 2 — stub only in Phase 1)
├── orchestrator.py             # Stage runner, artifact guard, error handling
├── config.py                   # pydantic-settings config + PipelineConfig dataclass
│
├── stages/
│   ├── __init__.py
│   ├── base.py                 # Stage protocol: run(video_id, work_dir, config) -> Path
│   ├── ingest.py               # yt-dlp metadata fetch + lazy video/audio download
│   ├── transcript.py           # youtube-transcript-api + faster-whisper fallback
│   ├── filter.py               # Two-stage non-strategy filter
│   ├── translate.py            # Language detection + OpenRouter translation
│   └── extract.py              # OpenRouter LLM + instructor + Pydantic schema
│
├── models/
│   ├── __init__.py
│   ├── artifacts.py            # Dataclasses: VideoMetadata, TranscriptArtifact, etc.
│   └── extraction.py           # Pydantic: TradingLogicExtraction, StrategyObject
│
├── llm/
│   ├── __init__.py
│   ├── client.py               # OpenRouter wrapper (openai SDK base_url)
│   └── prompts/
│       ├── translate.txt       # Translation prompt with glossary injection slot
│       ├── filter_content.txt  # Non-strategy classification prompt
│       └── extract_trading.txt # Trading logic extraction prompt
│
├── glossary/
│   └── trading_zh_en.json      # 50-100 Chinese-English trading term pairs
│
└── work/                       # Auto-created; gitignored
    └── <video_id>/
        ├── metadata.json
        ├── raw_transcript.json
        ├── translated.txt
        ├── filter_result.json
        └── extracted_logic.json
```

### Pattern 1: Stage-as-Function with Artifact Guard

**What:** Each stage is a function `run(video_id: str, work_dir: Path, config: Config) -> Path`. Before executing, it checks whether its output artifact exists. If it does, it returns immediately (cache hit). The Orchestrator calls stages in sequence.

**When to use:** Every stage in this pipeline — transcript extraction, translation, and LLM extraction are all expensive (API calls, model inference). This pattern makes the pipeline resumable at any stage boundary.

**Example:**
```python
# stages/translate.py
def run(video_id: str, work_dir: Path, config: Config) -> Path:
    output = work_dir / "translated.txt"
    if output.exists():
        return output  # cache hit — skip
    raw_transcript = json.loads((work_dir / "raw_transcript.json").read_text())
    translated = llm_client.translate(raw_transcript, glossary=config.glossary)
    output.write_text(translated)
    return output
```

### Pattern 2: Typed Artifacts via Dataclasses

**What:** Each stage output is a typed dataclass, serialized to JSON. The next stage deserializes into the typed object — not a raw dict. Serialization is explicit via `dataclasses.asdict()` or `pydantic.model_dump()`.

**Example:**
```python
# models/artifacts.py
@dataclass
class TranscriptArtifact:
    video_id: str
    source_language: str
    segments: list[dict]  # [{start, end, text}]
    method: Literal["captions", "whisper"]
    caption_quality: Literal["good", "poor", "missing"]
```

### Pattern 3: Pydantic-Validated LLM Output via instructor

**What:** The extraction stage uses `instructor.from_openai(client).chat.completions.create(response_model=TradingLogicExtraction, ...)`. If the LLM response fails schema validation, instructor automatically retries with an error message appended to the conversation.

**Example:**
```python
# models/extraction.py
class EntryCondition(BaseModel):
    indicator: str
    condition: str
    value: str | None = None         # None = REQUIRES_SPECIFICATION
    timeframe: str | None = None
    raw_text: str                     # always populated as fallback

class StrategyObject(BaseModel):
    strategy_name: str
    market_conditions: list[str]
    entry_criteria: list[EntryCondition]
    exit_criteria: list[EntryCondition]
    indicators: list[str]
    risk_rules: list[str]
    unspecified_params: list[str]     # paths like "entry_criteria[0].value"

class TradingLogicExtraction(BaseModel):
    strategies: list[StrategyObject]  # array — some videos have aggressive/conservative variants
    video_id: str
    source_language: str
    is_strategy_content: bool
```

### Pattern 4: Caption Quality Heuristics

**What:** After fetching captions via youtube-transcript-api, apply quality heuristics before deciding the Whisper fallback is needed. Poor auto-captions from Chinese channels often look like: many short segments (<3 words), high ratio of `[Music]` or `[Applause]` tags, or a total character count far too low for the video duration.

**Example:**
```python
def is_caption_quality_acceptable(segments: list[dict], video_duration_s: float) -> bool:
    total_chars = sum(len(s["text"]) for s in segments)
    music_tag_ratio = sum(1 for s in segments if "[Music]" in s["text"]) / max(len(segments), 1)
    short_segment_ratio = sum(1 for s in segments if len(s["text"].split()) < 3) / max(len(segments), 1)

    expected_min_chars = video_duration_s * 2  # rough: 2 chars/sec minimum for speech

    if total_chars < expected_min_chars:
        return False
    if music_tag_ratio > 0.3:
        return False
    if short_segment_ratio > 0.6:
        return False
    return True
```

### Pattern 5: Two-Stage Non-Strategy Filter

**What:** Before expensive LLM extraction, gate the video with two cheap checks. Stage 1 is metadata pre-filter (title + description keyword score — fast, free). Stage 2 is transcript sample classification (first 500 words via LLM or keyword set). If both fail to confirm strategy content, skip the video.

**When to use:** Required before every extraction call. At channel scale, vlogs and news commentary represent significant wasted LLM tokens if unfiltered.

**Implementation recommendation (Claude's discretion area):** Use keyword heuristics for Stage 1 (fast, no API cost), and a lightweight LLM classification call for Stage 2 with a short prompt like "Does this transcript excerpt describe a specific trading strategy with entry/exit rules? Reply: STRATEGY or NOT_STRATEGY." This gives the strict threshold the user requested without rule brittleness.

### Anti-Patterns to Avoid

- **Monolithic `process_video()` function:** One function doing all stages = no resumption, no testability. Use separate stage functions with artifact guards.
- **Downloading video unconditionally:** Most YouTube trading videos have captions. Try caption extraction first; only download audio when captions fail or are poor quality.
- **Parsing LLM output with regex:** Use `instructor` + Pydantic schema validation. Regex breaks on model output variation; silent data loss when fields are missing.
- **Not setting `max_tokens` on LLM calls:** Long transcript prompts can generate multi-thousand-token outputs; uncapped calls produce surprise OpenRouter bills.
- **Loading Belle-whisper model per video:** Model load time is 5-15 seconds on CPU. Load once at process start, reuse across all videos in a session.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured LLM output parsing | Custom JSON parser + regex | `instructor` 1.15.1 | instructor handles retry-on-schema-failure, partial output recovery, and model-specific quirks |
| LLM API retry logic | Custom retry loop with sleep | `tenacity` with `wait_exponential` | tenacity handles jitter, backoff ceilings, exception filtering, and logging correctly |
| Typed config from `.env` | Raw `os.getenv()` calls | `pydantic-settings` | Typed validation, default values, clear error messages on missing required keys |
| Caption extraction | Direct YouTube API calls or HTML scraping | `youtube-transcript-api` | Handles auth edge cases, language fallback ordering, auto vs. manual caption disambiguation |
| Chinese ASR | Training a custom model or using online APIs | `faster-whisper` + Belle model | Belle-whisper-large-v3-zh-punct is purpose-built for this exact use case; local, no API cost |
| Audio decoding for Whisper | Direct ffmpeg subprocess calls | `PyAV` (auto via faster-whisper) | faster-whisper handles audio decoding internally via PyAV; no separate audio extraction step needed for ASR path |

**Key insight:** The transcript-to-structured-extraction problem is well-solved by the instructor + Pydantic + OpenRouter combination. Every attempt to build custom parsing around LLM output eventually encounters the same failure modes (model output variation, missing fields, partial JSON) that instructor already handles.

---

## Common Pitfalls

### Pitfall 1: Chinese Auto-Captions Frequently Absent or Garbled

**What goes wrong:** `youtube-transcript-api` raises `TranscriptsDisabled`, `NoTranscriptAvailable`, or `VideoUnavailable` for a significant fraction of Chinese trading videos. Many Mandarin-language channels publish without any captions; YouTube's auto-caption engine struggles with tonal languages.

**Why it happens:** Developers test against English videos which reliably have auto-generated captions. Target channel (Trader Feng Ge) is exactly the problematic category.

**How to avoid:**
- Wire Whisper fallback in the same phase as caption extraction — not deferred
- Catch the full `youtube-transcript-api` exception hierarchy: `TranscriptsDisabled`, `NoTranscriptAvailable`, `VideoUnavailable`
- Apply caption quality heuristics after a successful fetch (short/repeated segments, Music tags) to trigger Whisper even when captions "exist"
- Probe 10-20 target channel videos before committing to caption-first vs. Whisper-first

**Warning signs:** `TranscriptsDisabled` errors without a fallback branch firing; transcripts shorter than 200 characters for 10+ minute videos.

### Pitfall 2: Whisper Hallucination on Intro Jingles and Music

**What goes wrong:** `faster-whisper` hallucinations on non-speech audio segments (branded intro music, transition sounds) — it outputs plausible-sounding Chinese text that was never spoken. This inserts fabricated content at the start of transcripts.

**Why it happens:** Whisper models are trained to produce text, not to abstain. Given ambiguous audio they generate the most probable sequence.

**How to avoid:**
- Always enable `vad_filter=True` in faster-whisper calls — this strips non-speech segments before transcription
- Use the punctuation variant `Belle-whisper-large-v3-zh-punct` — produces more coherent output, lower hallucination rate
- Post-transcription: flag segments with unusually high repetition rate (same phrase 3+ times consecutively)

**Warning signs:** Transcript begins with repeated phrases; transcript length wildly mismatches video duration; same phrase appears 3+ consecutive times.

### Pitfall 3: Trading Terminology Mistranslation Corrupting Downstream Extraction

**What goes wrong:** General-purpose LLM translation optimizes for fluency, not domain fidelity. "多头" → "long position" is correct; a naive translation might produce "multiple heads" or "bull" depending on context. Corrupted translation means corrupted extraction means corrupted `extracted_logic.json`.

**Why it happens:** Without explicit instruction, the LLM picks the most common English word sense, not the trading-specific term.

**How to avoid:**
- Build the 50-100 term glossary BEFORE the first extraction run (STATE.md blocker — acknowledged)
- Inject glossary into translation system prompt: "The following term pairs MUST be translated using the English form exactly as specified: ..."
- LLM-augmented approach: instruct the translation LLM to flag trading terms not in the glossary for later addition
- A high `REQUIRES_SPECIFICATION` rate (>40% of fields) in extraction output is often a symptom of bad translation, not vague source content

**Warning signs:** `REQUIRES_SPECIFICATION` rate >40% on videos known to have specific parameters; SKILL.md entry criteria using vague directional language ("open position") instead of "buy"/"sell".

### Pitfall 4: LLM Hallucinating Specific Parameters Not in Source

**What goes wrong:** When asked to extract structured trading rules, the LLM fills in specific numeric values (e.g., "stop loss at 2%", "RSI threshold 65") that were never stated in the transcript.

**Why it happens:** LLMs are trained to produce complete, coherent outputs. Schema fields with required numeric types incentivize fabrication over absence.

**How to avoid:**
- Every numeric field in `TradingLogicExtraction` must be explicitly `Optional[str]` with `None` as the unspecified sentinel
- Extraction prompt must include: "If a parameter was NOT explicitly stated in the transcript, you MUST return null. Do NOT infer, estimate, or assume values."
- Set extraction temperature to 0
- The `unspecified_params` top-level array lists all paths to null fields — makes gaps visible

**Warning signs:** Zero `REQUIRES_SPECIFICATION` / null fields across multiple videos; round numbers (2%, 5%, 10%) in stop-loss fields consistently; numeric values that can't be found in the translated transcript text.

### Pitfall 5: OpenRouter Structured Output Silently Dropped for Unsupported Models

**What goes wrong:** When `response_format: {type: "json_schema", ...}` is passed to a model that doesn't support structured output via OpenRouter, the schema constraint is silently dropped. Code that parses the free-text response as the expected schema fails or produces malformed data.

**Why it happens:** Structured output support is model-specific on OpenRouter; no programmatic per-model capability flag exists (as of 2026).

**How to avoid:**
- Use `instructor` — it provides retry-on-schema-failure regardless of whether the model natively supports `json_schema` mode
- Maintain an allowlist of model IDs confirmed to support structured output (Claude 3.x, GPT-4o, Gemini 2.x, Mistral Large are known-good)
- Always set `max_tokens` on every call to prevent unbounded billing
- Log model ID, token count, and stage name for every LLM call

**Warning signs:** Parsing errors that only appear when the model is swapped; list fields returning as strings; no JSON in response despite `response_format` being set.

### Pitfall 6: yt-dlp Bot Detection During Audio Download

**What goes wrong:** YouTube temporarily blocks IPs running yt-dlp without authentication cookies, especially with aggressive retry settings. The "Sign in to confirm you're not a bot" wall fails the download with no useful error message.

**Why it happens:** yt-dlp's default `fragment-retries` (10) sends burst traffic that triggers YouTube's anti-abuse systems.

**How to avoid:**
- Use `--format bestaudio` or `--format worstaudio` (not `best`) when only audio is needed for Whisper — saves 5-10x bandwidth and reduces request profile
- Support `--cookies-from-browser` or cookies file as optional config for authenticated downloads
- Lower `fragment-retries` to 3 in the yt-dlp options dict
- Add random jitter (2-8 seconds) between download attempts

**Warning signs:** "Sign in to confirm you're not a bot" in yt-dlp output; downloads failing after several consecutive videos.

---

## Code Examples

### Caption Extraction with Full Exception Handling

```python
# stages/transcript.py
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptAvailable,
    VideoUnavailable,
)

def fetch_captions(video_id: str, language_priority: list[str]) -> tuple[list[dict], str] | None:
    """Returns (segments, language_code) or None if unavailable."""
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        # Try manual captions first, then auto-generated
        for lang in language_priority:
            try:
                transcript = transcript_list.find_transcript([lang])
                segments = transcript.fetch()
                return [{"start": s.start, "end": s.start + s.duration, "text": s.text}
                        for s in segments], transcript.language_code
            except Exception:
                continue
        # Fallback: get any available transcript
        for transcript in transcript_list:
            segments = transcript.fetch()
            return [{"start": s.start, "end": s.start + s.duration, "text": s.text}
                    for s in segments], transcript.language_code
    except (TranscriptsDisabled, NoTranscriptAvailable, VideoUnavailable):
        return None  # triggers Whisper fallback
```

### Belle-whisper Transcription (loaded once, reused)

```python
# stages/transcript.py — Whisper fallback
from faster_whisper import WhisperModel

_whisper_model: WhisperModel | None = None

def get_whisper_model(device: str = "cpu") -> WhisperModel:
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = WhisperModel(
            "Huan69/Belle-whisper-large-v3-zh-punct-fasterwhisper",
            device=device,
            compute_type="int8",
        )
    return _whisper_model

def transcribe_audio(audio_path: Path, device: str = "cpu") -> list[dict]:
    model = get_whisper_model(device)
    segments, info = model.transcribe(
        str(audio_path),
        language="zh",
        task="transcribe",
        vad_filter=True,        # REQUIRED: strips non-speech, suppresses hallucination
        beam_size=5,
    )
    return [{"start": s.start, "end": s.end, "text": s.text} for s in segments]
```

### OpenRouter Client Wrapper

```python
# llm/client.py
from openai import OpenAI
import instructor
from models.extraction import TradingLogicExtraction

def make_openai_client(api_key: str) -> OpenAI:
    return OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )

def make_instructor_client(api_key: str):
    return instructor.from_openai(make_openai_client(api_key))

def extract_trading_logic(
    client,  # instructor client
    translated_text: str,
    model: str = "anthropic/claude-3-5-sonnet",  # known-good for json_schema
    max_tokens: int = 4096,
) -> TradingLogicExtraction:
    return client.chat.completions.create(
        model=model,
        response_model=TradingLogicExtraction,
        max_tokens=max_tokens,  # REQUIRED: always cap tokens
        temperature=0,           # REQUIRED: deterministic extraction
        messages=[
            {"role": "system", "content": open("llm/prompts/extract_trading.txt").read()},
            {"role": "user", "content": translated_text},
        ],
    )
```

### Glossary Injection in Translation Prompt

```python
# stages/translate.py
import json
from pathlib import Path

def build_translation_prompt(glossary_path: Path) -> str:
    glossary = json.loads(glossary_path.read_text())
    term_list = "\n".join(f"- {zh}: {en}" for zh, en in glossary.items())
    return f"""Translate the following Chinese trading video transcript to English.

CRITICAL TRADING TERMINOLOGY — translate these terms EXACTLY as specified:
{term_list}

Rules:
1. If a Chinese term matches a glossary entry, use the English form exactly as listed.
2. If you encounter a trading term NOT in the glossary that you believe has a standard English equivalent, append it to a section at the end: GLOSSARY_ADDITIONS: <term>: <english>
3. Preserve all timestamps and segment structure.
4. Do NOT paraphrase trading concepts — translate literally and technically."""
```

### yt-dlp Lazy Audio Download

```python
# stages/ingest.py
import yt_dlp

def download_audio_for_whisper(video_id: str, work_dir: Path) -> Path:
    """Download audio only when Whisper fallback is needed."""
    audio_path = work_dir / "audio.m4a"
    if audio_path.exists():
        return audio_path

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(work_dir / "audio.%(ext)s"),
        "fragment-retries": 3,          # lower than default 10 to reduce bot detection
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [],           # no conversion — keep native format for faster-whisper
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

    # Find the downloaded file (extension may vary)
    for f in work_dir.glob("audio.*"):
        return f
    raise FileNotFoundError(f"Audio download failed for {video_id}")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| openai/whisper (PyTorch) | faster-whisper (CTranslate2) | 2023 | 4x speed, 70% less memory, no PyTorch dependency |
| requirements.txt + pip | pyproject.toml + uv | 2024-2025 | 100x faster installs, lockfile semantics, Python version pinning |
| Direct OpenAI API | OpenRouter as unified gateway | 2024 | Single API key, model flexibility, no vendor lock-in |
| LangChain structured output | instructor + Pydantic v2 | 2024 | Lighter dependency, more reliable schema enforcement, retry-on-parse-error |
| Single-language transcript extraction | Language-agnostic with priority list | This project | Handles mixed-language channels, not just Chinese-only |

**Deprecated/outdated for this project:**
- `pytube` / `pytubefix`: Fragile, breaks when YouTube changes frontend; yt-dlp is the only reliable option
- `openai/whisper` (original): Pulls PyTorch; strictly inferior to faster-whisper for this use case
- `requirements.txt`: No lockfile semantics; use pyproject.toml + uv.lock
- Direct API calls to `deepl` or `googletrans`: MT tools mangle trading idioms; OpenRouter LLM with glossary is required
- `ffmpeg-python` (pip): Only a wrapper, not binaries; use system ffmpeg via Homebrew

---

## Open Questions

1. **Caption availability rate on Trader Feng Ge channel**
   - What we know: "Significant fraction" of Chinese trading channels have no captions; Whisper fallback is required
   - What's unclear: The specific rate for this channel — could be 20% or 80% needing Whisper
   - Recommendation: Probe 10-20 channel videos in Wave 0 (a quick script using youtube-transcript-api before full pipeline implementation); this determines whether caption-first is optimal or whether lazy download should have low latency

2. **Glossary term coverage for Trader Feng Ge content**
   - What we know: 50-100 terms required; BTC/crypto focus; sources are OKX/Binance Chinese docs, Investopedia Chinese
   - What's unclear: Whether the initial 50-100 terms cover Feng Ge's specific idioms and indicator naming conventions
   - Recommendation: Seed glossary with 50 core terms from verified sources, then run LLM-augmented expansion on 3-5 real transcripts before the extraction stage is considered production-ready

3. **Audio-only vs full video download for Whisper path**
   - What we know: `bestaudio` format is significantly smaller than full video; faster-whisper accepts audio files directly
   - What's unclear: Whether yt-dlp with `bestaudio` consistently works for Trader Feng Ge's video format mix
   - Recommendation (Claude's discretion): Download audio-only (`bestaudio`); if any video format causes faster-whisper to fail, add a conversion step via ffmpeg; the bandwidth savings are substantial enough to justify this as the default

4. **Filter implementation: LLM vs. heuristics for Stage 2**
   - What we know: Two-stage filter is locked; Stage 1 is metadata keyword heuristics; Stage 2 implementation is Claude's discretion
   - Recommendation (Claude's discretion): Stage 2 should use a cheap LLM classification call (short prompt, small model like `mistral-7b-instruct` via OpenRouter, ~200-token input) on the first 500 words of the transcript. This is more robust than keyword matching against Chinese terms and gives a confidence score. Cost: ~$0.0001 per video — negligible compared to extraction cost.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (to be installed) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` section — Wave 0 |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INPT-01 | Caption extraction returns segments for a video with captions | unit (mock youtube-transcript-api) | `pytest tests/test_transcript.py::test_caption_fetch -x` | Wave 0 |
| INPT-01 | Caption quality heuristics flag garbled captions correctly | unit | `pytest tests/test_transcript.py::test_caption_quality_heuristics -x` | Wave 0 |
| INPT-02 | Whisper fallback fires when captions unavailable | unit (mock TranscriptsDisabled) | `pytest tests/test_transcript.py::test_whisper_fallback_triggered -x` | Wave 0 |
| INPT-02 | `vad_filter=True` is set in Whisper call | unit (mock faster-whisper) | `pytest tests/test_transcript.py::test_whisper_vad_enabled -x` | Wave 0 |
| INPT-03 | yt-dlp download uses `bestaudio` format | unit (mock yt-dlp) | `pytest tests/test_ingest.py::test_audio_format_selection -x` | Wave 0 |
| INPT-05 | Stage skips execution when output artifact exists | unit | `pytest tests/test_orchestrator.py::test_artifact_guard -x` | Wave 0 |
| EXTR-01 | Translation prompt includes glossary terms | unit | `pytest tests/test_translate.py::test_glossary_injection -x` | Wave 0 |
| EXTR-01 | Translation stage skips if `translated.txt` exists | unit | `pytest tests/test_translate.py::test_translate_cache_hit -x` | Wave 0 |
| EXTR-02 | Extraction schema validates a well-formed LLM response | unit (Pydantic) | `pytest tests/test_models.py::test_extraction_schema_valid -x` | Wave 0 |
| EXTR-02 | Extraction schema rejects a response missing required fields | unit (Pydantic) | `pytest tests/test_models.py::test_extraction_schema_invalid -x` | Wave 0 |
| EXTR-03 | Null fields serialize to `unspecified_params` list | unit | `pytest tests/test_models.py::test_requires_specification_mapping -x` | Wave 0 |
| EXTR-04 | Metadata pre-filter rejects obvious non-strategy title | unit | `pytest tests/test_filter.py::test_metadata_prefilter_rejects -x` | Wave 0 |
| EXTR-04 | Metadata pre-filter passes a strategy-sounding title | unit | `pytest tests/test_filter.py::test_metadata_prefilter_passes -x` | Wave 0 |
| INFR-01 | OpenRouter client uses correct `base_url` | unit | `pytest tests/test_llm_client.py::test_openrouter_base_url -x` | Wave 0 |
| INFR-01 | All LLM calls go through `llm/client.py` (no direct openai imports in stages) | static analysis / unit | `pytest tests/test_llm_client.py::test_no_direct_openai_in_stages -x` | Wave 0 |
| INFR-02 | Each stage writes artifact to correct `work/<video_id>/` path | unit | `pytest tests/test_stages.py::test_artifact_output_paths -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q` (fast unit tests only, <10 seconds)
- **Per wave merge:** `pytest tests/ -v` (full suite)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/__init__.py` — package init
- [ ] `tests/conftest.py` — shared fixtures: `tmp_work_dir`, `mock_video_id`, `sample_transcript_segments`, `sample_extraction_result`
- [ ] `tests/test_transcript.py` — covers INPT-01, INPT-02
- [ ] `tests/test_ingest.py` — covers INPT-03
- [ ] `tests/test_orchestrator.py` — covers INPT-05
- [ ] `tests/test_translate.py` — covers EXTR-01
- [ ] `tests/test_models.py` — covers EXTR-02, EXTR-03
- [ ] `tests/test_filter.py` — covers EXTR-04
- [ ] `tests/test_llm_client.py` — covers INFR-01
- [ ] `tests/test_stages.py` — covers INFR-02
- [ ] Framework install: `uv add --dev pytest ruff mypy` — if none detected
- [ ] `pyproject.toml` test config: `[tool.pytest.ini_options] testpaths = ["tests"]`

---

## Sources

### Primary (HIGH confidence)
- `.planning/research/STACK.md` — full version table verified against PyPI; Python 3.11 requirement; installation commands
- `.planning/research/ARCHITECTURE.md` — stage-as-function pattern; project structure; data flow diagrams; anti-patterns; integration boundaries
- `.planning/research/PITFALLS.md` — pitfalls 1-5 directly apply to Phase 1; prevention strategies and warning signs
- `.planning/research/FEATURES.md` — feature dependency graph; MVP definition; Phase 1 requirements coverage
- `.planning/research/SUMMARY.md` — executive summary; research gaps; confidence assessment
- [youtube-transcript-api 1.2.4 — PyPI](https://pypi.org/project/youtube-transcript-api/) — exception hierarchy, language codes, no-auth behavior
- [faster-whisper 1.2.1 — PyPI](https://pypi.org/project/faster-whisper/) — `vad_filter`, `WhisperModel` API, CTranslate2 backend
- [openai SDK 2.31.0 — PyPI](https://pypi.org/project/openai/) — `base_url` OpenRouter pattern
- [instructor 1.15.1 — PyPI](https://pypi.org/project/instructor/) + [OpenRouter integration](https://python.useinstructor.com/integrations/openrouter/)
- [OpenRouter Structured Outputs documentation](https://openrouter.ai/docs/guides/features/structured-outputs) — json_schema per-model support
- [Huan69/Belle-whisper-large-v3-zh-punct-fasterwhisper — HuggingFace](https://huggingface.co/Huan69/Belle-whisper-large-v3-zh-punct-fasterwhisper)

### Secondary (MEDIUM confidence)
- [yt-dlp bot detection — GitHub issues #15899, #13067](https://github.com/yt-dlp/yt-dlp/issues/15899) — `fragment-retries` behavior, cookie-auth mitigation
- [Towards reducing hallucination in financial report extraction — arXiv](https://arxiv.org/html/2310.10760) — REQUIRES_SPECIFICATION mechanism rationale

### Tertiary (LOW confidence)
- Belle-whisper hallucination characteristics on intro audio — from model card descriptions; empirical validation needed on Trader Feng Ge intro patterns

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified against PyPI; compatibility matrix explicit in prior research
- Architecture: HIGH — stage-as-function pattern is well-documented; build order logically derived from dependencies
- Pitfalls: HIGH for pitfalls 1-5 (directly verified); MEDIUM for Whisper hallucination on target channel intro specifically (LOW confidence on channel-specific behavior)
- Validation architecture: HIGH — pytest patterns are standard; test map is directly derived from requirement IDs

**Research date:** 2026-04-14
**Valid until:** 2026-05-14 (stable stack — yt-dlp version pins may need updating if YouTube changes break it; OpenRouter model allowlist may need updating as new models launch)
