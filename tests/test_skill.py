"""Tests for yt_to_skill.stages.skill — SKILL.md generation stage."""

import json
from pathlib import Path

import pytest
import yaml

from yt_to_skill.errors import FormatError
from yt_to_skill.models.extraction import (
    EntryCondition,
    StrategyObject,
    TradingLogicExtraction,
)
from yt_to_skill.stages.base import StageResult
from yt_to_skill.stages.skill import render_skill_md, run_skill


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_entry_condition(
    indicator: str = "RSI",
    condition: str = "below 30",
    value: str | None = "30",
    timeframe: str | None = "1h",
    confirmation: str | None = None,
    raw_text: str = "RSI below 30 on 1h",
) -> EntryCondition:
    return EntryCondition(
        indicator=indicator,
        condition=condition,
        value=value,
        timeframe=timeframe,
        confirmation=confirmation,
        raw_text=raw_text,
    )


def make_strategy(
    name: str = "Trend Following",
    market_conditions: list[str] | None = None,
    entry_criteria: list[EntryCondition] | None = None,
    exit_criteria: list[EntryCondition] | None = None,
    indicators: list[str] | None = None,
    risk_rules: list[str] | None = None,
) -> StrategyObject:
    return StrategyObject(
        strategy_name=name,
        market_conditions=market_conditions or ["Uptrend", "High volume"],
        entry_criteria=entry_criteria
        or [make_entry_condition(value="30", timeframe="1h")],
        exit_criteria=exit_criteria
        or [make_entry_condition(indicator="MA", condition="price crosses below", value=None, timeframe="4h", raw_text="price crosses below MA on 4h")],
        indicators=indicators or ["RSI", "MACD"],
        risk_rules=risk_rules or ["Risk 1% per trade", "Stop loss at swing low"],
        unspecified_params=[],
    )


def make_extraction(
    video_id: str = "abc123",
    source_language: str = "zh",
    strategies: list[StrategyObject] | None = None,
) -> TradingLogicExtraction:
    return TradingLogicExtraction(
        video_id=video_id,
        source_language=source_language,
        strategies=strategies if strategies is not None else [make_strategy()],
        is_strategy_content=True,
    )


# ---------------------------------------------------------------------------
# Frontmatter tests
# ---------------------------------------------------------------------------


class TestRenderSkillMdFrontmatter:
    def test_render_skill_md_frontmatter(self):
        extraction = make_extraction()
        output = render_skill_md(extraction)
        # YAML frontmatter delimited by ---
        assert output.startswith("---\n")
        # Parse the frontmatter block
        parts = output.split("---\n", 2)
        assert len(parts) >= 3, "Expected frontmatter delimited by ---"
        fm = yaml.safe_load(parts[1])
        assert "name" in fm
        assert "description" in fm
        assert "metadata" in fm
        meta = fm["metadata"]
        assert "version" in meta
        assert "source_url" in meta
        assert "source_language" in meta

    def test_name_field_lowercase(self):
        extraction = make_extraction(video_id="ABC_DEF")
        output = render_skill_md(extraction)
        parts = output.split("---\n", 2)
        fm = yaml.safe_load(parts[1])
        assert fm["name"] == "abc_def"

    def test_name_field_max_64(self):
        long_id = "x" * 100
        extraction = make_extraction(video_id=long_id)
        output = render_skill_md(extraction)
        parts = output.split("---\n", 2)
        fm = yaml.safe_load(parts[1])
        assert len(fm["name"]) <= 64

    def test_description_field_max_1024(self):
        # Strategy with very long name
        strategy = make_strategy(name="S" * 2000)
        extraction = make_extraction(strategies=[strategy])
        output = render_skill_md(extraction)
        parts = output.split("---\n", 2)
        fm = yaml.safe_load(parts[1])
        assert len(fm["description"]) <= 1024

    def test_description_includes_strategy_names(self):
        strategy = make_strategy(name="MomentumBreakout")
        extraction = make_extraction(strategies=[strategy])
        output = render_skill_md(extraction)
        parts = output.split("---\n", 2)
        fm = yaml.safe_load(parts[1])
        assert "MomentumBreakout" in fm["description"]


# ---------------------------------------------------------------------------
# Body structure tests
# ---------------------------------------------------------------------------


class TestRenderSkillMdBody:
    def test_body_has_four_sections(self):
        extraction = make_extraction()
        output = render_skill_md(extraction)
        assert "## Strategy Overview" in output
        assert "## Entry/Exit Criteria" in output
        assert "## Risk Management" in output
        assert "## Market Regime Filters" in output
        # Check order
        idx_overview = output.index("## Strategy Overview")
        idx_entry = output.index("## Entry/Exit Criteria")
        idx_risk = output.index("## Risk Management")
        idx_market = output.index("## Market Regime Filters")
        assert idx_overview < idx_entry < idx_risk < idx_market

    def test_entry_conditions_rendered(self):
        entry = make_entry_condition(
            indicator="MACD", condition="crosses above signal", value="0", timeframe="4h"
        )
        strategy = make_strategy(entry_criteria=[entry])
        extraction = make_extraction(strategies=[strategy])
        output = render_skill_md(extraction)
        assert "MACD" in output
        assert "crosses above signal" in output

    def test_exit_conditions_rendered(self):
        exit_cond = make_entry_condition(
            indicator="ATR", condition="reaches 2x", value="2", timeframe="1d",
            raw_text="ATR reaches 2x on 1d"
        )
        strategy = make_strategy(exit_criteria=[exit_cond])
        extraction = make_extraction(strategies=[strategy])
        output = render_skill_md(extraction)
        assert "Exit" in output or "exit" in output
        assert "ATR" in output

    def test_requires_specification_inline(self):
        """REQUIRES_SPECIFICATION must appear inline within sections, not as its own section."""
        # Force unspecified param by having a None value — but unspecified_params is
        # auto-populated by model_validator when value=None
        entry = make_entry_condition(value=None, timeframe=None, confirmation=None)
        strategy = make_strategy(entry_criteria=[entry])
        extraction = make_extraction(strategies=[strategy])
        output = render_skill_md(extraction)

        # Should have REQUIRES_SPECIFICATION markers
        assert "REQUIRES_SPECIFICATION" in output

        # The marker should NOT appear as its own top-level "## REQUIRES_SPECIFICATION" section
        assert "## REQUIRES_SPECIFICATION" not in output

        # The marker should appear WITHIN the entry/exit section (not after the last section)
        entry_exit_start = output.index("## Entry/Exit Criteria")
        risk_start = output.index("## Risk Management")
        marker_idx = output.index("REQUIRES_SPECIFICATION")
        assert entry_exit_start < marker_idx < risk_start, (
            "REQUIRES_SPECIFICATION marker should appear within Entry/Exit Criteria section"
        )

    def test_risk_rules_rendered(self):
        strategy = make_strategy(risk_rules=["Never risk more than 2%", "Use ATR stop"])
        extraction = make_extraction(strategies=[strategy])
        output = render_skill_md(extraction)
        assert "Never risk more than 2%" in output
        assert "Use ATR stop" in output

    def test_market_conditions_rendered(self):
        strategy = make_strategy(market_conditions=["Bull market", "Low volatility"])
        extraction = make_extraction(strategies=[strategy])
        output = render_skill_md(extraction)
        assert "Bull market" in output
        assert "Low volatility" in output

    def test_multiple_strategies_sections(self):
        s1 = make_strategy(name="StrategyAlpha")
        s2 = make_strategy(name="StrategyBeta")
        extraction = make_extraction(strategies=[s1, s2])
        output = render_skill_md(extraction)
        assert "StrategyAlpha" in output
        assert "StrategyBeta" in output
        # Both strategies should have their own sections
        assert output.count("## Strategy Overview") == 2 or "StrategyAlpha" in output

    def test_empty_strategies_list(self):
        extraction = make_extraction(strategies=[])
        output = render_skill_md(extraction)
        assert "No trading strategies were extracted" in output


# ---------------------------------------------------------------------------
# run_skill tests
# ---------------------------------------------------------------------------


class TestRunSkill:
    def test_run_skill_creates_scaffold(self, tmp_path: Path):
        work_dir = tmp_path / "work"
        skills_dir = tmp_path / "skills"
        video_id = "testvid001"

        # Create the extracted_logic.json
        extraction = make_extraction(video_id=video_id)
        (work_dir / video_id).mkdir(parents=True)
        extraction.to_file(work_dir / video_id / "extracted_logic.json")

        run_skill(video_id=video_id, work_dir=work_dir, skills_dir=skills_dir)

        assert (skills_dir / video_id / "assets").is_dir()
        assert (skills_dir / video_id / "scripts").is_dir()
        assert (skills_dir / video_id / "references").is_dir()

    def test_run_skill_writes_skill_md(self, tmp_path: Path):
        work_dir = tmp_path / "work"
        skills_dir = tmp_path / "skills"
        video_id = "testvid002"

        extraction = make_extraction(video_id=video_id)
        (work_dir / video_id).mkdir(parents=True)
        extraction.to_file(work_dir / video_id / "extracted_logic.json")

        run_skill(video_id=video_id, work_dir=work_dir, skills_dir=skills_dir)

        skill_md = skills_dir / video_id / "SKILL.md"
        assert skill_md.exists()
        content = skill_md.read_text()
        assert "---" in content  # has frontmatter

    def test_run_skill_returns_stage_result(self, tmp_path: Path):
        work_dir = tmp_path / "work"
        skills_dir = tmp_path / "skills"
        video_id = "testvid003"

        extraction = make_extraction(video_id=video_id)
        (work_dir / video_id).mkdir(parents=True)
        extraction.to_file(work_dir / video_id / "extracted_logic.json")

        result = run_skill(video_id=video_id, work_dir=work_dir, skills_dir=skills_dir)

        assert isinstance(result, StageResult)
        assert result.stage_name == "skill"
        assert result.artifact_path == skills_dir / video_id / "SKILL.md"
        assert result.skipped is False

    def test_run_skill_artifact_guard_skip(self, tmp_path: Path):
        work_dir = tmp_path / "work"
        skills_dir = tmp_path / "skills"
        video_id = "testvid004"

        # Pre-create SKILL.md
        skill_dir = skills_dir / video_id
        skill_dir.mkdir(parents=True)
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("existing content")

        result = run_skill(video_id=video_id, work_dir=work_dir, skills_dir=skills_dir)

        assert result.skipped is True
        # Content should be unchanged
        assert skill_md.read_text() == "existing content"

    def test_run_skill_force_flag(self, tmp_path: Path):
        work_dir = tmp_path / "work"
        skills_dir = tmp_path / "skills"
        video_id = "testvid005"

        # Pre-create SKILL.md with old content
        skill_dir = skills_dir / video_id
        skill_dir.mkdir(parents=True)
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text("old content — should be overwritten")

        extraction = make_extraction(video_id=video_id)
        (work_dir / video_id).mkdir(parents=True)
        extraction.to_file(work_dir / video_id / "extracted_logic.json")

        result = run_skill(
            video_id=video_id, work_dir=work_dir, skills_dir=skills_dir, force=True
        )

        assert result.skipped is False
        assert skill_md.read_text() != "old content — should be overwritten"

    def test_run_skill_missing_extraction(self, tmp_path: Path):
        work_dir = tmp_path / "work"
        skills_dir = tmp_path / "skills"
        video_id = "nonexistent"

        # Don't create extracted_logic.json
        with pytest.raises(FormatError):
            run_skill(video_id=video_id, work_dir=work_dir, skills_dir=skills_dir)
