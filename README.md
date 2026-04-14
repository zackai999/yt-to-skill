# yt-to-skill

Convert YouTube trading videos into structured, installable Claude skill files (SKILL.md).

## What it does

`yt-to-skill` takes a YouTube video URL (single video, playlist, or channel) and runs it through a multi-stage pipeline:

1. **Ingest** — Fetches video metadata via yt-dlp
2. **Transcript** — Extracts captions (or falls back to Whisper audio transcription)
3. **Filter** — Detects whether the video contains actionable trading strategy content
4. **Translate** — Translates non-English transcripts using a 97-term trading glossary
5. **Extract** — Pulls structured strategy data (entries, exits, indicators) via LLM + Pydantic
6. **Skill** — Renders a SKILL.md file with frontmatter, entry/exit criteria, and risk rules
7. **Keyframes** — Extracts key visual frames (scene detection + perceptual dedup) and adds a chart gallery

The output is a self-contained skill directory per video with `SKILL.md`, reference scripts, and keyframe assets.

## Installation

Requires Python 3.11–3.12.

```bash
# Clone and install
git clone https://github.com/criox4/yt-to-skill.git
cd yt-to-skill
uv sync

# Set up environment
cp .env.example .env
# Add your OpenRouter API key to .env
```

## Usage

```bash
# Single video
yt-to-skill https://www.youtube.com/watch?v=VIDEO_ID

# Playlist
yt-to-skill https://www.youtube.com/playlist?list=PLAYLIST_ID

# Channel (all videos)
yt-to-skill https://www.youtube.com/@Channel/videos

# Options
yt-to-skill URL --output-dir ~/my-skills  # Custom output directory
yt-to-skill URL --force                   # Re-process cached videos
yt-to-skill URL --no-keyframes            # Skip keyframe extraction
yt-to-skill URL --max-keyframes 10        # Limit keyframe count
yt-to-skill URL --verbose                 # Debug logging
```

## Project structure

```
yt_to_skill/
├── cli.py              # CLI entry point
├── config.py           # Pipeline configuration (env-based)
├── errors.py           # Typed error hierarchy
├── orchestrator.py     # 7-stage pipeline runner
├── resolver.py         # URL resolver (video/playlist/channel)
├── glossary/           # Chinese-English trading term glossary
├── llm/                # OpenRouter LLM client with retry
├── models/             # Pydantic data models and extraction schema
└── stages/
    ├── ingest.py       # Metadata + audio download
    ├── transcript.py   # Captions / Whisper fallback
    ├── filter.py       # Strategy content detection
    ├── translate.py    # Translation with glossary injection
    ├── extract.py      # Structured extraction via instructor
    ├── skill.py        # SKILL.md renderer
    └── keyframe.py     # Scene detection + dedup
```

## Development

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check .
```

## License

MIT
