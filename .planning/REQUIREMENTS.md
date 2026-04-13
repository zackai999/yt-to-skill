# Requirements: YouTube-to-Skill

**Defined:** 2026-04-14
**Core Value:** Given any YouTube trading video URL, produce a high-quality Claude skill that lets Claude act as a trading assistant, generate backtest code, or serve as an on-demand knowledge base — with zero manual intervention.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Transcript & Input

- [ ] **INPT-01**: User can extract transcript from any YouTube video with captions via youtube-transcript-api
- [ ] **INPT-02**: User can extract transcript from caption-less videos via Whisper (Belle-whisper-large-v3-zh)
- [ ] **INPT-03**: User can download video locally via yt-dlp for audio extraction and keyframe capture
- [ ] **INPT-04**: User can extract keyframes from trading videos via PySceneDetect capturing chart transitions and indicator setups
- [ ] **INPT-05**: Pipeline skips already-processed videos using download archive (idempotent)

### Translation & Extraction

- [ ] **EXTR-01**: User can translate Chinese transcripts to English via OpenRouter LLM with trading terminology glossary
- [x] **EXTR-02**: User can extract structured trading logic (entry/exit criteria, indicators, timeframes, risk rules, market conditions) from translated transcripts
- [x] **EXTR-03**: Extracted strategies flag implicit/unstated parameters with REQUIRES_SPECIFICATION markers
- [ ] **EXTR-04**: Pipeline filters out non-strategy content (vlogs, news, clickbait) before full extraction

### Output & CLI

- [ ] **OUTP-01**: Pipeline generates SKILL.md following Agent Skills spec (YAML frontmatter + structured Markdown body)
- [ ] **OUTP-02**: Skill output includes directory structure with assets/ (keyframes), scripts/, references/
- [ ] **OUTP-03**: Generated skills use three-level structure: strategy overview, entry/exit criteria, risk management, market regime filters
- [ ] **OUTP-04**: User can run pipeline via CLI with single video URL, playlist URL, or channel URL
- [ ] **OUTP-05**: Pipeline processes channels/playlists in batch with per-video error isolation
- [ ] **OUTP-06**: Pipeline reports clear error messages distinguishing network, extraction, LLM, and format failures

### Infrastructure

- [x] **INFR-01**: All LLM calls route through OpenRouter as unified gateway
- [x] **INFR-02**: Pipeline uses intermediate artifacts on disk (work/<video_id>/) for resumability and debugging

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Extensibility

- **EXTD-01**: Domain-extensible architecture with language + domain as YAML config profiles
- **EXTD-02**: Multi-platform video support (Bilibili, TikTok) via yt-dlp backend
- **EXTD-03**: SKILL.md validation via skills-ref CLI validator

### Advanced

- **ADVN-01**: Automatic skill versioning and diff tracking across video updates
- **ADVN-02**: Cost tracking and reporting for OpenRouter LLM usage per video/batch

## Out of Scope

| Feature | Reason |
|---------|--------|
| Cloud deployment / hosted service | Local CLI only — no infrastructure ops |
| Live trading execution / broker integration | Skills are knowledge artifacts, not automation |
| Custom Whisper model training | Belle-whisper-large-v3-zh is purpose-built; marginal gain doesn't justify cost |
| GUI or web interface | CLI is the interface |
| Gemini native video route | Local-first pipeline; no external video processing dependency |
| Real-time channel monitoring | Run on demand; no persistent process |
| Scheduled polling / cron | Out of scope for v1; user runs when needed |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INPT-01 | Phase 1 | Pending |
| INPT-02 | Phase 1 | Pending |
| INPT-03 | Phase 1 | Pending |
| INPT-04 | Phase 3 | Pending |
| INPT-05 | Phase 1 | Pending |
| EXTR-01 | Phase 1 | Pending |
| EXTR-02 | Phase 1 | Complete |
| EXTR-03 | Phase 1 | Complete |
| EXTR-04 | Phase 1 | Pending |
| OUTP-01 | Phase 2 | Pending |
| OUTP-02 | Phase 2 | Pending |
| OUTP-03 | Phase 2 | Pending |
| OUTP-04 | Phase 2 | Pending |
| OUTP-05 | Phase 2 | Pending |
| OUTP-06 | Phase 2 | Pending |
| INFR-01 | Phase 1 | Complete |
| INFR-02 | Phase 1 | Complete |

**Coverage:**
- v1 requirements: 17 total
- Mapped to phases: 17
- Unmapped: 0

---
*Requirements defined: 2026-04-14*
*Last updated: 2026-04-14 after roadmap creation*
