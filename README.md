# Unit_Converter: Point File Unit Converter

**Use it:** [QUICK-START.md](QUICK-START.md). **Status:** [docs/CURRENT-STATUS.md](docs/CURRENT-STATUS.md). **All documents:** [docs/README.md](docs/README.md).

Convert survey point-file coordinates between metres, international feet and U.S. survey feet, preserve everything outside the selected coordinate values, and keep a verifiable record of the operation. You establish source units and column meaning; a pass checks arithmetic and preservation under those declarations.

## Use the converter

Open **[Point-File-Unit-Converter.html](Point-File-Unit-Converter.html)** in a desktop browser. This is the complete offline app, including the new expandable “What this tool does” summary. No account, upload, server, Python or Node is needed for normal use. A GitHub source page displays HTML code; download the file before opening it.

The same HTML is supplied for Mac and Windows. This is a platform-neutral browser app, not a signed macOS `.app` or Autodesk plug-in. Actual macOS browser acceptance is still pending.

## Develop and verify

Use Python 3.13 and Node.js 24 for the supplied development checks. From this directory:

```sh
python3 scripts/check.py --suite core
```

On Windows use `python` instead of `python3` if appropriate. Checks run from a temporary copy with spaces in its path. They leave source and historical evidence unchanged and write logs to `.checks/`. Core checks deliberately exclude browser execution. Optional browser setup and tests are in the Mac guide.

The GitHub Actions workflow has separate core and Chromium jobs for Windows, macOS and Linux. It is prepared, not a record of successful GitHub runs. It never deploys or publishes a release. A 1 MiB browser lifecycle pass does not validate the full file-size limit.

## Included

| Path | Purpose |
|---|---|
| `Point-File-Unit-Converter.html` | Primary app; one complete HTML |
| `pointfile_units.py` | Exact-arithmetic Python CLI; standard library only |
| `tests/` | Oracle fixtures, regressions, differential checks and utility failure controls |
| `scripts/` | Mac/Windows/Linux check entry point and repository checks |
| `.github/workflows/checks.yml` | Proposed cross-platform GitHub Actions jobs |
| `acceptance/civil3d-completed/` | Six-point native Civil 3D round trip: source, conversion, export and its checker (screenshots, drawings and operator logs are kept privately) |
| `acceptance/next-native-tests/` | Three prepared cases; native execution remains NOT RUN |
| `docs/PROVENANCE.json` | Exact current app identity and changes from the tested candidate |
| `QUICK-START.md` | One-page guide for people converting files |
| `scripts/build_consumer_release.py` | Builds `dist/Unit_Converter-<revision>.zip`: app, CLI, guide, LICENSE, license note, checksums |
| `docs/TEST-GATE-MAP.md` | What each check runs and what it proves |

The bundled PointTruth rc.1 file under `tests/differential/` is a comparison dependency, not a second app the user must choose. This package does not imply that PFU and the earlier PointTruth repository have been merged into a shared runtime.

The passing CAD route used Python-produced files and a Windows Civil 3D operator. Browser-to-CAD, wider native cases, macOS acceptance and large-file profiles remain pending. See [current status](docs/CURRENT-STATUS.md).

## License

MIT, copyright freyjay; see [`LICENSE`](LICENSE) and [`LICENSE-NOTE.md`](LICENSE-NOTE.md). Developed with the help of AI assistants (Claude and Codex) as tools.

## Consumer release

`python3 scripts/build_consumer_release.py` builds `dist/Unit_Converter-<page-text revision>.zip` containing only what a user needs: the app, the CLI, `QUICK-START.md`, `LICENSE`, the license note and a checksum file. It refuses to build if the app or CLI differs from `docs/PROVENANCE.json`. The build is reproducible, so the same inputs always produce the same ZIP bytes.

## Evidence

This repository is the public copy of the project. The historical test evidence (runs on Linux, macOS and Windows, review records, screenshots and Civil 3D operator logs) is kept privately, because much of it contains local file paths. Every omitted file is listed with its SHA-256 in [`docs/PUBLIC-EVIDENCE-MAP.json`](docs/PUBLIC-EVIDENCE-MAP.json), and every tested archive in [`docs/EVIDENCE-ARCHIVES.json`](docs/EVIDENCE-ARCHIVES.json). This copy's own checks run fresh on its own commits.
