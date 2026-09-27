# Immutable historical records (compatibility fixtures)

Produced by earlier releases and never edited. `run_regressions.py` replays each through the current Python reader and
`run_browser_tests.py` through the current browser reader; the expected outcome and the adapter used are asserted there.

| Directory | Producer | Schema | Rule text | Digest spelling | Expected outcome today |
|---|---|---|---|---|---|
| `v3.1.0-browser/record` | Point-File-Unit-Converter.html 3.1.0 (reviewer's round-2 harness run) | pointfile-units-report/2 | pre-schema-3 | uppercase | PASS via the schema-2 adapter; absent observation fields listed as not checked |
| `v3.2.0-browser/cross` | Point-File-Unit-Converter.html 3.2.0 (reviewer's round-3 harness run) | pointfile-units-report/3 | acceptance without the floor-interval clause | uppercase | PASS via schema-3 legacy adapter A; legacy fingerprint spelling noted |
| `v3.3.1-python/base`, `cross-unicode` | pointfile_units.py 3.3.1, Windows / Python 3.13 (partner's round-6 evidence) | pointfile-units-report/3 | acceptance without the floor-interval clause | uppercase | PASS via schema-3 legacy adapter A; legacy fingerprint spelling noted |
| `v3.3.2-python-handoff/handoff` | pointfile_units.py 3.3.2, embedded in the partner's round-5 forged-prose handoff | pointfile-units-report/3 | current | lowercase | PASS, no adapter |

Sources: the reviewers' evidence bundles under `tests/review-evidence/` and the harness scratch directories those bundles regenerate.
