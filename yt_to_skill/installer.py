"""Installer module for yt-to-skill.

Handles agent detection, skill installation, provenance tracking, listing,
and uninstalling across all Agent Skills-compatible tools.

Supported agents:
- Claude Code  (~/.claude/skills/)
- Codex CLI    (~/.agents/skills/)
- Cursor       (~/.cursor/skills/)
- Gemini CLI   (~/.gemini/skills/)
- GitHub Copilot (~/.copilot/skills/)  [global] / (.github/skills/)  [project]
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml
from loguru import logger

# ---------------------------------------------------------------------------
# Path maps (evaluated at call time to support test monkeypatching)
# ---------------------------------------------------------------------------


def get_global_paths() -> dict[str, Path]:
    """Return agent name -> global skills directory, evaluated at call time.

    Path.home() is called inside so tests can monkeypatch it.
    """
    home = Path.home()
    return {
        "claude-code": home / ".claude" / "skills",
        "codex": home / ".agents" / "skills",
        "cursor": home / ".cursor" / "skills",
        "gemini": home / ".gemini" / "skills",
        "copilot": home / ".copilot" / "skills",
    }


def get_project_paths() -> dict[str, Path]:
    """Return agent name -> project-local skills directory (relative paths).

    These are relative to the current working directory.
    Copilot uses .github/skills/ (not .copilot/skills/).
    """
    return {
        "claude-code": Path(".claude") / "skills",
        "codex": Path(".agents") / "skills",
        "cursor": Path(".cursor") / "skills",
        "gemini": Path(".gemini") / "skills",
        "copilot": Path(".github") / "skills",
    }


# Expose as module-level names for backwards compatibility
AGENT_GLOBAL_PATHS = get_global_paths()
AGENT_PROJECT_PATHS = get_project_paths()


# ---------------------------------------------------------------------------
# Agent detection
# ---------------------------------------------------------------------------


def detect_installed_agents() -> list[str]:
    """Return names of agents whose global skills directory exists on disk.

    Iterates over get_global_paths() at call time so monkeypatching Path.home()
    works correctly in tests.
    """
    found: list[str] = []
    for agent, path in get_global_paths().items():
        if path.is_dir():
            found.append(agent)
        else:
            logger.debug("Agent {agent!r} not found: {path} does not exist", agent=agent, path=path)
    return found


# ---------------------------------------------------------------------------
# Name sanitization
# ---------------------------------------------------------------------------


def sanitize_skill_name(name: str) -> str:
    """Convert a raw name to a safe skill directory name.

    Rules:
    - Lowercase
    - Replace any non-alphanumeric character (except existing hyphens) with a hyphen
    - Collapse consecutive hyphens into one
    - Strip leading/trailing hyphens
    - Truncate to 64 characters

    Args:
        name: Raw name string (e.g. "BTC@MACD#2024").

    Returns:
        Sanitized name string (e.g. "btc-macd-2024").
    """
    lowered = name.lower()
    # Replace non-alphanumeric (not hyphen) with hyphens
    replaced = re.sub(r"[^a-z0-9-]", "-", lowered)
    # Collapse consecutive hyphens
    collapsed = re.sub(r"-{2,}", "-", replaced)
    # Strip leading/trailing hyphens
    stripped = collapsed.strip("-")
    # Truncate to 64 characters
    return stripped[:64]


# ---------------------------------------------------------------------------
# Provenance injection
# ---------------------------------------------------------------------------


def _inject_provenance(skill_md_text: str, video_id: str) -> str:
    """Add source_video_id and installed_at to SKILL.md frontmatter.

    Parses the YAML block between the first two --- markers, adds the provenance
    fields, and re-serializes. Returns the text unchanged if no frontmatter found.

    Args:
        skill_md_text: Full text of a SKILL.md file.
        video_id: YouTube video ID to record as source.

    Returns:
        Updated SKILL.md text with provenance fields, or the original text
        if no frontmatter (--- markers) is present.
    """
    if not skill_md_text.startswith("---"):
        return skill_md_text

    # Split on the closing --- of the frontmatter
    # Format: "---\n<yaml>\n---\n<body>"
    parts = skill_md_text.split("---\n", 2)
    if len(parts) < 3:
        return skill_md_text

    _opening, fm_yaml, body = parts
    fm: dict = yaml.safe_load(fm_yaml) or {}

    fm["source_video_id"] = video_id
    fm["installed_at"] = datetime.now(timezone.utc).isoformat()

    new_fm_yaml = yaml.dump(fm, default_flow_style=False, allow_unicode=True).rstrip()
    return f"---\n{new_fm_yaml}\n---\n{body}"


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------


def _check_conflict(install_path: Path, skill_name: str) -> bool:
    """Return True if a skill with this name already exists at install_path.

    Args:
        install_path: Base directory where skills are stored.
        skill_name: Skill directory name to check.

    Returns:
        True if (install_path / skill_name) exists, False otherwise.
    """
    return (install_path / skill_name).exists()


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------


def install_skill(
    src_dir: Path,
    target_base: Path,
    skill_name: str,
    video_id: str,
    *,
    overwrite: bool = False,
) -> Path:
    """Copy the skill directory tree to a target agent skills path.

    Copies the full tree (SKILL.md + assets/ + scripts/ + references/),
    creates parent directories as needed, injects provenance into SKILL.md.

    Args:
        src_dir: Source skill directory (e.g. skills/<video_id>/).
        target_base: Base agent skills directory (e.g. ~/.claude/skills/).
        skill_name: Sanitized skill directory name.
        video_id: YouTube video ID for provenance tracking.
        overwrite: When True, replaces an existing skill at the target.

    Returns:
        Path to the installed skill directory.

    Raises:
        FileExistsError: When a skill with the same name exists and overwrite=False.
    """
    dest_dir = target_base / skill_name

    # Create parent dirs
    target_base.mkdir(parents=True, exist_ok=True)

    # Conflict check
    if _check_conflict(target_base, skill_name):
        if not overwrite:
            raise FileExistsError(
                f"Skill '{skill_name}' already exists at {dest_dir}. "
                "Use overwrite=True to replace it."
            )
        logger.debug("Overwriting existing skill at {path}", path=dest_dir)
        shutil.rmtree(dest_dir)

    # Copy entire directory tree
    shutil.copytree(src_dir, dest_dir, dirs_exist_ok=False)
    logger.info("Skill '{name}' installed to {path}", name=skill_name, path=dest_dir)

    # Inject provenance into installed SKILL.md
    skill_md_path = dest_dir / "SKILL.md"
    if skill_md_path.exists():
        original = skill_md_path.read_text(encoding="utf-8")
        updated = _inject_provenance(original, video_id)
        skill_md_path.write_text(updated, encoding="utf-8")

    return dest_dir


# ---------------------------------------------------------------------------
# List installed skills
# ---------------------------------------------------------------------------


def list_installed_skills() -> list[dict]:
    """Scan all global and project paths for yt-to-skill-installed skills.

    Identifies skills by the presence of source_video_id in their SKILL.md
    frontmatter. Scans both global (~/.agent/skills/) and project-local
    (.agent/skills/) paths.

    Returns:
        List of dicts with keys:
        - agent: agent name (e.g. "claude-code")
        - name: skill directory name
        - source_video_id: YouTube video ID
        - installed_at: ISO timestamp string
        - path: absolute Path to the skill directory
        - scope: "global" or "project"
    """
    results: list[dict] = []

    def _scan(agent: str, base_path: Path, scope: str) -> None:
        if not base_path.is_dir():
            return
        for skill_dir in base_path.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                text = skill_md.read_text(encoding="utf-8")
                if not text.startswith("---"):
                    continue
                parts = text.split("---\n", 2)
                if len(parts) < 3:
                    continue
                fm = yaml.safe_load(parts[1]) or {}
                if "source_video_id" not in fm:
                    continue
                results.append(
                    {
                        "agent": agent,
                        "name": skill_dir.name,
                        "source_video_id": fm["source_video_id"],
                        "installed_at": fm.get("installed_at", ""),
                        "path": skill_dir,
                        "scope": scope,
                    }
                )
            except Exception as exc:
                logger.debug("Skipping {path}: {exc}", path=skill_md, exc=exc)

    for agent, path in get_global_paths().items():
        _scan(agent, path, "global")

    for agent, path in get_project_paths().items():
        _scan(agent, path.resolve(), "project")

    return results


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------


def uninstall_skill(name: str) -> list[Path]:
    """Remove a skill from all agent paths where it is installed.

    Searches both global and project-local paths for a directory named `name`
    containing a SKILL.md with source_video_id (i.e. installed by yt-to-skill).
    Removes matching directories with shutil.rmtree.

    Args:
        name: Skill directory name to remove (e.g. "btc-macd-crossover").

    Returns:
        List of Paths that were removed. Empty if skill not found anywhere.
    """
    removed: list[Path] = []

    def _try_remove(base_path: Path) -> None:
        target = base_path / name
        if not target.is_dir():
            return
        skill_md = target / "SKILL.md"
        if not skill_md.exists():
            return
        try:
            text = skill_md.read_text(encoding="utf-8")
            parts = text.split("---\n", 2)
            if len(parts) >= 3:
                fm = yaml.safe_load(parts[1]) or {}
                if "source_video_id" in fm:
                    shutil.rmtree(target)
                    removed.append(target)
                    logger.info("Uninstalled skill '{name}' from {path}", name=name, path=target)
                    return
        except Exception as exc:
            logger.debug("Error reading {path}: {exc}", path=skill_md, exc=exc)

    for path in get_global_paths().values():
        _try_remove(path)

    for path in get_project_paths().values():
        _try_remove(path.resolve())

    return removed
