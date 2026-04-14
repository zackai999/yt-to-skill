"""Keyframe extraction stage: scene detection, interval sampling, perceptual dedup."""

from pathlib import Path

import cv2
import imagehash
import scenedetect
from loguru import logger
from PIL import Image
from scenedetect import SceneManager
from scenedetect.detectors import AdaptiveDetector
from scenedetect.scene_manager import save_images

from yt_to_skill.config import PipelineConfig
from yt_to_skill.stages.base import StageResult
from yt_to_skill.stages.ingest import download_video

# Scenes longer than this (seconds) get change-detected for extra captures
_LONG_SCENE_THRESHOLD = 45
# Check for changes every N seconds within long scenes
_PROBE_INTERVAL = 3
# Mean pixel diff (0-255) above which we consider a frame "changed"
_CHANGE_THRESHOLD = 4.0
# Minimum seconds between captured frames (cooldown to avoid burst captures)
_MIN_CAPTURE_GAP = 10


def timecode_to_filename(timecode) -> str:
    """Convert a FrameTimecode to a PNG filename like keyframe_MMSS.png.

    Args:
        timecode: A FrameTimecode (or any object with get_seconds()).

    Returns:
        Filename string e.g. "keyframe_0142.png" for 1m42s.
    """
    total_seconds = int(timecode.get_seconds())
    mm = total_seconds // 60
    ss = total_seconds % 60
    return f"keyframe_{mm:02d}{ss:02d}.png"


def deduplicate_frames(frame_paths: list[Path], threshold: int = 10) -> list[Path]:
    """Remove near-identical frames using perceptual hashing.

    Iterates frame_paths in order. Keeps a frame only if its pHash differs
    from ALL previously kept frames by more than `threshold` bits.

    Args:
        frame_paths: Paths to PNG files to deduplicate.
        threshold: Maximum hamming distance to consider two frames identical.

    Returns:
        List of kept frame Paths (in original order).
    """
    if not frame_paths:
        return []

    kept: list[Path] = []
    kept_hashes: list[imagehash.ImageHash] = []

    for path in frame_paths:
        h = imagehash.phash(Image.open(path))
        if all(h - kh > threshold for kh in kept_hashes):
            kept.append(path)
            kept_hashes.append(h)

    return kept


def _seconds_to_filename(total_seconds: int) -> str:
    """Convert a timestamp in seconds to a keyframe_MMSS.png filename."""
    mm = total_seconds // 60
    ss = total_seconds % 60
    return f"keyframe_{mm:02d}{ss:02d}.png"


def _sample_long_scenes(
    video_path: Path,
    scene_list: list,
    output_dir: Path,
    max_keyframes: int,
) -> list[Path]:
    """Capture extra frames from long scenes when visual changes occur.

    Instead of uniform interval sampling, probes every _PROBE_INTERVAL seconds
    and captures a frame only when the mean pixel difference vs. the last
    captured frame exceeds _CHANGE_THRESHOLD. This catches moments when the
    trader draws annotations, switches timeframes, or zooms — while skipping
    idle periods where the chart barely moves.

    A cooldown (_MIN_CAPTURE_GAP) prevents burst captures during rapid drawing.

    Returns list of saved PNG paths.
    """
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    extra_frames: list[Path] = []

    for start_tc, end_tc in scene_list:
        if len(extra_frames) >= max_keyframes:
            break
        start_s = int(start_tc.get_seconds())
        end_s = int(end_tc.get_seconds())
        duration = end_s - start_s
        if duration < _LONG_SCENE_THRESHOLD:
            continue

        # Read the scene-start frame as our baseline
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(start_s * fps))
        ret, prev_frame = cap.read()
        if not ret:
            continue
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        last_capture_t = start_s

        # Probe at regular intervals, capture only on change
        for t in range(start_s + _PROBE_INTERVAL, end_s, _PROBE_INTERVAL):
            if len(extra_frames) >= max_keyframes:
                break

            cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
            ret, frame = cap.read()
            if not ret:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            diff = cv2.absdiff(prev_gray, gray).mean()

            if diff >= _CHANGE_THRESHOLD and (t - last_capture_t) >= _MIN_CAPTURE_GAP:
                fname = _seconds_to_filename(t)
                dest = output_dir / fname
                if not dest.exists():
                    cv2.imwrite(str(dest), frame)
                    extra_frames.append(dest)
                    last_capture_t = t
                # Update baseline to the captured frame so we detect the
                # NEXT change relative to this one, not the scene start
                prev_gray = gray

    cap.release()
    logger.info(
        "Change-detected {n} extra frames from long scenes", n=len(extra_frames)
    )
    return extra_frames


def run_keyframes(video_id: str, work_dir: Path, config: PipelineConfig) -> StageResult:
    """Extract keyframes from a YouTube video using scene detection + interval sampling.

    1. Sentinel guard: skip if keyframes.done exists.
    2. Download video (720p cap) via download_video().
    3. Detect scene transitions with AdaptiveDetector.
    4. Cap at config.max_keyframes scenes.
    5. Save one PNG per scene, rename to timestamp format.
    6. Interval-sample extra frames from long scenes (>60s).
    7. Deduplicate near-identical frames via pHash.
    8. Delete video file.
    9. Write sentinel file.

    Args:
        video_id: YouTube video ID
        work_dir: Root directory for pipeline artifacts
        config: Pipeline configuration

    Returns:
        StageResult with stage_name="keyframe", artifact_path=keyframes.done
    """
    video_dir = work_dir / video_id
    keyframes_done = video_dir / "keyframes.done"

    # Sentinel guard (artifact guard)
    if keyframes_done.exists():
        logger.info("Keyframes already extracted for {video_id} — skipping", video_id=video_id)
        return StageResult(
            stage_name="keyframe",
            artifact_path=keyframes_done,
            skipped=True,
        )

    # Download video
    video_path = download_video(video_id, work_dir, config)

    # Prepare output directory
    output_dir = video_dir / "keyframes"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Open video and detect scenes
    logger.info("Detecting scenes in {path}", path=video_path)
    video = scenedetect.open_video(str(video_path))
    manager = SceneManager()
    manager.add_detector(AdaptiveDetector(adaptive_threshold=8.0, min_scene_len=30))
    manager.detect_scenes(video, show_progress=False)
    scene_list = manager.get_scene_list()

    if len(scene_list) == 0:
        logger.warning("No scenes detected in video {video_id}", video_id=video_id)
        keyframes_done.write_text("0")
        return StageResult(
            stage_name="keyframe",
            artifact_path=keyframes_done,
            skipped=False,
        )

    # Apply hard cap
    scene_list = scene_list[: config.max_keyframes]
    logger.info("Processing {n} scenes (capped at {cap})", n=len(scene_list), cap=config.max_keyframes)

    # Save one PNG per scene using scenedetect
    save_images(
        scene_list,
        video,
        num_images=1,
        image_extension="png",
        encoder_param=9,
        output_dir=str(output_dir),
        show_progress=False,
    )

    # Rename saved PNGs to timestamp format (keyframe_MMSS.png)
    # save_images creates files like: {VIDEO_NAME}-Scene-001-01.png
    # We map them to timestamp names via scene start timecodes
    raw_pngs = sorted(output_dir.glob("*.png"))
    renamed: list[Path] = []
    for raw_png, (start_tc, _end_tc) in zip(raw_pngs, scene_list):
        new_name = timecode_to_filename(start_tc)
        dest = output_dir / new_name
        # Avoid clobbering if two scenes map to same second
        if dest.exists() and dest != raw_png:
            # Append scene index to disambiguate
            base = new_name.replace(".png", "")
            dest = output_dir / f"{base}_{raw_png.stem}.png"
        raw_png.rename(dest)
        renamed.append(dest)

    # Interval-sample extra frames from long scenes
    remaining_cap = config.max_keyframes - len(renamed)
    if remaining_cap > 0:
        extra = _sample_long_scenes(video_path, scene_list, output_dir, remaining_cap)
        renamed.extend(extra)
        renamed.sort(key=lambda p: p.name)

    # Deduplicate by perceptual hash (threshold=5 to distinguish chart states
    # that share the same TradingView layout but show different data/annotations)
    kept_frames = deduplicate_frames(renamed, threshold=5)
    removed = set(renamed) - set(kept_frames)
    for dup in removed:
        dup.unlink()
    logger.info(
        "Kept {kept}/{total} keyframes after dedup",
        kept=len(kept_frames),
        total=len(renamed),
    )

    # Delete video file to save disk space
    video_path.unlink()
    logger.info("Deleted video file {path}", path=video_path)

    # Write sentinel
    keyframes_done.write_text(str(len(kept_frames)))
    logger.info("Keyframe extraction complete: {n} frames", n=len(kept_frames))

    return StageResult(
        stage_name="keyframe",
        artifact_path=keyframes_done,
        skipped=False,
    )
