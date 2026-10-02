# Current status: Point File Unit Converter (pre-release)

**What it is:** an offline browser app and a Python command-line tool that convert the coordinate columns of survey point files between metres, international feet and U.S. survey feet with exact arithmetic. It leaves every other byte unchanged and checks its own output before offering it.

## Verified (each result belongs to the version named)

- **Arithmetic and preservation:** exact rational conversion with declared rounding; an independent second calculation; hand-derived reference values; a second implementation (the PointTruth comparator in `tests/differential/`). On `ff68746` the Windows review recomputed all 70,194 coordinates of a lifecycle fixture without the converter's code and reproduced the output exactly.
- **Operating systems:** on `d4ef080` (3.3.7) the core test gate passed on macOS 15.7.1 (Apple Silicon, the owner's Mac) and on Windows 10 (the Windows review), and in the contributor's automated runs. The Windows tested archive is **byte-identical** to the automated-run archives, and the Windows rebuild of the download matches (`ebda4aeb…`). The same held on `ff68746` and `625fbbc`.
- **Continuous integration:** run 36923277069 on `d4ef080` (3.3.7) passed all six jobs with no failed steps: the core gate and the automated Chromium lifecycle (through Playwright) on each of GitHub's three test systems, including Windows and macOS. Earlier: run 36708843874 on `ff68746`. Later commits have their own runs on the Actions tab.
- **The current page** adds a fix to the run status (a separate Verifying phase, so Convert and Preview stay disabled until the result is checked; found by the Windows review of 3.3.7). Its own runs are listed on the Actions tab.
- **Safari by hand:** a conversion and its round trip came out byte-identical on the 28 September page (`a4e2b388`, the same conversion engine). Not yet repeated on the current page.
- **Civil 3D:** one six-point case (international feet to metres, PENZD, Civil 3D 2027) was imported and exported natively, and the export came back byte-identical to the converted file (`acceptance/civil3d-completed/`).

- **3.3.8** fixes the one defect the Windows review found in 3.3.7 (PFU-01): the page now stays busy, showing *Verifying*, until a result is verified and published. Status and timing only; the arithmetic is unchanged. Its own CI run is on the Actions tab.

## Not yet verified

- Installed browsers on the current version: Safari, Chrome, Edge and Brave by hand (these are the intended targets; the automated Chromium runs above are a different, narrower check). Firefox is not a target.
- Phone screens: not supported in this pre-release (the page is designed for desktop browsers).
- Intel Macs.
- In Civil 3D: the U.S. survey foot, metres-to-feet and PNEZD cases (prepared in `acceptance/next-native-tests/`), and a file produced by the browser app.
- Very large files up to the 64 MiB input limit on typical hardware.
- A full accessibility review. Keyboard access to the file chooser and labels for every setting were added on 1 October 2026; a broader review is pending.

## What a pass means

A pass means the arithmetic is exact to the written precision and nothing outside the converted numbers changed. It does not confirm that the right units, columns or survey reference were chosen, and it does not handle coordinate systems or datums.

## This copy

This repository started from a fresh public snapshot (`87a202a`). Its own checks run on its own commits, and CI runs on every push. The historical evidence behind the statements above is kept privately and identified by hash in `PUBLIC-EVIDENCE-MAP.json` and `EVIDENCE-ARCHIVES.json`. License: MIT, copyright freyjay.
