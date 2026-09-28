# Current status: Point File Unit Converter (pre-release)

**What it is:** an offline browser app and a Python command-line tool that convert the coordinate columns of survey point files between metres, international feet and U.S. survey feet with exact arithmetic. It leaves every other byte unchanged and checks its own output before offering it.

## Verified

- **Arithmetic and preservation:** exact rational conversion with declared rounding; an independent second calculation; hand-derived reference values; a second implementation (the PointTruth comparator in `tests/differential/`) agreeing on 47 cases, refusing the same 33, and differing only in 3 named policies; round-trip loops that reproduce the original bytes at the original precision.
- **Operating systems:** the complete core test gate passed on macOS 15.7.1 (Apple Silicon) and Windows 10, and in continuous integration. On the accepted packaging revision, every machine built a **byte-identical** tested candidate, verified by opening and comparing the archives themselves (`docs/PAYLOAD-IDENTITY.md`, `scripts/compare_runs.py`). Browser tests passed in Chromium. **Continuous integration:** on the public commit `625fbbc`, all six GitHub Actions jobs succeeded: the core gate and the Chromium lifecycle (through Playwright), including on Windows and macOS ([run 36348557774](https://github.com/freyjay/Unit_Converter/actions/runs/36348557774)). The Windows and macOS core gates also passed locally on that commit, and the Windows tested archive is byte-identical to the other machines' archives.
- **Civil 3D:** one six-point case (international feet to metres, PENZD, Civil 3D 2027) was imported and exported natively, and the export came back byte-identical to the converted file (`acceptance/civil3d-completed/`).

## Not yet verified

The browser app on Windows and macOS; Edge, Firefox and Safari; Intel Macs; the U.S. survey foot, metres-to-feet and PNEZD cases in Civil 3D (prepared in `acceptance/next-native-tests/`); files produced by the browser app in Civil 3D; accessibility; very large files on typical computers. Safari on macOS has been checked by hand (a conversion and its round trip, on the previous page design with the same engine). Hands-on checks in Edge, Chrome and Brave on Windows and Chrome on macOS are still pending (`docs/BROWSER-TESTS.md`).md`). Official CI that builds once and tests the same artifact on every OS is planned; today each OS rebuilds.

## What a pass means

A pass means the arithmetic is exact to the written precision and nothing outside the converted numbers changed. It does not confirm that the right units, columns or survey reference were chosen, and it does not handle coordinate systems or datums.

## This copy

This repository started from a fresh public snapshot (`87a202a`). Its own checks run on its own commits, and CI runs on every push. The historical evidence behind the statements above is kept privately and identified by hash in `PUBLIC-EVIDENCE-MAP.json` and `EVIDENCE-ARCHIVES.json`. License: MIT, copyright freyjay.
