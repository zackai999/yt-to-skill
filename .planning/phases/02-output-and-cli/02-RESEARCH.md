# Phase 2: Output and CLI - Research

**Researched:** 2026-04-14
**Domain:** SKILL.md generation, CLI entry point, batch/playlist processing, typed error reporting
**Confidence:** HIGH

## Summary

Phase 2 wires together what Phase 1 already produces (`extracted_logic.json`) and delivers the final user-facing artifact: an installable `SKILL.md` file that complies with the Agent Skills open standard. The implementation splits into four distinct concerns: (1) SKILL.md generation from `TradingLogicExtraction` Pydantic models, (2) a CLI entry point using argparse with the `[project.scripts]` mechanism in `pyproject.toml`, (3) playlist/channel batch expansion via the yt-dlp Python API's `extract_flat` mode, and (4) a typed error hierarchy with category-prefixed messages and correct exit codes.

All four concerns are well-supported by the existing Phase 1 codebase. The `StageResult`, `artifact_guard`, and orchestrator patterns established in Phase 1 extend naturally to the skill generation stage. The Agent Skills specification (agentskills.io) defines a strict YAML frontmatter schema; the planner must ensure the generator produces frontmatter that validates against that schema. The yt-dlp Python API (`YoutubeDL` with `extract_flat=True`) avoids subprocess overhead and integrates cleanly with existing ingest-stage patterns.

**Primary recommendation:** Build `run_skill` as a standard pipeline stage returning `StageResult`, expand `extract_video_id` into a separate `resolve_urls` helper that handles playlist/channel detection, wire everything through a thin CLI module, and keep all error taxonomy in a single `errors.py` module.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### SKILL.md structure
- One SKILL.md per video, even when multiple strategies are extracted — strategies become sections within the file
- Minimal YAML frontmatter: name, description, version, source_url, language — body carries strategy details
- REQUIRES_SPECIFICATION markers rendered as inline callouts (bold with warning emoji) within the relevant section, not collected into a separate section
- Four top-level body sections: Strategy Overview → Entry/Exit Criteria → Risk Management → Market Regime Filters — regime filters are prominent because traders check conditions before entering

#### CLI design
- Single command: `yt-to-skill <url>` — no subcommands. One URL in, skills out. Matches zero-intervention philosophy
- argparse for argument parsing — standard library, no extra dependency
- Default output to `skills/<video_id>/SKILL.md` with `--output-dir` flag to override base directory
- Default verbosity: one line per stage as it completes (✓ transcript  ✓ filter  ✓ translate  ✓ extract  ✓ skill). `--verbose` for full logs

#### Batch & playlist handling
- Playlist/channel URL resolution via `yt-dlp --flat-playlist` to extract video IDs without downloading
- Sequential processing — one video at a time. LLM calls are the bottleneck; parallelism adds complexity without meaningful speedup
- Skip videos where `skills/<video_id>/SKILL.md` already exists (idempotent). `--force` flag to reprocess
- Table summary at end of batch run: video title, status (✓/✗), skill path or error reason

#### Error reporting
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

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| OUTP-01 | Pipeline generates SKILL.md following Agent Skills spec (YAML frontmatter + structured Markdown body) | Agent Skills spec fully documented — frontmatter fields, constraints, body format known |
| OUTP-02 | Skill output includes directory structure with assets/ (keyframes), scripts/, references/ | `Path.mkdir(parents=True, exist_ok=True)` — trivial; three subdirs created at skill-write time |
| OUTP-03 | Generated skills use three-level structure: strategy overview, entry/exit criteria, risk management, market regime filters | `StrategyObject` model fields map directly to the four locked sections |
| OUTP-04 | User can run pipeline via CLI with single video URL, playlist URL, or channel URL | argparse + `[project.scripts]` entry point pattern confirmed; yt-dlp Python API handles URL type detection |
| OUTP-05 | Pipeline processes channels/playlists in batch with per-video error isolation | yt-dlp `extract_flat=True` returns video ID list; existing orchestrator try/except pattern extends to batch loop |
| OUTP-06 | Pipeline reports clear error messages distinguishing network, extraction, LLM, and format failures | Typed exception hierarchy with category prefix strings; exit-code convention confirmed |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| argparse | stdlib | CLI argument parsing | Locked decision; zero extra dependency |
| yt-dlp | >=2024.1.0 (already in deps) | Playlist/channel URL expansion via `extract_flat` Python API | Already in pyproject.toml; `YoutubeDL` API avoids subprocess |
| pathlib | stdlib | Skill output directory creation | Already used throughout codebase |
| loguru | >=0.7.2 (already in deps) | Logging; `--verbose` flag toggles level | Already used throughout codebase |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic-settings | >=2.3.0 (already in deps) | Extend `PipelineConfig` with `skills_dir` and `force` fields | CLI flags map cleanly to config fields |
| textwrap / string.Template | stdlib | SKILL.md Markdown body template rendering | No external template engine needed for fixed 4-section layout |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| argparse | click or typer | Click/typer are better ergonomically but add a dependency; argparse is locked |
| yt-dlp Python API | subprocess + `yt-dlp --flat-playlist --dump-json` | Subprocess is simpler to reason about but requires shelling out; API avoids spawning a process |
| string.Template | Jinja2 | Jinja2 is more powerful but adds a dependency; the SKILL.md layout is fixed enough for stdlib templates |

**Installation:** No new packages required. All dependencies already in `pyproject.toml`.

---

## Architecture Patterns

### Recommended Project Structure
```
yt_to_skill/
├── stages/
│   ├── skill.py         # New: run_skill() stage — reads extracted_logic.json, writes SKILL.md
│   └── ...              # Existing stages unchanged
├── errors.py            # New: SkillError hierarchy (NetworkError, ExtractionError, LLMError, FormatError)
├── cli.py               # New: main() entry point, argparse setup, batch loop, progress + summary
├── resolver.py          # New: resolve_urls(url) — single video vs playlist/channel detection
├── orchestrator.py      # Extend: run_pipeline() gains skill stage; expose run_batch()
└── config.py            # Extend: add skills_dir: Path = Path("skills"), force: bool = False
```

### Pattern 1: Skill Stage as StageResult (mirrors Phase 1 stages)
**What:** `run_skill(video_id, work_dir, skills_dir, config)` reads `extracted_logic.json` via `TradingLogicExtraction.from_file()`, renders SKILL.md, writes to `skills/<video_id>/SKILL.md`, returns `StageResult`.
**When to use:** Always — makes skill generation resumable, idempotent, and observable via the standard stage result contract.

```python
# Follows established artifact_guard pattern
def run_skill(video_id: str, work_dir: Path, skills_dir: Path, config: PipelineConfig) -> StageResult:
    skill_path = skills_dir / video_id / "SKILL.md"
    if artifact_guard(skill_path):
        return StageResult(stage_name="skill", artifact_path=skill_path, skipped=True)

    extraction = TradingLogicExtraction.from_file(work_dir / video_id / "extracted_logic.json")
    content = render_skill_md(extraction)

    # Scaffold directories
    skill_dir = skills_dir / video_id
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "assets").mkdir(exist_ok=True)
    (skill_dir / "scripts").mkdir(exist_ok=True)
    (skill_dir / "references").mkdir(exist_ok=True)

    skill_path.write_text(content, encoding="utf-8")
    return StageResult(stage_name="skill", artifact_path=skill_path, skipped=False)
```

### Pattern 2: SKILL.md Frontmatter Compliance
**What:** Agent Skills spec requires exactly: `name` (lowercase, hyphens, max 64 chars), `description` (max 1024 chars). Additional fields (`version`, `source_url`, `language`) go under `metadata:` map.
**When to use:** Always — `name` must match the parent directory name (the `video_id`).

```yaml
# Source: https://agentskills.io/specification
---
name: {video_id}        # Must match directory name; video IDs are already URL-safe
description: {<=1024 chars describing the trading strategy and when to use it}
metadata:
  version: "1.0"
  source_url: https://www.youtube.com/watch?v={video_id}
  language: {source_language from TradingLogicExtraction}
---
```

**Critical constraint:** `name` must be lowercase letters, numbers, hyphens only. YouTube video IDs (e.g., `dQw4w9WgXcQ`) contain uppercase letters — the directory name should use the raw video ID but the `name` field must be the lowercased form. Consider whether to lowercase or use a slug.

### Pattern 3: URL Resolution (single vs batch)
**What:** `resolve_urls(url: str) -> list[str]` returns a list of video IDs. For single video URLs, returns `[extract_video_id(url)]`. For playlist/channel URLs, uses yt-dlp `extract_flat=True` to fetch all IDs.
**When to use:** Always in CLI — every URL goes through this function before the batch loop.

```python
# Source: yt-dlp Python API (extract_flat option)
import yt_dlp

def resolve_urls(url: str) -> list[str]:
    """Return list of video IDs from any YouTube URL (single, playlist, or channel)."""
    try:
        video_id = extract_video_id(url)  # Raises ValueError for non-video URLs
        return [video_id]
    except ValueError:
        pass  # Not a single-video URL — try as playlist/channel

    ydl_opts = {"extract_flat": True, "skip_download": True, "quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    entries = info.get("entries", [])
    return [entry["id"] for entry in entries if entry.get("id")]
```

### Pattern 4: Typed Error Hierarchy
**What:** Single `errors.py` module with `SkillError` base and four subclasses. Each carries `category` (NETWORK/EXTRACTION/LLM/FORMAT), `message`, and `suggestion`.
**When to use:** Raise specific subclasses from stages; catch `SkillError` in the batch loop to extract category + suggestion for display.

```python
# yt_to_skill/errors.py
class SkillError(Exception):
    category: str
    suggestion: str

class NetworkError(SkillError):
    category = "NETWORK"
    suggestion = "Check internet connection or retry later."

class ExtractionError(SkillError):
    category = "EXTRACTION"
    suggestion = "Video may lack captions; try with --force to rerun Whisper."

class LLMError(SkillError):
    category = "LLM"
    suggestion = "Check OPENROUTER_API_KEY and model availability."

class FormatError(SkillError):
    category = "FORMAT"
    suggestion = "extracted_logic.json may be malformed; delete work/<id>/ and rerun."
```

### Pattern 5: CLI Entry Point
**What:** `cli.py` with `main()` function registered in `pyproject.toml` as `yt-to-skill`. The `main()` function: parses args, resolves URLs, runs batch loop, prints progress lines, prints summary table, exits with 0 or 1.

```toml
# pyproject.toml addition
[project.scripts]
yt-to-skill = "yt_to_skill.cli:main"
```

```python
# yt_to_skill/cli.py
import argparse
import sys

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="yt-to-skill",
        description="Convert YouTube trading videos to installable Claude skill files.",
    )
    parser.add_argument("url", help="YouTube video, playlist, or channel URL")
    parser.add_argument("--output-dir", default="skills", help="Base directory for skill output")
    parser.add_argument("--force", action="store_true", help="Reprocess even if SKILL.md exists")
    parser.add_argument("--verbose", action="store_true", help="Show full logs")
    args = parser.parse_args()

    # ... resolve, loop, summarize
    sys.exit(0 if all_succeeded else 1)
```

### Pattern 6: Batch Summary Table
**What:** Plain text table printed at end of batch run. No third-party library needed — format with `str.ljust()` or `f-string` alignment.
**When to use:** Always for batch (>1 video). For single video, the progress line suffices.

```
Video ID        Title                    Status  Detail
dQw4w9WgXcQ    Never Gonna Give You Up  ✓       skills/dQw4w9WgXcQ/SKILL.md
abc123xyz       Another Video            ✗       LLM: OpenRouter rate limit exceeded. Check API key.
```

### Anti-Patterns to Avoid
- **Building SKILL.md name from video title:** Video titles contain non-ASCII chars, spaces, and special chars. Use the video ID as the directory name; derive `name:` frontmatter from it.
- **Hardcoding `description:` as empty or stub:** Planner should generate description from strategy names in `TradingLogicExtraction.strategies[*].strategy_name` — a short summary of what strategies are covered.
- **Raising exceptions from the batch loop:** Catch all exceptions in the per-video iteration so one failure cannot abort subsequent videos.
- **Writing SKILL.md before creating subdirectories:** Create `assets/`, `scripts/`, `references/` before writing SKILL.md so the scaffold is always complete.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Playlist/channel URL expansion | Custom YouTube API client | yt-dlp `YoutubeDL(extract_flat=True)` | Already in deps; handles authentication, geo-blocks, pagination, channel /videos tab, @handle URLs |
| YAML frontmatter serialization | Custom YAML writer | `PyYAML` (stdlib-equivalent pattern) or manual `---\nkey: value\n---` | Frontmatter is 5-6 lines of simple key-value; manual f-string is safe and removes a dep |
| Exit code management | Custom return-code registry | `sys.exit(0)` / `sys.exit(1)` | Standard POSIX convention; no abstraction needed |
| Progress display | Rich or tqdm progress bar | Simple `print(f"✓ {stage}")` lines | Claude's discretion — simplest approach for discrete stage count; Rich adds a dep |

**Key insight:** The yt-dlp Python API is the only meaningful "don't hand-roll" item here. Every other problem is trivially solvable with stdlib.

---

## Common Pitfalls

### Pitfall 1: Agent Skills `name` field case constraint
**What goes wrong:** YouTube video IDs contain uppercase letters (e.g., `dQw4w9WgXcQ`). Writing the video ID directly as the SKILL.md `name:` field will fail validation because the spec requires lowercase only.
**Why it happens:** The spec says "Lowercase letters, numbers, and hyphens only." The `name` must also match the parent directory name.
**How to avoid:** Use the raw video ID as the directory name, then use `video_id.lower()` as the `name:` field value. Confirm these are consistent (directory created with same lowercase name).
**Warning signs:** `skills-ref validate` fails with "invalid name" error.

### Pitfall 2: Empty strategies list from extraction
**What goes wrong:** `TradingLogicExtraction.strategies` can be an empty list if the filter passed but extraction produced nothing. Writing a SKILL.md with empty sections is misleading.
**Why it happens:** Filter and extraction are separate LLM calls; the filter is a cheaper classifier that can have false positives.
**How to avoid:** In `run_skill`, detect `len(extraction.strategies) == 0` and write a clearly marked "No strategies extracted" body rather than empty sections. Log a warning. Count this as a non-fatal condition (skill file is still written).
**Warning signs:** SKILL.md with empty `## Entry/Exit Criteria` section and no REQUIRES_SPECIFICATION markers.

### Pitfall 3: yt-dlp `extract_flat` returns partial entry dicts
**What goes wrong:** In `extract_flat=True` mode, `entries` may contain dicts with no `id` key for unavailable/private/deleted videos in a playlist. Iterating without guard causes `KeyError`.
**Why it happens:** yt-dlp returns placeholder entries for unavailable videos.
**How to avoid:** Filter with `entry.get("id")` — already shown in Pattern 3 example. Log a warning for entries with no ID.
**Warning signs:** `KeyError: 'id'` in the resolver function.

### Pitfall 4: `--force` flag bypasses `artifact_guard` but not orchestrator
**What goes wrong:** If `--force` is implemented only in `run_skill` (by not calling `artifact_guard`), the previous pipeline stages (ingest, transcript, etc.) still skip via their own artifact guards. This is correct behavior — but the SKILL.md is regenerated from potentially stale `extracted_logic.json` if the extraction logic changed.
**Why it happens:** The `--force` flag semantics are only specified for the skill stage in the context decisions.
**How to avoid:** Document clearly that `--force` only re-runs the skill generation stage, not the full pipeline. For full re-extraction, the user must delete `work/<video_id>/`.

### Pitfall 5: Table formatting breaks on long video titles
**What goes wrong:** Video titles from Trader Feng Ge may contain CJK characters. Python's `str.ljust()` aligns by character count, not display width. CJK characters are double-width; a 20-char title with CJK will appear misaligned in a fixed-width table.
**Why it happens:** Terminal display width ≠ Python string length for CJK.
**How to avoid:** Truncate titles to a safe max length (e.g., 40 chars) before table formatting. Accept slight misalignment as non-critical UX. Do not add `wcwidth` as a dependency.

### Pitfall 6: `sys.exit(1)` called before cleanup
**What goes wrong:** If `sys.exit(1)` is called mid-batch (e.g., on unhandled exception), the summary table is never printed.
**Why it happens:** Exception escapes the batch loop.
**How to avoid:** Wrap the entire batch loop in a `try/finally` that prints the summary table regardless of outcome.

---

## Code Examples

### SKILL.md Template (verified against agentskills.io spec)
```python
# Source: https://agentskills.io/specification
def render_skill_md(extraction: TradingLogicExtraction) -> str:
    name = extraction.video_id.lower()  # spec: lowercase only
    strategy_names = ", ".join(s.strategy_name for s in extraction.strategies) or "Trading strategy"
    description = (
        f"Trading strategy skill extracted from YouTube video {extraction.video_id}. "
        f"Covers: {strategy_names}. "
        f"Use when asked to analyze, backtest, or apply these trading strategies."
    )[:1024]  # spec: max 1024 chars

    frontmatter = (
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        "metadata:\n"
        "  version: \"1.0\"\n"
        f"  source_url: https://www.youtube.com/watch?v={extraction.video_id}\n"
        f"  source_language: {extraction.source_language}\n"
        "---\n"
    )
    body = render_body(extraction)
    return frontmatter + "\n" + body
```

### SKILL.md Body Section Order (locked by user decisions)
```markdown
## Strategy Overview
{strategy_name} — {brief description from market_conditions}

## Entry/Exit Criteria
### Entry Conditions
{entry_criteria list — each EntryCondition rendered as bullet}

### Exit Conditions
{exit_criteria list}

> **REQUIRES_SPECIFICATION: entry_criteria[0].value** — exact threshold not stated in video

## Risk Management
{risk_rules list}

## Market Regime Filters
{market_conditions list}
```

### Playlist Resolution (yt-dlp Python API)
```python
# Source: yt-dlp Python API — extract_flat option
import yt_dlp

ydl_opts = {
    "extract_flat": True,
    "skip_download": True,
    "quiet": True,
    "no_warnings": True,
}
with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(playlist_url, download=False)

video_ids = [entry["id"] for entry in info.get("entries", []) if entry.get("id")]
```

### CLI Entry Point Registration
```toml
# pyproject.toml — add to existing [project] section
[project.scripts]
yt-to-skill = "yt_to_skill.cli:main"
```

After running `pip install -e .` or `uv sync`, the `yt-to-skill` command is available on PATH.

### Typed Error Construction
```python
# yt_to_skill/errors.py
class SkillError(Exception):
    category: str = "UNKNOWN"
    suggestion: str = ""

    def __init__(self, message: str) -> None:
        super().__init__(f"[{self.category}] {message} — {self.suggestion}")

class NetworkError(SkillError):
    category = "NETWORK"
    suggestion = "Check internet connection or retry later."

class LLMError(SkillError):
    category = "LLM"
    suggestion = "Check OPENROUTER_API_KEY and model availability on openrouter.ai."

class ExtractionError(SkillError):
    category = "EXTRACTION"
    suggestion = "Video may lack captions; delete work/<video_id>/ and rerun."

class FormatError(SkillError):
    category = "FORMAT"
    suggestion = "extracted_logic.json may be malformed; delete work/<video_id>/ and rerun."
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `console_scripts` in `setup.py` | `[project.scripts]` in `pyproject.toml` | PEP 517/518 (2017-2020) | pyproject.toml is the current standard; hatchling already used in this project |
| yt-dlp subprocess | yt-dlp Python API with `YoutubeDL` class | Always available; preferred since yt-dlp packaged as library | No subprocess overhead; same process, better error propagation |
| Agent Skills custom YAML | agentskills.io standardized spec (2025) | Late 2025 | Skills installable in Claude Code, Copilot, Cursor, Gemini CLI — standard frontmatter is required for portability |

**Deprecated/outdated:**
- `setup.py console_scripts`: Replaced by `[project.scripts]` in `pyproject.toml`. Do not use.

---

## Open Questions

1. **`name` field vs directory name for video IDs with uppercase**
   - What we know: Agent Skills spec requires `name` to be lowercase; also requires `name` to match parent directory name
   - What's unclear: Should the directory be `skills/<lowercased-video-id>/` or `skills/<original-video-id>/`? YouTube video IDs are case-sensitive (the URL `?v=dQw4w9WgXcQ` would 404 if lowercased)
   - Recommendation: Use original video ID as directory name, store `video_id.lower()` as `name:` in frontmatter, and document that the directory name and `name:` intentionally differ. The spec validator checks `name:` value, not directory name consistency, in practice. Alternatively, derive a slug from the video title. **Planner should resolve this explicitly.**

2. **Handling videos where `filter_result.is_strategy = False` in batch**
   - What we know: The orchestrator stops after the filter stage for non-strategy videos; no `extracted_logic.json` is produced
   - What's unclear: Should non-strategy videos appear in the summary table as "skipped (not a trading strategy)" or "failed"?
   - Recommendation: Show as "⚠ skipped — not a strategy video" in the table, with exit code still 0 (user asked for it; the pipeline correctly identified non-content). Treat as expected outcome, not failure.

3. **`PipelineConfig` extension for `skills_dir` and `force`**
   - What we know: `PipelineConfig` uses pydantic-settings, reads from `.env`
   - What's unclear: Should `--output-dir` and `--force` live in `PipelineConfig` (making them env-var-settable) or only in CLI args?
   - Recommendation: Add `skills_dir: Path = Path("skills")` to `PipelineConfig` (env-var-settable is useful for CI). `force: bool = False` can stay CLI-only since env-var forcing is a footgun.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.2.0 |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `pytest tests/test_skill.py tests/test_cli.py tests/test_resolver.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OUTP-01 | render_skill_md() produces valid YAML frontmatter with required fields | unit | `pytest tests/test_skill.py::test_render_skill_md_frontmatter -x` | ❌ Wave 0 |
| OUTP-01 | name field is lowercase and max 64 chars | unit | `pytest tests/test_skill.py::test_name_field_constraints -x` | ❌ Wave 0 |
| OUTP-01 | description field is non-empty and max 1024 chars | unit | `pytest tests/test_skill.py::test_description_field_constraints -x` | ❌ Wave 0 |
| OUTP-02 | run_skill() creates assets/, scripts/, references/ subdirs | unit | `pytest tests/test_skill.py::test_scaffold_directories_created -x` | ❌ Wave 0 |
| OUTP-03 | Generated SKILL.md body contains all four required sections | unit | `pytest tests/test_skill.py::test_body_has_four_sections -x` | ❌ Wave 0 |
| OUTP-03 | REQUIRES_SPECIFICATION rendered as inline callout not separate section | unit | `pytest tests/test_skill.py::test_requires_specification_inline -x` | ❌ Wave 0 |
| OUTP-04 | CLI parses single video URL and produces SKILL.md | unit | `pytest tests/test_cli.py::test_cli_single_video -x` | ❌ Wave 0 |
| OUTP-04 | CLI --output-dir flag overrides default skills/ path | unit | `pytest tests/test_cli.py::test_output_dir_flag -x` | ❌ Wave 0 |
| OUTP-04 | CLI --force flag bypasses artifact_guard for skill stage | unit | `pytest tests/test_cli.py::test_force_flag -x` | ❌ Wave 0 |
| OUTP-05 | resolve_urls() returns list of IDs for playlist URL | unit | `pytest tests/test_resolver.py::test_resolve_playlist_url -x` | ❌ Wave 0 |
| OUTP-05 | Batch loop continues after per-video failure | unit | `pytest tests/test_cli.py::test_batch_continues_on_failure -x` | ❌ Wave 0 |
| OUTP-05 | Exit code is 1 if any video fails, 0 if all succeed | unit | `pytest tests/test_cli.py::test_exit_code_all_success -x` | ❌ Wave 0 |
| OUTP-06 | NetworkError, LLMError, ExtractionError, FormatError carry category prefix | unit | `pytest tests/test_errors.py::test_error_categories -x` | ❌ Wave 0 |
| OUTP-06 | Error message includes one-line suggestion | unit | `pytest tests/test_errors.py::test_error_suggestions -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_skill.py tests/test_cli.py tests/test_resolver.py tests/test_errors.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_skill.py` — covers OUTP-01, OUTP-02, OUTP-03
- [ ] `tests/test_cli.py` — covers OUTP-04, OUTP-05 (exit codes, force flag, batch isolation)
- [ ] `tests/test_resolver.py` — covers OUTP-05 (playlist URL resolution, single video passthrough)
- [ ] `tests/test_errors.py` — covers OUTP-06 (error categories, suggestions)
- [ ] `yt_to_skill/errors.py` — must exist before any test imports it
- [ ] `yt_to_skill/stages/skill.py` — must exist before test_skill.py can import run_skill
- [ ] `yt_to_skill/resolver.py` — must exist before test_resolver.py can import resolve_urls
- [ ] `yt_to_skill/cli.py` — must exist before test_cli.py can import main

---

## Sources

### Primary (HIGH confidence)
- https://agentskills.io/specification — Complete SKILL.md format: frontmatter field constraints, body recommendations, directory structure, progressive disclosure model
- https://docs.python.org/3/library/argparse.html — argparse API: `add_argument`, `parse_args`, `exit_on_error`, exit code behavior
- https://packaging.python.org/en/latest/guides/creating-command-line-tools/ — `[project.scripts]` entry point registration pattern
- yt-dlp Python API (deepwiki.com/yt-dlp/yt-dlp/2.2-information-extraction-pipeline) — `extract_flat=True` option, `YoutubeDL` class, entries structure

### Secondary (MEDIUM confidence)
- https://github.com/yt-dlp/yt-dlp — Official yt-dlp repository for `extract_flat` behavior and API options
- https://tech-champion.com/programming/python-programming/packaging-executables-with-pyproject-toml-a-comprehensive-guide/ — pyproject.toml `[project.scripts]` usage confirmed

### Tertiary (LOW confidence)
- None identified — all critical claims verified against primary sources

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in deps or stdlib; Agent Skills spec directly read from official source
- Architecture: HIGH — patterns are direct extensions of Phase 1 patterns already in codebase
- Pitfalls: MEDIUM — spec constraint (name field case) verified; CJK table alignment and empty strategies are code-level reasoning

**Research date:** 2026-04-14
**Valid until:** 2026-05-14 (Agent Skills spec is stable; yt-dlp Python API `extract_flat` has been stable across versions)
