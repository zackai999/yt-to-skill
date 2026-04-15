"""Tests for CLI entry point, config extension, and orchestrator wiring."""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

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
         patch("yt_to_skill.cli.run_pipeline", return_value=_make_success_results("vid1xxx")), \
         patch("yt_to_skill.cli._run_install_flow"):

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
         patch("yt_to_skill.cli.run_pipeline", side_effect=mock_run_pipeline), \
         patch("yt_to_skill.cli._run_install_flow"):

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
         patch("yt_to_skill.cli.run_pipeline", side_effect=mock_run_pipeline), \
         patch("yt_to_skill.cli._run_install_flow"):

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
         patch("yt_to_skill.cli.run_pipeline", return_value=_make_success_results("vid1xxx")), \
         patch("yt_to_skill.cli._run_install_flow"):

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
         patch("yt_to_skill.cli.run_pipeline", side_effect=mock_run_pipeline), \
         patch("yt_to_skill.cli._run_install_flow"):

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
         patch("yt_to_skill.cli.run_pipeline", return_value=_make_success_results("vid1xxx")), \
         patch("yt_to_skill.cli._run_install_flow"):

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
         patch("yt_to_skill.cli.run_pipeline", side_effect=mock_run_pipeline), \
         patch("yt_to_skill.cli._run_install_flow"):

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
         patch("yt_to_skill.cli.run_pipeline", side_effect=mock_run_pipeline), \
         patch("yt_to_skill.cli._run_install_flow"):

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
         patch("yt_to_skill.cli.run_pipeline") as mock_run, \
         patch("yt_to_skill.cli._run_install_flow"):

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
             patch("yt_to_skill.cli.run_pipeline", return_value=_make_success_results("vid1xxx")), \
             patch("yt_to_skill.cli._run_install_flow"):
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
             patch("yt_to_skill.cli.run_pipeline", side_effect=mock_run_pipeline), \
             patch("yt_to_skill.cli._run_install_flow"):
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
             patch("yt_to_skill.cli.run_pipeline", return_value=_make_success_results("vid1xxx")), \
             patch("yt_to_skill.cli._run_install_flow"):
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
             patch("yt_to_skill.cli.run_pipeline", side_effect=mock_run_pipeline), \
             patch("yt_to_skill.cli._run_install_flow"):
            with pytest.raises(SystemExit):
                main()

        assert captured_config[0].max_keyframes == 7


# ---------------------------------------------------------------------------
# New subcommand tests (Plan 04-02)
# ---------------------------------------------------------------------------


def test_process_subcommand(monkeypatch, capsys):
    """yt-to-skill process <url> routes to pipeline and exits 0."""
    from yt_to_skill.cli import main

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("sys.argv", ["yt-to-skill", "process", "https://www.youtube.com/watch?v=vid1"])

    with patch("yt_to_skill.cli.resolve_urls", return_value=["vid1"]), \
         patch("yt_to_skill.cli.run_pipeline", return_value=_make_success_results("vid1")), \
         patch("yt_to_skill.cli._run_install_flow"):

        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 0


def test_bare_url_backward_compat(monkeypatch, capsys):
    """yt-to-skill <url> (no subcommand) behaves same as yt-to-skill process <url>."""
    from yt_to_skill.cli import main

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("sys.argv", ["yt-to-skill", "https://www.youtube.com/watch?v=vid1"])

    with patch("yt_to_skill.cli.resolve_urls", return_value=["vid1"]) as mock_resolve, \
         patch("yt_to_skill.cli.run_pipeline", return_value=_make_success_results("vid1")), \
         patch("yt_to_skill.cli._run_install_flow"):

        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 0
    mock_resolve.assert_called_once_with("https://www.youtube.com/watch?v=vid1")


def test_list_subcommand(monkeypatch, capsys):
    """yt-to-skill list calls list_installed_skills and prints results."""
    from yt_to_skill.cli import main

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("sys.argv", ["yt-to-skill", "list"])

    mock_skills = [
        {
            "agent": "claude-code",
            "name": "btc-macd",
            "source_video_id": "abc123",
            "installed_at": "2026-04-15T10:00:00Z",
            "path": Path("/home/user/.claude/skills/btc-macd"),
            "scope": "global",
        }
    ]

    with patch("yt_to_skill.cli.list_installed_skills", return_value=mock_skills):
        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "btc-macd" in out
    assert "claude-code" in out


def test_list_subcommand_empty(monkeypatch, capsys):
    """yt-to-skill list with no skills prints a message."""
    from yt_to_skill.cli import main

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("sys.argv", ["yt-to-skill", "list"])

    with patch("yt_to_skill.cli.list_installed_skills", return_value=[]):
        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "No yt-to-skill" in out or "no skills" in out.lower()


def test_uninstall_subcommand(monkeypatch, capsys):
    """yt-to-skill uninstall <name> calls uninstall_skill and reports results."""
    from yt_to_skill.cli import main

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("sys.argv", ["yt-to-skill", "uninstall", "btc-macd"])

    removed_paths = [Path("/home/user/.claude/skills/btc-macd")]

    with patch("yt_to_skill.cli.uninstall_skill", return_value=removed_paths) as mock_uninstall:
        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 0
    mock_uninstall.assert_called_once_with("btc-macd")
    out = capsys.readouterr().out
    assert "btc-macd" in out


def test_uninstall_not_found(monkeypatch, capsys):
    """yt-to-skill uninstall <missing> prints 'not found' message."""
    from yt_to_skill.cli import main

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("sys.argv", ["yt-to-skill", "uninstall", "missing-skill"])

    with patch("yt_to_skill.cli.uninstall_skill", return_value=[]):
        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "not found" in out.lower() or "missing-skill" in out


def test_install_flag_skips_prompt(monkeypatch):
    """--install claude-code,codex bypasses interactive prompt, installs to specified agents."""
    from yt_to_skill.cli import main

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("sys.argv", [
        "yt-to-skill", "process", "https://www.youtube.com/watch?v=vid1",
        "--install", "claude-code,codex",
    ])

    with patch("yt_to_skill.cli.resolve_urls", return_value=["vid1"]), \
         patch("yt_to_skill.cli.run_pipeline", return_value=_make_success_results("vid1")), \
         patch("yt_to_skill.cli._run_install_flow") as mock_flow:

        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 0
    # _run_install_flow must be called (install flag is passed via args)
    mock_flow.assert_called_once()
    call_args = mock_flow.call_args
    # args.install should be set
    args_passed = call_args[0][1]  # second positional arg is args
    assert args_passed.install == "claude-code,codex"


def test_install_flag_unknown_agent(monkeypatch, capsys):
    """--install bogus-agent prints error about unknown agent."""
    from yt_to_skill.cli import _run_install_flow
    from yt_to_skill.config import PipelineConfig

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    # Create a mock args object with install flag set to an unknown agent
    args = MagicMock()
    args.install = "bogus-agent"

    skill_entries = [(Path("skills/vid1"), "vid1")]

    with patch("yt_to_skill.cli.detect_installed_agents", return_value=["claude-code", "codex"]), \
         patch("yt_to_skill.cli.install_skill"):
        _run_install_flow(skill_entries, args)

    out = capsys.readouterr().out
    assert "bogus-agent" in out or "unknown" in out.lower() or "not found" in out.lower()


def test_existing_flags_under_process(monkeypatch):
    """yt-to-skill process <url> --force --verbose --no-keyframes --max-keyframes 5 all parse correctly."""
    from yt_to_skill.cli import main

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("sys.argv", [
        "yt-to-skill", "process", "https://www.youtube.com/watch?v=vid1",
        "--force", "--verbose", "--no-keyframes", "--max-keyframes", "5",
    ])

    captured = {}

    def mock_run_pipeline(video_id, config, *, force=False):
        captured["force"] = force
        captured["keyframes_enabled"] = config.keyframes_enabled
        captured["max_keyframes"] = config.max_keyframes
        return _make_success_results(video_id)

    with patch("yt_to_skill.cli.resolve_urls", return_value=["vid1"]), \
         patch("yt_to_skill.cli.run_pipeline", side_effect=mock_run_pipeline), \
         patch("yt_to_skill.cli._run_install_flow"):

        with pytest.raises(SystemExit) as exc_info:
            main()

    assert exc_info.value.code == 0
    assert captured["force"] is True
    assert captured["keyframes_enabled"] is False
    assert captured["max_keyframes"] == 5


def test_no_args_shows_help(monkeypatch, capsys):
    """yt-to-skill with no args prints help and exits 0."""
    from yt_to_skill.cli import main

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("sys.argv", ["yt-to-skill"])

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    assert "usage" in out.lower() or "yt-to-skill" in out


def test_batch_collects_skills_for_single_prompt(monkeypatch):
    """Playlist URL processes all videos, then shows ONE install prompt for all generated skills."""
    from yt_to_skill.cli import main

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr("sys.argv", [
        "yt-to-skill", "process", "https://www.youtube.com/playlist?list=PLx",
    ])

    with patch("yt_to_skill.cli.resolve_urls", return_value=["vid1", "vid2"]), \
         patch("yt_to_skill.cli.run_pipeline") as mock_run, \
         patch("yt_to_skill.cli._run_install_flow") as mock_flow:

        mock_run.side_effect = [
            _make_success_results("vid1"),
            _make_success_results("vid2"),
        ]

        with pytest.raises(SystemExit):
            main()

    # install flow called exactly once (not per-video)
    assert mock_flow.call_count == 1
    # All skill entries passed in one call
    install_call_args = mock_flow.call_args[0]
    skill_entries = install_call_args[0]
    assert len(skill_entries) == 2


def test_non_tty_skips_interactive_prompt(monkeypatch, capsys):
    """When sys.stdin.isatty() is False, install prompt is skipped with info message."""
    from yt_to_skill.cli import _run_install_flow

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    args = MagicMock()
    args.install = None  # no --install flag

    skill_entries = [(Path("skills/vid1"), "vid1")]

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = False
        _run_install_flow(skill_entries, args)

    out = capsys.readouterr().out
    assert "non-interactive" in out.lower() or "skipping" in out.lower()


def test_skill_summary_shown_before_install(monkeypatch, capsys, tmp_path):
    """After processing, skill summary (name, strategy count) is printed before install prompt."""
    from yt_to_skill.cli import _run_install_flow

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    # Create a mock skill dir with a SKILL.md
    skill_dir = tmp_path / "my-strategy"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        "---\nname: My Strategy\nsource_video_id: abc123\n---\n# My Strategy\n",
        encoding="utf-8",
    )

    args = MagicMock()
    args.install = None

    skill_entries = [(skill_dir, "abc123")]

    with patch("sys.stdin") as mock_stdin:
        mock_stdin.isatty.return_value = False  # skip interactive part
        _run_install_flow(skill_entries, args)

    out = capsys.readouterr().out
    assert "My Strategy" in out or "my-strategy" in out


def test_install_conflict_prompts_overwrite(monkeypatch, tmp_path):
    """When skill exists at target, questionary.confirm('Overwrite?') is called."""
    from yt_to_skill.cli import _run_install_flow

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    skill_dir = tmp_path / "my-strategy"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: My Strategy\nsource_video_id: abc123\n---\n# My Strategy\n",
        encoding="utf-8",
    )

    args = MagicMock()
    args.install = None

    target_base = tmp_path / "claude-skills"
    target_base.mkdir()

    skill_entries = [(skill_dir, "abc123")]

    with patch("sys.stdin") as mock_stdin, \
         patch("yt_to_skill.cli.detect_installed_agents", return_value=["claude-code"]), \
         patch("yt_to_skill.cli.get_global_paths", return_value={"claude-code": target_base}), \
         patch("yt_to_skill.cli.get_project_paths", return_value={"claude-code": tmp_path / "proj"}), \
         patch("yt_to_skill.cli._check_conflict", return_value=True), \
         patch("yt_to_skill.cli.install_skill") as mock_install, \
         patch("yt_to_skill.cli.questionary") as mock_q:

        mock_stdin.isatty.return_value = True

        # Setup questionary chain
        mock_q.checkbox.return_value.ask.return_value = ["claude-code"]
        mock_q.select.return_value.ask.return_value = "global"
        mock_q.confirm.return_value.ask.return_value = True  # overwrite confirmed

        _run_install_flow(skill_entries, args)

    mock_q.confirm.assert_called_once()
    confirm_call_str = str(mock_q.confirm.call_args)
    assert "verwrite" in confirm_call_str or "exist" in confirm_call_str.lower()


def test_install_conflict_offers_custom_name(monkeypatch, tmp_path):
    """When skill exists and user declines overwrite, questionary.text() prompts for custom name."""
    from yt_to_skill.cli import _run_install_flow

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    skill_dir = tmp_path / "my-strategy"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: My Strategy\nsource_video_id: abc123\n---\n# My Strategy\n",
        encoding="utf-8",
    )

    args = MagicMock()
    args.install = None

    target_base = tmp_path / "claude-skills"
    target_base.mkdir()

    skill_entries = [(skill_dir, "abc123")]

    with patch("sys.stdin") as mock_stdin, \
         patch("yt_to_skill.cli.detect_installed_agents", return_value=["claude-code"]), \
         patch("yt_to_skill.cli.get_global_paths", return_value={"claude-code": target_base}), \
         patch("yt_to_skill.cli.get_project_paths", return_value={"claude-code": tmp_path / "proj"}), \
         patch("yt_to_skill.cli._check_conflict", return_value=True), \
         patch("yt_to_skill.cli.install_skill") as mock_install, \
         patch("yt_to_skill.cli.sanitize_skill_name", return_value="my-custom-name") as mock_sanitize, \
         patch("yt_to_skill.cli.questionary") as mock_q:

        mock_stdin.isatty.return_value = True
        mock_q.checkbox.return_value.ask.return_value = ["claude-code"]
        mock_q.select.return_value.ask.return_value = "global"
        mock_q.confirm.return_value.ask.return_value = False  # decline overwrite
        mock_q.text.return_value.ask.return_value = "my-custom-name"

        _run_install_flow(skill_entries, args)

    mock_q.text.assert_called_once()
    mock_sanitize.assert_called()
    mock_install.assert_called_once()
    install_kwargs = mock_install.call_args[1]
    assert install_kwargs.get("skill_name") == "my-custom-name" or \
           mock_install.call_args[0][2] == "my-custom-name"


def test_install_conflict_custom_name_cancel(monkeypatch, tmp_path):
    """When skill exists, user declines overwrite, and cancels custom name prompt — skill skipped."""
    from yt_to_skill.cli import _run_install_flow

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    skill_dir = tmp_path / "my-strategy"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: My Strategy\nsource_video_id: abc123\n---\n# My Strategy\n",
        encoding="utf-8",
    )

    args = MagicMock()
    args.install = None

    target_base = tmp_path / "claude-skills"
    target_base.mkdir()

    skill_entries = [(skill_dir, "abc123")]

    with patch("sys.stdin") as mock_stdin, \
         patch("yt_to_skill.cli.detect_installed_agents", return_value=["claude-code"]), \
         patch("yt_to_skill.cli.get_global_paths", return_value={"claude-code": target_base}), \
         patch("yt_to_skill.cli.get_project_paths", return_value={"claude-code": tmp_path / "proj"}), \
         patch("yt_to_skill.cli._check_conflict", return_value=True), \
         patch("yt_to_skill.cli.install_skill") as mock_install, \
         patch("yt_to_skill.cli.questionary") as mock_q:

        mock_stdin.isatty.return_value = True
        mock_q.checkbox.return_value.ask.return_value = ["claude-code"]
        mock_q.select.return_value.ask.return_value = "global"
        mock_q.confirm.return_value.ask.return_value = False  # decline overwrite
        mock_q.text.return_value.ask.return_value = None  # cancel custom name

        _run_install_flow(skill_entries, args)

    # install_skill must NOT be called
    mock_install.assert_not_called()
