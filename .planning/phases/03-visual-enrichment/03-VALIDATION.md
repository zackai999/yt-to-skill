---
phase: 3
slug: visual-enrichment
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-14
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.2.0+ |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] testpaths = ["tests"] |
| **Quick run command** | `pytest tests/test_keyframe.py -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_keyframe.py tests/test_skill.py -x`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 0 | INPT-04 | unit (mock yt-dlp) | `pytest tests/test_keyframe.py::TestDownloadVideo -x` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 0 | INPT-04 | unit | `pytest tests/test_keyframe.py::TestRunKeyframes::test_artifact_guard -x` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 0 | INPT-04 | unit (mock scene_list) | `pytest tests/test_keyframe.py::TestRunKeyframes::test_cap_enforced -x` | ❌ W0 | ⬜ pending |
| 03-01-04 | 01 | 0 | INPT-04 | unit | `pytest tests/test_keyframe.py::TestDedup -x` | ❌ W0 | ⬜ pending |
| 03-01-05 | 01 | 0 | INPT-04 | unit | `pytest tests/test_keyframe.py::TestRunKeyframes::test_pngs_in_assets -x` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 1 | INPT-04 | unit | `pytest tests/test_skill.py::TestGallerySection -x` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 1 | INPT-04 | unit | `pytest tests/test_skill.py::TestGallerySection::test_no_gallery_when_empty -x` | ❌ W0 | ⬜ pending |
| 03-03-01 | 03 | 1 | INPT-04 | unit (CLI) | `pytest tests/test_cli.py::TestNoKeyframesFlag -x` | ❌ W0 | ⬜ pending |
| 03-03-02 | 03 | 1 | INPT-04 | unit (CLI) | `pytest tests/test_cli.py::TestMaxKeyframesFlag -x` | ❌ W0 | ⬜ pending |
| 03-01-06 | 01 | 1 | INPT-04 | unit | `pytest tests/test_keyframe.py::TestRunKeyframes::test_video_deleted -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_keyframe.py` — all INPT-04 keyframe stage tests (new file)
- [ ] `tests/test_skill.py` — append `TestGallerySection` class (extend existing file)
- [ ] `tests/test_cli.py` — append `TestNoKeyframesFlag` and `TestMaxKeyframesFlag` (extend existing file)
- [ ] `pyproject.toml` — add `scenedetect[opencv-headless]>=0.6.7` and `imagehash>=4.3.2` to dependencies

*Existing infrastructure covers pytest framework and config.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| AdaptiveDetector threshold calibration on Trader Feng Ge videos | INPT-04 | Requires real video content + visual inspection of extracted frames | Run pipeline on 5-10 sample videos, inspect `assets/` directory, verify no explosion and meaningful frame selection |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
