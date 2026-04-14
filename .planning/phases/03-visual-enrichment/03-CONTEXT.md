# Phase 3: Visual Enrichment - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Extract keyframes from downloaded trading videos and populate `skills/<video_id>/assets/` with deduplicated chart screenshot PNGs at scene-transition boundaries. Integrate keyframe references into SKILL.md via a gallery section. Video download, keyframe detection, deduplication, and SKILL.md regeneration are in scope. Content classification of frames (chart vs non-chart) is out of scope.

</domain>

<decisions>
## Implementation Decisions

### Video download strategy
- Lazy download: only download video when the keyframe stage runs — not during ingest
- Follows existing `download_audio()` pattern in `ingest.py` (artifact guard, yt-dlp)
- Cap video quality at 720p — good enough to read chart indicators, keeps file size reasonable
- Delete video file after keyframe extraction to save disk space — PNGs are the durable artifact
- Add `--no-keyframes` CLI flag to skip the entire visual enrichment stage (opt-out)

### Keyframe detection tuning
- Use PySceneDetect AdaptiveDetector — best suited for screen-recording trading content
- Default keyframe cap: 20 frames per video
- Cap configurable via `--max-keyframes` CLI flag and `PipelineConfig` setting
- Conservative (high) default threshold — under-detect rather than over-detect
- Plan must include a calibration task: test on 5-10 Trader Feng Ge videos and adjust threshold

### Frame selection & dedup
- No content filtering (no chart vs webcam classification) — cap at 20 frames limits noise naturally
- Perceptual hash deduplication: compare frames using perceptual hashing, drop near-identical frames
- Output format: PNG (lossless) — chart text and indicator lines stay crisp

### SKILL.md integration
- Keyframe PNGs named by timestamp: `keyframe_0142.png` (1m42s into video) — chronological sort, self-documenting
- Separate `## Chart References` gallery section at bottom of SKILL.md — not inline in strategy sections
- Each gallery entry includes video timestamp + image link: `**1:42** — ![](assets/keyframe_0142.png)`
- SKILL.md regenerated when keyframes are extracted to include the gallery section — gated by existing `--force` semantics

### Claude's Discretion
- PySceneDetect AdaptiveDetector threshold value (calibrate during spike)
- Perceptual hash similarity threshold for dedup
- Video download implementation details (yt-dlp format string for 720p cap)
- Keyframe stage placement in orchestrator pipeline (after skill gen or before)
- How to handle videos with zero detected keyframes

</decisions>

<specifics>
## Specific Ideas

- STATE.md blocker acknowledged: PySceneDetect AdaptiveDetector threshold calibration requires spike on 5-10 real sample videos — default values cause keyframe explosion on screen-recording content
- Primary test channel: Trader Feng Ge (Chinese crypto trading, BTC-focused screen recordings)
- Progressive disclosure model: assets loaded on demand, not at skill startup — gallery section is a pointer, not embedded content

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `download_audio()` in `yt_to_skill/stages/ingest.py`: artifact-guard + yt-dlp download pattern — mirror for video download
- `StageResult` / `artifact_guard()` in `yt_to_skill/stages/base.py`: standard stage result and caching pattern
- `run_skill()` in `yt_to_skill/stages/skill.py`: already creates `assets/` directory scaffold — keyframes write into this
- `render_skill_md()` in `yt_to_skill/stages/skill.py`: SKILL.md renderer — extend with gallery section

### Established Patterns
- Artifact guard: `Path.exists()` check before any stage work — apply to keyframe PNGs
- Sequential stage orchestration in `orchestrator.py` — add keyframe stage to pipeline
- LLM clients created once and passed to stages — keyframe stage needs no LLM client
- `PipelineConfig` (pydantic-settings): extend with `max_keyframes` and `keyframes_enabled` settings

### Integration Points
- Video download: new `download_video()` function alongside `download_audio()` in `ingest.py`
- Keyframe stage: new `yt_to_skill/stages/keyframe.py` producing PNGs in `work/<video_id>/keyframes/`
- Orchestrator: add keyframe stage after extraction, copy/move PNGs to `skills/<video_id>/assets/`
- SKILL.md: `render_skill_md()` needs keyframe list parameter to render gallery section
- CLI: add `--no-keyframes` and `--max-keyframes` flags to argparse

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-visual-enrichment*
*Context gathered: 2026-04-14*
