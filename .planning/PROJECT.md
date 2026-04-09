# YouTube-to-Skill

## What This Is

A fully automated Python CLI pipeline that converts YouTube trading videos (starting with Chinese-language crypto content) into structured Claude Code skills. Point it at a channel, playlist, or single video — it extracts transcripts, translates, captures keyframes, isolates actionable trading logic, and outputs installable SKILL.md files following the Agent Skills specification. Designed to be language- and domain-extensible beyond crypto trading.

## Core Value

Given any YouTube trading video URL, produce a high-quality Claude skill that lets Claude act as a trading assistant, generate backtest code, or serve as an on-demand knowledge base for that strategy — with zero manual intervention.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Transcript extraction from YouTube videos (captions + auto-generated)
- [ ] Chinese-to-English translation of transcripts via OpenRouter LLM
- [ ] Whisper-based transcription fallback for videos without captions (Belle-whisper-large-v3-zh for Chinese)
- [ ] Local video download via yt-dlp
- [ ] Keyframe extraction via PySceneDetect for chart/indicator screenshots
- [ ] Trading logic extraction from translated transcripts (entry/exit criteria, indicators, risk rules, market conditions)
- [ ] SKILL.md generation following Agent Skills specification (YAML frontmatter + structured Markdown)
- [ ] Batch processing of channels and playlists (fully automated, no human in loop)
- [ ] OpenRouter as unified LLM gateway for all model calls
- [ ] CLI interface (single video, playlist, or channel URL as input)
- [ ] Skill output directory with SKILL.md, reference charts in assets/, helper scripts in scripts/
- [ ] Three-level skill structure: overview + entry/exit criteria + risk management + market regime filters
- [ ] REQUIRES_SPECIFICATION flags for implicit/missing parameters in extracted strategies
- [ ] Video filtering — detect and skip non-strategy content (clickbait, vlogs, news commentary)

### Out of Scope

- Cloud deployment or hosted service — local CLI only
- Live trading execution or broker integration — skills are knowledge, not automation
- Custom ML model training — use existing models (Whisper, Belle-whisper) as-is
- Real-time channel monitoring / scheduled polling — run on demand
- GUI or web interface — CLI is the interface
- Gemini native video route — local-first pipeline (download + process locally)

## Context

- Primary test channel: Trader Feng Ge (Chinese crypto trading, BTC-focused)
- Existing ecosystem: yfe404/youtube-to-skill handles ~80% of the generic pipeline; RogueQuant's 2-prompt extraction engine specializes in trading logic
- Agent Skills spec (agentskills.io) is an open standard — output works in Claude Code, Codex CLI, Copilot, Cursor, Gemini CLI
- Skills use progressive disclosure: name+description loaded at startup (~100 tokens), full body loaded on trigger, assets loaded on demand
- Key linguistic challenge: Chinese trading idioms, indicator names, and market terminology must translate accurately into actionable English instructions
- OpenRouter provides unified access to Claude, GPT, Gemini, and open-source models via single API key

## Constraints

- **LLM Access**: All model calls go through OpenRouter — no direct Anthropic/Google/OpenAI API keys
- **Language**: Python — all core dependencies (youtube-transcript-api, yt-dlp, faster-whisper, PySceneDetect) are Python-native
- **Local execution**: Must run entirely on local machine, no cloud dependencies beyond OpenRouter API
- **Skill format**: Output must comply with Agent Skills specification (SKILL.md with YAML frontmatter)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| OpenRouter as sole LLM gateway | Single API key, model flexibility, no vendor lock-in | — Pending |
| Local-first video processing | More control, works offline except LLM calls, no Gemini rate limits | — Pending |
| Python stack | Natural fit — every key dependency is Python-native | — Pending |
| Fully automated pipeline | User wants zero intervention from URL to installed skill | — Pending |
| Domain-extensible design | Start with Chinese crypto trading, but architecture supports any language/domain | — Pending |

---
*Last updated: 2026-04-13 after initialization*
