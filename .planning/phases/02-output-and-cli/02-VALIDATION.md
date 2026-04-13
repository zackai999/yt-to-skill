---
phase: 2
slug: output-and-cli
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-14
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.2.0 |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `pytest tests/test_skill.py tests/test_cli.py tests/test_resolver.py tests/test_errors.py -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_skill.py tests/test_cli.py tests/test_resolver.py tests/test_errors.py -x`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0 | OUTP-01 | unit | `pytest tests/test_skill.py::test_render_skill_md_frontmatter -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 0 | OUTP-01 | unit | `pytest tests/test_skill.py::test_name_field_constraints -x` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 0 | OUTP-01 | unit | `pytest tests/test_skill.py::test_description_field_constraints -x` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01 | 0 | OUTP-02 | unit | `pytest tests/test_skill.py::test_scaffold_directories_created -x` | ❌ W0 | ⬜ pending |
| 02-01-05 | 01 | 0 | OUTP-03 | unit | `pytest tests/test_skill.py::test_body_has_four_sections -x` | ❌ W0 | ⬜ pending |
| 02-01-06 | 01 | 0 | OUTP-03 | unit | `pytest tests/test_skill.py::test_requires_specification_inline -x` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 0 | OUTP-04 | unit | `pytest tests/test_cli.py::test_cli_single_video -x` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 0 | OUTP-04 | unit | `pytest tests/test_cli.py::test_output_dir_flag -x` | ❌ W0 | ⬜ pending |
| 02-02-03 | 02 | 0 | OUTP-04 | unit | `pytest tests/test_cli.py::test_force_flag -x` | ❌ W0 | ⬜ pending |
| 02-02-04 | 02 | 0 | OUTP-05 | unit | `pytest tests/test_resolver.py::test_resolve_playlist_url -x` | ❌ W0 | ⬜ pending |
| 02-02-05 | 02 | 0 | OUTP-05 | unit | `pytest tests/test_cli.py::test_batch_continues_on_failure -x` | ❌ W0 | ⬜ pending |
| 02-02-06 | 02 | 0 | OUTP-05 | unit | `pytest tests/test_cli.py::test_exit_code_all_success -x` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 0 | OUTP-06 | unit | `pytest tests/test_errors.py::test_error_categories -x` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 0 | OUTP-06 | unit | `pytest tests/test_errors.py::test_error_suggestions -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_skill.py` — stubs for OUTP-01, OUTP-02, OUTP-03
- [ ] `tests/test_cli.py` — stubs for OUTP-04, OUTP-05 (exit codes, force flag, batch isolation)
- [ ] `tests/test_resolver.py` — stubs for OUTP-05 (playlist URL resolution, single video passthrough)
- [ ] `tests/test_errors.py` — stubs for OUTP-06 (error categories, suggestions)
- [ ] `yt_to_skill/errors.py` — must exist before any test imports it
- [ ] `yt_to_skill/stages/skill.py` — must exist before test_skill.py can import run_skill
- [ ] `yt_to_skill/resolver.py` — must exist before test_resolver.py can import resolve_urls
- [ ] `yt_to_skill/cli.py` — must exist before test_cli.py can import main

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CJK title truncation in summary table | OUTP-05 | Display width depends on terminal | Run batch with a CJK-title video, visually inspect table |

*All other phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
