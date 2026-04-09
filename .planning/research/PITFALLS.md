# Pitfalls Research

**Domain:** YouTube transcript extraction / LLM content processing / automated skill generation
**Researched:** 2026-04-13
**Confidence:** MEDIUM-HIGH (most findings verified via official docs or multiple sources; Whisper/Belle-whisper dialect limits are LOW confidence from single vendor descriptions)

---

## Critical Pitfalls

### Pitfall 1: Chinese YouTube Videos Frequently Have No Auto-Generated Captions

**What goes wrong:**
`youtube-transcript-api` raises `TranscriptsDisabled` or `NoTranscriptFound` for a significant fraction of Mandarin-language videos. YouTube's auto-caption engine cannot reliably handle tonal languages because character selection is ambiguous from phonetics alone. Many Chinese-language crypto channels publish without any captions at all.

**Why it happens:**
Developers assume auto-generated captions are universally available, as they are for English content. This assumption is baked into demos and tutorials which all use English videos. The project depends on Trader Feng Ge and similar channels — these are exactly the channels with unreliable or absent captions.

**How to avoid:**
- Design the pipeline with Whisper fallback as a first-class path, not an afterthought. The transcript fetch step must catch `TranscriptsDisabled` / `NoTranscriptFound` and fall through to `belle-whisper-large-v3-zh` without human intervention.
- At startup, probe a sample of videos from the target channel and measure the caption-available rate so the pipeline can choose the optimal path before processing a full playlist.
- Never report "0 transcripts extracted" as a silent success — surface whether each video used captions or Whisper.

**Warning signs:**
- Test batch of 10 target channel videos produces fewer than 7 successful transcript fetches.
- `TranscriptsDisabled` errors appearing in logs without triggering a fallback branch.
- Output transcripts that are empty strings or very short (< 200 chars) where the video is 10+ minutes long.

**Phase to address:**
Transcript extraction phase (Phase 1 / core pipeline). Whisper fallback must be wired up in the same phase, not deferred.

---

### Pitfall 2: yt-dlp Bot Detection and IP Temporary Blocking

**What goes wrong:**
YouTube actively detects and rate-limits or temporarily blocks IPs running yt-dlp. Aggressive retry logic (the default `fragment-retries` setting) compounds the problem — it sends burst traffic that triggers the "Sign in to confirm you're not a bot" wall, making subsequent requests fail for minutes to hours. Batch channel processing is especially exposed.

**Why it happens:**
yt-dlp's default retry settings were tuned for reliability, not stealth. Unauthenticated requests at scale are flagged by YouTube's anti-abuse systems. The issue escalated sharply in 2025-2026 as YouTube tightened enforcement.

**How to avoid:**
- Pass authenticated cookies to yt-dlp via `--cookies-from-browser` or a cookies file. This is the most reliable long-term mitigation.
- Lower `fragment-retries` to 3 (from default 10) to avoid burst retry patterns.
- Add a random jitter delay (2–8 seconds) between video downloads in batch mode.
- Implement exponential backoff when a 429 or "bot" error is detected, not just linear retries.
- Structure the downloader as a separate, rate-controlled queue, not a tight loop.

**Warning signs:**
- Errors containing "Sign in to confirm you're not a bot" in yt-dlp output.
- HTTP 429 responses appearing in yt-dlp verbose logs.
- Downloads suddenly failing after the 5th–10th video in a batch.

**Phase to address:**
Local video download phase. Must be addressed before any batch/playlist processing is attempted.

---

### Pitfall 3: OpenRouter Structured Output Silently Ignored for Unsupported Models

**What goes wrong:**
When `response_format: {type: "json_schema", ...}` is passed to a model that does not support structured outputs through OpenRouter, the schema constraint is silently dropped. The model returns free-form text or unstructured JSON. Code that tries to parse this as the expected schema will crash or, worse, silently produce malformed data.

**Why it happens:**
OpenRouter's API surface is OpenAI-compatible but the capability is model-specific. There is no programmatic per-model flag exposing structured output support in the `/models` endpoint (as of early 2026 this is a filed feature request, not yet resolved). Developers assume the API uniformly enforces their schema.

**How to avoid:**
- Maintain an explicit allowlist of OpenRouter model IDs confirmed to support `json_schema` structured output (Claude 3.x, GPT-4o, Gemini 2.x, Mistral Large are known-good).
- Always validate the returned JSON against your Pydantic/dataclass schema even when using structured output mode — do not trust the API to guarantee conformance.
- Use `instructor` library with OpenRouter as the backend: it provides retry-on-schema-failure and automatic re-prompting without requiring per-model awareness.
- Log the model ID used for every extraction call so failures can be triaged by model.

**Warning signs:**
- Parsing errors that occur only when the model is swapped (e.g., a cheaper model used for cost-saving).
- Fields that should be structured lists coming back as strings.
- No JSON at all returned despite `response_format` being set.

**Phase to address:**
LLM extraction phase. Model allowlist and validation must be built into extraction helpers before any trading logic extraction is attempted.

---

### Pitfall 4: Trading Terminology and Idiom Mistranslation

**What goes wrong:**
Chinese crypto/trading terminology does not map literally to English equivalents. Terms like "多头" (long position), "空头" (short position), "止盈" (take profit), "补仓" (average down / add to position), and chart pattern names have accepted English equivalents that a general-purpose translation will get wrong or paraphrase inconsistently. An LLM generating a SKILL.md from a flawed translation will encode the wrong strategy semantics.

**Why it happens:**
General-purpose LLM translation optimizes for fluency, not domain fidelity. Without explicit instruction, the model picks the most common English word sense, not the trading-specific term. Compound failures occur: translation produces an approximate phrase, then extraction reads that phrase as a different concept than intended.

**How to avoid:**
- Inject a trading terminology glossary into the translation prompt. This is the single highest-leverage fix. Minimum 30–50 term pairs covering: position sizing, entry/exit types, indicator names (MACD, RSI, Bollinger, EMA), Chinese-specific patterns, and risk management vocabulary.
- Use a two-stage approach: raw translation pass first, then a terminology-normalization pass that corrects technical terms against the glossary.
- After translation, run an LLM check that flags any segment where critical terms are ambiguous or where the glossary term was likely applicable but not used.
- Source the glossary from verified bilingual trading resources (e.g., Investopedia Chinese, official exchange documentation from OKX/Binance Chinese docs) — not from general dictionaries.

**Warning signs:**
- Translated transcripts containing "empty position" when "short selling" is meant.
- SKILL.md entry criteria that reference ambiguous direction (e.g., "open position" instead of "buy" or "sell").
- LLM extraction returning `REQUIRES_SPECIFICATION` flags at a very high rate (>50% of parameters) — this often means translation quality was poor, not that the video lacked specifics.

**Phase to address:**
Translation phase. Glossary must be authored before translation runs, not retrofitted after extraction quality issues appear.

---

### Pitfall 5: LLM Hallucinating Specific Trading Parameters Not Present in Source

**What goes wrong:**
When asked to extract structured trading rules, LLMs fill in specific numeric values (e.g., "stop loss at 2%", "RSI threshold 65", "hold for 4 hours") that were never stated in the transcript. The source content may discuss a concept vaguely, and the model invents plausible-sounding specifics to complete the schema. These hallucinated parameters end up in SKILL.md as authoritative rules.

**Why it happens:**
LLMs are trained to be helpful and produce complete, coherent outputs. An extraction schema with required numeric fields incentivizes the model to fabricate values rather than report absence. This is especially dangerous for a trading skill where a wrong stop-loss value could cause real financial harm.

**How to avoid:**
- Make every numeric field in the extraction schema explicitly nullable with a dedicated "not specified" sentinel (`null` or `"REQUIRES_SPECIFICATION"`).
- Prompt the model with a hard instruction: "If a parameter was not explicitly stated in the transcript, you MUST return REQUIRES_SPECIFICATION. Do NOT infer, estimate, or assume values."
- Run a post-extraction verification pass: re-query the LLM with the original transcript and the extracted value, asking "Does the transcript explicitly state [value]?" — flag mismatches.
- Keep extraction temperature at 0 to reduce creative variation.

**Warning signs:**
- Extraction outputs with zero `REQUIRES_SPECIFICATION` flags for a video that uses vague language.
- Numeric values appearing in extracted output that cannot be found verbatim in the translated transcript.
- Consistent round numbers (2%, 5%, 10%) in stop-loss fields across different videos from different strategies.

**Phase to address:**
LLM extraction phase. The `REQUIRES_SPECIFICATION` mechanism and post-extraction verification pass must be part of the initial extraction prompt design.

---

### Pitfall 6: PySceneDetect Keyframe Explosion on Screen-Recording Trading Videos

**What goes wrong:**
Trading tutorial videos frequently use screen recordings of charting software where price data updates every second. PySceneDetect's `ContentDetector` registers every minor price tick or indicator update as a scene cut, producing hundreds or thousands of "keyframes" per video rather than the handful of meaningful chart configurations the user cares about.

**Why it happens:**
`ContentDetector` measures pixel-level difference between frames. Live chart data changes constantly, so nearly every frame qualifies as a new scene at default thresholds. The detector was designed for film/narrative video, not screen-recordings of data-dense dashboards.

**How to avoid:**
- Use `AdaptiveDetector` instead of `ContentDetector` for this video type — it compares each frame's score against its neighborhood, which handles gradual changes better.
- Significantly raise the detection threshold (start with `threshold=3.0` for `AdaptiveDetector`, compared to the default 27 for `ContentDetector`) and calibrate on sample videos from the target channel before batch processing.
- Apply a post-detection deduplication step: compute perceptual hash (pHash) of each extracted keyframe and discard frames with Hamming distance < 8 from an already-selected frame.
- Cap maximum keyframes per video at a sensible ceiling (e.g., 20) and log when the cap is hit so the threshold can be tuned.

**Warning signs:**
- More than 30 keyframes extracted per 10-minute video.
- Output `assets/` directory growing to hundreds of MBs for a single video.
- Keyframes that are visually nearly identical (same chart, different candle timestamp).

**Phase to address:**
Keyframe extraction phase. Threshold calibration on sample videos from the target channel must precede any batch run.

---

### Pitfall 7: Whisper Hallucination on Low-Quality or Music-Heavy Audio

**What goes wrong:**
faster-whisper and Belle-whisper can hallucinate entire sentences when encountering background music, intro jingles, long silences, or low-quality microphone audio. The model does not output an empty string — it outputs plausible-sounding Chinese text that was never spoken. For a trading video with a branded intro, this inserts fabricated content at the start of the transcript.

**Why it happens:**
Whisper models are trained to produce transcriptions, not to abstain. Given an ambiguous or noisy audio segment, they generate the most probable text sequence, which may be entirely synthetic. This is a known, documented failure mode for all Whisper variants.

**How to avoid:**
- Enable VAD (Voice Activity Detection) filtering before passing audio to Whisper: `vad_filter=True` in faster-whisper strips non-speech segments, dramatically reducing hallucination triggers.
- Trim or skip the first 30–60 seconds of videos that have branded intros (detectable via silence/music detection with `librosa` or `ffmpeg`'s `silencedetect` filter).
- After transcription, check for suspiciously high repetition rate (a sign of hallucination loops) and flag those segments.
- Use Belle-whisper's punctuation variant (`belle-whisper-large-v3-zh-punct`) — punctuation models tend to produce more coherent output with lower hallucination on clean speech.

**Warning signs:**
- Transcript begins with repeated phrases or generic-sounding Chinese phrases unrelated to trading.
- Transcription length wildly mismatches expected content volume (a 30-minute video producing 500-word transcript, or a 10-minute video producing 5000 words).
- The same phrase appearing 3+ times consecutively in the transcript.

**Phase to address:**
Whisper transcription phase (fallback path). VAD filtering must be enabled by default, not opt-in.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skip translation glossary, use raw LLM translation | Faster initial build | Systematically wrong trading term mapping in all SKILL.md files; requires mass re-extraction | Never — build glossary before first extraction run |
| Hardcode a single OpenRouter model | Simpler code | Pipeline breaks when that model is deprecated or pricing spikes | Never in production; use model allowlist with fallback |
| No `REQUIRES_SPECIFICATION` in schema | Cleaner-looking output | Hallucinated parameters in SKILL.md files used for actual trading decisions | Never for trading parameters |
| Skip PySceneDetect threshold calibration | Faster to ship | Gigabytes of near-duplicate keyframes; downstream multimodal prompts bloat with irrelevant images | Only acceptable in unit tests with synthetic video |
| Parse LLM output with regex instead of schema validation | Quick fix | Silent data corruption when LLM slightly changes output format | Acceptable only in a one-off script, never in pipeline |
| Download full video always (skip caption probe) | Simpler code path | Unnecessary bandwidth and storage for videos that have captions | Never — caption probe is cheap |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `youtube-transcript-api` | Catching only `TranscriptsDisabled`, missing `NoTranscriptAvailable` and `VideoUnavailable` | Catch the full exception hierarchy from the library; all three require Whisper fallback |
| `yt-dlp` | Using `--format best` which downloads highest-res video | Use `--format bestaudio` or a low-res format code when only audio is needed for Whisper; saves 5–10x bandwidth |
| OpenRouter `response_format` | Assuming schema enforcement is model-agnostic | Check `supported_parameters` in model metadata; maintain explicit model allowlist |
| OpenRouter billing | Not setting `max_tokens` | Long transcripts with open-ended prompts can generate multi-thousand-token outputs; uncapped batch runs produce surprise bills |
| `faster-whisper` + Belle model | Loading model fresh for every video in a batch | Load the model once at pipeline startup and reuse; model load time is 5–15 seconds on CPU |
| PySceneDetect | Running on full 1080p video download | Resize video to 360p before scene detection; pixel-level detection does not need full resolution and runs 4–6x faster |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Sequential video download + transcribe + extract | Single 30-min video takes 10 minutes; 50-video playlist takes 8+ hours | Parallelize download queue; pipeline stages don't need to be strictly serial | Any playlist > 10 videos |
| Loading Belle-whisper per video | Each Whisper run starts with a 10–15 second model load | Load model once at process start; pass audio paths to loaded model instance | From the first batch run |
| Uncapped keyframe extraction | `assets/` directory fills local disk on a long channel batch | Cap frames per video, use pHash deduplication, only keep unique frames | Any channel with 20+ screen-recording videos |
| Single large LLM prompt for full transcript | Long transcripts (30k+ tokens) hit context limits or cause severe quality degradation | Chunk transcripts into 4k-token segments with overlap, then aggregate extracted rules | Videos longer than ~45 minutes with verbose speech |
| No caching of intermediate artifacts | Re-running pipeline on same video re-downloads, re-transcribes, re-translates | Cache each pipeline stage by video ID; transcripts, translations, and keyframes are immutable for a given video | Any iterative development or re-run scenario |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing OpenRouter API key in code or `.env` committed to repo | Key leak, unauthorized API charges | Use OS keychain or environment variable injection at runtime; add `.env` to `.gitignore` before first commit |
| Passing raw YouTube video metadata to LLM prompts without sanitization | Prompt injection via crafted video titles or descriptions | Sanitize title/description fields before embedding in prompts; treat them as untrusted user input |
| Logging full LLM responses at DEBUG level in production | Transcripts may contain PII (speaker names, contact info referenced in videos) | Log only metadata (model, token count, status) at INFO; full response only at DEBUG with explicit opt-in |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Silent success on empty/useless SKILL.md | User installs skill, Claude gives nonsensical answers; no indication something went wrong | Gate SKILL.md creation on a minimum quality score: must have at least one entry criterion, one exit criterion, and one risk rule — or report failure explicitly |
| No progress output during long batch runs | User cannot tell if the pipeline is running or hung | Emit structured progress lines: `[2/15] Processing: <video title> (stage: transcribing)` |
| Generic `Error: extraction failed` messages | User cannot diagnose whether to retry, skip, or fix configuration | Include video ID, stage name, and actionable suggestion in every error message |
| Overwriting existing SKILL.md on re-run | User's manual edits to a skill are silently destroyed | Check for existing file; prompt user or use `--overwrite` flag |

---

## "Looks Done But Isn't" Checklist

- [ ] **Caption availability rate**: Tested on the actual target channel (Trader Feng Ge), not just any English YouTube video — verify fallback triggers correctly for Chinese-only videos
- [ ] **Glossary coverage**: Trading terminology glossary validated against at least 5 real translated transcripts — verify no key terms are missing or mistranslated
- [ ] **REQUIRES_SPECIFICATION rate**: Checked on a video with known explicit parameters — verify hallucinated values are not being generated for parameters the video explicitly states
- [ ] **Keyframe count**: Run on a screen-recording video from target channel — verify output is < 20 frames, not hundreds
- [ ] **SKILL.md format compliance**: Output parsed by a spec-compliant YAML + Markdown parser — verify YAML frontmatter is valid and all required sections present
- [ ] **Batch mode rate limiting**: Run against a 10-video playlist without authentication — verify no IP block is triggered and delays are functioning
- [ ] **Whisper VAD enabled**: Confirmed `vad_filter=True` is set in the faster-whisper call — verify intro jingles do not produce hallucinated text
- [ ] **OpenRouter cost cap**: Confirmed `max_tokens` is set on all LLM calls — verify no single video run can produce an unbounded API bill

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Mass-produced SKILL.md files with hallucinated parameters | HIGH | Re-run extraction with corrected prompt and `REQUIRES_SPECIFICATION` logic; previously generated files must be quarantined or deleted |
| Wrong trading terminology in all translated transcripts | HIGH | Author glossary, re-run translation step for all videos, re-run extraction; intermediate artifacts should be cached to avoid re-downloading/re-transcribing |
| IP block from YouTube | LOW | Wait 15–30 minutes, add cookies auth, lower retry count; no data loss |
| Keyframe directory full of duplicates | LOW-MEDIUM | Run pHash deduplication script on existing `assets/` dirs; future runs use corrected threshold |
| OpenRouter unexpected charges from uncapped tokens | MEDIUM | Set `max_tokens` immediately; review OpenRouter billing dashboard; adjust per-video cost budgeting |
| Whisper hallucinated intro text in transcripts | MEDIUM | Enable VAD filter; re-transcribe affected videos (cheap if model already loaded); re-run downstream extraction |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Chinese captions unavailable | Phase 1: Transcript extraction | Test on 10 Trader Feng Ge videos; confirm fallback fires for ≥3 of them |
| yt-dlp bot detection | Phase 1: Video download | Run 10-video batch; no IP block errors in logs |
| Trading term mistranslation | Phase 2: Translation | Spot-check 20 key terms in 3 translated transcripts against glossary |
| LLM hallucinated parameters | Phase 3: Extraction | Extract from a video with known explicit values; compare output to source |
| OpenRouter structured output silently ignored | Phase 3: Extraction | Test extraction with a non-allowlisted model; confirm error is raised, not silent failure |
| Keyframe explosion on screen recordings | Phase 4: Keyframe extraction | Run on 3 screen-recording videos; confirm < 25 frames each |
| Whisper hallucination on intro audio | Phase 1: Whisper fallback | Check transcript start for known intro phrases from target channel |
| SKILL.md format non-compliance | Phase 5: Skill generation | Parse every generated file with YAML + Markdown validator before writing to output dir |

---

## Sources

- [Free YouTube Transcript API: Options and Limitations](https://www.notelm.ai/blog/youtube-transcript-api-free)
- [How to Tackle yt-dlp Challenges in AI-Scale Scraping](https://medium.com/@DataBeacon/how-to-tackle-yt-dlp-challenges-in-ai-scale-scraping-8b78242fedf0)
- [fragment-retries default behavior triggers YouTube IP ban (yt-dlp issue #15899)](https://github.com/yt-dlp/yt-dlp/issues/15899)
- [YouTube video download fails due to bot detection (yt-dlp issue #13067)](https://github.com/yt-dlp/yt-dlp/issues/13067)
- [OpenRouter Structured Outputs documentation](https://openrouter.ai/docs/guides/features/structured-outputs)
- [Response Healing: Reduce JSON Defects by 80%+ (OpenRouter announcement)](https://openrouter.ai/announcements/response-healing-reduce-json-defects-by-80percent)
- [Structured outputs with OpenRouter — Instructor library guide](https://python.useinstructor.com/integrations/openrouter/)
- [Feature request: list structured output support in OpenRouter model index](https://github.com/OpenRouterTeam/openrouter-examples/issues/20)
- [Chinese Financial Localization: Precision Terms from 1-StopAsia](https://www.1stopasia.com/blog/chinese-financial-terminology-orange-book/)
- [Improving LLM Abilities in Idiomatic Translation (ACL 2025)](https://aclanthology.org/2025.loreslm-1.13.pdf)
- [Towards reducing hallucination in extracting information from financial reports using LLMs](https://arxiv.org/html/2310.10760)
- [Belle Faster Whisper Large V3 Zh Punct — model description](https://dataloop.ai/library/model/xa9_belle-faster-whisper-large-v3-zh-punct/)
- [faster-whisper GitHub](https://github.com/SYSTRAN/faster-whisper)
- [Reduce false positives in ContentDetector due to camera movement (PySceneDetect issue #153)](https://github.com/Breakthrough/PySceneDetect/issues/153)
- [PySceneDetect Detection Algorithms documentation](https://www.scenedetect.com/docs/latest/api/detectors.html)
- [youtube-transcript-api PyPI](https://pypi.org/project/youtube-transcript-api/)

---
*Pitfalls research for: YouTube-to-Skill pipeline (Chinese crypto trading videos)*
*Researched: 2026-04-13*
