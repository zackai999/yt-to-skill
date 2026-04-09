---
phase: 1
slug: text-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-14
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (to be installed) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` section — Wave 0 |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | INPT-01 | unit (mock youtube-transcript-api) | `pytest tests/test_transcript.py::test_caption_fetch -x` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 1 | INPT-01 | unit | `pytest tests/test_transcript.py::test_caption_quality_heuristics -x` | ❌ W0 | ⬜ pending |
| 01-01-03 | 01 | 1 | INPT-02 | unit (mock TranscriptsDisabled) | `pytest tests/test_transcript.py::test_whisper_fallback_triggered -x` | ❌ W0 | ⬜ pending |
| 01-01-04 | 01 | 1 | INPT-02 | unit (mock faster-whisper) | `pytest tests/test_transcript.py::test_whisper_vad_enabled -x` | ❌ W0 | ⬜ pending |
| 01-01-05 | 01 | 1 | INPT-03 | unit (mock yt-dlp) | `pytest tests/test_ingest.py::test_audio_format_selection -x` | ❌ W0 | ⬜ pending |
| 01-01-06 | 01 | 1 | INPT-05 | unit | `pytest tests/test_orchestrator.py::test_artifact_guard -x` | ❌ W0 | ⬜ pending |
| 01-01-07 | 01 | 1 | EXTR-01 | unit | `pytest tests/test_translate.py::test_glossary_injection -x` | ❌ W0 | ⬜ pending |
| 01-01-08 | 01 | 1 | EXTR-01 | unit | `pytest tests/test_translate.py::test_translate_cache_hit -x` | ❌ W0 | ⬜ pending |
| 01-01-09 | 01 | 1 | EXTR-02 | unit (Pydantic) | `pytest tests/test_models.py::test_extraction_schema_valid -x` | ❌ W0 | ⬜ pending |
| 01-01-10 | 01 | 1 | EXTR-02 | unit (Pydantic) | `pytest tests/test_models.py::test_extraction_schema_invalid -x` | ❌ W0 | ⬜ pending |
| 01-01-11 | 01 | 1 | EXTR-03 | unit | `pytest tests/test_models.py::test_requires_specification_mapping -x` | ❌ W0 | ⬜ pending |
| 01-01-12 | 01 | 1 | EXTR-04 | unit | `pytest tests/test_filter.py::test_metadata_prefilter_rejects -x` | ❌ W0 | ⬜ pending |
| 01-01-13 | 01 | 1 | EXTR-04 | unit | `pytest tests/test_filter.py::test_metadata_prefilter_passes -x` | ❌ W0 | ⬜ pending |
| 01-01-14 | 01 | 1 | INFR-01 | unit | `pytest tests/test_llm_client.py::test_openrouter_base_url -x` | ❌ W0 | ⬜ pending |
| 01-01-15 | 01 | 1 | INFR-01 | static analysis / unit | `pytest tests/test_llm_client.py::test_no_direct_openai_in_stages -x` | ❌ W0 | ⬜ pending |
| 01-01-16 | 01 | 1 | INFR-02 | unit | `pytest tests/test_stages.py::test_artifact_output_paths -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/__init__.py` — package init
- [ ] `tests/conftest.py` — shared fixtures: `tmp_work_dir`, `mock_video_id`, `sample_transcript_segments`, `sample_extraction_result`
- [ ] `tests/test_transcript.py` — covers INPT-01, INPT-02
- [ ] `tests/test_ingest.py` — covers INPT-03
- [ ] `tests/test_orchestrator.py` — covers INPT-05
- [ ] `tests/test_translate.py` — covers EXTR-01
- [ ] `tests/test_models.py` — covers EXTR-02, EXTR-03
- [ ] `tests/test_filter.py` — covers EXTR-04
- [ ] `tests/test_llm_client.py` — covers INFR-01
- [ ] `tests/test_stages.py` — covers INFR-02
- [ ] Framework install: `uv add --dev pytest ruff mypy` — if none detected
- [ ] `pyproject.toml` test config: `[tool.pytest.ini_options] testpaths = ["tests"]`

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Whisper transcription quality on real Chinese audio | INPT-02 | Requires actual audio file + GPU inference | Run pipeline on a known caption-less Feng Ge video, inspect transcript.txt |
| End-to-end extracted_logic.json quality | EXTR-02 | LLM output varies; needs human review of field accuracy | Run pipeline on a strategy video, review JSON fields against video content |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
