"""CLI entry point for yt-to-skill.

Usage:
    yt-to-skill <url> [--output-dir DIR] [--force] [--verbose]

Examples:
    yt-to-skill https://www.youtube.com/watch?v=dQw4w9WgXcQ
    yt-to-skill https://www.youtube.com/playlist?list=PLxxx --output-dir ~/skills
    yt-to-skill https://www.youtube.com/@Channel/videos --force
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loguru import logger

from yt_to_skill.config import PipelineConfig
from yt_to_skill.errors import NetworkError, SkillError
from yt_to_skill.orchestrator import run_pipeline
from yt_to_skill.resolver import resolve_urls


# ---------------------------------------------------------------------------
# Status types
# ---------------------------------------------------------------------------

_STATUS_SUCCESS = "success"
_STATUS_SKIPPED = "skipped"
_STATUS_FAILED = "failed"


def _is_non_strategy(results: list) -> bool:
    """Return True if the pipeline stopped at filter due to non-strategy detection.

    This is indicated by the last StageResult having stage_name='filter'
    (pipeline returned early, no translate/extract/skill stages ran).
    """
    if not results:
        return False
    last_stage = results[-1].stage_name
    return last_stage == "filter" and results[-1].error is None


def _print_stage_results(results: list) -> None:
    """Print per-stage progress lines (✓ or ✗) for a video's results."""
    for result in results:
        if result.error:
            print(f"  ✗ {result.stage_name}: {result.error}")
        elif result.skipped:
            print(f"  - {result.stage_name} (cached)")
        else:
            print(f"  ✓ {result.stage_name}")


def _print_summary_table(batch_results: list[tuple[str, str, str]]) -> None:
    """Print a formatted summary table for batch runs.

    Args:
        batch_results: List of (video_id, status, detail) tuples.
    """
    # Column widths
    max_id_len = max(len(vid) for vid, _, _ in batch_results)
    max_id_len = max(max_id_len, 8)  # at least 8 chars for "Video ID"
    max_detail_len = max(len(detail) for _, _, detail in batch_results)
    max_detail_len = max(max_detail_len, 6)  # at least 6 chars for "Detail"

    # Clamp to reasonable widths
    id_width = min(max_id_len, 20)
    detail_width = min(max_detail_len, 60)

    def _truncate(s: str, width: int) -> str:
        if len(s) > width:
            return s[: width - 3] + "..."
        return s

    separator = f"+{'-' * (id_width + 2)}+--------+{'-' * (detail_width + 2)}+"
    header = (
        f"| {'Video ID':<{id_width}} | Status | {'Detail':<{detail_width}} |"
    )

    print()
    print("Summary")
    print(separator)
    print(header)
    print(separator)

    for video_id, status, detail in batch_results:
        if status == _STATUS_SUCCESS:
            marker = "✓"
        elif status == _STATUS_SKIPPED:
            marker = "⚠"
        else:
            marker = "✗"

        vid_col = _truncate(video_id, id_width)
        det_col = _truncate(detail, detail_width)
        print(f"| {vid_col:<{id_width}} | {marker}      | {det_col:<{detail_width}} |")

    print(separator)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for yt-to-skill."""
    parser = argparse.ArgumentParser(
        prog="yt-to-skill",
        description="Convert YouTube trading videos to installable Claude skill files.",
    )
    parser.add_argument(
        "url",
        help="YouTube video, playlist, or channel URL",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        metavar="DIR",
        help="Base directory for skill output (default: skills/)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess even if SKILL.md already exists",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show full debug logs",
    )
    parser.add_argument(
        "--no-keyframes",
        action="store_true",
        help="Skip keyframe extraction",
    )
    parser.add_argument(
        "--max-keyframes",
        type=int,
        default=None,
        metavar="N",
        help="Maximum keyframes per video (default: 20)",
    )

    args = parser.parse_args()

    # ── Configure logging ──────────────────────────────────────────────────
    logger.remove()
    if args.verbose:
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.add(sys.stderr, level="INFO", format="{level}: {message}")

    # ── Build config ───────────────────────────────────────────────────────
    try:
        config = PipelineConfig()  # type: ignore[call-arg]  # loads from .env
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Failed to load configuration: {exc}")
        print("Hint: ensure OPENROUTER_API_KEY is set in your environment or .env file.")
        sys.exit(1)

    if args.output_dir is not None:
        config = config.model_copy(update={"skills_dir": Path(args.output_dir)})

    if args.no_keyframes:
        config = config.model_copy(update={"keyframes_enabled": False})

    if args.max_keyframes is not None:
        config = config.model_copy(update={"max_keyframes": args.max_keyframes})

    # ── Resolve URLs ───────────────────────────────────────────────────────
    try:
        video_ids = resolve_urls(args.url)
    except NetworkError as exc:
        print(str(exc))
        sys.exit(1)

    if not video_ids:
        print("No videos found at the given URL.")
        sys.exit(0)

    # ── Batch loop ─────────────────────────────────────────────────────────
    batch_results: list[tuple[str, str, str]] = []

    try:
        for video_id in video_ids:
            print(f"\nProcessing: {video_id}")

            try:
                results = run_pipeline(video_id, config, force=args.force)
                _print_stage_results(results)

                if _is_non_strategy(results):
                    # Pipeline stopped at filter — not a strategy video
                    batch_results.append((video_id, _STATUS_SKIPPED, "skipped — not a strategy video"))
                else:
                    # Find skill stage result for detail
                    skill_results = [r for r in results if r.stage_name == "skill"]
                    if skill_results and skill_results[-1].error is None:
                        detail = str(skill_results[-1].artifact_path)
                    elif skill_results and skill_results[-1].error:
                        detail = skill_results[-1].error
                        batch_results.append((video_id, _STATUS_FAILED, detail))
                        continue
                    else:
                        detail = "completed"
                    batch_results.append((video_id, _STATUS_SUCCESS, detail))

            except SkillError as exc:
                error_msg = str(exc)
                print(f"  ✗ ERROR: {error_msg}")
                batch_results.append((video_id, _STATUS_FAILED, error_msg))

            except Exception as exc:  # noqa: BLE001
                error_msg = f"UNKNOWN: {exc}"
                print(f"  ✗ {error_msg}")
                batch_results.append((video_id, _STATUS_FAILED, error_msg))

    finally:
        # Print summary table for batch runs (>1 video) or always on failure
        if len(video_ids) > 1:
            _print_summary_table(batch_results)

    # ── Exit code ──────────────────────────────────────────────────────────
    any_failed = any(status == _STATUS_FAILED for _, status, _ in batch_results)
    sys.exit(1 if any_failed else 0)
