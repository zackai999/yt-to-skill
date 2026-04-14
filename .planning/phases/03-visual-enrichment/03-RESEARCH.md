# Phase 3: Visual Enrichment - Research

**Researched:** 2026-04-14
**Domain:** Video keyframe extraction, scene detection, perceptual hashing, SKILL.md integration
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Video download strategy**
- Lazy download: only download video when the keyframe stage runs — not during ingest
- Follows existing `download_audio()` pattern in `ingest.py` (artifact guard, yt-dlp)
- Cap video quality at 720p — good enough to read chart indicators, keeps file size reasonable
- Delete video file after keyframe extraction to save disk space — PNGs are the durable artifact
- Add `--no-keyframes` CLI flag to skip the entire visual enrichment stage (opt-out)

**Keyframe detection tuning**
- Use PySceneDetect AdaptiveDetector — best suited for screen-recording trading content
- Default keyframe cap: 20 frames per video
- Cap configurable via `--max-keyframes` CLI flag and `PipelineConfig` setting
- Conservative (high) default threshold — under-detect rather than over-detect
- Plan must include a calibration task: test on 5-10 Trader Feng Ge videos and adjust threshold

**Frame selection & dedup**
- No content filtering (no chart vs webcam classification) — cap at 20 frames limits noise naturally
- Perceptual hash deduplication: compare frames using perceptual hashing, drop near-identical frames
- Output format: PNG (lossless) — chart text and indicator lines stay crisp

**SKILL.md integration**
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

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INPT-04 | User can extract keyframes from trading videos via PySceneDetect capturing chart transitions and indicator setups | PySceneDetect 0.6.7.1 AdaptiveDetector API, imagehash 4.3.2 perceptual dedup, yt-dlp 720p format string, SKILL.md render_skill_md extension pattern |
</phase_requirements>

---

## Summary

Phase 3 adds a keyframe extraction stage to the pipeline: lazily download the video at 720p via yt-dlp, run PySceneDetect AdaptiveDetector to find scene transitions, deduplicate the resulting frames using perceptual hashing (imagehash), write the surviving PNGs into `skills/<video_id>/assets/`, then regenerate SKILL.md with a `## Chart References` gallery section. The video file is deleted after extraction — PNGs are the durable artifact.

The primary technical risk is the calibration blocker acknowledged in STATE.md: AdaptiveDetector's default `adaptive_threshold=3.0` is tuned for cinematic cuts and will produce a keyframe explosion on screen-recording trading content (which has many subtle incremental chart updates). The plan must include a dedicated calibration spike before the main implementation tasks. The cap of 20 frames is the safety net, but threshold calibration should prevent the cap from being the primary control.

The integration touches five files: `ingest.py` (new `download_video()`), new `keyframe.py` stage, `orchestrator.py` (add stage, wire `--no-keyframes`), `skill.py` (extend `render_skill_md` with gallery), and `cli.py` (add two flags). The existing `StageResult`/`artifact_guard` pattern fits this stage cleanly with no LLM dependency.

**Primary recommendation:** Use `scenedetect[opencv-headless]>=0.6.7` + `imagehash>=4.3.2` + `Pillow`. Start threshold calibration at `adaptive_threshold=8.0` (well above default 3.0) and tune down from there on real trading screen-recordings.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| scenedetect | >=0.6.7 | Scene boundary detection via AdaptiveDetector | User-locked choice; AdaptiveDetector uniquely uses rolling-average threshold suited for screen recordings |
| imagehash | >=4.3.2 | Perceptual hash computation and comparison (pHash/dHash) | User-locked choice; 4.3.2 released Feb 2025, active maintenance |
| Pillow | >=10.0 | Load PNG frames for imagehash (already an imagehash dependency) | Already likely present as transitive dep; explicit to avoid version surprises |
| opencv-python-headless | (via scenedetect extra) | OpenCV backend for scenedetect; headless avoids GUI/X11 dep | CLI pipeline — no display needed; smaller install |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| yt-dlp | >=2024.1.0 | Video download at 720p cap (already in stack) | Reuse existing dep — `download_video()` mirrors `download_audio()` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| scenedetect AdaptiveDetector | ContentDetector | ContentDetector uses fixed threshold — more brittle on screen-recordings with gradual transitions |
| imagehash (pHash/dHash) | imagededup CNN | CNN approach overkill for same-video dedup; imagehash is faster, zero GPU requirement |
| opencv-headless | pyav backend | pyav is scenedetect's other supported backend but less battle-tested; opencv is the standard |

**Installation:**
```bash
pip install "scenedetect[opencv-headless]>=0.6.7" "imagehash>=4.3.2"
```

Add to `pyproject.toml` dependencies:
```toml
"scenedetect[opencv-headless]>=0.6.7",
"imagehash>=4.3.2",
```

---

## Architecture Patterns

### Recommended Project Structure
```
yt_to_skill/
├── stages/
│   ├── base.py          # StageResult, artifact_guard (existing)
│   ├── ingest.py        # add download_video() here (existing file)
│   ├── keyframe.py      # NEW: run_keyframes() stage
│   └── skill.py         # extend render_skill_md() (existing)
└── config.py            # extend PipelineConfig with max_keyframes, keyframes_enabled

skills/<video_id>/
├── SKILL.md             # extended with ## Chart References gallery
└── assets/
    ├── keyframe_0142.png
    └── keyframe_0310.png

work/<video_id>/
├── keyframes/           # intermediate PNG staging (cleared after copy)
└── video.*              # deleted after keyframe extraction
```

### Pattern 1: download_video() — Mirror of download_audio()
**What:** Lazy download video at 720p cap, artifact guard on video file glob, delete after extraction.
**When to use:** Only when keyframe stage runs (lazy, not during ingest).
**Example:**
```python
# Source: mirrors ingest.py download_audio() pattern
def download_video(video_id: str, work_dir: Path, config: PipelineConfig) -> Path:
    video_dir = work_dir / video_id
    video_dir.mkdir(parents=True, exist_ok=True)

    existing = list(video_dir.glob("video.*"))
    if existing:
        logger.info("Video already exists at {path} — skipping download", path=existing[0])
        return existing[0]

    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        # Best video up to 720p merged with best audio — requires ffmpeg
        # Fallback: best combined stream up to 720p if no separate streams
        "format": "bestvideo[height<=720][ext=mp4]+bestaudio/best[height<=720]",
        "outtmpl": str(video_dir / "video.%(ext)s"),
        "merge_output_format": "mp4",
        "fragment_retries": 3,
        "quiet": True,
        "no_warnings": True,
    }

    logger.info("Downloading video for video {video_id}", video_id=video_id)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    video_files = list(video_dir.glob("video.*"))
    if not video_files:
        raise FileNotFoundError(
            f"Video download for video {video_id!r} produced no output file"
        )
    return video_files[0]
```

**Note:** ffmpeg must be installed for stream merging. Add a dependency note in errors or setup docs.

### Pattern 2: PySceneDetect Detection + Image Saving
**What:** Open video, create SceneManager with AdaptiveDetector, detect scenes, save one image per scene using save_images() with PNG format.
**When to use:** Core of run_keyframes() stage.
**Example:**
```python
# Source: https://www.scenedetect.com/docs/latest/api.html
# Source: https://www.scenedetect.com/docs/latest/api/detectors.html
from scenedetect import open_video, AdaptiveDetector
from scenedetect.scene_manager import SceneManager, save_images

video = open_video(str(video_path))
manager = SceneManager()
manager.add_detector(AdaptiveDetector(
    adaptive_threshold=8.0,   # HIGH starting value — calibrate down
    min_scene_len=30,         # at 30fps = 1s minimum between cuts
))
manager.detect_scenes(video, show_progress=False)
scene_list = manager.get_scene_list()

# scene_list is list[tuple[FrameTimecode, FrameTimecode]] — (start, end)
# Each FrameTimecode has .get_seconds() and .get_timecode()
```

### Pattern 3: Capping and Deduplication
**What:** After scene detection, apply hard cap (take first N) then perceptual-hash dedup.
**When to use:** Always run dedup before writing to assets.
**Example:**
```python
# Source: https://pypi.org/project/ImageHash/ (imagehash 4.3.2)
from PIL import Image
import imagehash

DEDUP_THRESHOLD = 8  # Hamming distance; 0=identical, higher=more different

def deduplicate_frames(frame_paths: list[Path], threshold: int = DEDUP_THRESHOLD) -> list[Path]:
    """Drop near-duplicate frames using perceptual hash (pHash)."""
    kept: list[Path] = []
    kept_hashes: list[imagehash.ImageHash] = []

    for path in frame_paths:
        img = Image.open(path)
        h = imagehash.phash(img)
        # Check against all already-kept hashes
        if all((h - kh) > threshold for kh in kept_hashes):
            kept.append(path)
            kept_hashes.append(h)

    return kept
```

**Threshold guidance:**
- `threshold=0` — only exact duplicates removed
- `threshold=8` — recommended starting point for near-identical frames
- `threshold=12` — more aggressive; may drop visually distinct frames

### Pattern 4: Timestamp-to-Filename Conversion
**What:** Convert FrameTimecode to `keyframe_MMSS.png` filename format (self-documenting, chronological sort).
**When to use:** When writing PNGs, before dedup to preserve timestamp info.
**Example:**
```python
def timecode_to_filename(timecode) -> str:
    """Convert FrameTimecode to keyframe_MMSS.png filename.

    Example: 1m42s -> keyframe_0142.png
    """
    total_seconds = int(timecode.get_seconds())
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"keyframe_{minutes:02d}{seconds:02d}.png"
```

### Pattern 5: SKILL.md Gallery Section Extension
**What:** Extend `render_skill_md()` to accept an optional list of keyframe paths and append a `## Chart References` section.
**When to use:** When keyframes exist in assets/ at render time.
**Example:**
```python
# Extension to skill.py render_skill_md()
def render_gallery_section(keyframe_paths: list[Path]) -> str:
    """Render ## Chart References gallery section for SKILL.md."""
    if not keyframe_paths:
        return ""

    lines = ["\n## Chart References\n"]
    for path in sorted(keyframe_paths):
        # Extract timestamp from filename: keyframe_0142.png -> 1:42
        stem = path.stem  # "keyframe_0142"
        raw = stem.replace("keyframe_", "")  # "0142"
        minutes = int(raw[:2])
        seconds = int(raw[2:])
        timestamp = f"{minutes}:{seconds:02d}"
        lines.append(f"**{timestamp}** — ![](assets/{path.name})")

    return "\n".join(lines)
```

### Anti-Patterns to Avoid
- **Running detect_scenes on the full video at default threshold:** Default `adaptive_threshold=3.0` will produce hundreds of detected scenes on screen-recording content. Start high (8.0+) and tune down.
- **Saving multiple images per scene via save_images num_images>1:** We want exactly one frame per transition boundary — use `num_images=1` to avoid per-scene start/end frames doubling the count.
- **Using opencv-python (not headless) in a CLI pipeline:** GUI dependency chains X11 libraries unnecessarily. Use `scenedetect[opencv-headless]`.
- **Not deleting the video file:** Video files are 500MB–2GB. Omitting the delete step exhausts disk on batch processing.
- **Regenerating SKILL.md unconditionally on keyframe re-run:** The existing `--force` semantics must gate SKILL.md regeneration. Keyframe-only re-runs (when SKILL.md already has gallery) should respect the cache.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Scene boundary detection | Custom frame differencing | `scenedetect.AdaptiveDetector` | Rolling-average threshold handles screen-recording gradual transitions; dozens of edge cases around codec artifacts |
| Perceptual similarity | Pixel-diff or MD5 | `imagehash.phash()` + hamming distance | pHash is robust to JPEG artifacts, minor color shifts, compression; pixel-diff catches nothing |
| Frame extraction from video | Manual OpenCV `cap.read()` loop | `scenedetect.save_images()` | Handles seek, threading, frame margin, output naming template — already battle-tested |

**Key insight:** The combination of detection (PySceneDetect) + dedup (imagehash) is standard pattern. Building custom scene detection is 200+ lines of fragile frame differencing that still won't handle codec IDR frame boundaries correctly.

---

## Common Pitfalls

### Pitfall 1: Keyframe Explosion on Screen-Recording Content
**What goes wrong:** AdaptiveDetector's default `adaptive_threshold=3.0` triggers on every minor chart update (price tick, cursor movement), producing 200+ "scenes" for a 30-minute trading video.
**Why it happens:** Default threshold tuned for cinematic content (hard cuts between camera shots). Screen recordings have constant low-level pixel changes.
**How to avoid:** Start with `adaptive_threshold=8.0` or higher. The calibration spike (5-10 Trader Feng Ge videos) is mandatory before shipping. Apply hard cap of 20 frames as a safety net regardless.
**Warning signs:** Detected scene count >> 20 on first run; all frames look nearly identical.

### Pitfall 2: Missing ffmpeg for Stream Merging
**What goes wrong:** yt-dlp downloads video and audio as separate files and cannot merge them without ffmpeg — or falls back to a lower-quality combined stream (not 720p video).
**Why it happens:** YouTube serves best-quality video and audio in separate streams (DASH format). Merging requires a muxer.
**How to avoid:** Document ffmpeg as a system dependency. Alternatively, use a format string that falls back gracefully: `"bestvideo[height<=720][ext=mp4]+bestaudio/best[height<=720]/best[height<=720]"`. Consider adding `postprocessors` in ydl_opts to explicitly invoke ffmpeg merge.
**Warning signs:** Output video is 480p or lower; video file extension is `.webm` or unusual format.

### Pitfall 3: save_images() Signature Mismatch
**What goes wrong:** `save_images()` expects `(scene_list, video, ...)` — note scene_list comes FIRST, then video. Getting this backwards raises a TypeError that's confusing.
**Why it happens:** Different from most OpenCV patterns where the video/stream is the first argument.
**How to avoid:** Follow the exact verified signature: `save_images(scene_list, video, num_images=1, image_extension='png', output_dir=str(output_dir))`.

### Pitfall 4: FrameTimecode is Not a Plain Number
**What goes wrong:** Treating `scene_list[i][0]` (a `FrameTimecode`) as an integer or float fails — it has its own `.get_seconds()`, `.get_frames()`, `.get_timecode()` methods.
**Why it happens:** The tuple contains `FrameTimecode` objects, not primitive types.
**How to avoid:** Use `.get_seconds()` for timestamp arithmetic. Use `int(timecode.get_seconds())` to derive the filename.

### Pitfall 5: Artifact Guard Applied to Wrong Path
**What goes wrong:** Using the video file as the artifact guard target for the keyframe stage. If video was partially downloaded and deleted, the guard will say "re-download needed" but the video is gone.
**Why it happens:** Logical confusion between the transient artifact (video) and the durable artifact (PNGs).
**How to avoid:** Use the sentinel file for the keyframe stage as a manifest or the presence of any PNG in the keyframes dir. A clean pattern: `keyframes_done_path = work_dir / video_id / "keyframes.done"` — write this sentinel after successful extraction.

### Pitfall 6: render_skill_md() Gallery with Zero Keyframes
**What goes wrong:** Rendering an empty `## Chart References` section pollutes SKILL.md with a section heading and no content, confusing downstream consumers.
**Why it happens:** Edge case where AdaptiveDetector finds no cuts (e.g., very short video or uniform content).
**How to avoid:** Skip gallery section entirely when `keyframe_paths` is empty. Established pattern: `if not keyframe_paths: return ""`.

---

## Code Examples

Verified patterns from official sources:

### Complete PySceneDetect Detection Pattern
```python
# Source: https://www.scenedetect.com/docs/latest/api.html (v0.6.7.1)
from scenedetect import open_video, AdaptiveDetector
from scenedetect.scene_manager import SceneManager, save_images

video_path = Path("work/abc123/video.mp4")
output_dir = Path("work/abc123/keyframes")
output_dir.mkdir(parents=True, exist_ok=True)

video = open_video(str(video_path))
manager = SceneManager()
manager.add_detector(AdaptiveDetector(
    adaptive_threshold=8.0,   # Starting value — tune from calibration spike
    min_scene_len=30,         # Minimum frames between cuts (~1s at 30fps)
))
manager.detect_scenes(video, show_progress=False)
scene_list = manager.get_scene_list()

# Save one PNG per scene at start frame (num_images=1)
# Template: $FRAME_NUMBER used, but we rename after the fact by timestamp
save_images(
    scene_list,
    video,
    num_images=1,
    image_extension='png',
    encoder_param=9,          # Best PNG compression (1-9 scale)
    output_dir=str(output_dir),
    show_progress=False,
)
```

### Perceptual Hash Deduplication
```python
# Source: https://pypi.org/project/ImageHash/ (imagehash 4.3.2)
from PIL import Image
import imagehash

def deduplicate_frames(frame_paths: list[Path], threshold: int = 8) -> list[Path]:
    kept: list[Path] = []
    kept_hashes: list[imagehash.ImageHash] = []
    for path in sorted(frame_paths):
        h = imagehash.phash(Image.open(path))
        if all((h - kh) > threshold for kh in kept_hashes):
            kept.append(path)
            kept_hashes.append(h)
    return kept
```

### yt-dlp 720p Format String
```python
# Source: yt-dlp documentation, format selector syntax
ydl_opts = {
    "format": "bestvideo[height<=720][ext=mp4]+bestaudio/best[height<=720]/best[height<=720]",
    "outtmpl": str(video_dir / "video.%(ext)s"),
    "merge_output_format": "mp4",
    "fragment_retries": 3,
    "quiet": True,
    "no_warnings": True,
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ContentDetector (fixed threshold) | AdaptiveDetector (rolling average) | PySceneDetect 0.6.x | Better handling of screen-recording content; fewer false positives on gradual transitions |
| scenedetect v0.5.x VideoManager | open_video() + SceneManager | 0.6.0 | VideoManager deprecated; open_video() is the current API |
| opencv-python (GUI) | opencv-python-headless | Current recommendation | Avoids X11/GUI chain in server/CLI contexts |

**Deprecated/outdated:**
- `VideoManager` class: Deprecated in 0.6.x — use `open_video()` instead. Documentation for v0.5 shows VideoManager; do not copy those examples.
- `scenedetect.detect()` simple function: Still available but returns scene list without `save_images()` integration — use SceneManager directly for more control.

---

## Open Questions

1. **AdaptiveDetector threshold for Trader Feng Ge screen-recordings**
   - What we know: Default 3.0 will over-detect; screen recordings have constant low-level changes
   - What's unclear: The exact threshold (8.0? 12.0? 20.0?) — depends on video encoding, frame rate, and chart update frequency
   - Recommendation: The calibration spike (Wave 1, Task 1) must run on 5-10 real videos before implementing the cap logic

2. **Perceptual hash threshold for same-video frames**
   - What we know: Standard recommendation is hamming distance of 8-10 for near-duplicates; `0` = identical, `64` = completely different (for 8-bit pHash)
   - What's unclear: Trading chart frames may share chart background with only indicator line changes — these SHOULD be kept, not deduped
   - Recommendation: Start conservative at threshold=10 (keep more), tighten if duplicates appear

3. **ffmpeg system dependency**
   - What we know: yt-dlp requires ffmpeg for stream merging to get 720p quality
   - What's unclear: Whether the project's target environment (dev machines, CI) always has ffmpeg
   - Recommendation: Add format fallback that degrades gracefully; document in CLAUDE.md or setup instructions

4. **Zero keyframes edge case handling**
   - What we know: Some videos may produce 0 detected scenes (uniform content, very short clips)
   - What's unclear: Should `run_keyframes()` return skipped=False with 0 keyframes, or is this a soft error?
   - Recommendation: Treat as success with 0 keyframes — log a warning, skip gallery section in SKILL.md, write sentinel file so stage doesn't re-run

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.2.0+ |
| Config file | `pyproject.toml` [tool.pytest.ini_options] testpaths = ["tests"] |
| Quick run command | `pytest tests/test_keyframe.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INPT-04 | `download_video()` downloads at 720p cap via yt-dlp | unit (mock yt-dlp) | `pytest tests/test_keyframe.py::TestDownloadVideo -x` | ❌ Wave 0 |
| INPT-04 | `run_keyframes()` respects artifact guard (sentinel file) | unit | `pytest tests/test_keyframe.py::TestRunKeyframes::test_artifact_guard -x` | ❌ Wave 0 |
| INPT-04 | AdaptiveDetector cap: never produces > max_keyframes PNGs in output | unit (mock scene_list) | `pytest tests/test_keyframe.py::TestRunKeyframes::test_cap_enforced -x` | ❌ Wave 0 |
| INPT-04 | Perceptual hash dedup removes near-identical frames | unit | `pytest tests/test_keyframe.py::TestDedup -x` | ❌ Wave 0 |
| INPT-04 | PNGs written to `skills/<video_id>/assets/` after stage | unit | `pytest tests/test_keyframe.py::TestRunKeyframes::test_pngs_in_assets -x` | ❌ Wave 0 |
| INPT-04 | `render_skill_md()` includes gallery section when keyframes present | unit | `pytest tests/test_skill.py::TestGallerySection -x` | ❌ Wave 0 |
| INPT-04 | `render_skill_md()` omits gallery section when no keyframes | unit | `pytest tests/test_skill.py::TestGallerySection::test_no_gallery_when_empty -x` | ❌ Wave 0 |
| INPT-04 | `--no-keyframes` flag skips keyframe stage entirely | unit (CLI) | `pytest tests/test_cli.py::TestNoKeyframesFlag -x` | ❌ Wave 0 |
| INPT-04 | `--max-keyframes` flag configures the cap | unit (CLI) | `pytest tests/test_cli.py::TestMaxKeyframesFlag -x` | ❌ Wave 0 |
| INPT-04 | Video file deleted after keyframe extraction | unit | `pytest tests/test_keyframe.py::TestRunKeyframes::test_video_deleted -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_keyframe.py tests/test_skill.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_keyframe.py` — all INPT-04 keyframe stage tests (new file)
- [ ] `tests/test_skill.py` — append `TestGallerySection` class (extend existing file)
- [ ] `tests/test_cli.py` — append `TestNoKeyframesFlag` and `TestMaxKeyframesFlag` (extend existing file)
- [ ] `pyproject.toml` — add `scenedetect[opencv-headless]>=0.6.7` and `imagehash>=4.3.2` to dependencies

---

## Sources

### Primary (HIGH confidence)
- [PySceneDetect Detectors API v0.6.7.1](https://www.scenedetect.com/docs/latest/api/detectors.html) — AdaptiveDetector class signature, all parameters, defaults
- [PySceneDetect Package API v0.6.7.1](https://www.scenedetect.com/docs/latest/api.html) — SceneManager, save_images(), open_video() usage patterns
- [SceneManager API v0.6.7.1](https://www.scenedetect.com/docs/latest/api/scene_manager.html) — save_images() full signature, detect_scenes(), get_scene_list()
- [ImageHash 4.3.2 on PyPI](https://pypi.org/project/ImageHash/) — hash algorithms, comparison API, latest version (Feb 2025)

### Secondary (MEDIUM confidence)
- [yt-dlp format string documentation](https://github.com/yt-dlp/yt-dlp) — `bestvideo[height<=720]+bestaudio` format pattern, verified against multiple community sources
- [scenedetect PyPI](https://pypi.org/project/scenedetect/) — version 0.6.7.1 (Sep 2025), Python >=3.7 support, opencv-headless recommendation

### Tertiary (LOW confidence)
- WebSearch community findings on AdaptiveDetector threshold calibration for screen recordings — no official benchmark exists; threshold values in research are author estimates requiring validation against real Trader Feng Ge videos

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — PySceneDetect 0.6.7.1 and imagehash 4.3.2 confirmed on PyPI with current dates; APIs verified from official docs
- Architecture: HIGH — all patterns mirror established codebase conventions (StageResult, artifact_guard, download_audio); integration points verified from reading existing code
- Pitfalls: HIGH (explosion pitfall), MEDIUM (ffmpeg pitfall) — explosion risk is documented in STATE.md blocker; ffmpeg dependency is standard yt-dlp knowledge
- Threshold calibration: LOW — no official guidance for screen-recording content; calibration spike required

**Research date:** 2026-04-14
**Valid until:** 2026-05-14 (stable libraries; PySceneDetect and imagehash change infrequently)
