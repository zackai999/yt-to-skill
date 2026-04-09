# Architecture Research

**Domain:** YouTube-to-Skill — video processing + LLM extraction pipeline (Python CLI)
**Researched:** 2026-04-13
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         CLI Entry Point                           │
│              yt-to-skill <url> [--domain] [--lang]               │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│                        Pipeline Orchestrator                      │
│   Drives stage sequence, checks stage cache, handles retries,    │
│   writes/reads intermediate artifacts from work directory.       │
└──────┬───────────┬──────────┬────────────┬────────┬─────────────┘
       │           │          │            │        │
┌──────▼──┐  ┌─────▼──┐  ┌───▼────┐  ┌───▼────┐  ┌▼──────────┐
│ Ingest  │  │Transcr. │  │Transl. │  │ Vision │  │Extraction │
│ Stage   │  │ Stage   │  │ Stage  │  │ Stage  │  │  Stage    │
│         │  │         │  │        │  │        │  │           │
│yt-dlp   │  │YT API   │  │OpenRtr │  │yt-dlp  │  │OpenRouter │
│metadata │  │+Whisper │  │LLM     │  │+PyScene│  │LLM        │
│+video   │  │fallback │  │        │  │Detect  │  │           │
└────┬────┘  └────┬────┘  └───┬────┘  └───┬────┘  └─────┬─────┘
     │            │           │           │             │
┌────▼────────────▼───────────▼───────────▼─────────────▼─────────┐
│                    Artifact Store (local filesystem)             │
│  work/<video_id>/                                                │
│    metadata.json   raw_transcript.json   translated.txt          │
│    video.mp4       keyframes/            extracted_logic.json    │
└──────────────────────────────────────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│                        Renderer Stage                            │
│         Assembles SKILL.md from extracted_logic.json +           │
│         keyframe paths using Jinja2 templates.                   │
└──────────────────────────────┬───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│                        Output Directory                          │
│  skills/<video_id>/                                              │
│    SKILL.md          assets/frame_001.png  scripts/backtest.py  │
└──────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Key Libraries |
|-----------|----------------|---------------|
| CLI Entry Point | Parses args, resolves URL type (single/playlist/channel), invokes Orchestrator | Click or Typer |
| Pipeline Orchestrator | Stage sequencing, cache checking, retry logic, progress reporting | Custom — no framework needed at this scale |
| Ingest Stage | Resolves video IDs from URL, downloads video file and metadata JSON | yt-dlp |
| Transcript Stage | Fetches captions via YouTube API; falls back to Whisper on missing captions | youtube-transcript-api, faster-whisper (Belle model) |
| Translation Stage | Detects source language; calls OpenRouter LLM to translate Chinese → English | OpenRouter (OpenAI-compatible SDK), langdetect |
| Vision Stage | Scene-change detection, keyframe extraction, saved as PNG assets | PySceneDetect, OpenCV |
| Extraction Stage | Structured trading logic extraction from translated transcript + keyframe context | OpenRouter LLM, Pydantic, instructor |
| Renderer Stage | Fills SKILL.md Jinja2 template with extracted data | Jinja2 |
| Artifact Store | Filesystem-backed stage outputs; presence = stage complete (enables resumption) | pathlib |
| Config System | Domain profiles (trading, general) and language profiles (zh, en) as YAML files | PyYAML, dataclasses |

## Recommended Project Structure

```
yt_to_skill/
├── cli.py                    # Click/Typer entry point; URL → Orchestrator
├── orchestrator.py           # Stage runner, cache check, batch loop
├── config.py                 # Config dataclasses + YAML loader
│
├── stages/
│   ├── __init__.py
│   ├── base.py               # Stage protocol / abstract base class
│   ├── ingest.py             # yt-dlp metadata + video download
│   ├── transcript.py         # youtube-transcript-api + Whisper fallback
│   ├── translate.py          # Language detect + OpenRouter translation
│   ├── vision.py             # PySceneDetect + keyframe save
│   ├── extraction.py         # OpenRouter LLM structured extraction
│   └── render.py             # Jinja2 SKILL.md assembly
│
├── models/
│   ├── __init__.py
│   ├── artifacts.py          # Dataclasses for each stage's output
│   └── extraction.py         # Pydantic schemas for LLM structured output
│
├── llm/
│   ├── __init__.py
│   ├── client.py             # OpenRouter API wrapper (OpenAI SDK base)
│   └── prompts/
│       ├── translate.txt
│       ├── extract_trading.txt   # Domain prompt — trading
│       └── filter_content.txt    # Content filter prompt
│
├── templates/
│   └── skill.md.j2           # Jinja2 SKILL.md template
│
├── config/
│   ├── domains/
│   │   └── trading.yaml      # Domain-specific extraction schema + prompts
│   └── languages/
│       └── zh.yaml           # Language-specific Whisper model + translation hints
│
└── work/                     # Auto-created; gitignored
    └── <video_id>/
        ├── metadata.json
        ├── raw_transcript.json
        ├── translated.txt
        ├── video.mp4
        ├── keyframes/
        │   └── frame_001.png
        └── extracted_logic.json
```

### Structure Rationale

- **stages/:** Each stage is an independent unit. Adding a new stage (e.g., audio-only extraction) means adding one file without touching others.
- **models/artifacts.py:** Typed dataclasses define what each stage emits and what the next stage expects. This is the contract between stages — not function signatures.
- **models/extraction.py:** Pydantic schemas live separately from stage logic so they can be versioned and swapped without touching pipeline orchestration.
- **llm/prompts/:** Plain-text prompt files (not hardcoded strings) make prompt iteration fast and diff-friendly in git.
- **config/domains/ and config/languages/:** YAML overrides for domain and language let you add a new domain (e.g., equities, options) or language (e.g., Japanese) without touching Python code.
- **work/:** Intermediate artifacts on disk. Stage presence check: `if (work_dir / "translated.txt").exists(): skip`. This is the cheapest resumption mechanism.

## Architectural Patterns

### Pattern 1: Stage-as-Function with Artifact Guard

**What:** Each stage is a pure function `run(video_id, work_dir, config) -> ArtifactPath`. Before executing, it checks whether its output artifact already exists on disk. If it does, it returns immediately (cache hit). The Orchestrator calls stages in sequence and short-circuits on cache hits.

**When to use:** Any multi-step pipeline where steps are expensive (API calls, model inference, video download). This is the right pattern here — every stage costs time or money.

**Trade-offs:** Simple to implement and debug. Works perfectly for a local CLI. Not suitable for distributed or parallel execution (use a DAG framework like Prefect/Dagster if that becomes a requirement).

**Example:**
```python
# stages/translate.py
def run(video_id: str, work_dir: Path, config: Config) -> Path:
    output = work_dir / "translated.txt"
    if output.exists():
        return output  # already done — skip
    raw = (work_dir / "raw_transcript.json").read_text()
    translated = llm_client.translate(raw, source_lang=config.language)
    output.write_text(translated)
    return output
```

### Pattern 2: Typed Artifacts via Dataclasses

**What:** Each stage output is a typed dataclass loaded from the artifact file. The next stage receives a typed object, not a raw dict or file path. Serialization is explicit (JSON via `dataclasses.asdict` or `pydantic.model_dump`).

**When to use:** Whenever stage N passes data to stage N+1. Avoids implicit coupling through shared file formats — the dataclass is the contract.

**Trade-offs:** Small overhead to write serialization. Pays off immediately when debugging — you can inspect any intermediate artifact as a valid typed object.

**Example:**
```python
# models/artifacts.py
@dataclass
class TranscriptArtifact:
    video_id: str
    source_language: str
    segments: list[dict]  # [{start, end, text}]
    method: Literal["captions", "whisper"]
```

### Pattern 3: Pydantic-Validated LLM Output

**What:** The extraction stage sends a prompt to OpenRouter and requests a response matching a Pydantic schema (via `response_format: json_schema` or the `instructor` library). The LLM response is parsed and validated against `TradingLogicExtraction` before being written to disk.

**When to use:** Whenever you need structured data from an LLM. Using raw string parsing on LLM output is fragile. Pydantic gives you validation, default values, and clear error messages.

**Trade-offs:** Adds instructor/pydantic dependency. Some OpenRouter models don't support structured outputs (check model list). Fallback: use `json_object` mode and validate manually.

**Example:**
```python
# models/extraction.py
class TradingLogicExtraction(BaseModel):
    strategy_name: str
    market_conditions: list[str]
    entry_criteria: list[str]
    exit_criteria: list[str]
    indicators: list[str]
    risk_rules: list[str]
    requires_specification: list[str]  # REQUIRES_SPECIFICATION flags
    is_strategy_content: bool  # False = skip (clickbait/news)
```

### Pattern 4: Domain + Language Config Profiles

**What:** Domain profiles (trading, general) and language profiles (zh, en) are YAML files loaded at startup. A domain profile specifies: extraction Pydantic schema to use, prompt file, SKILL.md template variant, and content-filter criteria. A language profile specifies: Whisper model to use, translation prompt, and any special terminology hints.

**When to use:** When extensibility to new domains or languages is a first-class requirement (as it is here). Avoids conditionals like `if domain == "trading"` scattered through the codebase.

**Trade-offs:** Adds YAML indirection. The payoff is adding a new domain without touching Python — just add a YAML file and a prompt.

## Data Flow

### Single-Video Flow

```
CLI: yt-to-skill https://youtube.com/watch?v=XYZ
    ↓
Orchestrator resolves video_id = "XYZ"
    ↓
Stage: Ingest
  yt-dlp → work/XYZ/metadata.json, work/XYZ/video.mp4
    ↓
Stage: Transcript
  youtube-transcript-api → raw_transcript.json (cache hit → skip)
  [fallback] faster-whisper (Belle model) on video.mp4 → raw_transcript.json
    ↓
Stage: Translate
  langdetect → source_language = "zh"
  OpenRouter (translation prompt) → work/XYZ/translated.txt
    ↓
Stage: Vision
  PySceneDetect on video.mp4 → scene boundaries
  Save I-frames → work/XYZ/keyframes/frame_001.png ... frame_N.png
    ↓
Stage: Extraction
  OpenRouter (trading domain prompt) + translated.txt → Pydantic validation
  → work/XYZ/extracted_logic.json
    ↓
Stage: Render
  Jinja2 + extracted_logic.json + keyframe paths
  → skills/XYZ/SKILL.md
  → skills/XYZ/assets/ (copies of keyframes)
    ↓
Output: skills/XYZ/SKILL.md installed and ready
```

### Batch Flow (Channel / Playlist)

```
CLI: yt-to-skill https://youtube.com/@TraderFengGe
    ↓
Orchestrator: yt-dlp playlist extraction → [video_id_1, video_id_2, ...]
    ↓
For each video_id:
  Content filter (is_strategy_content check) → skip if False
  Run single-video flow above
  On error: log, continue to next video (no batch abort)
    ↓
Summary report: N processed, M skipped (non-strategy), K failed
```

### Key Data Flows

1. **Transcript → Translation:** `raw_transcript.json` contains timed segments with source-language text. Translation preserves segment structure so timestamps remain usable.
2. **Translation → Extraction:** Full translated transcript text passed as context. Keyframe timestamps from Vision stage optionally annotated into the prompt ("at 03:24, chart shows RSI divergence") if keyframes are available.
3. **Extraction → Render:** `extracted_logic.json` (validated `TradingLogicExtraction`) is the sole data source for the Jinja2 template. The renderer never calls the LLM — it only formats.

## Suggested Build Order

Dependencies drive this order. Each layer is testable before the next is started.

| Order | Component | Why This Position |
|-------|-----------|-------------------|
| 1 | Config system + artifact dataclasses | Every stage depends on config and typed outputs. Build contracts before implementations. |
| 2 | Ingest Stage (yt-dlp) | No dependencies. First stage in every pipeline run. Validates yt-dlp integration early. |
| 3 | Transcript Stage | Depends only on video file from Ingest. Unblocks the entire text path. |
| 4 | Translation Stage | Depends on Transcript. Requires OpenRouter client — first LLM integration point. |
| 5 | OpenRouter client + LLM prompts | Needed by Translation and Extraction. Build as shared utility during step 4. |
| 6 | Extraction Stage + Pydantic models | Depends on Translation. Core value: trading logic out of text. |
| 7 | Vision Stage (PySceneDetect) | Independent of text path. Can be built in parallel with steps 3-6 but not needed until Extraction enrichment. |
| 8 | Renderer Stage + SKILL.md template | Depends on Extraction. Last step before useful output. |
| 9 | Orchestrator + CLI | Wires all stages together. Batch loop and error recovery here. |
| 10 | Domain/Language config profiles | Refactors hardcoded assumptions into YAML after the pipeline proves itself end-to-end. |

## Scaling Considerations

This is a local CLI, not a service. Scale concerns are throughput and cost, not concurrent users.

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-10 videos | Serial stage execution is fine. No changes needed. |
| 10-100 videos (playlist) | Add `--workers N` flag: use `concurrent.futures.ThreadPoolExecutor` for I/O-bound stages (Ingest, Transcript, Translation). Vision and Whisper are CPU/GPU-bound — keep serial or add GPU detection. |
| 100+ videos (full channel) | Add SQLite-backed run registry instead of filesystem presence checks. Enables filtering by status (pending/done/failed) and cost tracking per video. |

### Scaling Priorities

1. **First bottleneck:** OpenRouter API rate limits and cost. Each video makes 2-3 LLM calls (translate + extract + optionally filter). Add per-call cost logging from day one.
2. **Second bottleneck:** Whisper transcription on CPU. Belle-whisper-large-v3-zh is slow on CPU. Add `--device cuda` pass-through to faster-whisper when GPU is available.

## Anti-Patterns

### Anti-Pattern 1: Monolithic Pipeline Function

**What people do:** Write one 300-line `process_video()` function that does everything from download to SKILL.md in sequence.
**Why it's wrong:** No resumption. One failed LLM call means rerunning the download and Whisper transcription. Untestable as a unit. Impossible to add new stages cleanly.
**Do this instead:** Separate stage functions with artifact guards. Each stage is independently testable and resumable.

### Anti-Pattern 2: LLM as String Parser

**What people do:** Ask the LLM to extract trading logic and then parse its free-text response with regex or string splitting.
**Why it's wrong:** LLM output format is non-deterministic. Regex breaks on model updates. Silent data loss when fields are missing.
**Do this instead:** Use `response_format: json_schema` via OpenRouter + Pydantic validation. If the model doesn't support structured outputs, use instructor's retry-on-parse-error loop.

### Anti-Pattern 3: Hardcoded Domain Logic in Stage Code

**What people do:** Embed trading-specific prompts and Pydantic schemas directly inside `extraction.py`.
**Why it's wrong:** Adding a new domain (e.g., options trading, equities) requires forking the extraction stage. Language and domain specifics bleed into orchestration logic.
**Do this instead:** Load domain config from YAML. The extraction stage reads `config.domain.prompt_file` and `config.domain.schema_class` — it knows nothing about trading specifically.

### Anti-Pattern 4: Downloading Video Unconditionally

**What people do:** Always run `yt-dlp` to download the full video before checking whether Whisper transcription is even needed.
**Why it's wrong:** Most YouTube trading videos have auto-generated captions. Downloading hundreds of MB of video only to discard it after a caption hit is wasteful.
**Do this instead:** Try caption extraction first (fast, no download). Only download the video if captions are unavailable or below quality threshold.

### Anti-Pattern 5: Batch Abort on Single Failure

**What people do:** Wrap the entire batch loop in a try/except that stops on first error.
**Why it's wrong:** One deleted video or API timeout kills a 200-video channel batch.
**Do this instead:** Log and continue. Write a `failures.json` artifact in the work directory. Report a summary at the end: "197 succeeded, 3 failed — see work/failures.json."

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| YouTube (yt-dlp) | Subprocess or Python API; no auth for public videos | Rate limiting is rare for individual channel processing; add `--sleep-interval` for large batches |
| youtube-transcript-api | Direct Python library call; no auth for public captions | Returns timed segments with language codes — pass language code to translation stage |
| OpenRouter | OpenAI-compatible REST API via `openai` SDK with `base_url="https://openrouter.ai/api/v1"` | Use `response_format` for structured outputs; log model + token counts per call for cost tracking |
| faster-whisper (Belle model) | Local model loaded once, reused across videos in a session | First load downloads model weights (~3GB for large-v3); cache to `~/.cache/huggingface/` |
| PySceneDetect | Python library; operates on local video file path | Returns scene list with timestamps; save I-frames using `save_images()` API |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| CLI → Orchestrator | Function call with typed `PipelineConfig` | CLI is thin — no business logic. Resolves URL type and builds config only. |
| Orchestrator → Stages | Function call: `stage.run(video_id, work_dir, config)` returns `Path` to artifact | Orchestrator does not inspect artifact content — only checks existence |
| Stage → LLM Client | Function call via `llm/client.py` wrapper | All LLM calls go through one module — model swaps and cost logging happen in one place |
| Extraction Stage → Pydantic | `instructor.from_openai(client).chat.completions.create(response_model=TradingLogicExtraction, ...)` | Validates LLM output before writing to disk. Raises on schema mismatch. |
| Renderer → Artifacts | Reads `extracted_logic.json` directly from work dir — no live LLM calls | Renderer is pure: same inputs always produce same SKILL.md output |

## Sources

- [yt-dlp Information Extraction Pipeline — DeepWiki](https://deepwiki.com/yt-dlp/yt-dlp/2.2-information-extraction-pipeline)
- [PySceneDetect 0.6.7.1 Python API](https://www.scenedetect.com/docs/latest/api.html)
- [OpenRouter Structured Outputs documentation](https://openrouter.ai/docs/guides/features/structured-outputs)
- [Instructor + OpenRouter integration guide](https://python.useinstructor.com/integrations/openrouter/)
- [Multimodal LLM Pipeline for Video Understanding — Medium](https://eng-mhasan.medium.com/a-multimodal-llm-pipeline-for-video-understanding-b1738304f96d)
- [Data Pipeline Design Patterns #2 — Start Data Engineering](https://www.startdataengineering.com/post/code-patterns/)
- [ETL Pipeline with Intermediate Storage — Michael Fuchs Python](https://michael-fuchs-python.netlify.app/2020/11/27/etl-pipeline-with-intermediate-storage/)
- [Structured Data Extraction with LLMs — PyCon 2025](https://building-with-llms-pycon-2025.readthedocs.io/en/latest/structured-data-extraction.html)
- [Choosing between Whisper variants — Modal](https://modal.com/blog/choosing-whisper-variants)

---
*Architecture research for: YouTube-to-Skill Python CLI pipeline*
*Researched: 2026-04-13*
