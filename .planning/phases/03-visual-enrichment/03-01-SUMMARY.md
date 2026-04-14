---
phase: 03-visual-enrichment
plan: 01
subsystem: pipeline
tags: [scenedetect, imagehash, yt-dlp, opencv, phash, keyframes, video]

# Dependency graph
requires:
  - phase: 01-text-pipeline
    provides: artifact_guard pattern, StageResult dataclass, PipelineConfig base
  - phase: 02-output-and-cli
    provides: established stage pattern used throughout

provides:
  - download_video() in ingest.py — 720p video download with artifact guard
  - yt_to_skill/stages/keyframe.py — full keyframe extraction stage
  - PipelineConfig.max_keyframes (default 20) and keyframes_enabled (default True)
  - deduplicate_frames() — pHash-based near-duplicate removal
  - run_keyframes() — sentinel-guarded extraction pipeline

affects:
  - 03-visual-enrichment (downstream plans that compose keyframes into skill output)

# Tech tracking
tech-stack:
  added:
    - scenedetect[opencv-headless]>=0.6.7
    - imagehash>=4.3.2
    - pillow (transitive, required for imagehash)
    - opencv-python-headless (transitive, required for scenedetect)
  patterns:
    - Sentinel file (keyframes.done) for keyframe artifact guard — same pattern as metadata.json guard
    - pHash deduplication loop: keep frame if hamming distance > threshold vs ALL kept hashes
    - save_images() call signature: scene_list FIRST, then video (not video first)

key-files:
  created:
    - yt_to_skill/stages/keyframe.py
    - tests/test_keyframe.py
  modified:
    - pyproject.toml
    - yt_to_skill/config.py
    - yt_to_skill/stages/ingest.py
    - uv.lock

key-decisions:
  - "save_images(scene_list, video, ...) — scene_list is first arg, not video (known pitfall)"
  - "Solid color images produce identical pHash — tests must use structured patterns (checkerboard/gradient)"
  - "AdaptiveDetector(adaptive_threshold=8.0, min_scene_len=30) per research recommendation"
  - "Hard cap applied before save_images call via scene_list slicing"
  - "Video deleted after extraction to save disk space"

patterns-established:
  - "Sentinel guard: keyframes.done written after successful extraction with frame count as content"
  - "pHash dedup: imagehash.phash + hamming distance threshold=10 for near-duplicate detection"
  - "timecode_to_filename: int(timecode.get_seconds()) → keyframe_MMSS.png format"

requirements-completed:
  - INPT-04

# Metrics
duration: 5min
completed: 2026-04-14
---

# Phase 3 Plan 01: Keyframe Extraction Stage Summary

**PySceneDetect-based keyframe extraction with AdaptiveDetector, imagehash pHash deduplication, 720p video download, and sentinel-guarded artifact caching**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-14T06:52:43Z
- **Completed:** 2026-04-14T06:57:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Added `download_video()` to `ingest.py` — mirrors `download_audio()` with 720p cap and artifact guard on `video.*` glob
- Created `yt_to_skill/stages/keyframe.py` implementing full pipeline: download → scene detect → cap → rename → pHash dedup → delete video → write sentinel
- Extended `PipelineConfig` with `max_keyframes=20` and `keyframes_enabled=True`
- 12 tests covering config defaults, download_video, dedup, and run_keyframes (artifact guard, cap enforcement, video deletion, zero scenes)

## Task Commits

Each task was committed atomically:

1. **Task 1: Dependencies, config, download_video, and tests** - `17954ad` (feat)
2. **Task 2: Keyframe extraction stage with dedup and capping** - `7dd6fd4` (feat)

_Note: TDD tasks — tests written first (RED), then implementation (GREEN)_

## Files Created/Modified
- `yt_to_skill/stages/keyframe.py` - Full keyframe extraction stage: run_keyframes, deduplicate_frames, timecode_to_filename
- `tests/test_keyframe.py` - 12-test suite: TestConfig, TestDownloadVideo, TestDedup, TestRunKeyframes
- `pyproject.toml` - Added scenedetect[opencv-headless]>=0.6.7 and imagehash>=4.3.2
- `yt_to_skill/config.py` - Added max_keyframes=20 and keyframes_enabled=True to PipelineConfig
- `yt_to_skill/stages/ingest.py` - Added download_video() mirroring download_audio() pattern
- `uv.lock` - Updated for new dependencies

## Decisions Made
- `save_images(scene_list, video, ...)` — scene_list is the first argument (not video), a known PySceneDetect pitfall documented in research
- pHash on solid-color images produces identical hashes (all-uniform images hash to same value) — tests use structured patterns (checkerboard vs gradient) to get meaningful hamming distances
- Hard cap applied via Python slicing `scene_list[:config.max_keyframes]` before `save_images` call — simple and reliable
- Sentinel file `keyframes.done` contains the kept frame count as text (consistent with pattern from other stages)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_keeps_distinct using solid color pHash collision**
- **Found during:** Task 2 (TestDedup implementation)
- **Issue:** Test used solid red vs solid blue PNGs, but all solid/uniform images produce identical pHash (hash = `8000000000000000`), so distance was 0 and the "distinct" test expected 2 but got 1
- **Fix:** Replaced solid colors with structured patterns: numpy checkerboard (alternating 0/255) vs gradient (rows 0-255). These produce pHash distance of 31, well above threshold=10.
- **Files modified:** tests/test_keyframe.py
- **Verification:** TestDedup::test_keeps_distinct passes; all 12 tests green
- **Committed in:** 7dd6fd4 (Task 2 commit)

**2. [Rule 1 - Bug] Fixed test PNG stubs using .touch() (empty files) causing PIL error in dedup**
- **Found during:** Task 2 (TestRunKeyframes tests)
- **Issue:** Fake PNG stubs created with `.touch()` (0-byte files) were passed to `deduplicate_frames`, which calls `Image.open()` — PIL raises `UnidentifiedImageError` on empty files
- **Fix:** Added `_make_png(path, color)` helper creating real 8x8 PIL images; updated all fake_save_images test helpers to use it
- **Files modified:** tests/test_keyframe.py
- **Verification:** All 12 tests green; 187 total tests pass
- **Committed in:** 7dd6fd4 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - bugs in test assumptions)
**Impact on plan:** Both fixes corrected test implementation details; production code unchanged. No scope creep.

## Issues Encountered
- `uv add` required instead of `pip install` (no pip in venv, managed by uv) — straightforward fix

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Keyframe extraction stage complete and tested
- `run_keyframes(video_id, work_dir, config)` ready to be called from pipeline orchestrator
- Sentinel guard prevents redundant re-extraction on reruns
- Video file auto-deleted after extraction to manage disk usage

---
*Phase: 03-visual-enrichment*
*Completed: 2026-04-14*
