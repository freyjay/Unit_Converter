# PointTruth 1.0.0 audit harnesses (2026-09-21)

These are the harnesses behind the "73 checks" reported to the PointTruth team, supplied here so the results can be rerun rather than taken as a claim.

| File | What it does | Result when run here |
|---|---|---|
| `audit_pt.cjs` | Engine in a Node `vm` context: 36 independent fixtures (both reviewers' Decimal oracles), every reproduction from review rounds 1–3, verifier attacks, manifest attacks via `verifyPackage`, and — when a Python engine is reachable (`PFU_PY`, `../../pointfile_units.py` or `./pointfile_units.py`) — a byte comparison of PointTruth's output with `pointfile_units.py` on a shared PENZD file, otherwise a printed `SKIP` | 46/46 with the Python comparison (45/45 + SKIP without it); the earlier `DATA`/`MAPPING` expectation mismatch was a wrong expectation and is corrected |
| `audit_pt2.cjs` | SHA-256 fallback vs Node at 13 padding boundaries; ties-to-even on both signs in both rounding procedures; trailing comma, header-after-comment, CR-only endings, NUL, 70-token descriptions, multiline CSV, 13-decimal refusal, duplicate identifiers | 17/17 |
| `ui-audit.py` | Playwright + Chromium against the real `PointTruth.html`: worker conversion, download, check-saved-file good/tampered, save handoff → reopen → re-verify, tampered handoff refused, settings change under a 60,000-line load, 60k-line timing | 11/11 |

Run: `node audit_pt.cjs` and `node audit_pt2.cjs` from a directory containing `PointTruth.html`, `fx1.json` and `fx2.json` (copies of `tests/independent-expected-outputs*.json`); `python3 ui-audit.py` needs `pip install playwright && playwright install chromium` and the `make_fixtures.py` fixtures in the same directory.

## Exit codes (R6-05)

Every runner sets a nonzero exit status when any assertion fails or the harness itself throws or rejects: `audit_pt.cjs`/`audit_pt2.cjs` exit 1 on failures and 2 on a harness error; `ui-audit.py` exits 1 on failures. Proven on 2026-09-21 by (a) deliberately breaking one expected value (`passed 44 failed 1`, exit 1) and (b) injecting a `throw` after setup (exit 1 via the rejection handler). `results/run-record.json` records each run's exit status alongside its summary line.

Scope: these establish that the tested cases behave as described in that environment (Linux, Node 22, Chromium via Playwright). They do not establish that PointTruth has no defects, and the 60,000-line timing is an observation from this machine, not a guarantee.
