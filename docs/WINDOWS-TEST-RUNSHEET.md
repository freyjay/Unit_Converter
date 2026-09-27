# Windows test runsheet — PFU 3.3.6 (contribution candidate) beside PointTruth 1.1.0-rc.1

Two tracks. The **user track** needs nothing installed. The **engineer track** needs Python 3.10+ (and Node 20+, Playwright with Chromium for the browser suite). Fill in `tests/windows/results-template.json` as you go; every field left blank means NOT RUN, which is a valid answer.

Identify what you are testing first (PowerShell): `Get-FileHash -Algorithm SHA256 Point-File-Unit-Converter.html, PointTruth.html`. Record both hashes. PFU's expected value is `html_sha256` in `docs/PROVENANCE.json` (this runsheet no longer repeats it, so it cannot go stale); rc.1 is `bf98e65dc89eeb77…` (the repository's `dist/PointTruth.html` is **1.0.0**, `9fb87ec289fe924a…` — a different build; say which one you used).

## User track (about 20 minutes, no installs)

1. **Open by double-click.** Double-click `Point-File-Unit-Converter.html`. Note the browser and version (Edge/Chrome/Firefox: menu → About) and that the address bar starts with `file:///`. If the page shows anything other than the app, record it verbatim.
2. **Self-test.** Click *Self-test* → *Run*. Record the summary line (expect "all 50 checks passed (build …)") and the build id it prints.
3. **Convert the acceptance source.** Load `tests/roundtrip/acceptance-source-international-feet.csv`. Settings: format **PENZD**, delimiter **comma**, first line **is data**, source **international feet**, target **metres**, decimals **8**, unit reference exactly: `Fictional acceptance fixture; international foot declared in ACCEPTANCE.md`. Tick the confirmation, **Convert**. Record the data-row count (expect 6) and the max reverse error line.
4. **Download and hash.** Download the point file. Do not open it in Excel or Notepad. `Get-FileHash` it: expected `6a858d7e2b8a7574498b180fde57826c0b96ef87515deea45fdc06424b5b1412`. Record what you observe either way.
5. **Save, close, reopen.** Save the complete handoff. Close the browser entirely. Double-click the saved `.handoff.html`. Record the status line (expect "Handoff verified …") and whether the editor shows the settings with the confirmation box **unchecked**.
6. **Save again from the reopened handoff.** Click *Save complete handoff* again, reopen that second file, download its point file, hash it: must equal step 4. Record.
7. **Repeat 3–4 in PointTruth rc.1** with the equivalent settings (columns P/E/N/Z, no header, precision 8). Record its output hash: must also equal step 4. If it differs, keep both files.
8. **The foot trap, deliberately.** In PFU, load the metres file you downloaded in step 4, convert **metres → US survey feet**, auto precision. It will verify. Look at point 110: its easting reads **999998** followed by zeros (the number of decimals depends on the input's precision — with the eight-decimal metres file, auto writes ten — and is not the point), instead of 1000000; its northing reads 1999996 instead of 2000000. Record the values you saw. Everything verified; the declaration was wrong; this is the truth the tool cannot protect by itself.

## Engineer track (adds about 30 minutes; 64 MiB capacity runs add ~10)

From the extracted package root, in PowerShell:

```text
py -3 tests\roundtrip\roundtrip_cli.py --report             # expect "round-trip gate: PASS (0 problem(s))"; RESULT.md is regenerated from the observations
py -3 tests\run_all_tests.py                                 # CLI baseline 30/30, regressions 115; browser suite runs only if Playwright is installed
pip install playwright ; playwright install chromium         # optional, for the two lines below
$env:PT_HTML="C:\path\to\PointTruth.html" ; py -3 tests\run_all_tests.py --require-browser
py -3 tests\capacity\measure_lifecycle.py --sizes 16,64 --out cap-win-open
py -3 tests\capacity\measure_lifecycle.py --sizes 64 --close-producer --out cap-win-closed
```

Run the first two with Python UTF-8 mode **off** (the default on Windows) so the locale path is exercised; if anything fails, rerun with `$env:PYTHONUTF8=1` and record both. Attach `cap-win-*/capacity-record.json` — these will be the first non-Linux capacity evidence either team has. The Linux numbers in `tests/capacity/results/` are contributor evidence only.

## What to send back

`results-template.json` filled in, the hashes you observed, any file that did not match, and the capacity records. "Not run" is fine; a guessed field is not.
