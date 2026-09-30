# Quick start: Point File Unit Converter

Converts the coordinate columns of a survey point file between metres, international feet and U.S. survey feet using exact arithmetic. Every other character in the file is left unchanged, and the output is checked by a second, independent calculation before it is offered to you.

Works in Chrome, Safari, Edge and Brave.

## In a browser (nothing to install)

1. **Open `Point-File-Unit-Converter.html`** by double-clicking it. It works offline, and your file never leaves your computer.
2. **Load your point file** (`.txt`, `.csv` or `.pnt`).
3. **Confirm the format.** Check the column preview. PENZD (point, easting, northing, elevation, description) and PNEZD (point, northing, easting, …) look alike, and choosing the wrong one swaps easting and northing. Choose the delimiter, and say whether the first line is a header.
4. **Declare the units.** Pick the source and target units yourself; the tool never assumes a foot. The international foot is exactly 0.3048 m and the U.S. survey foot is 1200/3937 m. They differ by 2 parts per million, about 2 ft on a coordinate of 1,000,000 ft, and nothing in the file can tell them apart. Record where you got the unit information in *Source unit reference*.
5. **Optional: add a control point.** If you know one point's coordinates in the target units from an independent source (a benchmark, monument or control sheet, not a value computed from this same file), enter it under *Control points* with the tolerance that source justifies. A wrong unit choice is refused only when the difference it causes exceeds that tolerance, so a point near zero or a loose tolerance may not tell the two feet apart.
6. **Tick the confirmation, then Convert & verify.**
7. **Download "Point data for import".** This is the file for your CAD software. The report and the manifest are records of the conversion; do not import them. *Save complete handoff* keeps the source, output and records in one HTML file that re-checks itself when opened.

To check a file later, open the app and choose **Verify a file you already have**.

## Importing into Civil 3D

Use *Import Points* with the point file format that matches the columns you confirmed (for example, PENZD comma-delimited). Make sure the drawing's units match the units you converted to, and that no coordinate transformation is applied during import unless you intend one. One six-point import-and-export round trip has been verified in Civil 3D 2027 (see *What this release has been checked for* below).

Prefer a page? Open `START-HERE.html`: the same guide for Windows and Mac, side by side.

## Command line (Python 3, standard library only)

Windows (PowerShell), on one line; use `py -3` instead of `python` if that is how Python is installed:

```powershell
python pointfile_units.py convert --in points.txt --out points-m.txt --format PENZD --delimiter comma --header no --conversion USFeetToMeters --source-unit-reference "Survey report, sheet 2"
```

macOS (Terminal):

```text
python3 pointfile_units.py convert --in points.txt --out points-m.txt \
    --format PENZD --delimiter comma --header no \
    --conversion USFeetToMeters --source-unit-reference "Survey report, sheet 2"
```

Conversions: `IntlFeetToMeters`, `MetersToIntlFeet`, `USFeetToMeters`, `MetersToUSFeet`, `USFeetToIntlFeet`, `IntlFeetToUSFeet`, and `Custom`. To add a control point, add `--control-point "ID V1 V2 V3 TOLERANCE"`, with the values in the format's coordinate order and in the target units. The command writes the point file plus `.report.txt` and `.manifest.json` records next to it. Exit code 0 means it converted and verified. Any other exit code means you have no trusted output.

To check the files later (on Windows, use `python` or `py -3`):

```text
python3 pointfile_units.py verify --source points.txt --output points-m.txt --manifest points-m.txt.manifest.json
```

## What a pass means

A pass means the arithmetic is exact to the written precision and nothing outside the converted numbers changed. It does **not** confirm that you chose the right units or columns, and it does not deal with coordinate systems, datums or survey quality.

## What this release has been checked for

The files in this release are identified in `CHECKSUMS.sha256`. The conversion engine inside the app and the command-line tool are the same ones that passed the checks below; later versions changed the page's colours and wording, not the conversion.

- **Arithmetic:** exact, and checked against calculations written independently of the converter and against a second implementation (PointTruth).
- **Automated checks:** every version published on GitHub is tested automatically on Windows and macOS, with core and browser checks. The results are on the project's GitHub Actions page.
- **By hand:** in Safari on macOS, a conversion (international feet to metres) and its round trip back came out byte-identical to the originals, on the previous page design with the same conversion engine.
- **Civil 3D:** one six-point import-and-export round trip in Civil 3D 2027 (international feet to metres) came back byte-identical.
- **Not yet checked:** Edge, Chrome and Brave on Windows and Chrome on macOS, by hand; Intel Macs; the U.S. survey foot, metres-to-feet and PNEZD cases in Civil 3D; files produced by the browser app in Civil 3D; accessibility; very large files on typical computers.

## Status and license

This is a pre-release build. It is released under the MIT License (`LICENSE`). The software is provided "as is", without warranty.
