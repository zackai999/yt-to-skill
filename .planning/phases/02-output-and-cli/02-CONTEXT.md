# Phase 2: Output and CLI - Context

**Gathered:** 2026-04-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Generate installable SKILL.md files from `extracted_logic.json` and expose the full pipeline via CLI for single video, playlist, and channel URLs. Covers SKILL.md generation with YAML frontmatter and structured body, CLI entry point with argparse, batch processing with per-video error isolation, and typed error reporting.

</domain>

<decisions>
## Implementation Decisions

### SKILL.md structure
- One SKILL.md per video, even when multiple strategies are extracted — strategies become sections within the file
- Minimal YAML frontmatter: name, description, version, source_url, language — body carries strategy details
- REQUIRES_SPECIFICATION markers rendered as inline callouts (bold with warning emoji) within the relevant section, not collected into a separate section
- Four top-level body sections: Strategy Overview → Entry/Exit Criteria → Risk Management → Market Regime Filters — regime filters are prominent because traders check conditions before entering

### CLI design
- Single command: `yt-to-skill <url>` — no subcommands. One URL in, skills out. Matches zero-intervention philosophy
- argparse for argument parsing — standard library, no extra dependency
- Default output to `skills/<video_id>/SKILL.md` with `--output-dir` flag to override base directory
- Default verbosity: one line per stage as it completes (✓ transcript  ✓ filter  ✓ translate  ✓ extract  ✓ skill). `--verbose` for full logs

### Batch & playlist handling
- Playlist/channel URL resolution via `yt-dlp --flat-playlist` to extract video IDs without downloading
- Sequential processing — one video at a time. LLM calls are the bottleneck; parallelism adds complexity without meaningful speedup
- Skip videos where `skills/<video_id>/SKILL.md` already exists (idempotent). `--force` flag to reprocess
- Table summary at end of batch run: video title, status (✓/✗), skill path or error reason

### Error reporting
- Typed + actionable errors with category prefix: NETWORK, EXTRACTION, LLM, FORMAT — each includes a one-line suggestion
- Batch errors: inline warning line when a video fails, plus inclusion in the final summary table. Failed videos don't stop the run
- Exit code: 0 only if all videos succeed, 1 if any failed — standard for CI pipeline detection
- No CLI-level retries — tenacity retries in the LLM client handle transient failures. CLI reports final error if retries exhausted

### Claude's Discretion
- Exact SKILL.md Markdown formatting and section styling
- Directory scaffold creation for assets/, scripts/, references/
- How to handle videos with no strategies extracted (empty extraction)
- Batch progress display mechanics (progress bar vs simple lines)
- Internal error type hierarchy design

</decisions>

<specifics>
## Specific Ideas

- Agent Skills spec compliance (agentskills.io) — YAML frontmatter + structured Markdown body is the target format
- Progressive disclosure: name+description loaded at startup (~100 tokens), full body on trigger, assets on demand
- Skills should be installable in Claude Code, Codex CLI, Copilot, Cursor, Gemini CLI
- Primary test channel: Trader Feng Ge (Chinese crypto trading, BTC-focused)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `TradingLogicExtraction` model (`yt_to_skill/models/extraction.py`): `from_file()` loads extracted_logic.json — direct input for SKILL.md generation
- `StrategyObject` model: has `strategy_name`, `entry_criteria`, `exit_criteria`, `risk_rules`, `market_conditions`, `unspecified_params` — maps directly to SKILL.md sections
- `EntryCondition` model: structured fields (indicator, condition, value, timeframe, confirmation) + `raw_text` fallback
- `PipelineConfig` (`yt_to_skill/config.py`): pydantic-settings with env/dotenv support — extend for CLI flags
- `extract_video_id()` (`yt_to_skill/orchestrator.py`): parses single video URLs — needs extension for playlist/channel detection
- `run_pipeline()`: processes one video_id, returns `list[StageResult]` — wrap in batch loop

### Established Patterns
- Artifact-guard: check `Path.exists()` before running stages — extend to SKILL.md existence check
- Stage results: `StageResult(stage_name, artifact_path, skipped, error)` — reuse for skill generation stage
- LLM clients created once in orchestrator and passed to stages
- Loguru for logging throughout

### Integration Points
- Input: `work/<video_id>/extracted_logic.json` from Phase 1 pipeline
- Output: `skills/<video_id>/SKILL.md` + directory scaffold (assets/, scripts/, references/)
- CLI entry point: needs `[project.scripts]` in pyproject.toml
- Orchestrator needs a new `run_skill_generation()` stage or post-pipeline step

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-output-and-cli*
*Context gathered: 2026-04-14*
