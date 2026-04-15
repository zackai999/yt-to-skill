"""Tests for yt_to_skill.installer — agent detection, install, provenance, list, uninstall."""

from __future__ import annotations

import textwrap
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from yt_to_skill.installer import (
    detect_installed_agents,
    get_global_paths,
    get_project_paths,
    install_skill,
    list_installed_skills,
    sanitize_skill_name,
    uninstall_skill,
)
from yt_to_skill.installer import _check_conflict, _inject_provenance


# ---------------------------------------------------------------------------
# Helper to create a minimal SKILL.md in a temp dir
# ---------------------------------------------------------------------------

_SAMPLE_FRONTMATTER = textwrap.dedent("""\
    ---
    name: btc-macd-crossover
    description: Trading strategy skill
    user-invocable: true
    allowed-tools: Read Bash(echo *)
    ---

    Body text here.
    """)


def _make_skill_dir(base: Path, skill_name: str, *, with_assets: bool = False) -> Path:
    """Create a minimal skill directory under base/skill_name/."""
    skill_dir = base / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(_SAMPLE_FRONTMATTER)
    if with_assets:
        (skill_dir / "assets").mkdir(exist_ok=True)
        (skill_dir / "assets" / "chart.png").write_bytes(b"\x89PNG...")
        (skill_dir / "scripts").mkdir(exist_ok=True)
        (skill_dir / "references").mkdir(exist_ok=True)
    return skill_dir


# ---------------------------------------------------------------------------
# AGENT_GLOBAL_PATHS / AGENT_PROJECT_PATHS tests
# ---------------------------------------------------------------------------


class TestAgentPathsDefined:
    def test_agent_global_paths_defined(self, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        paths = get_global_paths()
        assert set(paths.keys()) == {"claude-code", "codex", "cursor", "gemini", "copilot"}
        assert paths["claude-code"] == tmp_path / ".claude" / "skills"
        assert paths["codex"] == tmp_path / ".agents" / "skills"
        assert paths["cursor"] == tmp_path / ".cursor" / "skills"
        assert paths["gemini"] == tmp_path / ".gemini" / "skills"
        assert paths["copilot"] == tmp_path / ".copilot" / "skills"

    def test_agent_project_paths_defined(self):
        paths = get_project_paths()
        assert set(paths.keys()) == {"claude-code", "codex", "cursor", "gemini", "copilot"}
        # copilot uses .github/skills/, others use .<agent>/skills/
        assert paths["copilot"] == Path(".github") / "skills"
        assert paths["claude-code"] == Path(".claude") / "skills"
        assert paths["codex"] == Path(".agents") / "skills"
        assert paths["cursor"] == Path(".cursor") / "skills"
        assert paths["gemini"] == Path(".gemini") / "skills"


# ---------------------------------------------------------------------------
# detect_installed_agents tests
# ---------------------------------------------------------------------------


class TestDetectInstalledAgents:
    def test_detect_installed_agents_returns_existing_only(self, monkeypatch, tmp_path):
        # Create claude-code and cursor global skills dirs
        (tmp_path / ".claude" / "skills").mkdir(parents=True)
        (tmp_path / ".cursor" / "skills").mkdir(parents=True)
        # codex, gemini, copilot dirs do NOT exist
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        result = detect_installed_agents()
        assert set(result) == {"claude-code", "cursor"}

    def test_detect_installed_agents_empty_when_none_exist(self, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        result = detect_installed_agents()
        assert result == []


# ---------------------------------------------------------------------------
# sanitize_skill_name tests
# ---------------------------------------------------------------------------


class TestSanitizeSkillName:
    def test_sanitize_skill_name_lowercase(self):
        assert sanitize_skill_name("BTC-MACD") == "btc-macd"

    def test_sanitize_skill_name_spaces(self):
        assert sanitize_skill_name("my strategy name") == "my-strategy-name"

    def test_sanitize_skill_name_special_chars(self):
        assert sanitize_skill_name("btc@macd#2024") == "btc-macd-2024"

    def test_sanitize_skill_name_max_64(self):
        long_name = "a" * 100
        result = sanitize_skill_name(long_name)
        assert len(result) <= 64

    def test_sanitize_skill_name_collapse_hyphens(self):
        assert sanitize_skill_name("btc--macd---crossover") == "btc-macd-crossover"

    def test_sanitize_skill_name_strip_leading_trailing_hyphens(self):
        assert sanitize_skill_name("-btc-macd-") == "btc-macd"


# ---------------------------------------------------------------------------
# _inject_provenance tests
# ---------------------------------------------------------------------------


class TestInjectProvenance:
    def test_inject_provenance_adds_fields(self):
        text = "---\nname: btc-macd\ndescription: test\n---\nBody.\n"
        result = _inject_provenance(text, "abc123")
        fm_text = result.split("---\n", 2)[1]
        fm = yaml.safe_load(fm_text)
        assert fm["source_video_id"] == "abc123"
        assert "installed_at" in fm
        # Verify installed_at parses as ISO datetime
        datetime.fromisoformat(fm["installed_at"])

    def test_inject_provenance_no_frontmatter(self):
        text = "Just plain text without frontmatter markers."
        result = _inject_provenance(text, "abc123")
        assert result == text

    def test_inject_provenance_preserves_existing_fields(self):
        text = "---\nname: btc-macd\ndescription: original desc\n---\nBody.\n"
        result = _inject_provenance(text, "abc123")
        fm_text = result.split("---\n", 2)[1]
        fm = yaml.safe_load(fm_text)
        assert fm["name"] == "btc-macd"
        assert fm["description"] == "original desc"


# ---------------------------------------------------------------------------
# _check_conflict tests
# ---------------------------------------------------------------------------


class TestCheckConflict:
    def test_check_conflict_true(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        assert _check_conflict(tmp_path, "my-skill") is True

    def test_check_conflict_false(self, tmp_path):
        assert _check_conflict(tmp_path, "nonexistent-skill") is False


# ---------------------------------------------------------------------------
# install_skill tests
# ---------------------------------------------------------------------------


class TestInstallSkill:
    def test_install_skill_copies_full_tree(self, tmp_path):
        src_dir = tmp_path / "src" / "my-skill"
        src_dir.mkdir(parents=True)
        (src_dir / "SKILL.md").write_text(_SAMPLE_FRONTMATTER)
        (src_dir / "assets").mkdir()
        (src_dir / "assets" / "chart.png").write_bytes(b"\x89PNG")
        (src_dir / "scripts").mkdir()
        (src_dir / "references").mkdir()

        target_base = tmp_path / "target"
        result = install_skill(src_dir, target_base, "my-skill", "abc123")

        assert (result / "SKILL.md").exists()
        assert (result / "assets" / "chart.png").exists()
        assert (result / "scripts").is_dir()
        assert (result / "references").is_dir()

    def test_install_skill_creates_parent_dirs(self, tmp_path):
        src_dir = tmp_path / "src" / "my-skill"
        src_dir.mkdir(parents=True)
        (src_dir / "SKILL.md").write_text(_SAMPLE_FRONTMATTER)

        target_base = tmp_path / "deeply" / "nested" / "path"
        result = install_skill(src_dir, target_base, "my-skill", "abc123")

        assert result.exists()
        assert result == target_base / "my-skill"

    def test_install_skill_injects_provenance(self, tmp_path):
        src_dir = tmp_path / "src" / "my-skill"
        src_dir.mkdir(parents=True)
        (src_dir / "SKILL.md").write_text(_SAMPLE_FRONTMATTER)

        target_base = tmp_path / "target"
        result = install_skill(src_dir, target_base, "my-skill", "testvid99")

        skill_md_content = (result / "SKILL.md").read_text()
        fm_text = skill_md_content.split("---\n", 2)[1]
        fm = yaml.safe_load(fm_text)
        assert fm["source_video_id"] == "testvid99"
        assert "installed_at" in fm

    def test_install_skill_overwrites_existing(self, tmp_path):
        src_dir = tmp_path / "src" / "my-skill"
        src_dir.mkdir(parents=True)
        (src_dir / "SKILL.md").write_text(_SAMPLE_FRONTMATTER)

        target_base = tmp_path / "target"
        target_skill = target_base / "my-skill"
        target_skill.mkdir(parents=True)
        (target_skill / "old_file.txt").write_text("should be gone")
        (target_skill / "SKILL.md").write_text("old content")

        result = install_skill(src_dir, target_base, "my-skill", "abc123", overwrite=True)
        assert not (result / "old_file.txt").exists()
        assert (result / "SKILL.md").read_text() != "old content"

    def test_install_skill_raises_on_conflict_no_overwrite(self, tmp_path):
        src_dir = tmp_path / "src" / "my-skill"
        src_dir.mkdir(parents=True)
        (src_dir / "SKILL.md").write_text(_SAMPLE_FRONTMATTER)

        target_base = tmp_path / "target"
        target_skill = target_base / "my-skill"
        target_skill.mkdir(parents=True)
        (target_skill / "SKILL.md").write_text("old content")

        with pytest.raises(FileExistsError):
            install_skill(src_dir, target_base, "my-skill", "abc123", overwrite=False)


# ---------------------------------------------------------------------------
# list_installed_skills tests
# ---------------------------------------------------------------------------

_YT_FRONTMATTER = textwrap.dedent("""\
    ---
    name: btc-macd-crossover
    description: Trading strategy
    source_video_id: abc123
    installed_at: '2026-04-15T10:00:00+00:00'
    ---

    Body.
    """)

_NON_YT_FRONTMATTER = textwrap.dedent("""\
    ---
    name: my-other-skill
    description: Some other skill without video id
    ---

    Body.
    """)


class TestListInstalledSkills:
    def test_list_installed_skills_finds_yt_skills(self, monkeypatch, tmp_path):
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        skill_dir = skills_dir / "btc-macd"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(_YT_FRONTMATTER)

        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        result = list_installed_skills()
        names = [r["name"] for r in result]
        assert "btc-macd" in names

    def test_list_installed_skills_ignores_non_yt_skills(self, monkeypatch, tmp_path):
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        skill_dir = skills_dir / "other-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(_NON_YT_FRONTMATTER)

        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        result = list_installed_skills()
        names = [r["name"] for r in result]
        assert "other-skill" not in names

    def test_list_installed_skills_scans_multiple_agents(self, monkeypatch, tmp_path):
        # claude-code global path
        claude_skills = tmp_path / ".claude" / "skills"
        claude_skills.mkdir(parents=True)
        skill_dir1 = claude_skills / "skill-one"
        skill_dir1.mkdir()
        (skill_dir1 / "SKILL.md").write_text(_YT_FRONTMATTER)

        # codex global path
        codex_skills = tmp_path / ".agents" / "skills"
        codex_skills.mkdir(parents=True)
        skill_dir2 = codex_skills / "skill-two"
        skill_dir2.mkdir()
        (skill_dir2 / "SKILL.md").write_text(_YT_FRONTMATTER.replace("btc-macd-crossover", "skill-two-strategy"))

        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        result = list_installed_skills()
        names = [r["name"] for r in result]
        assert "skill-one" in names
        assert "skill-two" in names

    def test_list_installed_skills_result_has_required_keys(self, monkeypatch, tmp_path):
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        skill_dir = skills_dir / "btc-macd"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(_YT_FRONTMATTER)

        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        result = list_installed_skills()
        assert len(result) >= 1
        entry = result[0]
        assert set(entry.keys()) >= {"agent", "name", "source_video_id", "installed_at", "path", "scope"}


# ---------------------------------------------------------------------------
# uninstall_skill tests
# ---------------------------------------------------------------------------


class TestUninstallSkill:
    def test_uninstall_removes_from_all_agents(self, monkeypatch, tmp_path):
        # Install skill into claude-code and codex global paths
        for agent_dir in [".claude/skills", ".agents/skills"]:
            skill_dir = tmp_path / agent_dir / "my-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(_YT_FRONTMATTER)

        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        removed = uninstall_skill("my-skill")
        assert len(removed) == 2
        assert not (tmp_path / ".claude" / "skills" / "my-skill").exists()
        assert not (tmp_path / ".agents" / "skills" / "my-skill").exists()

    def test_uninstall_returns_removed_paths(self, monkeypatch, tmp_path):
        skill_dir = tmp_path / ".claude" / "skills" / "my-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(_YT_FRONTMATTER)

        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        removed = uninstall_skill("my-skill")
        assert len(removed) == 1
        assert isinstance(removed[0], Path)
        assert removed[0] == tmp_path / ".claude" / "skills" / "my-skill"

    def test_uninstall_handles_missing_gracefully(self, monkeypatch, tmp_path):
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        removed = uninstall_skill("nonexistent-skill")
        assert removed == []
