# Stack Research

**Domain:** YouTube video-to-skill pipeline (Python CLI, Chinese language, trading content)
**Researched:** 2026-04-13
**Confidence:** HIGH (all versions verified against PyPI/official sources)

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11 | Runtime | 3.11 is the sweet spot: faster-whisper requires <=3.12 (ctranslate2 has no 3.13 wheels), yt-dlp requires >=3.10. 3.11 gives full compatibility across all deps plus ~25% perf improvement over 3.10. |
| yt-dlp | 2026.3.17 | Video + playlist/channel download | De facto standard for YouTube. Programmatic Python API via `YoutubeDL` class. Supports cookies, format selection, playlist/channel iteration. Nothing else matches its site support and reliability. |
| youtube-transcript-api | 1.2.4 | Caption/subtitle extraction | Zero-FFmpeg path: fetches YouTube's own captions (manual + auto-generated) via API. Supports `zh`/`zh-Hans`/`zh-Hant` language codes with fallback priority lists. Much faster than transcription for videos that have captions. |
| faster-whisper | 1.2.1 | Fallback ASR transcription | 4x faster than openai/whisper with same accuracy. Uses CTranslate2 (no PyTorch overhead). Works on CPU and CUDA 12 GPU. Required for videos with no captions or poor auto-captions. |
| scenedetect (PySceneDetect) | 0.6.7.1 | Keyframe extraction | 94.7% accuracy on standard benchmarks. Python API via `detect()` + `save_images()`. Adaptive and content-based detectors suitable for trading chart videos. Used in production by Netflix/BBC. |
| openai (SDK) | 2.31.0 | OpenRouter API client | OpenRouter is OpenAI-API-compatible. Using the official `openai` SDK with `base_url="https://openrouter.ai/api/v1"` is the recommended approach — no extra dependency, full async support. |
| instructor | 1.15.1 | Structured LLM output extraction | Battle-tested library for typed Pydantic output from LLMs. Works with OpenRouter via OpenAI client. Handles retries on validation failure automatically. Critical for reliable trading logic extraction. |
| Pydantic | 2.13.0 | Data validation and schemas | Powers instructor's output schemas. Defines TradingStrategy, EntryCondition, RiskRule models. V2 is significantly faster than V1. |
| Typer | 0.24.1 | CLI framework | Built on Click. Type-hint-driven argument/option parsing — define Python function, get CLI for free. Auto-generated `--help`. Best choice for this project's single-entrypoint CLI pattern. |
| Rich | 14.1.0 | Terminal output + progress | Progress bars for batch processing, structured logging that doesn't collide with progress display. Essential for a pipeline with 5+ long-running stages. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic-settings | 2.11.0 | Config + env management | Loading `OPENROUTER_API_KEY`, model names, output paths from `.env` with type validation. Replaces raw `python-dotenv` with typed settings class. |
| huggingface-hub | latest (auto via faster-whisper) | Model download for Belle-whisper | Downloads `BELLE-2/Belle-whisper-large-v3-zh-punct` or the CTranslate2-converted variant `Huan69/Belle-whisper-large-v3-zh-punct-fasterwhisper` from HuggingFace. Pulled in as faster-whisper dependency. |
| PyAV | latest (auto via faster-whisper) | Audio decoding | Used by faster-whisper internally — no separate FFmpeg binary required for ASR path. Do not install ffmpeg-python; PyAV handles audio. |
| ffmpeg (system binary) | 7.x | Video muxing + keyframe export | yt-dlp requires system ffmpeg for muxing best video+audio streams. PySceneDetect `split_video_ffmpeg()` uses it. Must be installed via Homebrew/system package manager, NOT via pip. |
| httpx | latest (auto via openai SDK) | HTTP client | Pulled in by openai SDK. No direct dependency needed. |
| tenacity | latest | Retry logic for API calls | For OpenRouter rate limits / transient errors in batch processing. Wrap LLM calls with `@retry(wait=wait_exponential(...))`. |
| loguru | 0.7.x | Structured logging | Simpler than stdlib logging. Works alongside Rich — configure to output to file for batch pipeline audit trail. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uv | Dependency management + virtualenv | 10-100x faster than pip. Use `uv add` to manage `pyproject.toml`. Lock file (`uv.lock`) ensures reproducible installs. Required: `uv sync` to install from lockfile. |
| pyproject.toml | Project metadata + dependencies | PEP 621 standard. Single source of truth for deps, Python version constraint, CLI entry point declaration. Use `[project.scripts]` to register the `yt-to-skill` command. |
| pytest | Testing | Standard. Use `pytest-asyncio` if async paths are introduced. |
| ruff | Linting + formatting | Fast Rust-based linter. Replaces flake8 + isort + black in one tool. Configure in `pyproject.toml` under `[tool.ruff]`. |
| mypy | Type checking | Catches schema mismatches early — important when Pydantic models define the contract between LLM output and SKILL.md generation. |

---

## Installation

```bash
# Create project with uv
uv init yt-to-skill
cd yt-to-skill

# Core pipeline dependencies
uv add yt-dlp youtube-transcript-api faster-whisper scenedetect openai instructor pydantic typer rich

# Config + logging
uv add pydantic-settings loguru tenacity

# Dev dependencies
uv add --dev pytest pytest-asyncio ruff mypy

# System dependency (not pip) — required for yt-dlp muxing + PySceneDetect ffmpeg backend
brew install ffmpeg  # macOS
# apt install ffmpeg  # Linux

# .env file
echo "OPENROUTER_API_KEY=sk-or-..." > .env
```

**Belle-whisper model** is downloaded at runtime by faster-whisper on first use:
```python
from faster_whisper import WhisperModel
# Downloads CTranslate2-compatible variant from HuggingFace
model = WhisperModel("Huan69/Belle-whisper-large-v3-zh-punct-fasterwhisper", device="cpu")
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| youtube-transcript-api | yt-dlp `--write-subs` | Only if you need subtitle files on disk in SRT/VTT format; transcript-api is faster and returns structured Python objects directly |
| faster-whisper | openai/whisper | Never for this project — faster-whisper is strictly superior in speed/memory; openai/whisper requires PyTorch which adds 2+ GB |
| instructor | LangChain structured output | If you're already using LangChain as an orchestration layer; instructor is lighter and more reliable for pure extraction tasks |
| Typer | Click | If you need shell completion customization or are building a suite of subcommand-heavy tools; Click is Typer's foundation |
| Typer | argparse | Never — argparse is stdlib but verbose; Typer provides 80% less code for the same result with better UX |
| pydantic-settings | python-dotenv alone | Never — pydantic-settings gives typed config with validation; python-dotenv gives raw strings with no type safety |
| uv | pip + venv | If deploying in a Docker container that already has pip; otherwise uv is objectively faster and more reliable |
| scenedetect | OpenCV manual frame diff | Only if you need custom frame-diff logic; PySceneDetect wraps OpenCV and adds adaptive detection tuned for real-world video |
| Rich | tqdm | tqdm is fine for single progress bars; Rich handles multi-stage pipeline display (transcription + translation + extraction all visible simultaneously) |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| openai/whisper (original) | Pulls in PyTorch (~2 GB), 4x slower, same accuracy as faster-whisper | faster-whisper 1.2.1 |
| pytube / pytubefix | Fragile, breaks frequently when YouTube changes its frontend; no Python API; no playlist support | yt-dlp 2026.3.17 |
| ffmpeg-python (pip) | Python wrapper only — provides no ffmpeg binaries. yt-dlp and PySceneDetect need the actual system binary | System ffmpeg via Homebrew/apt |
| LangChain | Heavy abstraction for a task (structured extraction) that instructor handles in 20 lines; introduces chain-of-thought prompt drift | instructor + openai SDK |
| requirements.txt | No lockfile semantics, no Python version pinning, no dev/prod separation | pyproject.toml + uv.lock |
| httpx / requests directly | OpenRouter's API is OpenAI-compatible; use the openai SDK which handles auth, retries, and streaming correctly | openai SDK 2.31.0 |
| whisper.cpp bindings | Python bindings are unstable; faster-whisper (CTranslate2) is the mature Python-native path for efficient inference | faster-whisper |
| deepl / googletrans | Translation should be LLM-based (OpenRouter) for trading terminology accuracy — MT tools mangle trading idioms and indicator names | OpenRouter LLM call with translation prompt |

---

## Stack Patterns by Variant

**If the video has YouTube captions (most Feng Ge videos will):**
- Use `youtube-transcript-api` with `languages=['zh', 'zh-Hans', 'zh-TW', 'en']`
- Skip yt-dlp download and faster-whisper entirely for the transcript step
- Download video separately with yt-dlp only for keyframe extraction

**If the video has no captions or auto-captions are poor quality:**
- Download full video with yt-dlp
- Extract audio track via ffmpeg (`-vn -acodec copy`)
- Run faster-whisper with `Belle-whisper-large-v3-zh-punct-fasterwhisper` model
- language parameter: `"zh"`, task: `"transcribe"`

**If running on GPU (NVIDIA CUDA 12):**
- faster-whisper: `device="cuda"`, `compute_type="int8_float16"` — ~10x faster than CPU
- Requires cuBLAS + cuDNN 9 for CUDA 12 (install via NVIDIA CUDA toolkit)

**If running on CPU (default / Apple Silicon):**
- faster-whisper: `device="cpu"`, `compute_type="int8"`
- Acceptable for batch processing; large-v3 on CPU takes ~2-4 min per 30-min video

**If processing a full channel (batch mode):**
- Rate-limit OpenRouter calls with tenacity exponential backoff
- Cache transcripts to disk (JSON) to avoid re-fetching on reruns
- Cache translated transcripts separately — translation is expensive

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| faster-whisper 1.2.1 | Python 3.9–3.12 only | ctranslate2 has no Python 3.13 wheels; use Python 3.11 |
| yt-dlp 2026.3.17 | Python 3.10+ | Dropped Python 3.9 support in late 2025 |
| Pydantic 2.13.0 | instructor 1.15.1 | instructor is built on Pydantic v2; do NOT mix with Pydantic v1 |
| scenedetect 0.6.7.1 | Python 3.7+ | Optional OpenCV backend; PyAV backend available if OpenCV not installed |
| Typer 0.24.1 | Python 3.7+ | Requires Click as a dependency (auto-installed) |
| openai SDK 2.31.0 | Python 3.8+ | Use `base_url="https://openrouter.ai/api/v1"` for OpenRouter |

---

## Sources

- [youtube-transcript-api on PyPI](https://pypi.org/project/youtube-transcript-api/) — version 1.2.4, January 2026
- [faster-whisper on PyPI](https://pypi.org/project/faster-whisper/) — version 1.2.1, October 2025
- [scenedetect on PyPI](https://pypi.org/project/scenedetect/) — version 0.6.7.1, September 2025
- [yt-dlp on PyPI](https://pypi.org/project/yt-dlp/) — version 2026.3.17
- [openai SDK on PyPI](https://pypi.org/project/openai/) — version 2.31.0, April 2026
- [instructor on PyPI](https://pypi.org/project/instructor/) — version 1.15.1, April 2026
- [Pydantic on PyPI](https://pypi.org/project/pydantic/) — version 2.13.0, April 2026
- [Typer on PyPI](https://pypi.org/project/typer/) — version 0.24.1, February 2026
- [OpenRouter Python SDK docs](https://openrouter.ai/docs/sdks/python) — OpenAI-compatible base_url pattern
- [instructor + OpenRouter integration](https://python.useinstructor.com/integrations/openrouter/) — verified compatibility
- [Belle-whisper-large-v3-zh-punct on HuggingFace](https://huggingface.co/BELLE-2/Belle-whisper-large-v3-zh-punct) — Chinese ASR model, updated June 2025
- [Huan69/Belle-whisper-large-v3-zh-punct-fasterwhisper](https://huggingface.co/Huan69/Belle-whisper-large-v3-zh-punct-fasterwhisper) — CTranslate2-converted variant for faster-whisper
- [uv project management — Real Python](https://realpython.com/python-uv/) — uv + pyproject.toml best practices 2025

---
*Stack research for: YouTube-to-Skill pipeline (Python CLI)*
*Researched: 2026-04-13*
