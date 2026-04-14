"""Tests for keyframe extraction stage: download_video, run_keyframes, dedup."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yt_to_skill.config import PipelineConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Path) -> PipelineConfig:
    return PipelineConfig(
        openrouter_api_key="test-key",
        work_dir=tmp_path,
    )


# ---------------------------------------------------------------------------
# TestConfig
# ---------------------------------------------------------------------------


class TestConfig:
    """Verify new PipelineConfig fields added in Task 1."""

    def test_max_keyframes_default(self, monkeypatch):
        """PipelineConfig.max_keyframes defaults to 20."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "test")
        config = PipelineConfig()
        assert config.max_keyframes == 20

    def test_keyframes_enabled_default(self, monkeypatch):
        """PipelineConfig.keyframes_enabled defaults to True."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "test")
        config = PipelineConfig()
        assert config.keyframes_enabled is True


# ---------------------------------------------------------------------------
# TestDownloadVideo
# ---------------------------------------------------------------------------


class TestDownloadVideo:
    """Tests for download_video() in ingest.py."""

    def test_skips_existing(self, tmp_path: Path) -> None:
        """download_video skips when a video.* file already exists."""
        from yt_to_skill.stages.ingest import download_video

        config = _make_config(tmp_path)
        video_id = "abc123"
        video_dir = tmp_path / video_id
        video_dir.mkdir(parents=True)
        existing = video_dir / "video.mp4"
        existing.touch()

        with patch("yt_to_skill.stages.ingest.yt_dlp.YoutubeDL") as mock_ydl_cls:
            result = download_video(video_id, tmp_path, config)
            mock_ydl_cls.assert_not_called()

        assert result == existing

    def test_downloads_720p(self, tmp_path: Path) -> None:
        """download_video calls yt-dlp with 720p-capped format."""
        from yt_to_skill.stages.ingest import download_video

        config = _make_config(tmp_path)
        video_id = "abc123"
        video_dir = tmp_path / video_id
        video_dir.mkdir(parents=True)
        captured_opts: list[dict] = []

        def capturing_ydl(opts: dict):
            captured_opts.append(opts)
            mock_ydl = MagicMock()
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)
            # Simulate file creation by yt-dlp
            (video_dir / "video.mp4").touch()
            return mock_ydl

        with patch("yt_to_skill.stages.ingest.yt_dlp.YoutubeDL", side_effect=capturing_ydl):
            result = download_video(video_id, tmp_path, config)

        assert len(captured_opts) == 1
        opts = captured_opts[0]
        assert "720" in opts["format"]
        assert opts["merge_output_format"] == "mp4"
        assert opts["fragment_retries"] == 3
        assert opts["quiet"] is True
        assert opts["no_warnings"] is True
        assert result == video_dir / "video.mp4"

    def test_raises_on_no_output(self, tmp_path: Path) -> None:
        """download_video raises FileNotFoundError when yt-dlp produces no video file."""
        from yt_to_skill.stages.ingest import download_video

        config = _make_config(tmp_path)
        video_id = "abc123"
        video_dir = tmp_path / video_id
        video_dir.mkdir(parents=True)

        def no_op_ydl(opts: dict):
            mock_ydl = MagicMock()
            mock_ydl.__enter__ = MagicMock(return_value=mock_ydl)
            mock_ydl.__exit__ = MagicMock(return_value=False)
            # Does NOT create any video file
            return mock_ydl

        with patch("yt_to_skill.stages.ingest.yt_dlp.YoutubeDL", side_effect=no_op_ydl):
            with pytest.raises(FileNotFoundError):
                download_video(video_id, tmp_path, config)


# ---------------------------------------------------------------------------
# TestDedup  (Task 2 — written in this block for co-location)
# ---------------------------------------------------------------------------


class TestDedup:
    """Tests for deduplicate_frames() in keyframe.py."""

    def test_empty_input(self) -> None:
        """deduplicate_frames([]) returns []."""
        from yt_to_skill.stages.keyframe import deduplicate_frames

        assert deduplicate_frames([]) == []

    def test_removes_near_identical(self, tmp_path: Path) -> None:
        """deduplicate_frames removes near-identical frames (same solid color)."""
        from PIL import Image

        from yt_to_skill.stages.keyframe import deduplicate_frames

        # Create two identical-looking solid red PNGs
        frame_a = tmp_path / "frame_a.png"
        frame_b = tmp_path / "frame_b.png"
        img = Image.new("RGB", (64, 64), color=(200, 0, 0))
        img.save(frame_a)
        img.save(frame_b)

        result = deduplicate_frames([frame_a, frame_b], threshold=10)
        assert len(result) == 1
        assert result[0] == frame_a  # first frame kept

    def test_keeps_distinct(self, tmp_path: Path) -> None:
        """deduplicate_frames keeps visually distinct frames."""
        from PIL import Image

        from yt_to_skill.stages.keyframe import deduplicate_frames

        frame_a = tmp_path / "frame_a.png"
        frame_b = tmp_path / "frame_b.png"
        # Visually very different: red vs blue
        Image.new("RGB", (64, 64), color=(200, 0, 0)).save(frame_a)
        Image.new("RGB", (64, 64), color=(0, 0, 200)).save(frame_b)

        result = deduplicate_frames([frame_a, frame_b], threshold=10)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# TestRunKeyframes  (Task 2)
# ---------------------------------------------------------------------------


class TestRunKeyframes:
    """Tests for run_keyframes() in keyframe.py."""

    def test_artifact_guard(self, tmp_path: Path) -> None:
        """run_keyframes returns skipped=True when keyframes.done sentinel exists."""
        from yt_to_skill.stages.keyframe import run_keyframes

        config = _make_config(tmp_path)
        video_id = "abc123"
        video_dir = tmp_path / video_id
        video_dir.mkdir(parents=True)
        sentinel = video_dir / "keyframes.done"
        sentinel.write_text("5")

        result = run_keyframes(video_id, tmp_path, config)

        assert result.skipped is True
        assert result.stage_name == "keyframe"

    def test_cap_enforced(self, tmp_path: Path) -> None:
        """run_keyframes only processes up to max_keyframes scenes."""
        from yt_to_skill.stages.keyframe import run_keyframes

        config = _make_config(tmp_path)
        config = PipelineConfig(openrouter_api_key="test-key", work_dir=tmp_path, max_keyframes=3)
        video_id = "abc123"
        video_dir = tmp_path / video_id
        video_dir.mkdir(parents=True)
        keyframes_dir = video_dir / "keyframes"
        keyframes_dir.mkdir()

        # Create a dummy video file so download_video returns immediately
        dummy_video = video_dir / "video.mp4"
        dummy_video.touch()

        # Build 10 fake scene tuples (start_tc, end_tc) with get_seconds()
        def make_tc(seconds: int):
            tc = MagicMock()
            tc.get_seconds.return_value = float(seconds)
            return tc

        fake_scenes = [(make_tc(i * 10), make_tc(i * 10 + 9)) for i in range(10)]

        saved_scene_lists: list = []

        def fake_save_images(scene_list, video, **kwargs):
            saved_scene_lists.append(scene_list)
            # Create PNG stubs for each scene
            output_dir = Path(kwargs.get("output_dir", str(keyframes_dir)))
            for idx, (start_tc, _) in enumerate(scene_list):
                secs = int(start_tc.get_seconds())
                mm = secs // 60
                ss = secs % 60
                (output_dir / f"keyframe_{mm:02d}{ss:02d}.png").touch()

        mock_video = MagicMock()
        mock_manager = MagicMock()
        mock_manager.get_scene_list.return_value = fake_scenes

        with patch("yt_to_skill.stages.keyframe.scenedetect.open_video", return_value=mock_video), \
             patch("yt_to_skill.stages.keyframe.SceneManager", return_value=mock_manager), \
             patch("yt_to_skill.stages.keyframe.save_images", side_effect=fake_save_images), \
             patch("yt_to_skill.stages.ingest.yt_dlp.YoutubeDL"):  # guard download_video

            result = run_keyframes(video_id, tmp_path, config)

        # Only 3 scenes should have been passed to save_images (max_keyframes=3)
        assert len(saved_scene_lists) == 1
        assert len(saved_scene_lists[0]) == 3
        assert result.stage_name == "keyframe"
        assert result.skipped is False

    def test_video_deleted(self, tmp_path: Path) -> None:
        """run_keyframes deletes the video file after extraction."""
        from yt_to_skill.stages.keyframe import run_keyframes

        config = _make_config(tmp_path)
        video_id = "abc123"
        video_dir = tmp_path / video_id
        video_dir.mkdir(parents=True)
        keyframes_dir = video_dir / "keyframes"
        keyframes_dir.mkdir()

        dummy_video = video_dir / "video.mp4"
        dummy_video.write_text("fake")

        def make_tc(seconds: int):
            tc = MagicMock()
            tc.get_seconds.return_value = float(seconds)
            return tc

        fake_scenes = [(make_tc(0), make_tc(9))]

        def fake_save_images(scene_list, video, **kwargs):
            output_dir = Path(kwargs.get("output_dir", str(keyframes_dir)))
            (output_dir / "keyframe_0000.png").touch()

        mock_video = MagicMock()
        mock_manager = MagicMock()
        mock_manager.get_scene_list.return_value = fake_scenes

        with patch("yt_to_skill.stages.keyframe.scenedetect.open_video", return_value=mock_video), \
             patch("yt_to_skill.stages.keyframe.SceneManager", return_value=mock_manager), \
             patch("yt_to_skill.stages.keyframe.save_images", side_effect=fake_save_images), \
             patch("yt_to_skill.stages.ingest.yt_dlp.YoutubeDL"):

            run_keyframes(video_id, tmp_path, config)

        assert not dummy_video.exists()

    def test_zero_scenes(self, tmp_path: Path) -> None:
        """run_keyframes handles zero scenes: writes sentinel, returns skipped=False."""
        from yt_to_skill.stages.keyframe import run_keyframes

        config = _make_config(tmp_path)
        video_id = "abc123"
        video_dir = tmp_path / video_id
        video_dir.mkdir(parents=True)

        dummy_video = video_dir / "video.mp4"
        dummy_video.touch()

        mock_video = MagicMock()
        mock_manager = MagicMock()
        mock_manager.get_scene_list.return_value = []

        with patch("yt_to_skill.stages.keyframe.scenedetect.open_video", return_value=mock_video), \
             patch("yt_to_skill.stages.keyframe.SceneManager", return_value=mock_manager), \
             patch("yt_to_skill.stages.ingest.yt_dlp.YoutubeDL"):

            result = run_keyframes(video_id, tmp_path, config)

        sentinel = video_dir / "keyframes.done"
        assert sentinel.exists()
        assert result.skipped is False
        assert result.stage_name == "keyframe"
