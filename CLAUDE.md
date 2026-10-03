# CLAUDE.md: working in this repository

Read this first, then `docs/HANDOFF.md` (history, decisions, open work) and `docs/CURRENT-STATUS.md`.

## The goal

Convert **complete Civil 3D projects** between declared units (points, linework, surfaces, alignments, profiles, **corridors, pipes, labels and references**) while preserving geometry, editable objects and working references. This repository holds the first component: **PFU, the Point File Unit Converter**. It is a single-file browser app (`Point-File-Unit-Converter.html`) plus the Python CLI (`pointfile_units.py`), and it converts survey point files exactly, with evidence. The full-project DWG work is planned (see `docs/HANDOFF.md`).

## The team

- **Owner (freyjay):** makes every product decision. Ask before changing scope, wording the owner chose, or defaults.
- **Mac side:** implementation. The Claude chat handles coordination, reviews, packages and the tracker; Claude Code implements in this repository.
- **Windows reviewer:** independent review, Windows gates and Civil 3D tests. Exchanges are review packages with probes and evidence.
- **Only one implementer edits at a time.** GitHub `master` and the shared project tracker (kept outside this repository) are the sources of truth.

## Non-negotiable rules

1. **The arithmetic engine never changes casually.** `<script id="engine">` in the HTML and the arithmetic in `pointfile_units.py` change only by the version string at a release. Assert this byte-for-byte when building (compare with the previous release). Interface work goes in `<script id="app">`.
2. **Never claim more than was checked.** Every result belongs to a named commit. Label who ran it: a contributor run, CI metadata, owner-reported, or Windows-verified. Historical results stay historical.
3. **Tests must fail on the broken version** (negative controls) and pass on the fix. Prefer real-browser checks through real entry points (the file input, buttons, the keyboard) over shortcuts like `_loadBytes`; shortcuts hid real defects before (see R338 in `docs/HANDOFF.md`).
4. **User-facing text** (`README.md`, `QUICK-START.md`, `START-HERE.html`, `docs/CURRENT-STATUS.md`, the page itself) must not mention Linux or Ubuntu (owner's rule). The support claim reads: "Works in Chrome, Safari, Edge and Brave on desktop computers", marked as intended support.
5. **No personal paths or usernames** in committed files. Private evidence (raw run folders, review packages, screenshots) stays outside this public repository.
6. **File names are never unit clues.** Only header coordinate fields and `# units:` comments count. Clues are advisory; the user makes the final call; nothing is blocked or switched automatically.

## Checks (run before every commit that changes code)

```bash
python3 scripts/check.py --suite core          # run twice; compare: python3 scripts/compare_runs.py <run1> <run2>
python3 scripts/check.py --suite browser       # needs the browser setup in docs/BROWSER-TESTS.md
node tests/<probe>.cjs Point-File-Unit-Converter.html   # any Windows probes supplied with a review
```

After changing the HTML or the CLI:

- update `docs/PROVENANCE.json` (`html_sha256`, `application_script_sha256` for all three script blocks, `python_sha256`, `html_text_revision`, `release_revision`, `html_change`);
- run `python3 scripts/update_package_contents.py`, `python3 scripts/verify_package.py .` and `python3 scripts/check_repository.py`.

## Releases

- **Version bump:** change the `VERSION` in the engine (that string only), the `VERSION` and docstring in `pointfile_units.py`, the page `<title>`, header and footer (`TOOL-01 vX.Y.Z · PAGE TEXT YYYY-MM-DD.N`), the tested-build name in `scripts/check.py` and `tests/release_check.py`, and browser check G33. Verification never compares versions; older manifests must still verify.
- **Commit identity:** `freyjay <222683341+freyjay@users.noreply.github.com>`. The **last commit** of every change set regenerates the exposure inventory on a clean tree: `python3 scripts/scan_exposure.py --markdown docs/EXPOSURE-INVENTORY.md`.
- **Pushing:** if SSH on port 22 is reset, use `GIT_SSH_COMMAND="ssh -o HostName=ssh.github.com -o Port=443" git push`. CI (`.github/workflows/checks.yml`) runs core and the Chromium lifecycle on three systems; all six jobs must pass.
