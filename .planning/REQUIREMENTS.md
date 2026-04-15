# Requirements: YouTube-to-Skill

**Defined:** 2026-04-14
**Core Value:** Given any YouTube trading video URL, produce a high-quality Claude skill that lets Claude act as a trading assistant, generate backtest code, or serve as an on-demand knowledge base — with zero manual intervention.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Transcript & Input

- [x] **INPT-01**: User can extract transcript from any YouTube video with captions via youtube-transcript-api
- [x] **INPT-02**: User can extract transcript from caption-less videos via Whisper (Belle-whisper-large-v3-zh)
- [x] **INPT-03**: User can download video locally via yt-dlp for audio extraction and keyframe capture
- [x] **INPT-04**: User can extract keyframes from trading videos via PySceneDetect capturing chart transitions and indicator setups
- [x] **INPT-05**: Pipeline skips already-processed videos using download archive (idempotent)

### Translation & Extraction

- [x] **EXTR-01**: User can translate Chinese transcripts to English via OpenRouter LLM with trading terminology glossary
- [x] **EXTR-02**: User can extract structured trading logic (entry/exit criteria, indicators, timeframes, risk rules, market conditions) from translated transcripts
- [x] **EXTR-03**: Extracted strategies flag implicit/unstated parameters with REQUIRES_SPECIFICATION markers
- [x] **EXTR-04**: Pipeline filters out non-strategy content (vlogs, news, clickbait) before full extraction

### Output & CLI

- [x] **OUTP-01**: Pipeline generates SKILL.md following Agent Skills spec (YAML frontmatter + structured Markdown body)
- [x] **OUTP-02**: Skill output includes directory structure with assets/ (keyframes), scripts/, references/
- [x] **OUTP-03**: Generated skills use three-level structure: strategy overview, entry/exit criteria, risk management, market regime filters
- [x] **OUTP-04**: User can run pipeline via CLI with single video URL, playlist URL, or channel URL
- [x] **OUTP-05**: Pipeline processes channels/playlists in batch with per-video error isolation
- [x] **OUTP-06**: Pipeline reports clear error messages distinguishing network, extraction, LLM, and format failures

### Infrastructure

- [x] **INFR-01**: All LLM calls route through OpenRouter as unified gateway
- [x] **INFR-02**: Pipeline uses intermediate artifacts on disk (work/<video_id>/) for resumability and debugging

### Skill Installation

- [x] **INST-01**: Pipeline detects installed Agent Skills-compatible tools (Claude Code, Codex CLI, Cursor, Gemini CLI, Copilot) on the machine
- [x] **INST-02**: Pipeline installs generated skill directory tree (SKILL.md + assets/ + scripts/ + references/) to selected agent skill directories
- [x] **INST-03**: Installed SKILL.md includes provenance fields (source_video_id, installed_at) in frontmatter
- [x] **INST-04**: User can list all yt-to-skill-generated skills across all agents via `yt-to-skill list`
- [x] **INST-05**: User can uninstall a skill from all agents via `yt-to-skill uninstall <name>`
- [x] **CLI-01**: CLI uses subcommand pattern (process, list, uninstall) with backward compatibility for bare `yt-to-skill <url>`
- [x] **CLI-02**: Interactive agent selection prompt shown after skill generation; skippable via `--install` flag
- [x] **CLI-03**: Batch runs (playlist/channel) collect all generated skills and show one install prompt at the end

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
| INPT-01 | Phase 1 | Complete |
| INPT-02 | Phase 1 | Complete |
| INPT-03 | Phase 1 | Complete |
| INPT-04 | Phase 3 | Complete |
| INPT-05 | Phase 1 | Complete |
| EXTR-01 | Phase 1 | Complete |
| EXTR-02 | Phase 1 | Complete |
| EXTR-03 | Phase 1 | Complete |
| EXTR-04 | Phase 1 | Complete |
| OUTP-01 | Phase 2 | Complete |
| OUTP-02 | Phase 2 | Complete |
| OUTP-03 | Phase 2 | Complete |
| OUTP-04 | Phase 2 | Complete |
| OUTP-05 | Phase 2 | Complete |
| OUTP-06 | Phase 2 | Complete |
| INFR-01 | Phase 1 | Complete |
| INFR-02 | Phase 1 | Complete |
| INST-01 | Phase 4 | Planned |
| INST-02 | Phase 4 | Planned |
| INST-03 | Phase 4 | Planned |
| INST-04 | Phase 4 | Planned |
| INST-05 | Phase 4 | Planned |
| CLI-01 | Phase 4 | Planned |
| CLI-02 | Phase 4 | Planned |
| CLI-03 | Phase 4 | Planned |

**Coverage:**
- v1 requirements: 25 total
- Mapped to phases: 25
- Unmapped: 0

---
*Requirements defined: 2026-04-14*
*Last updated: 2026-04-15 after Phase 4 planning*
