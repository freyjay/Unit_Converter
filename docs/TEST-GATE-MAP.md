# Test gate map

One page on what runs, what it proves, and what it does not. Every entry point writes logs and a `run-record.json` under `.checks/`. The record includes the hashes of the app, the CLI and the test tools used, the environment, and the Git commit when run from a checkout.

## `python3 scripts/check.py --suite core` (no browser)

| Step | What runs | What it proves |
|---|---|---|
| 1. repository-structure | `scripts/check_repository.py` | App scripts, app bytes and CLI bytes equal `docs/PROVENANCE.json`; the visible page-text revision matches; every browser navigation path executes (`tests/test_browser_paths.py`) |
| 2. extracted-package-core | `tests/release_check.py --partial` builds a candidate archive, refuses it if any file listed in `PACKAGE-CONTENTS.sha256` is missing, extracts it to a path with spaces, and runs `tests/run_all_tests.py` there | Everything below holds for the **packaged** bytes, not just the working tree |
| ↳ baseline, regressions | `tests/run_python_tests.sh`, `tests/run_regressions.py` | 30 known-answer checks and 115 regressions for every repaired defect: parsing, refusals, preservation, records, overwrite protection |
| ↳ round-trip gate | `tests/roundtrip/roundtrip_cli.py` (+ `--self-test`) | ft→m→ft→m→ft against an exact oracle written independently of the converter; the return trip reproduces the original bytes; mutations must fail |
| ↳ utility failure controls | `tests/test_utility_repairs.py` | The release builder and capacity runner fail correctly: injected failures, rejected candidates, dropped files |
| ↳ browser path check | `tests/test_browser_paths.py` | Four deliberately broken navigation variants must be caught |
| ↳ consumer release | `tests/test_consumer_release.py` | The user ZIP has exactly its six files; it matches provenance; the build is reproducible; a modified app is refused; the shipped CLI reproduces the bytes Civil 3D exported |
| ↳ semantic probes, differential | `tests/differential/` | Index-base, header and identifier boundaries across engines; 83 cases against PointTruth rc.1 (47 identical, 33 both refuse, 3 named policy differences); comparator mutations must be detected |
| 3. next-fixture-checker | `acceptance/next-native-tests/test_checker.py` | The checker for the three prepared Civil 3D cases accepts correct exports and rejects 27 synthetic bad ones |

## `python3 scripts/check.py --suite browser` (Chromium via Playwright)

| Step | What it proves |
|---|---|
| `tests/run_browser_tests.py` | 108 checks in the real app under a relaxed (diagnostic) CSP: conversion, refusals, handoff save/reopen/repeat-save, tamper refusal, restored settings, in-page self-test. The slow 16 MiB lifecycle runs only with `PFU_SLOW=1` |
| `tests/capacity/measure_lifecycle.py` ×2 | Normal CSP, ~1 MiB: convert → download → save handoff → reopen → download, with the producer tab open and then closed. All identities must hold |

## Not covered by any gate

Browser runs on Windows and macOS; Edge, Firefox and Safari; Intel Macs; Civil 3D itself (manual procedures in `acceptance/`); accessibility; and capacity beyond these sizes on real user hardware. A pass here never implies any of those.

The core gate itself has passed on Linux (contributor), Windows (partner) and macOS on Apple Silicon (owner); see `docs/PROVENANCE.json` for exact runs.
