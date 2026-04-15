---
phase: 4
slug: auto-install-generated-skills-to-claude-code-and-compatible-skill-systems
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-15
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_installer.py tests/test_cli.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_installer.py tests/test_cli.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-T1 | 01 | 1 | INST-01..05 — Installer module (agent detection, install, provenance, sanitize, conflict, list, uninstall) | unit | `uv run pytest tests/test_installer.py -x -q` | tests/test_installer.py (new) | pending |
| 04-01-T2 | 01 | 1 | INST-01 — source_video_id in staging frontmatter | unit | `uv run pytest tests/test_skill.py -x -q` | tests/test_skill.py (exists) | pending |
| 04-02-T1 | 02 | 2 | CLI-01..03 — Subcommand CLI, install flow, conflict custom name | unit | `uv run pytest tests/test_cli.py -x -q` | tests/test_cli.py (exists) | pending |
| 04-02-T2 | 02 | 2 | CLI-01..03 — End-to-end human verification | manual | `uv run pytest tests/ -q` (automated gate) + manual flow | n/a | pending |

*Status: pending -- green -- red -- flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_installer.py` — all installer unit tests (new file needed)
- [ ] `tests/test_cli.py` — new subcommand + conflict custom name tests (file exists, needs new test functions)

*Existing test infrastructure covers framework setup; only new test files/functions needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Interactive agent selection prompt | Agent selection UX | Requires TTY interaction | Run `yt-to-skill process <url>`, verify interactive prompt appears with detected agents |
| Conflict custom name prompt | Name conflict UX | Requires TTY interaction | Re-process same video, decline overwrite, verify custom name prompt appears |
| Batch install prompt for playlists | Batch UX | Requires TTY + real playlist | Run `yt-to-skill process <playlist_url>`, verify single install prompt at end |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
