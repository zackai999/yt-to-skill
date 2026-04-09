# Feature Research

**Domain:** YouTube-to-structured-skill extraction pipeline (trading strategy focus)
**Researched:** 2026-04-13
**Confidence:** HIGH

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| YouTube transcript extraction (captions API) | Core input mechanism — no transcript, no pipeline | LOW | `youtube-transcript-api` handles this; prefers manual captions over auto-generated; no API key required |
| Whisper fallback for caption-less videos | Many Chinese trading videos have no captions; Whisper is the established fallback | MEDIUM | Use `faster-whisper` with Belle-whisper-large-v3-zh for Chinese; language must be explicitly specified to avoid misdetection |
| Local video download via yt-dlp | Required for audio extraction when no captions exist; standard in all similar tools | LOW | yt-dlp is the de facto standard; supports playlists and channels natively |
| Chinese-to-English translation | Primary use case is Chinese-language content; untranslated output is unusable | MEDIUM | Route through OpenRouter LLM; preserve trading terminology accuracy; this is where most quality risk lives |
| Trading logic extraction (entry/exit, indicators, risk rules) | Core value proposition — without this it is just a transcript tool | HIGH | Structured LLM extraction with explicit output schema; requires domain prompt engineering |
| SKILL.md generation following Agent Skills spec | Output format the user explicitly requires; determines downstream usability | MEDIUM | YAML frontmatter (name, description, license, compatibility, metadata, allowed-tools) + Markdown body; keep under 500 lines |
| CLI interface (URL input, skill output) | Pipeline must be invocable; no GUI or scheduled service in scope | LOW | Accept single video, playlist, or channel URL as positional argument |
| Skill output directory structure | Agent Skills spec defines scripts/, references/, assets/ layout | LOW | `assets/` holds keyframe images; `scripts/` holds helper backtest scripts; `references/` holds deep reference content |
| Error reporting with clear failure messages | Pipeline has many failure modes; silent failures are worse than crashes | LOW | Distinguish network errors, extraction failures, LLM errors, and format validation errors |
| Idempotent processing / download archive | Batch runs over channels must not re-download and re-process already-completed videos | LOW | yt-dlp's `--download-archive` pattern; track processed video IDs in a local file |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but baseline tools lack them.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Video content filtering (skip non-strategy content) | Prevents wasted LLM calls and polluted skill outputs on vlogs, news, clickbait | MEDIUM | LLM-based title+transcript classification before full extraction; use heuristics first (duration, title keywords) then LLM confirm |
| Keyframe extraction for chart screenshots (PySceneDetect) | Trading strategies reference specific chart patterns; visual context anchors the text | HIGH | PySceneDetect scene-change detection; extract 1-3 representative frames per scene change; store in assets/ |
| REQUIRES_SPECIFICATION flags for ambiguous parameters | Distinguishes explicitly stated parameters from inferred ones; prevents false confidence | MEDIUM | Part of extraction prompt design; output structured markers in skill body wherever implicit values appear |
| Three-level skill structure (overview / criteria / risk / regime filters) | Mirrors how traders mentally organize strategies; more usable than a flat transcript dump | MEDIUM | Deliberate section headings enforced by extraction prompt schema |
| Domain-extensible architecture (language + domain as config) | One pipeline codebase handles Chinese crypto, English equities, any future domain | HIGH | Parameterize: source language, Whisper model variant, domain extraction prompt, output sections |
| OpenRouter as unified LLM gateway | Single API key, model-agnostic, easy swap between Claude/GPT/Gemini without code changes | LOW | Already the target architecture; wrap all LLM calls in one client module |
| Batch processing with channel/playlist support | Compounding value: ingest an entire channel in one command | MEDIUM | yt-dlp handles enumeration; pipeline orchestrates per-video processing with error isolation |
| SKILL.md validation against Agent Skills spec | Guarantees output is installable and passes `skills-ref validate` | LOW | Use `skills-ref` CLI validator as post-generation step; fail loudly on invalid output |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time channel monitoring / scheduled polling | "Keep skills up to date automatically" sounds valuable | Requires persistent process, cron management, and re-processing logic; out-of-scope for local CLI; adds operational complexity with no clear stopping condition | Run on demand; user runs pipeline when they want updates |
| GUI or web interface | Lower barrier to entry for non-technical users | Misaligns with local-first, Python CLI design; adds a full frontend dependency stack for no core value gain | CLI is the interface; document it well |
| Cloud deployment / hosted service | Share skills across machines or teams | Requires auth, data storage, infrastructure ops; the value is local skill files, not a SaaS product | Output is portable SKILL.md files; user shares files however they want |
| Live trading execution / broker integration | "Complete the loop" from strategy to trades | Catastrophically out of scope; skills are knowledge artifacts, not automation agents; liability and complexity are enormous | Skills feed Claude Code which can generate backtest code; execution is deliberately separate |
| Custom Whisper model training | Improve Chinese transcription accuracy | Training data curation, GPU infrastructure, and maintenance cycle are disproportionate to marginal gain; Belle-whisper-large-v3-zh is purpose-built for this | Use Belle-whisper-large-v3-zh as-is; tune via language/prompt parameters |
| Gemini native video route (Vision API) | Skip download + Whisper, send video directly to Gemini | Violates local-first constraint; introduces Gemini rate limits and cost unpredictability; makes pipeline depend on video upload infrastructure | Local download + process; only LLM text calls go to OpenRouter |
| Automatic skill versioning / diff tracking | Track how a strategy evolves across a creator's videos over time | Significant complexity for a v1 product; requires persistent state management and merge logic | Users can re-run pipeline and compare SKILL.md files manually; defer to v2+ |
| Multi-platform video support (TikTok, Bilibili) | Broaden addressable content | yt-dlp supports these technically, but transcript APIs and caption formats vary; scope creep before YouTube is validated | Architecture can support it later if yt-dlp handles download; focus YouTube first |

---

## Feature Dependencies

```
[Local video download (yt-dlp)]
    └──required by──> [Whisper transcription fallback]
                          └──required by──> [Caption-less video support]

[Transcript extraction]
    └──required by──> [Chinese-to-English translation]
                          └──required by──> [Trading logic extraction]
                                                └──required by──> [SKILL.md generation]

[Keyframe extraction (PySceneDetect)]
    └──enhances──> [SKILL.md generation]  (populates assets/ directory)
    └──requires──> [Local video download (yt-dlp)]

[Video content filtering]
    └──gates──> [Trading logic extraction]  (skip extraction on non-strategy videos)
    └──enhances──> [Batch processing]  (avoids wasted LLM calls at scale)

[SKILL.md validation]
    └──follows──> [SKILL.md generation]  (post-generation quality gate)

[Idempotent processing / download archive]
    └──required by──> [Batch processing]  (prevents duplicate work)
```

### Dependency Notes

- **Whisper fallback requires local video download:** Whisper processes audio; audio requires the video file locally.
- **Translation required before extraction:** LLM trading logic extraction must operate on English text; Chinese transcripts need translation first. (Alternatively, a Chinese-capable LLM could do both in one pass — evaluate in implementation.)
- **Keyframe extraction requires video download:** PySceneDetect operates on the local video file, not the transcript.
- **Content filtering gates extraction:** Must run before trading logic extraction to avoid spending LLM tokens on vlogs. Runs on title + short transcript sample (first 500 words), not full processing.
- **Batch processing depends on idempotency:** Without archive tracking, a channel run always reprocesses every video; with it, the pipeline is resumable after failure.
- **SKILL.md validation depends on generation:** Validation is a post-step, not a pre-step.

---

## MVP Definition

### Launch With (v1)

Minimum viable product — what validates the concept end-to-end on the primary use case.

- [ ] Transcript extraction via `youtube-transcript-api` — core input; captions exist on most tested channel videos
- [ ] Chinese-to-English translation via OpenRouter LLM — primary language pair; without this the output is not usable
- [ ] Whisper fallback (Belle-whisper-large-v3-zh) for caption-less videos — needed for complete channel coverage
- [ ] Trading logic extraction with structured LLM prompt — the core value; entry/exit/risk/regime sections
- [ ] REQUIRES_SPECIFICATION flags for implicit parameters — distinguishes good extraction from hallucinated extraction
- [ ] SKILL.md generation following Agent Skills spec — the deliverable format
- [ ] CLI interface accepting single video URL — minimum invocation surface
- [ ] Skill output directory with assets/ scaffold — even if keyframes are not populated, structure must be correct
- [ ] Error reporting with clear failure codes — pipeline has many failure modes; must not silently produce bad output
- [ ] Idempotent processing (download archive) — needed for any batch run, even small playlists

### Add After Validation (v1.x)

- [ ] Batch processing for playlists and channels — add when single-video pipeline is confirmed reliable; amplifies value significantly
- [ ] Video content filtering — add when batch is in place; wasted LLM calls become a real cost at channel scale
- [ ] Keyframe extraction via PySceneDetect — add when core text pipeline is stable; high complexity, high visual value
- [ ] SKILL.md validation via `skills-ref` — add as CI-style check after first batch run surfaces format regressions

### Future Consideration (v2+)

- [ ] Domain-extensible architecture (config-driven domain/language) — defer until Chinese crypto trading is fully validated; then parameterize
- [ ] Multi-platform support (Bilibili, etc.) — defer until YouTube pipeline is mature
- [ ] Automatic skill versioning / diff tracking — defer; requires persistent state design

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Transcript extraction (captions API) | HIGH | LOW | P1 |
| Chinese-to-English translation | HIGH | LOW | P1 |
| Whisper fallback | HIGH | MEDIUM | P1 |
| Trading logic extraction | HIGH | HIGH | P1 |
| SKILL.md generation | HIGH | MEDIUM | P1 |
| REQUIRES_SPECIFICATION flags | HIGH | LOW | P1 |
| CLI interface | HIGH | LOW | P1 |
| Error reporting | HIGH | LOW | P1 |
| Idempotent processing | MEDIUM | LOW | P1 |
| Batch processing (playlists/channels) | HIGH | MEDIUM | P2 |
| Video content filtering | MEDIUM | MEDIUM | P2 |
| Keyframe extraction | MEDIUM | HIGH | P2 |
| SKILL.md validation | MEDIUM | LOW | P2 |
| Domain-extensible architecture | MEDIUM | HIGH | P3 |
| Multi-platform video support | LOW | MEDIUM | P3 |
| Skill versioning / diff tracking | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when core is validated
- P3: Nice to have, future consideration

---

## Competitor Feature Analysis

| Feature | yfe404/AI-anything (generic tutorial-to-skill) | RogueQuant (trading extraction engine) | This Project |
|---------|------------------------------------------------|----------------------------------------|--------------|
| Transcript extraction | youtube-transcript-api + Whisper fallback | Not a pipeline tool; prompt templates only | Same approach; adds Chinese caption priority |
| Translation | English-focused; translation available but noted as accuracy risk | N/A | First-class: translate before extract |
| Domain-specific extraction | Generic: technologies, frameworks, libraries | Trading-specific: entry/exit, indicators, risk | Trading-specific + structured schema |
| Visual analysis | None documented | None documented | Keyframe extraction via PySceneDetect |
| Content filtering | None documented | None documented | LLM-based non-strategy detection |
| REQUIRES_SPECIFICATION flags | Not present | Part of 2-prompt design (flag missing params) | Adopted from RogueQuant pattern |
| Batch processing | Not documented | N/A | Full channel/playlist support |
| Output format | SKILL.md (Agent Skills spec) | Prompt output only | SKILL.md + assets/ + scripts/ |
| Validation | Not documented | N/A | `skills-ref validate` post-generation |

---

## Sources

- [yfe404/AI-anything GitHub](https://github.com/yfe404/AI-anything) — reference implementation for generic YouTube-to-skill pipeline
- [Agent Skills Specification — agentskills.io](https://agentskills.io/specification) — authoritative SKILL.md format, progressive disclosure model, validation tooling (HIGH confidence)
- [youtube-transcript-api PyPI](https://pypi.org/project/youtube-transcript-api/) — transcript extraction library capabilities (HIGH confidence)
- [yt-dlp batch processing patterns](https://medium.com/@DataBeacon/how-to-tackle-yt-dlp-challenges-in-ai-scale-scraping-8b78242fedf0) — rate limiting, archive flags, error recovery (MEDIUM confidence)
- [WhisperX advanced pipeline](https://www.marktechpost.com/2025/10/02/how-to-build-an-advanced-voice-ai-pipeline-with-whisperx-for-transcription-alignment-analysis-and-export/) — Whisper pipeline patterns for production use (MEDIUM confidence)
- [TradingAgents multi-agent framework](https://tradingagents-ai.github.io/) — LLM-based trading logic extraction patterns, structured output design (MEDIUM confidence)
- PROJECT.md — primary requirements source defining scope, constraints, and out-of-scope items (HIGH confidence)

---

*Feature research for: YouTube-to-Skill extraction pipeline (Chinese crypto trading)*
*Researched: 2026-04-13*
