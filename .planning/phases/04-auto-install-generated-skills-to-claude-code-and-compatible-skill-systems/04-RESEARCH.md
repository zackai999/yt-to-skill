# Phase 4: Auto-install Generated Skills — Research

**Researched:** 2026-04-15
**Domain:** CLI restructure, Agent Skills spec filesystem layout, interactive Python prompts, skill install/list/uninstall patterns
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Target systems**
- Install to ALL Agent Skills spec-compatible tools: Claude Code, Codex CLI, Cursor, Gemini CLI, Copilot
- Hard-coded path map for each known tool's skill directory — new tools added by updating the map
- Skip silently + debug log when a target tool is not installed on the machine (directory doesn't exist)
- Interactive CLI prompt after skill generation: show detected agents, user selects which to install into
- Flag override available (e.g. `--install claude-code,codex`) to skip the interactive prompt

**Install location**
- Ask the user each time: global (e.g. `~/.claude/skills/`) vs project-local (e.g. `.claude/skills/`)
- Copy the full skill directory tree: SKILL.md + assets/ + scripts/ + references/
- Installed directory named by skill name from YAML frontmatter (e.g. `~/.claude/skills/btc-macd-crossover/`)
- On frontmatter name conflicts: prompt user for a custom name

**CLI restructure**
- Subcommand pattern: `yt-to-skill process <url>`, `yt-to-skill list`, `yt-to-skill uninstall <name>`
- Default behavior (no subcommand) still runs `process` for backward compatibility
- Existing flags (`--force`, `--verbose`, `--no-keyframes`, `--max-keyframes`, `--output-dir`) move under `process` subcommand
- `--install <agents>` flag on `process` to skip interactive prompt

**Conflict & versioning**
- Ask before overwriting when a skill with the same name is already installed at the target
- Provenance tracked via YAML frontmatter: add `source_video_id` and `installed_at` fields to installed SKILL.md
- `yt-to-skill list` shows only yt-to-skill-generated skills (filtered by `source_video_id` presence in frontmatter)
- `yt-to-skill uninstall <name>` removes the skill from all agents where it was installed

**Post-install behavior**
- Verification step before install prompt: show skill summary (name, strategy count, entry/exit criteria count, keyframe count)
- After successful install: summary table showing skill name, agents installed to, install path, status
- Batch runs: collect all generated skills, then ONE install prompt at the end for the whole batch
- User selects agents once for the entire batch

### Claude's Discretion
- Exact hard-coded path map for each agent (research needed for Codex/Cursor/Gemini skill directories)
- Interactive prompt implementation (inquirer-style library vs manual input)
- How `yt-to-skill list` formats its output
- How `yt-to-skill uninstall` discovers which agents have the skill installed
- Backward compatibility shim for bare `yt-to-skill <url>` (argparse subcommand default)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

---

## Summary

Phase 4 has three distinct technical areas: (1) the **Agent Skills path map** — each compatible tool has a well-documented global and project-local directory for SKILL.md files; (2) the **argparse subcommand refactor** — Python 3.11 `add_subparsers()` supports a `default` subcommand via `set_defaults` plus manual fallback to preserve bare `yt-to-skill <url>` behavior; and (3) the **interactive prompt library** — `questionary` is the recommended choice given the project's existing dependency profile (no heavy extras, cross-platform, stable).

The Agent Skills spec is now well-established: all five target tools (Claude Code, Codex CLI, Cursor, Gemini CLI, Copilot) read SKILL.md files from both a global home-directory location and a project-local location. The canonical name field inside YAML frontmatter controls the installed directory name. Provenance fields (`source_video_id`, `installed_at`) can be appended to frontmatter at install time using `yaml.dump` — the same pattern already used in `stages/skill.py`.

**Primary recommendation:** New module `yt_to_skill/installer.py` owns all agent detection, path resolution, copy logic, and conflict handling. CLI refactor in `cli.py` adds subcommands while routing the bare-URL fallback through the `process` subparser.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| argparse | stdlib | Subcommand CLI routing | Already used; `add_subparsers()` is the idiomatic Python pattern |
| shutil | stdlib | Directory tree copy | `shutil.copytree()` handles recursive copy with `dirs_exist_ok` param |
| yaml (PyYAML) | already in deps | Frontmatter read/write | Already used in `stages/skill.py` for `yaml.dump()` |
| pathlib.Path | stdlib | Path detection and resolution | Already the project standard |
| loguru | already in deps | Debug-level skip logging | Already used throughout |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| questionary | ~2.x | Interactive multi-select + confirm prompts | Recommended for agent selection and confirm-overwrite prompts |
| datetime | stdlib | `installed_at` ISO timestamp | For provenance frontmatter field |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| questionary | python-inquirer | inquirer is heavier and had macOS readline issues in 2024; questionary is lighter and well-maintained |
| questionary | InquirerPy | InquirerPy is richer (fuzzy search) but overkill for a 5-item checkbox list |
| questionary | manual `input()` | Acceptable zero-dep fallback if questionary not installed, but worse UX; questionary is ~100KB and has no heavy transitive deps |
| shutil.copytree | manual recursive copy | copytree with `dirs_exist_ok=True` handles all edge cases; hand-rolling invites bugs |

**Installation:**
```bash
uv add questionary
```

---

## Architecture Patterns

### Recommended Project Structure
```
yt_to_skill/
├── cli.py              # Refactored: add_subparsers() + backward-compat fallback
├── installer.py        # NEW: agent detection, path map, copy, conflict, list, uninstall
└── stages/
    └── skill.py        # Extend frontmatter with source_video_id at generation time
```

### Agent Skills Path Map (VERIFIED)

| Agent | Global path | Project-local path | Detection check |
|-------|-------------|-------------------|-----------------|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` | `Path.home()/".claude/skills"` exists |
| Codex CLI | `~/.agents/skills/` | `.agents/skills/` | `Path.home()/".agents/skills"` exists |
| Cursor | `~/.cursor/skills/` | `.cursor/skills/` | `Path.home()/".cursor/skills"` exists |
| Gemini CLI | `~/.gemini/skills/` | `.gemini/skills/` | `Path.home()/".gemini/skills"` exists |
| Copilot | `~/.copilot/skills/` | `.github/skills/` | `Path.home()/".copilot/skills"` exists |

**Notes:**
- Cursor also accepts `.claude/skills/` and `~/.claude/skills/` for cross-tool compatibility, but we install to Cursor's canonical path to keep things explicit.
- Codex's canonical user-level path is `~/.agents/skills/` (not `~/.codex/skills/`); it also scans `~/.codex/skills/` but `~/.agents/skills/` is the primary.
- Copilot project-local uses `.github/skills/` (not `.copilot/skills/`).
- All tools use the same SKILL.md format — the spec is shared.

**Confidence on path map:** MEDIUM-HIGH. Claude Code path confirmed via official docs (HIGH). Cursor, Gemini, Codex, and Copilot paths verified via official docs and community sources but should be smoke-tested during implementation.

### Pattern 1: Agent Detection
**What:** Probe the filesystem to find which tools are present on the machine.
**When to use:** At the start of the install flow, before showing the user the selection prompt.

```python
# yt_to_skill/installer.py
from pathlib import Path
from loguru import logger

AGENT_GLOBAL_PATHS: dict[str, Path] = {
    "claude-code": Path.home() / ".claude" / "skills",
    "codex":       Path.home() / ".agents" / "skills",
    "cursor":      Path.home() / ".cursor" / "skills",
    "gemini":      Path.home() / ".gemini" / "skills",
    "copilot":     Path.home() / ".copilot" / "skills",
}

AGENT_PROJECT_PATHS: dict[str, Path] = {
    "claude-code": Path(".claude") / "skills",
    "codex":       Path(".agents") / "skills",
    "cursor":      Path(".cursor") / "skills",
    "gemini":      Path(".gemini") / "skills",
    "copilot":     Path(".github") / "skills",
}

def detect_installed_agents() -> list[str]:
    """Return agent IDs whose global skills directory exists."""
    found = []
    for agent_id, path in AGENT_GLOBAL_PATHS.items():
        if path.exists():
            found.append(agent_id)
        else:
            logger.debug("Agent {} not detected (path not found: {})", agent_id, path)
    return found
```

### Pattern 2: argparse Subcommand with Backward Compatibility

**What:** Refactor `cli.py` from flat argparse to `add_subparsers()`, with a default that runs `process` when no subcommand is given (bare `yt-to-skill <url>`).

**When to use:** This is the entire CLI structure for Phase 4.

```python
# cli.py — skeleton
def main() -> None:
    parser = argparse.ArgumentParser(prog="yt-to-skill", ...)
    subparsers = parser.add_subparsers(dest="subcommand")

    # process subcommand (all existing flags move here)
    process_parser = subparsers.add_parser("process", ...)
    process_parser.add_argument("url", ...)
    process_parser.add_argument("--force", ...)
    # ... other existing flags ...
    process_parser.add_argument("--install", metavar="AGENTS", ...)
    process_parser.set_defaults(func=_cmd_process)

    # list subcommand
    list_parser = subparsers.add_parser("list", ...)
    list_parser.set_defaults(func=_cmd_list)

    # uninstall subcommand
    uninstall_parser = subparsers.add_parser("uninstall", ...)
    uninstall_parser.add_argument("name", ...)
    uninstall_parser.set_defaults(func=_cmd_uninstall)

    args = parser.parse_args()

    # Backward compat: bare `yt-to-skill <url>` — no subcommand detected
    if args.subcommand is None:
        # Re-parse inserting "process" as first token if first arg looks like a URL
        if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
            sys.argv.insert(1, "process")
            args = parser.parse_args()
        else:
            parser.print_help()
            sys.exit(0)

    args.func(args)
```

**Alternative approach** (simpler): use `set_defaults(func=_cmd_process)` on the top-level parser, then check `args.subcommand` to decide. Either works; the `sys.argv.insert` approach makes the help text clearer.

### Pattern 3: Install with Provenance Frontmatter

**What:** When copying a skill to an agent directory, mutate the SKILL.md frontmatter to add `source_video_id` and `installed_at`.

```python
import yaml
from datetime import datetime, timezone

def _inject_provenance(skill_md_text: str, video_id: str) -> str:
    """Add source_video_id and installed_at to SKILL.md frontmatter."""
    if not skill_md_text.startswith("---"):
        return skill_md_text  # no frontmatter, skip
    parts = skill_md_text.split("---", 2)
    if len(parts) < 3:
        return skill_md_text
    fm = yaml.safe_load(parts[1]) or {}
    fm["source_video_id"] = video_id
    fm["installed_at"] = datetime.now(timezone.utc).isoformat()
    new_fm = yaml.dump(fm, default_flow_style=False, allow_unicode=True).rstrip()
    return f"---\n{new_fm}\n---{parts[2]}"
```

### Pattern 4: Conflict Detection
**What:** Before copying, check if a skill with the same name exists at the target path. Prompt user to overwrite or abort.

```python
def _check_conflict(install_path: Path, skill_name: str) -> bool:
    """Return True if target skill directory already exists (conflict)."""
    return (install_path / skill_name).exists()
```

### Pattern 5: List Skills (filter by source_video_id)

```python
def list_installed_skills(agents: dict[str, Path]) -> list[dict]:
    """Find all installed skills with source_video_id in frontmatter."""
    results = []
    for agent_id, base_path in agents.items():
        if not base_path.exists():
            continue
        for skill_dir in base_path.iterdir():
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            try:
                text = skill_md.read_text(encoding="utf-8")
                fm = _parse_frontmatter(text)
                if fm.get("source_video_id"):
                    results.append({
                        "agent": agent_id,
                        "name": fm.get("name", skill_dir.name),
                        "source_video_id": fm["source_video_id"],
                        "installed_at": fm.get("installed_at", "unknown"),
                        "path": str(skill_dir),
                    })
            except Exception:
                pass
    return results
```

### Anti-Patterns to Avoid

- **Mutating SKILL.md in the staging directory:** Only inject provenance fields into the installed copy. The staging `skills/<video_id>/SKILL.md` stays clean for re-installation.
- **Blocking on interactive prompt during batch processing:** The batch flow collects all generated skill paths first, then fires ONE install prompt at the end. Do not prompt per video.
- **Using `shutil.copytree` without `dirs_exist_ok=True`:** Without that flag, `copytree` raises if the destination exists. Since we prompt before overwriting but then need to replace, use `dirs_exist_ok=True` after confirming.
- **Hard-coding `Path.home()` expansion at module import time:** Evaluate paths at call time so tests can monkeypatch `Path.home()`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Interactive checkbox + confirm | Manual `input()` parsing | `questionary.checkbox()` + `questionary.confirm()` | Handles terminal raw mode, arrow keys, SIGINT cleanly |
| Recursive directory copy | Manual `os.walk` + file copy | `shutil.copytree(src, dst, dirs_exist_ok=True)` | Handles symlinks, permissions, race conditions |
| YAML frontmatter parse | String split heuristics | `yaml.safe_load()` on the between-`---` portion | Handles multi-line values, quoting edge cases |
| ISO timestamp | `str(datetime.now())` | `datetime.now(timezone.utc).isoformat()` | Timezone-aware, standards-compliant |

**Key insight:** The install flow looks simple (copy a directory) but the edge cases are real — existing skills, partial failures on multi-agent batch, conflicting names, and non-existent target directories all need explicit handling. `shutil.copytree` plus structured error collection handles them reliably.

---

## Common Pitfalls

### Pitfall 1: Missing target directory not auto-created
**What goes wrong:** When user selects "project-local" install for an agent and `.agents/skills/` doesn't exist, `shutil.copytree` will fail.
**Why it happens:** `copytree` creates the leaf directory but not intermediate parents.
**How to avoid:** Call `install_path.mkdir(parents=True, exist_ok=True)` before `copytree`.
**Warning signs:** `FileNotFoundError` on first install into a project that has never used agent skills.

### Pitfall 2: `shutil.copytree` with `dirs_exist_ok` and partial state
**What goes wrong:** If install is interrupted mid-copy (KeyboardInterrupt), the target has a partial skill tree.
**Why it happens:** `copytree` is not atomic.
**How to avoid:** Copy to a temp directory first, then `shutil.move` to the final path (atomic rename on same filesystem). Or accept the risk given this is a local CLI tool — partial copies are rare in practice and `--force` re-runs the install.
**Warning signs:** SKILL.md present but assets/ missing after install.

### Pitfall 3: Frontmatter `name` field not matching directory
**What goes wrong:** SKILL.md frontmatter says `name: btc-strategy` but the staging directory is `skills/<video_id>/`. The install copies to `~/.claude/skills/btc-strategy/` (using frontmatter name), which is correct — but if frontmatter name has uppercase or spaces, Claude Code silently ignores the skill.
**Why it happens:** The Agent Skills spec requires `name` to be lowercase, letters, numbers, hyphens only (max 64 chars).
**How to avoid:** Validate/sanitize the name at install time: `re.sub(r'[^a-z0-9-]', '-', name.lower())[:64]`.
**Warning signs:** Skill directory created but not visible in `claude /explain-code`-style invocation.

### Pitfall 4: argparse subcommand with `None` dest
**What goes wrong:** `args.subcommand` is `None` when user types bare `yt-to-skill <url>`. Attempting `args.func(args)` crashes with `AttributeError`.
**Why it happens:** `add_subparsers(required=False)` is the default; no subcommand sets `dest` to None.
**How to avoid:** Explicit `if args.subcommand is None` check before `args.func(args)`, with the backward-compat URL injection.
**Warning signs:** `AttributeError: Namespace object has no attribute 'func'` in test.

### Pitfall 5: `source_video_id` filter in `list` may miss skills from other tools
**What goes wrong:** If user manually installed a skill and it has no `source_video_id`, it correctly does not appear in `yt-to-skill list`. If they expect to see it, they may be confused.
**Why it happens:** The filter is by design (only show our skills), but should be documented in output.
**How to avoid:** Print "(only yt-to-skill generated skills shown)" as a footer note in `list` output.

### Pitfall 6: Overwrite confirmation skipped on `--install` flag path
**What goes wrong:** When `--install claude-code` bypasses the interactive prompt entirely, it may silently overwrite an existing skill.
**Why it happens:** Non-interactive flag path skips the questionary confirm step.
**How to avoid:** Even on `--install` flag path, check for conflicts and print a warning (or make `--force` required to auto-overwrite via flag).

---

## Code Examples

### questionary multi-select checkbox

```python
# Source: questionary docs (https://questionary.readthedocs.io)
import questionary

def prompt_agent_selection(available_agents: list[str]) -> list[str]:
    """Interactive multi-select for agent installation targets."""
    choices = questionary.checkbox(
        "Select agents to install into:",
        choices=available_agents,
    ).ask()
    return choices or []

def prompt_install_scope() -> str:
    """Ask global vs project-local."""
    return questionary.select(
        "Install scope:",
        choices=["global (~/<agent>/skills/)", "project-local (./<agent>/skills/)"],
    ).ask()

def prompt_overwrite_confirm(skill_name: str, agent: str) -> bool:
    return questionary.confirm(
        f"Skill '{skill_name}' already installed in {agent}. Overwrite?"
    ).ask()
```

### shutil.copytree install pattern

```python
import shutil
from pathlib import Path

def install_skill_dir(src_dir: Path, target_base: Path, skill_name: str) -> Path:
    """Copy skill directory tree to target agent path."""
    dest = target_base / skill_name
    target_base.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)  # clean slate after overwrite confirmed
    shutil.copytree(src_dir, dest)
    return dest
```

### argparse subcommand backward compat shim

```python
import sys
import argparse

def _is_url_like(s: str) -> bool:
    return s.startswith("http") or s.startswith("www.")

def main() -> None:
    # Backward compat: `yt-to-skill https://...` -> `yt-to-skill process https://...`
    if len(sys.argv) > 1 and _is_url_like(sys.argv[1]):
        sys.argv.insert(1, "process")

    parser = argparse.ArgumentParser(prog="yt-to-skill")
    subparsers = parser.add_subparsers(dest="subcommand")
    # ... register subcommands ...
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(0)
    args.func(args)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Skills as single CLAUDE.md section | Agent Skills spec: directory with SKILL.md + supporting files | 2024-2025 | Multi-file skills now standard |
| Tool-specific skill paths | Cross-tool `~/.agents/skills/` alias supported by all major tools | 2025 | Install once, works everywhere (but we still install per-tool for clarity) |
| PyInquirer (unmaintained) | questionary or InquirerPy | 2023+ | PyInquirer abandoned; questionary is the maintained successor |

**Deprecated/outdated:**
- `PyInquirer`: abandoned, Python 3.10+ incompatible. Do not use.
- `.claude/commands/` files: still work but Skills are the recommended format going forward per official Claude Code docs.

---

## Open Questions

1. **Codex CLI canonical user-level path: `~/.agents/skills/` vs `~/.codex/skills/`**
   - What we know: Official Codex docs say `~/.agents/skills/` is primary; the `~/.codex/skills/` path is scanned as a compatibility alias.
   - What's unclear: Whether the `~/.codex/skills/` global path also gets agent detection credit (i.e. does it exist on machines with Codex installed?).
   - Recommendation: Detect Codex by checking `which codex` or `~/.codex/` directory existence, install to `~/.agents/skills/` as primary global path.

2. **questionary behavior in non-TTY environments (CI, piped output)**
   - What we know: questionary uses prompt_toolkit which gracefully handles SIGINT but may hang or error in non-TTY contexts.
   - What's unclear: Whether CI / automated test runs need a `--no-interactive` flag or if questionary already exits cleanly.
   - Recommendation: Wrap `questionary` calls in a `try/except KeyboardInterrupt` + check `sys.stdin.isatty()` before prompting; fall back to auto-decline (no install) in non-TTY mode.

3. **`yt-to-skill uninstall` needs to find which agents have the skill**
   - What we know: We can scan `AGENT_GLOBAL_PATHS` and `AGENT_PROJECT_PATHS` looking for `<name>/SKILL.md` with `source_video_id` matching.
   - What's unclear: Whether uninstall should remove from global only, or also project-local installations.
   - Recommendation: Scan both global and project-local paths, list what was found, confirm per-location before deleting.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_installer.py tests/test_cli.py -x -q` |
| Full suite command | `uv run pytest tests/ -q` |

### Phase Requirements → Test Map

| Behavior | Test Type | Automated Command | File Exists? |
|----------|-----------|-------------------|-------------|
| Agent detection: returns only agents with existing directories | unit | `uv run pytest tests/test_installer.py::test_detect_installed_agents -x` | Wave 0 |
| Install copies full skill tree (SKILL.md + assets/ + scripts/ + references/) | unit | `uv run pytest tests/test_installer.py::test_install_skill_dir_copies_tree -x` | Wave 0 |
| Provenance fields (source_video_id, installed_at) injected into installed SKILL.md | unit | `uv run pytest tests/test_installer.py::test_provenance_injected -x` | Wave 0 |
| Conflict detection: prompt before overwrite | unit | `uv run pytest tests/test_installer.py::test_conflict_prompts_overwrite -x` | Wave 0 |
| list: only shows skills with source_video_id frontmatter | unit | `uv run pytest tests/test_installer.py::test_list_filters_by_provenance -x` | Wave 0 |
| uninstall: removes skill dir from all agents where installed | unit | `uv run pytest tests/test_installer.py::test_uninstall_removes_from_all_agents -x` | Wave 0 |
| `yt-to-skill process <url>` subcommand routes to pipeline | unit | `uv run pytest tests/test_cli.py::test_process_subcommand -x` | Wave 0 |
| Bare `yt-to-skill <url>` backward compat (no subcommand) | unit | `uv run pytest tests/test_cli.py::test_bare_url_backward_compat -x` | Wave 0 |
| `--install <agents>` flag skips interactive prompt | unit | `uv run pytest tests/test_cli.py::test_install_flag_skips_prompt -x` | Wave 0 |
| Name sanitization: uppercase/spaces -> lowercase-hyphens | unit | `uv run pytest tests/test_installer.py::test_name_sanitization -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_installer.py tests/test_cli.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -q`
- **Phase gate:** Full suite green (201 existing + new tests) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_installer.py` — all installer unit tests (no file exists yet)
- [ ] `tests/test_cli.py` — new subcommand tests (file exists, needs new test functions)

---

## Sources

### Primary (HIGH confidence)
- [Claude Code Skills docs](https://code.claude.com/docs/en/skills) — path map, SKILL.md format, frontmatter fields, live change detection
- [VS Code Copilot Agent Skills docs](https://code.visualstudio.com/docs/copilot/customization/agent-skills) — Copilot path map
- [OpenAI Codex Skills docs](https://developers.openai.com/codex/skills) — Codex discovery paths
- Python stdlib argparse docs — `add_subparsers`, `set_defaults`, `dest` parameter

### Secondary (MEDIUM confidence)
- [Gemini CLI Skills](https://geminicli.com/docs/cli/skills/) — Gemini path `~/.gemini/skills/` and `.gemini/skills/`
- [Cursor Agent Skills docs](https://cursor.com/docs/skills) — Cursor paths `~/.cursor/skills/` and `.cursor/skills/`
- [OpenCode Skills](https://opencode.ai/docs/skills/) — cross-tool path aliases

### Tertiary (LOW confidence)
- Community sources confirming Codex primary global path as `~/.agents/skills/` — needs smoke-test during implementation

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are stdlib or already-in-use; only `questionary` is new and well-established
- Agent path map: MEDIUM-HIGH — Claude Code confirmed HIGH; all others verified via official docs but should be smoke-tested
- Architecture: HIGH — patterns follow existing project conventions (StageResult, artifact_guard, loguru, summary table)
- Pitfalls: HIGH — identified from direct code inspection + known argparse and shutil edge cases

**Research date:** 2026-04-15
**Valid until:** 2026-07-15 (agent skill paths are stable; questionary API is stable)
