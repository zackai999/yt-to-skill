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
| 04-01-01 | 01 | 0 | Wave 0 setup | unit | `uv run pytest tests/test_installer.py -x -q` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 1 | Agent detection | unit | `uv run pytest tests/test_installer.py::test_detect_installed_agents -x` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 1 | Install copies full tree | unit | `uv run pytest tests/test_installer.py::test_install_skill_dir_copies_tree -x` | ❌ W0 | ⬜ pending |
| 04-02-03 | 02 | 1 | Provenance injection | unit | `uv run pytest tests/test_installer.py::test_provenance_injected -x` | ❌ W0 | ⬜ pending |
| 04-02-04 | 02 | 1 | Conflict prompts overwrite | unit | `uv run pytest tests/test_installer.py::test_conflict_prompts_overwrite -x` | ❌ W0 | ⬜ pending |
| 04-03-01 | 03 | 1 | list filters by provenance | unit | `uv run pytest tests/test_installer.py::test_list_filters_by_provenance -x` | ❌ W0 | ⬜ pending |
| 04-03-02 | 03 | 1 | uninstall removes from all agents | unit | `uv run pytest tests/test_installer.py::test_uninstall_removes_from_all_agents -x` | ❌ W0 | ⬜ pending |
| 04-04-01 | 04 | 1 | process subcommand | unit | `uv run pytest tests/test_cli.py::test_process_subcommand -x` | ❌ W0 | ⬜ pending |
| 04-04-02 | 04 | 1 | bare URL backward compat | unit | `uv run pytest tests/test_cli.py::test_bare_url_backward_compat -x` | ❌ W0 | ⬜ pending |
| 04-04-03 | 04 | 1 | --install flag skips prompt | unit | `uv run pytest tests/test_cli.py::test_install_flag_skips_prompt -x` | ❌ W0 | ⬜ pending |
| 04-02-05 | 02 | 1 | Name sanitization | unit | `uv run pytest tests/test_installer.py::test_name_sanitization -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_installer.py` — all installer unit tests (new file needed)
- [ ] `tests/test_cli.py` — new subcommand tests (file exists, needs new test functions)

*Existing test infrastructure covers framework setup; only new test files/functions needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Interactive agent selection prompt | Agent selection UX | Requires TTY interaction | Run `yt-to-skill process <url>`, verify interactive prompt appears with detected agents |
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
