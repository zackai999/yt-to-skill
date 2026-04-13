# Roadmap: YouTube-to-Skill

## Overview

Build a local Python CLI pipeline in three delivery phases. Phase 1 establishes the full text extraction chain — from YouTube URL to validated structured trading logic on disk — with both caption and Whisper fallback paths, translation with trading glossary, and idempotent artifact caching. Phase 2 converts that extracted logic into installable SKILL.md files and wires the CLI for single-video, playlist, and channel invocations with batch error isolation. Phase 3 adds visual enrichment by extracting keyframes from downloaded videos and populating the SKILL.md assets/ directory with chart screenshots.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Text Pipeline** - Extract, translate, and structure trading logic from any YouTube video URL to validated JSON on disk
- [ ] **Phase 2: Output and CLI** - Generate installable SKILL.md files and expose the full pipeline via CLI for single video, playlist, and channel URLs
- [ ] **Phase 3: Visual Enrichment** - Extract keyframes from downloaded trading videos and populate SKILL.md assets/ with chart screenshots

## Phase Details

### Phase 1: Text Pipeline
**Goal**: Given a YouTube video URL, produce a validated `extracted_logic.json` on disk containing structured trading strategy data
**Depends on**: Nothing (first phase)
**Requirements**: INPT-01, INPT-02, INPT-03, INPT-05, EXTR-01, EXTR-02, EXTR-03, EXTR-04, INFR-01, INFR-02
**Success Criteria** (what must be TRUE):
  1. User can point the pipeline at a YouTube video with captions and get a transcript extracted without downloading the video
  2. User can point the pipeline at a caption-less Chinese YouTube video and get a transcript via Whisper (Belle-whisper-large-v3-zh) fallback
  3. User can re-run the pipeline on the same video and have all completed stages skipped, with outputs served from disk artifacts in `work/<video_id>/`
  4. The pipeline produces `extracted_logic.json` containing entry/exit criteria, indicators, timeframes, risk rules, and market conditions — with `REQUIRES_SPECIFICATION` markers on any unstated parameters
  5. Non-strategy videos (vlogs, news, clickbait) are detected and skipped before LLM extraction calls are made
**Plans:** 4/5 plans executed

Plans:
- [ ] 01-01-PLAN.md — Project scaffold, config, data models, and test infrastructure
- [ ] 01-02-PLAN.md — OpenRouter LLM client wrapper, prompt templates, and trading glossary
- [ ] 01-03-PLAN.md — Ingest and Transcript stages (captions + Whisper fallback)
- [ ] 01-04-PLAN.md — Filter and Translation stages
- [ ] 01-05-PLAN.md — Extraction stage and Orchestrator wiring

### Phase 2: Output and CLI
**Goal**: Users can invoke `yt-to-skill <url>` and receive an installable `skills/<video_id>/SKILL.md` complying with the Agent Skills specification
**Depends on**: Phase 1
**Requirements**: OUTP-01, OUTP-02, OUTP-03, OUTP-04, OUTP-05, OUTP-06
**Success Criteria** (what must be TRUE):
  1. User can run `yt-to-skill <single-video-url>` and find a valid SKILL.md with YAML frontmatter and three-level strategy body in `skills/<video_id>/`
  2. User can run `yt-to-skill <playlist-or-channel-url>` and have all videos processed in batch; a single failed video does not abort the run
  3. Generated SKILL.md includes `assets/`, `scripts/`, and `references/` directory scaffold regardless of keyframe content
  4. Error messages distinguish network failures, extraction failures, LLM failures, and format failures with actionable descriptions
**Plans:** 1/2 plans executed

Plans:
- [ ] 02-01-PLAN.md — Typed error hierarchy and SKILL.md generation stage
- [ ] 02-02-PLAN.md — URL resolver, CLI entry point, batch processing, and orchestrator wiring

### Phase 3: Visual Enrichment
**Goal**: SKILL.md files include chart screenshots from downloaded trading videos, anchoring visual strategy references to real frames
**Depends on**: Phase 2
**Requirements**: INPT-04
**Success Criteria** (what must be TRUE):
  1. After running the pipeline on a video with chart content, `skills/<video_id>/assets/` contains deduplicated keyframe PNGs at scene-transition boundaries
  2. The pipeline does not produce keyframe explosions on screen-recording trading videos (frame count stays within configurable cap)
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Text Pipeline | 4/5 | In Progress|  |
| 2. Output and CLI | 1/2 | In Progress|  |
| 3. Visual Enrichment | 0/TBD | Not started | - |
