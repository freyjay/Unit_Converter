# Feature inventory — contribution candidate PFU 3.3.6 vs shared PointTruth 1.1.0-rc.1

**Updated 26 September 2026:** native Civil 3D, schema 4 and cross-family reader rows brought in line with `CURRENT-STATUS.md` and the agreed first-release scope. Other rows unchanged from the 3.3.6 draft.

Requested in the partner note (Q9). Status vocabulary: **implemented** (in the named artifact, with a test), **pending integration** (exists in one family, not yet in the consolidated package), **deliberately unsupported** (a product decision, recorded), **proposed for removal** (needs an explicit product decision — nothing here is removed by this document). "Owner" is a proposal for who signs off the gate; blank means undecided.

| Capability | PFU 3.3.6 | PointTruth rc.1 | Consolidated product (proposal) | Gate / evidence | Owner |
|---|---|---|---|---|---|
| Exact rational conversion, ties-to-even, declared decimals | implemented | implemented | implemented (two implementations, shared spec) | literal vectors (partner), differential gate (47/33/3), in-page self-test | both |
| Auto precision from source quantum, reverse-error acceptance | implemented | implemented | implemented; **record `rounding.requested`** (schema 4) | differential, R9-02 regression | both |
| Formats PENZD / PNEZD / ENZ / NEZ / CUSTOM with column roles | implemented | implemented | implemented; **one wire index convention** (schema 4) | adapter vectors index-base | both |
| Header policy `auto` (resolved per file) | implemented | not present (`none`/`first`) | pending integration: store declared + resolved + rule id (schema 4) | adapter vectors header-auto | PFU |
| Duplicate identifiers accepted without a referencing control | implemented (policy) | refused (policy) | **decision needed** (Q6): examples first, then a named profile | policy vectors `duplicate-identifiers` | partner + user |
| Empty identifier preserved | implemented (policy) | refused | decision needed (Q6) | policy vector `empty-identifier` | partner + user |
| Unquoted quote inside a CSV description field | preserved (policy) | refused | decision needed (Q6) | policy vector `csv-quote-in-unquoted-field` | partner + user |
| Anchors (range bounds per column, target units) | implemented | implemented | implemented | CLI regressions, self-test | both |
| Control points with tolerance; refusal on failure | implemented | implemented | implemented; independent provenance of expected values to be recorded (schema 4) | literal vectors `independent-control-*` | both |
| Source-unit reference as a declaration | implemented | implemented | implemented; `declared_not_checked` retained | record schema | both |
| Byte-preservation of everything outside coordinate spans; BOM; per-line endings | implemented | implemented | implemented | literal vector `preserve-unit-comment-and-bytes` | both |
| Record schema 3 (`pointfile-units-report/3`), canonical-json/1 fingerprint | implemented | own schema | **deferred until after the first release** (agreed scope: PFU app, PointTruth pinned comparator); if adopted, conformance fixtures and a migration contract before readers | canonical fixtures, legacy records | both |
| Legacy readers: schema 2 adapters, v3.1/v3.2 acceptance sentence (adapter A) | implemented | 1.0.0 adapter | pending integration as named profiles; producer record preserved, separate reverification record | `tests/legacy-records/` | PFU |
| Cross-family serialized-record reader (PFU record in PointTruth, and reverse) | not present | not present | deferred until after the first release; vectors first (adapter-vectors/2) if pursued | semantic boundary probes 18/18 | both |
| Standalone verify (source + output + record) in browser and CLI | implemented | implemented (verify-anything) | implemented | CLI `verify`, browser Verify pane | both |
| CLI `verify --result` re-verification record; UNSUPPORTED exit 3; publication failure exit 4 | implemented | n/a | implemented (Python path) | CLI regressions | PFU |
| Complete HTML handoff: save, reopen, re-verify, repeat-save, new run from an opened handoff | implemented (`pfu-handoff/3`) | own envelope | implemented; **complete-handoff budget separate from conversion budget** | R9-01 chain, slow lifecycle, capacity records | both |
| Conversion budget 64 MiB source (browser) | implemented (limit) | own limit | keep, on measured evidence per platform | capacity records | both |
| Complete-handoff budget 64 MiB source (~186 MB file) | implemented (limit) | own limit | **decision needed on Windows/macOS records**: on the Linux/4 GB reference, 3.3.6 passes with the producer tab open and closed (3.3.5 failed open; the production diagnostic copy was removed in between); no boundary or worst-case-dimension runs yet; memory release after save, if any, must be a deliberate tested step, not a side effect of the download click | capacity records 64 open / closed | partner + user |
| Windows locale (UTF-8 mode off) | harness fixed; CLI has explicit encodings | n/a | required release check on Windows | partner's native log (round 10) | partner |
| Full browser suite (Playwright) on Windows and macOS | Linux only | n/a | required for release; blocks the claim if the dependency is missing | `run_all_tests.py --require-browser` | partner (Windows), Mac maintainers |
| Native Civil 3D acceptance (import settings, controls, tolerance) | one six-point case PASSED 2026-09-24 (Python output, international feet → metres, operator-assisted; export byte-identical) | acceptance pack author | browser-output route and the three prepared cases (U.S. survey foot, reverse direction, PNEZD) still required; exact build/template/unit settings to be recorded; earlier crash undiagnosed | `acceptance/civil3d-completed/`, `acceptance/next-native-tests/` | user (operator) |
| LandXML companion export | not present | not present | proposed experiment after consolidation; own schema validation and native acceptance | none yet | undecided |
| In-page self-test (50 fixtures) | implemented | implemented | implemented | browser suite | both |
| Test-only diagnostics (`window._lastRun` full byte copy) | opt-in only since 3.3.6 | n/a | opt-in only | F11-04 | PFU |

Nothing in the "PFU" column is proposed for removal. Two items in the rc.1 column are absent from PFU (its own envelope, its own limits) and are not proposed for removal either: the consolidation carries one envelope and one set of limits chosen on evidence, and the deferred family's readers stay as legacy profiles.
