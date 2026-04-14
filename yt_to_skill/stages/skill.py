"""SKILL.md generation stage.

Converts an extracted_logic.json artifact into an installable Claude skill
following the Agent Skills specification: YAML frontmatter + four-section body.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from loguru import logger
from pydantic import ValidationError

from yt_to_skill.errors import FormatError
from yt_to_skill.models.extraction import TradingLogicExtraction, EntryCondition, StrategyObject
from yt_to_skill.stages.base import StageResult, artifact_guard

# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

_MAX_NAME = 64
_MAX_DESCRIPTION = 1024


def _render_entry_condition(cond: EntryCondition) -> str:
    """Render a single EntryCondition as a markdown bullet."""
    parts = [f"- **{cond.indicator}**: {cond.condition}"]
    extras = []
    if cond.value is not None:
        extras.append(f"value: {cond.value}")
    if cond.timeframe is not None:
        extras.append(f"timeframe: {cond.timeframe}")
    if cond.confirmation is not None:
        extras.append(f"confirmation: {cond.confirmation}")
    if extras:
        parts.append(f"  ({', '.join(extras)})")
    # Add raw_text as italic fallback when structured fields are sparse
    has_structured = cond.value is not None or cond.timeframe is not None
    if not has_structured:
        parts.append(f"\n  *{cond.raw_text}*")
    return "".join(parts)


def _requires_spec_marker(param: str) -> str:
    """Render a REQUIRES_SPECIFICATION inline callout."""
    return f"> **REQUIRES_SPECIFICATION: {param}** — exact value not stated in video"


def _render_strategy_block(strategy: StrategyObject, prefix: str = "") -> str:
    """Render the four canonical sections for a single strategy.

    If prefix is provided (e.g. the strategy name), it appears as a heading
    before the sections.
    """
    lines: list[str] = []

    if prefix:
        lines.append(f"### {prefix}\n")

    # ── Strategy Overview ──────────────────────────────────────────────────
    lines.append("## Strategy Overview\n")
    lines.append(f"**Strategy:** {strategy.strategy_name}\n")
    if strategy.indicators:
        lines.append("\n**Indicators used:**")
        for ind in strategy.indicators:
            lines.append(f"- {ind}")
    lines.append("")

    # ── Entry/Exit Criteria ───────────────────────────────────────────────
    lines.append("## Entry/Exit Criteria\n")
    lines.append("### Entry Conditions\n")
    if strategy.entry_criteria:
        for cond in strategy.entry_criteria:
            lines.append(_render_entry_condition(cond))
    else:
        lines.append("*No entry conditions specified.*")

    # Inline REQUIRES_SPECIFICATION for entry_criteria params
    entry_unspecified = [
        p for p in strategy.unspecified_params if p.startswith("entry_criteria")
    ]
    for param in entry_unspecified:
        lines.append(_requires_spec_marker(param))

    lines.append("")
    lines.append("### Exit Conditions\n")
    if strategy.exit_criteria:
        for cond in strategy.exit_criteria:
            lines.append(_render_entry_condition(cond))
    else:
        lines.append("*No exit conditions specified.*")

    # Inline REQUIRES_SPECIFICATION for exit_criteria params
    exit_unspecified = [
        p for p in strategy.unspecified_params if p.startswith("exit_criteria")
    ]
    for param in exit_unspecified:
        lines.append(_requires_spec_marker(param))

    lines.append("")

    # ── Risk Management ────────────────────────────────────────────────────
    lines.append("## Risk Management\n")
    if strategy.risk_rules:
        for rule in strategy.risk_rules:
            lines.append(f"- {rule}")
    else:
        lines.append("*No risk rules specified.*")
    lines.append("")

    # ── Market Regime Filters ──────────────────────────────────────────────
    lines.append("## Market Regime Filters\n")
    if strategy.market_conditions:
        for cond in strategy.market_conditions:
            lines.append(f"- {cond}")
    else:
        lines.append("*No market conditions specified.*")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Gallery rendering
# ---------------------------------------------------------------------------


def render_gallery_section(keyframe_paths: list[Path]) -> str:
    """Render a ## Chart References gallery section from keyframe PNG paths.

    Args:
        keyframe_paths: List of Path objects for keyframe PNGs.
            Expected filename stem format: keyframe_MMSS (e.g. keyframe_0142.png)

    Returns:
        Markdown string with gallery section, or empty string if no paths given.
    """
    if not keyframe_paths:
        return ""

    lines: list[str] = ["\n## Chart References\n"]
    for path in sorted(keyframe_paths):
        stem = path.stem  # e.g. "keyframe_0142"
        # Extract MMSS portion after the underscore
        raw = stem.split("_", 1)[1] if "_" in stem else stem  # "0142"
        try:
            minutes = int(raw[:2])
            seconds = int(raw[2:])
        except (ValueError, IndexError):
            minutes = 0
            seconds = 0
        lines.append(f"**{minutes}:{seconds:02d}** -- ![](assets/{path.name})")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_skill_md(
    extraction: TradingLogicExtraction,
    keyframe_paths: Optional[list[Path]] = None,
) -> str:
    """Render a TradingLogicExtraction to a SKILL.md string.

    Produces:
    - YAML frontmatter with name, description, metadata block
    - Four-section body per strategy (Strategy Overview, Entry/Exit Criteria,
      Risk Management, Market Regime Filters)
    - REQUIRES_SPECIFICATION inline callouts within relevant sections
    - Optional ## Chart References gallery when keyframe_paths provided

    Args:
        extraction: Parsed trading logic from the extract stage.
        keyframe_paths: Optional list of keyframe PNG paths. When provided,
            a gallery section is appended. Backward compatible: callers that
            pass no argument get the same output as before.
    """
    # ── Frontmatter ────────────────────────────────────────────────────────
    name = extraction.video_id.lower()[:_MAX_NAME]

    strategy_names = [s.strategy_name for s in extraction.strategies]
    if strategy_names:
        description = "Trading strategies extracted from video: " + ", ".join(strategy_names)
    else:
        description = f"Trading logic extracted from video {extraction.video_id}."
    description = description[:_MAX_DESCRIPTION]

    metadata = {
        "version": "1.0",
        "source_url": f"https://www.youtube.com/watch?v={extraction.video_id}",
        "source_language": extraction.source_language,
    }

    frontmatter_dict = {
        "name": name,
        "description": description,
        "metadata": metadata,
    }

    # Use yaml.dump but strip trailing newline, then wrap with ---
    fm_yaml = yaml.dump(frontmatter_dict, default_flow_style=False, allow_unicode=True).rstrip()
    frontmatter_block = f"---\n{fm_yaml}\n---\n\n"

    # ── Body ───────────────────────────────────────────────────────────────
    body_lines: list[str] = []

    if not extraction.strategies:
        body_lines.append("No trading strategies were extracted from this video.")
    elif len(extraction.strategies) == 1:
        body_lines.append(_render_strategy_block(extraction.strategies[0]))
    else:
        for strategy in extraction.strategies:
            body_lines.append(_render_strategy_block(strategy, prefix=strategy.strategy_name))

    body = "\n".join(body_lines)

    # ── Gallery (optional) ─────────────────────────────────────────────────
    gallery = ""
    if keyframe_paths:
        gallery = render_gallery_section(keyframe_paths)

    return frontmatter_block + body + gallery


def run_skill(
    video_id: str,
    work_dir: Path,
    skills_dir: Path,
    *,
    force: bool = False,
    keyframe_paths: Optional[list[Path]] = None,
) -> StageResult:
    """Execute the skill generation stage.

    Loads extracted_logic.json from work_dir/<video_id>/, renders SKILL.md,
    creates directory scaffold, and writes output to skills_dir/<video_id>/SKILL.md.

    Args:
        video_id: YouTube video identifier.
        work_dir: Root working directory containing stage artifacts.
        skills_dir: Root directory where skill packages are installed.
        force: When True, regenerate even if SKILL.md already exists.
        keyframe_paths: Optional list of keyframe PNG paths to include as a
            gallery section in SKILL.md.

    Returns:
        StageResult with stage_name="skill".

    Raises:
        FormatError: When extracted_logic.json is missing or malformed.
    """
    skill_path = skills_dir / video_id / "SKILL.md"

    # Artifact guard: skip if already generated (unless forced)
    if not force and artifact_guard(skill_path):
        return StageResult(stage_name="skill", artifact_path=skill_path, skipped=True)

    # Load extraction artifact
    extraction_path = work_dir / video_id / "extracted_logic.json"
    try:
        extraction = TradingLogicExtraction.from_file(extraction_path)
    except FileNotFoundError as exc:
        raise FormatError(
            f"extracted_logic.json not found at {extraction_path}"
        ) from exc
    except (ValidationError, Exception) as exc:
        raise FormatError(
            f"extracted_logic.json is malformed: {exc}"
        ) from exc

    # Create directory scaffold
    skill_dir = skills_dir / video_id
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "assets").mkdir(exist_ok=True)
    (skill_dir / "scripts").mkdir(exist_ok=True)
    (skill_dir / "references").mkdir(exist_ok=True)

    # Render and write SKILL.md
    content = render_skill_md(extraction, keyframe_paths=keyframe_paths)
    skill_path.write_text(content, encoding="utf-8")
    logger.info("Skill written to {path}", path=skill_path)

    return StageResult(stage_name="skill", artifact_path=skill_path, skipped=False)
