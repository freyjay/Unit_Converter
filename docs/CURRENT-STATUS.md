# Current status: Point File Unit Converter (pre-release)

**What it is:** an offline browser app and a Python command-line tool that convert the coordinate columns of survey point files between metres, international feet and U.S. survey feet with exact arithmetic. It leaves every other byte unchanged and checks its own output before offering it.

## Verified

- **Arithmetic and preservation:** exact rational conversion with declared rounding; an independent second calculation; hand-derived reference values; a second implementation (the PointTruth comparator in `tests/differential/`) agreeing on 47 cases, refusing the same 33, and differing only in 3 named policies; round-trip loops that reproduce the original bytes at the original precision.
- **Operating systems:** the complete core test gate passed on Linux (x86_64), macOS 15.7.1 (Apple Silicon) and Windows 10. On the accepted packaging revision, all three built a **byte-identical** tested candidate, verified by opening and comparing the archives themselves (`docs/PAYLOAD-IDENTITY.md`, `scripts/compare_runs.py`). Browser tests passed on Linux Chromium.
- **Civil 3D:** one six-point case (international feet to metres, PENZD, Civil 3D 2027) was imported and exported natively, and the export came back byte-identical to the converted file (`acceptance/civil3d-completed/`).

## Not yet verified

The browser app on Windows and macOS; Edge, Firefox and Safari; Intel Macs; the U.S. survey foot, metres-to-feet and PNEZD cases in Civil 3D (prepared in `acceptance/next-native-tests/`); files produced by the browser app in Civil 3D; accessibility; very large files on typical computers. Official CI (build once, test the same artifact on every OS) is planned.

## What a pass means

A pass means the arithmetic is exact to the written precision and nothing outside the converted numbers changed. It does not confirm that the right units, columns or survey reference were chosen, and it does not handle coordinate systems or datums.

## This copy

This is the first public snapshot. Its own checks run on its own commits. The historical evidence behind the statements above is kept privately and identified by hash in `PUBLIC-EVIDENCE-MAP.json` and `EVIDENCE-ARCHIVES.json`. License: MIT, copyright freyjay.
