"""CLI entry point for yt-to-skill.

Usage:
    yt-to-skill process <url> [--output-dir DIR] [--force] [--verbose] [--install AGENTS]
    yt-to-skill <url>  (backward compat — same as process)
    yt-to-skill list
    yt-to-skill uninstall <name>

Examples:
    yt-to-skill https://www.youtube.com/watch?v=dQw4w9WgXcQ
    yt-to-skill process https://www.youtube.com/watch?v=dQw4w9WgXcQ
    yt-to-skill process https://www.youtube.com/playlist?list=PLxxx --output-dir ~/skills
    yt-to-skill process https://www.youtube.com/@Channel/videos --force
    yt-to-skill process <url> --install claude-code,codex
    yt-to-skill list
    yt-to-skill uninstall my-skill
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import questionary
import yaml
from loguru import logger

from yt_to_skill.config import PipelineConfig
from yt_to_skill.errors import NetworkError, SkillError
from yt_to_skill.installer import (
    _check_conflict,
    detect_installed_agents,
    get_global_paths,
    get_project_paths,
    install_skill,
    list_installed_skills,
    sanitize_skill_name,
    uninstall_skill,
)
from yt_to_skill.orchestrator import run_pipeline
from yt_to_skill.resolver import resolve_urls


# ---------------------------------------------------------------------------
# Status types
# ---------------------------------------------------------------------------

_STATUS_SUCCESS = "success"
_STATUS_SKIPPED = "skipped"
_STATUS_FAILED = "failed"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_url_like(s: str) -> bool:
    """Return True if the string looks like a URL (for backward compat shim)."""
    return s.startswith(("http", "www."))


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


def _parse_skill_frontmatter(skill_dir: Path) -> dict:
    """Parse SKILL.md frontmatter from a skill directory.

    Returns empty dict if SKILL.md not found or has no frontmatter.
    """
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return {}
    try:
        text = skill_md.read_text(encoding="utf-8")
        if not text.startswith("---"):
            return {}
        parts = text.split("---\n", 2)
        if len(parts) < 3:
            return {}
        return yaml.safe_load(parts[1]) or {}
    except Exception:  # noqa: BLE001
        return {}


# ---------------------------------------------------------------------------
# Install flow
# ---------------------------------------------------------------------------


def _run_install_flow(skill_entries: list[tuple[Path, str]], args: argparse.Namespace) -> None:
    """Run the install flow for a list of generated skill entries.

    Args:
        skill_entries: List of (skill_dir_path, video_id) tuples from successful runs.
        args: Parsed CLI args (may have args.install set).
    """
    if not skill_entries:
        return

    # Print skill summary
    print("\nGenerated Skills:")
    for skill_dir, video_id in skill_entries:
        fm = _parse_skill_frontmatter(skill_dir)
        skill_name = fm.get("name", skill_dir.name)
        print(f"  - {skill_name} (video: {video_id})")

    # --install flag: bypass interactive prompt
    if getattr(args, "install", None):
        requested_agents = [a.strip() for a in args.install.split(",") if a.strip()]
        known_agents = list(get_global_paths().keys())

        valid_agents = []
        for agent in requested_agents:
            if agent not in known_agents:
                print(f"Unknown agent: '{agent}'. Known agents: {', '.join(known_agents)}")
            else:
                valid_agents.append(agent)

        if not valid_agents:
            return

        global_paths = get_global_paths()
        install_results: list[tuple[str, str, Path | None, str]] = []

        for skill_dir, video_id in skill_entries:
            fm = _parse_skill_frontmatter(skill_dir)
            raw_name = fm.get("name", skill_dir.name)
            skill_name = sanitize_skill_name(raw_name)

            for agent in valid_agents:
                target_base = global_paths[agent]
                if _check_conflict(target_base, skill_name):
                    print(f"Conflict: '{skill_name}' already exists in {agent}. Use --force to overwrite (skipping).")
                    install_results.append((skill_name, agent, None, "skipped (conflict)"))
                    continue
                try:
                    installed_path = install_skill(skill_dir, target_base, skill_name, video_id, overwrite=False)
                    install_results.append((skill_name, agent, installed_path, "installed"))
                except Exception as exc:  # noqa: BLE001
                    print(f"Failed to install '{skill_name}' to {agent}: {exc}")
                    install_results.append((skill_name, agent, None, f"failed: {exc}"))

        _print_install_summary(install_results)
        return

    # Non-interactive mode
    if not sys.stdin.isatty():
        print("(skipping install prompt in non-interactive mode)")
        return

    # Interactive mode
    agents = detect_installed_agents()
    if not agents:
        print("No Agent Skills-compatible tools detected.")
        return

    selected = questionary.checkbox(
        "Select agents to install into:",
        choices=agents,
    ).ask()
    if not selected:
        return

    scope = questionary.select(
        "Install scope:",
        choices=["global", "project-local"],
    ).ask()
    if scope is None:
        return

    global_paths = get_global_paths()
    project_paths = get_project_paths()

    install_results = []

    for skill_dir, video_id in skill_entries:
        fm = _parse_skill_frontmatter(skill_dir)
        raw_name = fm.get("name", skill_dir.name)
        skill_name = sanitize_skill_name(raw_name)

        for agent in selected:
            if scope == "global":
                target_base = global_paths.get(agent)
            else:
                target_base = project_paths.get(agent)

            if target_base is None:
                install_results.append((skill_name, agent, None, "no path"))
                continue

            if _check_conflict(target_base, skill_name):
                overwrite = questionary.confirm(
                    f"Skill '{skill_name}' already exists in {agent}. Overwrite?"
                ).ask()

                if overwrite:
                    try:
                        installed_path = install_skill(skill_dir, target_base, skill_name, video_id, overwrite=True)
                        install_results.append((skill_name, agent, installed_path, "installed (overwrite)"))
                    except Exception as exc:  # noqa: BLE001
                        install_results.append((skill_name, agent, None, f"failed: {exc}"))
                else:
                    # Prompt for custom name
                    custom = questionary.text("Enter a custom name for this skill:").ask()
                    if not custom:
                        print(f"Skipping {skill_name} for {agent}.")
                        install_results.append((skill_name, agent, None, "skipped"))
                        continue

                    custom_sanitized = sanitize_skill_name(custom)
                    try:
                        installed_path = install_skill(skill_dir, target_base, custom_sanitized, video_id, overwrite=False)
                        install_results.append((custom_sanitized, agent, installed_path, "installed (renamed)"))
                    except Exception as exc:  # noqa: BLE001
                        install_results.append((custom_sanitized, agent, None, f"failed: {exc}"))
            else:
                try:
                    installed_path = install_skill(skill_dir, target_base, skill_name, video_id, overwrite=False)
                    install_results.append((skill_name, agent, installed_path, "installed"))
                except Exception as exc:  # noqa: BLE001
                    install_results.append((skill_name, agent, None, f"failed: {exc}"))

    _print_install_summary(install_results)


def _print_install_summary(results: list[tuple[str, str, Path | None, str]]) -> None:
    """Print a summary table of install operations.

    Args:
        results: List of (skill_name, agent, path, status) tuples.
    """
    if not results:
        return
    print("\nInstall Summary:")
    for skill_name, agent, path, status in results:
        icon = "✓" if "installed" in status else "✗"
        path_str = str(path) if path else "—"
        print(f"  {icon} {skill_name} -> {agent}: {status} ({path_str})")


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def _cmd_process(args: argparse.Namespace) -> None:
    """Handle the 'process' subcommand: run pipeline and then install flow."""
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
    successful_entries: list[tuple[Path, str]] = []  # (skill_dir, video_id) for install

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
                        # Collect skill dir for install flow
                        skill_path = skill_results[-1].artifact_path
                        if skill_path is not None:
                            successful_entries.append((skill_path.parent, video_id))
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

    # ── Install flow ───────────────────────────────────────────────────────
    if successful_entries:
        _run_install_flow(successful_entries, args)

    # ── Exit code ──────────────────────────────────────────────────────────
    any_failed = any(status == _STATUS_FAILED for _, status, _ in batch_results)
    sys.exit(1 if any_failed else 0)


def _cmd_list(args: argparse.Namespace) -> None:  # noqa: ARG001
    """Handle the 'list' subcommand: list all installed yt-to-skill skills."""
    skills = list_installed_skills()
    if not skills:
        print("No yt-to-skill generated skills found.")
        print("(only yt-to-skill generated skills shown)")
    else:
        # Print formatted table
        name_width = max(len(s["name"]) for s in skills)
        name_width = max(name_width, 4)
        agent_width = max(len(s["agent"]) for s in skills)
        agent_width = max(agent_width, 5)
        vid_width = max(len(s.get("source_video_id", "")) for s in skills)
        vid_width = max(vid_width, 8)

        header = f"{'Name':<{name_width}}  {'Agent':<{agent_width}}  {'Source Video':<{vid_width}}  Installed At"
        print(header)
        print("-" * len(header))
        for s in skills:
            print(
                f"{s['name']:<{name_width}}  {s['agent']:<{agent_width}}  "
                f"{s.get('source_video_id', ''):<{vid_width}}  {s.get('installed_at', '')}"
            )
    sys.exit(0)


def _cmd_uninstall(args: argparse.Namespace) -> None:
    """Handle the 'uninstall' subcommand: remove a skill from all agents."""
    removed = uninstall_skill(args.name)
    if not removed:
        print(f"Skill '{args.name}' not found in any agent.")
    else:
        for path in removed:
            print(f"Removed: {path}")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for yt-to-skill."""
    # ── Backward compatibility shim ────────────────────────────────────────
    # If first real arg looks like a URL, treat it as 'process <url>'
    if len(sys.argv) > 1 and _is_url_like(sys.argv[1]):
        sys.argv.insert(1, "process")

    # ── Build parser ───────────────────────────────────────────────────────
    parser = argparse.ArgumentParser(
        prog="yt-to-skill",
        description="Convert YouTube trading videos to installable Claude skill files.",
    )

    subparsers = parser.add_subparsers(dest="subcommand")

    # -- process subcommand --
    process_parser = subparsers.add_parser(
        "process",
        help="Process a YouTube URL and generate a skill",
    )
    process_parser.add_argument(
        "url",
        help="YouTube video, playlist, or channel URL",
    )
    process_parser.add_argument(
        "--output-dir",
        default=None,
        metavar="DIR",
        help="Base directory for skill output (default: skills/)",
    )
    process_parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess even if SKILL.md already exists",
    )
    process_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show full debug logs",
    )
    process_parser.add_argument(
        "--no-keyframes",
        action="store_true",
        help="Skip keyframe extraction",
    )
    process_parser.add_argument(
        "--max-keyframes",
        type=int,
        default=None,
        metavar="N",
        help="Maximum keyframes per video (default: 20)",
    )
    process_parser.add_argument(
        "--install",
        default=None,
        metavar="AGENTS",
        help="Comma-separated agent IDs to install to, skipping interactive prompt",
    )

    # -- list subcommand --
    subparsers.add_parser(
        "list",
        help="List all yt-to-skill generated skills installed on this machine",
    )

    # -- uninstall subcommand --
    uninstall_parser = subparsers.add_parser(
        "uninstall",
        help="Uninstall a skill from all agents",
    )
    uninstall_parser.add_argument(
        "name",
        help="Skill name to uninstall",
    )

    args = parser.parse_args()

    # ── Dispatch ───────────────────────────────────────────────────────────
    if args.subcommand == "process":
        _cmd_process(args)
    elif args.subcommand == "list":
        _cmd_list(args)
    elif args.subcommand == "uninstall":
        _cmd_uninstall(args)
    else:
        # No subcommand, no URL — show help
        parser.print_help()
        sys.exit(0)
