# Phase 4: Auto-install generated skills to Claude Code and compatible skill systems - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning

<domain>
## Phase Boundary

After the pipeline generates `skills/<video_id>/SKILL.md`, detect available Agent Skills-compatible tools on the machine, verify the generated skill, and interactively prompt the user to install it into their chosen coding agents. Add `list` and `uninstall` subcommands. Restructure CLI from flat `yt-to-skill <url>` to subcommand pattern (`process`, `list`, `uninstall`).

</domain>

<decisions>
## Implementation Decisions

### Target systems
- Install to ALL Agent Skills spec-compatible tools (Claude Code, Codex CLI, Cursor, Gemini CLI, Copilot)
- Hard-coded path map for each known tool's skill directory — new tools added by updating the map
- Skip silently + debug log when a target tool is not installed on the machine (directory doesn't exist)
- Interactive CLI prompt after skill generation: show detected agents, user selects which to install into
- Flag override available (e.g. `--install claude-code,codex`) to skip the interactive prompt

### Install location
- Ask the user each time: global (e.g. `~/.claude/skills/`) vs project-local (e.g. `.claude/skills/`)
- Copy the full skill directory tree: SKILL.md + assets/ + scripts/ + references/
- Installed directory named by skill name from YAML frontmatter (e.g. `~/.claude/skills/btc-macd-crossover/`)
- On frontmatter name conflicts: prompt user for a custom name

### CLI restructure
- Subcommand pattern: `yt-to-skill process <url>`, `yt-to-skill list`, `yt-to-skill uninstall <name>`
- Default behavior (no subcommand) still runs `process` for backward compatibility
- Existing flags (`--force`, `--verbose`, `--no-keyframes`, `--max-keyframes`, `--output-dir`) move under `process` subcommand
- `--install <agents>` flag on `process` to skip interactive prompt

### Conflict & versioning
- Ask before overwriting when a skill with the same name is already installed at the target
- Provenance tracked via YAML frontmatter: add `source_video_id` and `installed_at` fields to installed SKILL.md
- `yt-to-skill list` shows only yt-to-skill-generated skills (filtered by `source_video_id` presence in frontmatter)
- `yt-to-skill uninstall <name>` removes the skill from all agents where it was installed

### Post-install behavior
- Verification step before install prompt: show skill summary (name, strategy count, entry/exit criteria count, keyframe count)
- After successful install: summary table showing skill name, agents installed to, install path, status (✓/✗)
- Batch runs (playlist/channel): collect all generated skills, then ONE install prompt at the end for the whole batch
- User selects agents once for the entire batch

### Claude's Discretion
- Exact hard-coded path map for each agent (research needed for Codex/Cursor/Gemini skill directories)
- Interactive prompt implementation (inquirer-style library vs manual input)
- How `yt-to-skill list` formats its output
- How `yt-to-skill uninstall` discovers which agents have the skill installed
- Backward compatibility shim for bare `yt-to-skill <url>` (argparse subcommand default)

</decisions>

<specifics>
## Specific Ideas

- Interactive CLI flow: accept URL → process pipeline → generate skill → show skill summary → prompt for agent selection → install → summary table
- The pipeline's zero-intervention philosophy applies to processing, but install is explicitly user-interactive (user chooses where skills go)
- Batch install: process all videos in playlist/channel first, then single install prompt at end with all generated skills
- Existing `skills/<video_id>/` output stays as the "staging" directory; install copies from there to agent skill directories

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `render_skill_md()` in `yt_to_skill/stages/skill.py`: generates SKILL.md with YAML frontmatter — frontmatter dict can be extended with `source_video_id` and `installed_at`
- `run_skill()` in `yt_to_skill/stages/skill.py`: creates full directory scaffold (assets/, scripts/, references/) — same structure to copy during install
- `_print_summary_table()` in `yt_to_skill/cli.py`: batch summary table pattern — reuse for install summary
- `PipelineConfig` in `yt_to_skill/config.py`: pydantic-settings with env/dotenv — extend with install targets config
- `resolve_urls()` in `yt_to_skill/resolver.py`: URL → video IDs — unchanged, feeds into batch processing

### Established Patterns
- Artifact guard: `Path.exists()` check before work — apply to detect installed skills
- Stage results: `StageResult` pattern — extend or create `InstallResult` for install outcomes
- argparse in `cli.py`: currently flat, needs restructure to `add_subparsers()`
- Loguru logging throughout — install stage follows same pattern
- Summary table at end of batch runs — extend for install results

### Integration Points
- `cli.py:main()`: needs refactor from flat argparse to subcommand pattern
- `orchestrator.py:run_pipeline()`: returns `list[StageResult]` — install stage runs after pipeline returns
- `stages/skill.py`: frontmatter dict needs `source_video_id` field added
- New module needed: `yt_to_skill/installer.py` (or similar) for install logic, agent detection, path map
- `pyproject.toml [project.scripts]`: entry point stays `yt-to-skill` but routes to subcommand handler

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-auto-install-generated-skills-to-claude-code-and-compatible-skill-systems*
*Context gathered: 2026-04-15*
