---
phase: 01-text-pipeline
plan: "03"
subsystem: pipeline
tags: [yt-dlp, youtube-transcript-api, faster-whisper, whisper, captions, audio, transcript, tdd]

# Dependency graph
requires:
  - phase: 01-text-pipeline
    plan: "01"
    provides: "VideoMetadata, TranscriptArtifact dataclasses, StageResult/artifact_guard base protocol, PipelineConfig"
provides:
  - "run_ingest: fetches YouTube video metadata via yt-dlp without downloading video"
  - "download_audio: lazy bestaudio audio download with artifact guard"
  - "fetch_captions: instance-based youtube-transcript-api v1.2+ caption extraction with zh language priority"
  - "is_caption_quality_acceptable: quality heuristics (char density, music ratio, short segment ratio)"
  - "transcribe_audio: Whisper transcription with vad_filter=True using Belle-whisper model"
  - "run_transcript: caption-first routing with automatic Whisper fallback and quality heuristics"
affects:
  - "01-04-PLAN.md (Filter and Translation — consumes raw_transcript.json TranscriptArtifact)"
  - "01-05-PLAN.md (Extraction and Orchestrator — calls run_ingest/run_transcript as pipeline stages)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Caption-first routing: try fetch_captions, quality check, then Whisper fallback — never Whisper unless needed"
    - "Instance-based YouTubeTranscriptApi v1.2+: api = YouTubeTranscriptApi(); api.list(video_id)"
    - "Whisper singleton: module-level _whisper_model, lazy-loaded on first call to get_whisper_model()"
    - "Chinese-aware short segment detection: (< 3 space tokens) AND (< 5 chars) — handles both Latin and CJK"

key-files:
  created:
    - "yt_to_skill/stages/ingest.py — run_ingest (metadata) + download_audio (bestaudio lazy)"
    - "yt_to_skill/stages/transcript.py — fetch_captions, is_caption_quality_acceptable, transcribe_audio, run_transcript"
    - "tests/test_ingest.py — 7 tests covering ingest artifact guard, metadata fields, download options"
    - "tests/test_transcript.py — 16 tests covering caption API, quality heuristics, Whisper fallback, artifact guard"
  modified: []

key-decisions:
  - "youtube-transcript-api v1.2+ uses instance-based API (YouTubeTranscriptApi().list(video_id)) not class methods"
  - "Short segment quality heuristic uses char count fallback for Chinese text: a segment is 'short' only if < 3 words AND < 5 chars"
  - "Whisper loaded as module-level singleton to avoid reloading the model across multiple transcribe_audio calls"
  - "Language priority list defaults to [zh, zh-Hans, zh-Hant, en] with any-transcript fallback"

patterns-established:
  - "Caption quality gate: density (chars < duration*2), noise (music ratio > 0.3), fragmentation (short ratio > 0.6)"
  - "Whisper path always goes through download_audio — no separate audio management in transcript stage"
  - "TDD with mocked APIs: patch YouTubeTranscriptApi class constructor, not class methods"

requirements-completed: [INPT-01, INPT-02, INPT-03]

# Metrics
duration: 10min
completed: 2026-04-14
---

# Phase 1 Plan 03: Ingest and Transcript Stages Summary

**yt-dlp metadata fetch + youtube-transcript-api caption extraction with Belle-whisper Whisper fallback — 23 tests passing, both stages idempotent**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-04-14
- **Completed:** 2026-04-14
- **Tasks:** 2 (both TDD)
- **Files modified:** 4 created

## Accomplishments

- Ingest stage fetches YouTube video metadata (title, description, duration, channel, tags) without downloading video/audio; writes VideoMetadata to work/<video_id>/metadata.json
- download_audio uses bestaudio/best format with fragment_retries=3; artifact guard returns cached audio.* file
- Caption extraction with language priority (zh > zh-Hans > zh-Hant > en > any) and three quality heuristics: char density, music tag ratio, short segment ratio
- Whisper fallback using Belle-whisper-large-v3-zh-punct model with vad_filter=True to suppress non-speech hallucination
- Both stages fully idempotent via artifact guard pattern

## Task Commits

Each task was committed atomically:

1. **Task 1 TDD RED: Failing ingest tests** - `a6090c2` (test)
2. **Task 1 TDD GREEN: Ingest implementation** - `c9e0262` (feat)
3. **Task 2 TDD RED: Failing transcript tests** - `91dbc55` (test)
4. **Task 2 TDD GREEN: Transcript implementation** - `0605729` (feat)

_Note: TDD tasks have separate commits for RED (failing tests) and GREEN (implementation)_

## Files Created/Modified

- `yt_to_skill/stages/ingest.py` — run_ingest + download_audio with yt-dlp
- `yt_to_skill/stages/transcript.py` — fetch_captions, is_caption_quality_acceptable, transcribe_audio, run_transcript
- `tests/test_ingest.py` — 7 tests: directory creation, metadata.json fields, artifact guards, bestaudio format, fragment_retries=3
- `tests/test_transcript.py` — 16 tests: caption API (segments, errors, language priority, fallback), quality heuristics (4 cases), run_transcript flow (captions, Whisper fallbacks, artifact guard), Whisper (vad_filter, model ID, segment dicts)

## Decisions Made

- **Instance-based YouTubeTranscriptApi v1.2+**: The installed version (1.2.4) uses `YouTubeTranscriptApi().list(video_id)` instead of the old class-method `YouTubeTranscriptApi.list_transcripts(video_id)`. Updated both implementation and test mocking.
- **Chinese-aware short segment detection**: Chinese text has no spaces, so `split() < 3` would flag every Chinese segment as "short". Combined condition: `< 3 words AND < 5 chars` correctly handles both Latin and CJK script.
- **NoTranscriptFound vs NoTranscriptAvailable**: The installed version exports `NoTranscriptFound` (not `NoTranscriptAvailable`); updated tests to use the correct class.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] youtube-transcript-api v1.2+ uses instance-based API**
- **Found during:** Task 2 (Transcript stage implementation)
- **Issue:** The plan referenced `YouTubeTranscriptApi.list_transcripts()` (class method pattern from v0.x), but installed version 1.2.4 requires instantiation (`YouTubeTranscriptApi().list(video_id)`)
- **Fix:** Updated implementation to use `api = YouTubeTranscriptApi(); api.list(video_id)`. Updated test mocks to patch the class constructor rather than class methods.
- **Files modified:** yt_to_skill/stages/transcript.py, tests/test_transcript.py
- **Verification:** 16 transcript tests pass
- **Committed in:** 0605729 (Task 2 GREEN commit)

**2. [Rule 1 - Bug] Chinese-aware short segment quality heuristic**
- **Found during:** Task 2 (quality heuristic tests)
- **Issue:** `split() < 3 words` check incorrectly flags all Chinese segments as "short" (Chinese text has no whitespace word separators)
- **Fix:** Combined condition: segment is "short" only when it has both `< 3 space-separated tokens` AND `< 5 characters` total
- **Files modified:** yt_to_skill/stages/transcript.py
- **Verification:** test_quality_acceptable_for_good_segments passes with Chinese segments
- **Committed in:** 0605729 (Task 2 GREEN commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs — API version mismatch, Chinese text heuristic)
**Impact on plan:** Both fixes required for correctness. The quality heuristic fix ensures Chinese-language captions are not incorrectly rejected. No scope creep.

## Issues Encountered

- Test fixture mismatch: GOOD_SEGMENTS (5 short Chinese segments = 97 chars) over default 360s duration failed the char density check. Fixed by using 20s duration in quality tests to match segment count, and 360s (large) in the sparse-segment test.

## User Setup Required

None - no external service configuration required for these stages. Whisper model downloads automatically from HuggingFace Hub on first use.

## Next Phase Readiness

- Ingest and Transcript stages complete; pipeline can now take a YouTube video ID and produce a TranscriptArtifact on disk
- Ready for 01-04: Filter and Translation stage (consumes raw_transcript.json)
- No blockers for next plan

---
*Phase: 01-text-pipeline*
*Completed: 2026-04-14*

## Self-Check: PASSED

All created files and commits verified:
- FOUND: yt_to_skill/stages/ingest.py
- FOUND: yt_to_skill/stages/transcript.py
- FOUND: tests/test_ingest.py
- FOUND: tests/test_transcript.py
- FOUND: .planning/phases/01-text-pipeline/01-03-SUMMARY.md
- FOUND commit a6090c2: test(01-03): add failing tests for ingest stage
- FOUND commit c9e0262: feat(01-03): implement ingest stage
- FOUND commit 91dbc55: test(01-03): add failing tests for transcript stage
- FOUND commit 0605729: feat(01-03): implement transcript stage
