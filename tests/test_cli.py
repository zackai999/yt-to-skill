"""Tests for CLI entry point, config extension, and orchestrator wiring."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yt_to_skill.config import PipelineConfig
from yt_to_skill.errors import LLMError, SkillError
from yt_to_skill.stages.base import StageResult


# ---------------------------------------------------------------------------
# Config extension
# ---------------------------------------------------------------------------


def test_config_skills_dir_field():
    """PipelineConfig.skills_dir defaults to Path('skills')."""
    config = PipelineConfig(openrouter_api_key="test-key")
    assert config.skills_dir == Path("skills")


def test_config_skills_dir_override():
    """PipelineConfig.skills_dir can be set to a custom path."""
    config = PipelineConfig(openrouter_api_key="test-key", skills_dir=Path("custom/output"))
    assert config.skills_dir == Path("custom/output")


# ---------------------------------------------------------------------------
# Orchestrator: skill stage included
# ---------------------------------------------------------------------------


def test_orchestrator_includes_skill_stage():
    """run_pipeline now calls run_skill as the 6th stage."""
    from yt_to_skill.orchestrator import run_pipeline

    mock_results = [
        StageResult("ingest", Path("work/v/metadata.json"), skipped=False),
        StageResult("transcript", Path("work/v/raw_transcript.json"), skipped=False),
        StageResult("filter", Path("work/v/filter_result.json"), skipped=False),
        StageResult("translate", Path("work/v/translated.txt"), skipped=False),
        StageResult("extract", Path("work/v/extracted_logic.json"), skipped=False),
        StageResult("skill", Path("skills/v/SKILL.md"), skipped=False),
    ]

    with patch("yt_to_skill.orchestrator.run_ingest") as mock_ingest, \
         patch("yt_to_skill.orchestrator.run_transcript") as mock_transcript, \
         patch("yt_to_skill.orchestrator.run_filter") as mock_filter, \
         patch("yt_to_skill.orchestrator.run_translate") as mock_translate, \
         patch("yt_to_skill.orchestrator.run_extract") as mock_extract, \
         patch("yt_to_skill.orchestrator.run_skill") as mock_skill, \
         patch("yt_to_skill.orchestrator.run_keyframes") as mock_keyframes, \
         patch("yt_to_skill.orchestrator.FilterResult") as mock_filter_result, \
         patch("yt_to_skill.orchestrator.make_openai_client"), \
         patch("yt_to_skill.orchestrator.make_instructor_client"):

        mock_ingest.return_value = mock_results[0]
        mock_transcript.return_value = mock_results[1]
        mock_filter.return_value = mock_results[2]
        mock_translate.return_value = mock_results[3]
        mock_extract.return_value = mock_results[4]
        mock_skill.return_value = mock_results[5]
        mock_keyframes.return_value = StageResult("keyframes", Path("work/v/keyframes.done"), skipped=False)

        # Make filter pass as strategy
        filter_data = MagicMock()
        filter_data.is_strategy = True
        mock_filter_result.from_json.return_value = filter_data

        config = PipelineConfig(openrouter_api_key="test-key")
        results = run_pipeline("v", config)

    # Skill stage was called
    mock_skill.assert_called_once()
    # Skill result is in the results list
    stage_names = [r.stage_name for r in results]
    assert "skill" in stage_names


def test_orchestrator_run_pipeline_force_flag():
    """run_pipeline accepts force=True and passes it to run_skill."""
    from yt_to_skill.orchestrator import run_pipeline

    skill_result = StageResult("skill", Path("skills/v/SKILL.md"), skipped=False)

    with patch("yt_to_skill.orchestrator.run_ingest") as mock_ingest, \
         patch("yt_to_skill.orchestrator.run_transcript") as mock_transcript, \
         patch("yt_to_skill.orchestrator.run_filter") as mock_filter, \
         patch("yt_to_skill.orchestrator.run_translate") as mock_translate, \
         patch("yt_to_skill.orchestrator.run_extract") as mock_extract, \
         patch("yt_to_skill.orchestrator.run_skill") as mock_skill, \
         patch("yt_to_skill.orchestrator.run_keyframes") as mock_keyframes, \
         patch("yt_to_skill.orchestrator.FilterResult") as mock_filter_result, \
         patch("yt_to_skill.orchestrator.make_openai_client"), \
         patch("yt_to_skill.orchestrator.make_instructor_client"):

        mock_ingest.return_value = StageResult("ingest", Path("w"), skipped=False)
        mock_transcript.return_value = StageResult("transcript", Path("w"), skipped=False)
        mock_filter.return_value = StageResult("filter", Path("w"), skipped=False)
        mock_translate.return_value = StageResult("translate", Path("w"), skipped=False)
        mock_extract.return_value = StageResult("extract", Path("w"), skipped=False)
        mock_skill.return_value = skill_result
        mock_keyframes.return_value = StageResult("keyframes", Path("w/keyframes.done"), skipped=False)

        filter_data = MagicMock()
        filter_data.is_strategy = True
        mock_filter_result.from_json.return_value = filter_data

        config = PipelineConfig(openrouter_api_key="test-key")
        run_pipeline("v", config, force=True)

    # run_skill first call (initial render) has force=True
    first_call_kwargs = mock_skill.call_args_list[0][1]
    assert first_call_kwargs.get("force") is True


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


def _make_success_results(video_id: str = "vid1") -> list[StageResult]:
    """Return a list of successful StageResults including skill stage."""
    return [
        StageResult("ingest", Path(f"work/{video_id}/metadata.json"), skipped=False),
        StageResult("transcript", Path(f"work/{video_id}/raw_transcript.json"), skipped=False),
        StageResult("filter", Path(f"work/{video_id}/filter_result.json"), skipped=False),
        StageResult("translate", Path(f"work/{video_id}/translated.txt"), skipped=False),
        StageResult("extract", Path(f"work/{video_id}/extracted_logic.json"), skipped=False),
        StageResult("skill", Path(f"skills/{video_id}/SKILL.md"), skipped=False),
    ]


def _make_filter_stop_results(video_id: str = "vid1") -> list[StageResult]:
    """Return StageResults where pipeline stopped at filter (non-strategy)."""
    return [
        StageResult("ingest", Path(f"work/{video_id}/metadata.json"), skipped=False),
        StageResult("transcript", Path(f"work/{video_id}/raw_transcript.json"), skipped=False),
        StageResult("filter", Path(f"work/{video_id}/filter_result.json"), skipped=False),
    ]


def test_cli_single_video(monkeypatch, capsys):
    """main() with single video URL processes it and exits 0."""
    from yt_to_skill.cli import main

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("sys.argv", ["yt-to-skill", "https://www.youtube.com/watch?v=vid1xxx"])

    with patch("yt_to_skill.cli.resolve_urls", return_value=["vid1xxx"]) as mock_resolve, \
         patch("yt_to_skill.cli.run_pipeline", return_value=_make_success_results("vid1xxx")):

        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 0
    mock_resolve.assert_called_once_with("https://www.youtube.com/watch?v=vid1xxx")


def test_cli_output_dir_flag(monkeypatch, tmp_path):
    """--output-dir overrides the default skills/ path."""
    from yt_to_skill.cli import main

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    custom_dir = str(tmp_path / "custom_skills")
    monkeypatch.setattr("sys.argv", [
        "yt-to-skill", "https://www.youtube.com/watch?v=vid1xxx",
        "--output-dir", custom_dir,
    ])

    captured_config: list = []

    def mock_run_pipeline(video_id, config, *, force=False):
        captured_config.append(config)
        return _make_success_results(video_id)

    with patch("yt_to_skill.cli.resolve_urls", return_value=["vid1xxx"]), \
         patch("yt_to_skill.cli.run_pipeline", side_effect=mock_run_pipeline):

        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 0
    assert captured_config[0].skills_dir == Path(custom_dir)


def test_cli_force_flag(monkeypatch):
    """--force passes force=True to run_pipeline."""
    from yt_to_skill.cli import main

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("sys.argv", [
        "yt-to-skill", "https://www.youtube.com/watch?v=vid1xxx",
        "--force",
    ])

    captured_force: list = []

    def mock_run_pipeline(video_id, config, *, force=False):
        captured_force.append(force)
        return _make_success_results(video_id)

    with patch("yt_to_skill.cli.resolve_urls", return_value=["vid1xxx"]), \
         patch("yt_to_skill.cli.run_pipeline", side_effect=mock_run_pipeline):

        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 0
    assert captured_force[0] is True


def test_cli_verbose_flag(monkeypatch, capsys):
    """--verbose sets loguru level to DEBUG (no crash)."""
    from yt_to_skill.cli import main

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("sys.argv", [
        "yt-to-skill", "https://www.youtube.com/watch?v=vid1xxx",
        "--verbose",
    ])

    with patch("yt_to_skill.cli.resolve_urls", return_value=["vid1xxx"]), \
         patch("yt_to_skill.cli.run_pipeline", return_value=_make_success_results("vid1xxx")):

        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 0


def test_batch_continues_on_failure(monkeypatch, capsys):
    """When one video raises SkillError, the next video still processes."""
    from yt_to_skill.cli import main

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("sys.argv", [
        "yt-to-skill", "https://www.youtube.com/playlist?list=PLxyz",
    ])

    call_count: list[int] = [0]

    def mock_run_pipeline(video_id, config, *, force=False):
        call_count[0] += 1
        if video_id == "vid1":
            raise LLMError("LLM timeout")
        return _make_success_results(video_id)

    with patch("yt_to_skill.cli.resolve_urls", return_value=["vid1", "vid2"]), \
         patch("yt_to_skill.cli.run_pipeline", side_effect=mock_run_pipeline):

        with pytest.raises(SystemExit) as exc_info:
            main()

    # Both videos were attempted
    assert call_count[0] == 2
    # Exit code 1 because one failed
    assert exc_info.value.code == 1


def test_exit_code_all_success(monkeypatch):
    """Exit code is 0 when all videos succeed."""
    from yt_to_skill.cli import main

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("sys.argv", [
        "yt-to-skill", "https://www.youtube.com/watch?v=vid1xxx",
    ])

    with patch("yt_to_skill.cli.resolve_urls", return_value=["vid1xxx"]), \
         patch("yt_to_skill.cli.run_pipeline", return_value=_make_success_results("vid1xxx")):

        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 0


def test_exit_code_partial_failure(monkeypatch):
    """Exit code is 1 when any video fails."""
    from yt_to_skill.cli import main

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("sys.argv", [
        "yt-to-skill", "https://www.youtube.com/playlist?list=PLx",
    ])

    def mock_run_pipeline(video_id, config, *, force=False):
        if video_id == "vid2":
            raise LLMError("rate limit")
        return _make_success_results(video_id)

    with patch("yt_to_skill.cli.resolve_urls", return_value=["vid1", "vid2"]), \
         patch("yt_to_skill.cli.run_pipeline", side_effect=mock_run_pipeline):

        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 1


def test_batch_summary_table(monkeypatch, capsys):
    """Summary table is printed at end of batch with video status."""
    from yt_to_skill.cli import main

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("sys.argv", [
        "yt-to-skill", "https://www.youtube.com/playlist?list=PLx",
    ])

    def mock_run_pipeline(video_id, config, *, force=False):
        if video_id == "vid2":
            raise LLMError("timeout")
        return _make_success_results(video_id)

    with patch("yt_to_skill.cli.resolve_urls", return_value=["vid1", "vid2"]), \
         patch("yt_to_skill.cli.run_pipeline", side_effect=mock_run_pipeline):

        with pytest.raises(SystemExit):
            main()

    out = capsys.readouterr().out
    # Summary table contains both video IDs
    assert "vid1" in out
    assert "vid2" in out
    # Contains status markers
    assert any(marker in out for marker in ["✓", "✗", "SKILL.md", "LLM"])


def test_non_strategy_video_in_batch(monkeypatch, capsys):
    """Non-strategy video shows as skipped in summary, not as failure."""
    from yt_to_skill.cli import main

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("sys.argv", [
        "yt-to-skill", "https://www.youtube.com/playlist?list=PLx",
    ])

    with patch("yt_to_skill.cli.resolve_urls", return_value=["vid1", "vid2"]), \
         patch("yt_to_skill.cli.run_pipeline") as mock_run:

        # vid1: strategy video (full results including skill)
        # vid2: non-strategy video (pipeline stopped at filter stage — no skill stage)
        mock_run.side_effect = [
            _make_success_results("vid1"),
            _make_filter_stop_results("vid2"),
        ]

        with pytest.raises(SystemExit) as exc_info:
            main()

    # Exit code 0 — non-strategy is not a failure
    assert exc_info.value.code == 0

    out = capsys.readouterr().out
    # vid2 shows as skipped/non-strategy (not error)
    assert "vid2" in out
    assert any(marker in out for marker in ["skipped", "not a strategy", "⚠"])


def test_resolve_error_exits_1(monkeypatch, capsys):
    """NetworkError from resolve_urls causes exit(1) with error message."""
    from yt_to_skill.cli import main
    from yt_to_skill.errors import NetworkError

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("sys.argv", [
        "yt-to-skill", "https://not-youtube.com/video",
    ])

    with patch("yt_to_skill.cli.resolve_urls", side_effect=NetworkError("connection failed")):
        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 1
    out = capsys.readouterr()
    assert "NETWORK" in out.out or "NETWORK" in out.err or "connection failed" in out.out or "connection failed" in out.err


# ---------------------------------------------------------------------------
# Keyframe CLI flags
# ---------------------------------------------------------------------------


class TestNoKeyframesFlag:
    def test_flag_parsed(self, monkeypatch):
        """--no-keyframes flag is accepted by argparse (no error)."""
        from yt_to_skill.cli import main

        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.setattr("sys.argv", [
            "yt-to-skill", "https://www.youtube.com/watch?v=vid1xxx",
            "--no-keyframes",
        ])

        with patch("yt_to_skill.cli.resolve_urls", return_value=["vid1xxx"]), \
             patch("yt_to_skill.cli.run_pipeline", return_value=_make_success_results("vid1xxx")):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0

    def test_flag_disables_keyframes(self, monkeypatch):
        """--no-keyframes sets config.keyframes_enabled=False."""
        from yt_to_skill.cli import main

        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.setattr("sys.argv", [
            "yt-to-skill", "https://www.youtube.com/watch?v=vid1xxx",
            "--no-keyframes",
        ])

        captured_config: list = []

        def mock_run_pipeline(video_id, config, *, force=False):
            captured_config.append(config)
            return _make_success_results(video_id)

        with patch("yt_to_skill.cli.resolve_urls", return_value=["vid1xxx"]), \
             patch("yt_to_skill.cli.run_pipeline", side_effect=mock_run_pipeline):
            with pytest.raises(SystemExit):
                main()

        assert captured_config[0].keyframes_enabled is False


class TestMaxKeyframesFlag:
    def test_flag_parsed(self, monkeypatch):
        """--max-keyframes flag is accepted by argparse (no error)."""
        from yt_to_skill.cli import main

        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.setattr("sys.argv", [
            "yt-to-skill", "https://www.youtube.com/watch?v=vid1xxx",
            "--max-keyframes", "10",
        ])

        with patch("yt_to_skill.cli.resolve_urls", return_value=["vid1xxx"]), \
             patch("yt_to_skill.cli.run_pipeline", return_value=_make_success_results("vid1xxx")):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0

    def test_flag_sets_cap(self, monkeypatch):
        """--max-keyframes N sets config.max_keyframes=N."""
        from yt_to_skill.cli import main

        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        monkeypatch.setattr("sys.argv", [
            "yt-to-skill", "https://www.youtube.com/watch?v=vid1xxx",
            "--max-keyframes", "7",
        ])

        captured_config: list = []

        def mock_run_pipeline(video_id, config, *, force=False):
            captured_config.append(config)
            return _make_success_results(video_id)

        with patch("yt_to_skill.cli.resolve_urls", return_value=["vid1xxx"]), \
             patch("yt_to_skill.cli.run_pipeline", side_effect=mock_run_pipeline):
            with pytest.raises(SystemExit):
                main()

        assert captured_config[0].max_keyframes == 7
