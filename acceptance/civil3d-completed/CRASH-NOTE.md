# Civil 3D test interruption — 24 September 2026

**Latest result — 2026-09-24:** the retry produced `civil3d-export.txt`. All six IDs/descriptions and all 18 coordinates passed; the 325-byte export is byte-identical to the converter output and expected fixture. See [EXPORT-RESULT.md](EXPORT-RESULT.md). Native operation was user-performed; mechanical file verification was performed by the assistant. The earlier crash cause remains unresolved. Instructions and incident notes below retain the prior sequence.


**Latest clarification:** the user reports that changing precision appeared to work, and may have clicked Modify again to check it. Reopening Modify is a suspected trigger, not an established cause. The test drawing has not yet reappeared in the window list. Reopen the saved Drawing1.dwg and first export the current PENZD format, with all adjustments off, without opening Modify again. Inspect the actual exported values mechanically. Treat this first export as diagnostic until it passes the existing 0.000001 m checks; do not relax tolerance if precision settings were lost. Do not re-import.


The user reported an error-report window followed by the Civil 3D application closing during the point-export setup. The exact triggering click and error text are not yet known. The test drawing's window is absent from the current window list; the separate practice drawing remains open in another instance.

## Confirmed evidence

- `Drawing1.dwg` still exists: 979,498 bytes.
- Its SHA-256 remains `775aefcf1b8f2c93a6f50a559abb8c9ad11c707c788a60d182aa9d5e35775d7b`, exactly matching the fingerprint recorded before the interruption.
- A byte-identical backup was made at `evidence/pre-recovery/Drawing1.dwg`.
- No `civil3d-export*` output exists in the acceptance folder.
- A read of recent Windows Application error events (IDs 1000, 1001 and 1026, two-hour window) found no matching records. A bounded check of recent, relevant names in the usual temporary/Autodesk locations did not identify a crash report. This does not prove no crash log exists elsewhere.
- Native COGO object counts and coordinates remain unverified. Matching the saved file's hash establishes unchanged bytes, not an internal DWG integrity test.

## Interpretation

The evidence supports an interrupted native CAD test, not a successful export. It does not establish the cause or attribute the failure to the converted point file, precision setting, application build, connector, or another component. The last supplied screenshot showed the expected PENZD layout and comma delimiter with transformations and sampling off.

Eight decimal places is within Autodesk's documented range of up to twelve for point-file numeric columns. This is a supported setting, not proof that the installed application cannot fail while editing it. [Autodesk column precision documentation](https://help.autodesk.com/cloudhelp/2027/ENU/Civil3D-UserGuide/files/GUID-15F74255-5B31-495C-BBEB-0B3247B0124F.htm).

## Resume without confusing the evidence

1. Identify which action immediately preceded the crash and retain any error text or screenshot available. No diagnostic report has been sent to Autodesk by the assistant.
2. Reopen the already-saved `Drawing1.dwg` in this folder. Do not re-import the six points.
3. Inspect the point count, IDs and a coordinate sample. The backup preserves the last saved state if a recovery step becomes necessary.
4. Change one export setting at a time, retaining the observed result. Do not immediately repeat an unidentified crash sequence.
5. Perform the native point export and run the independent comparison only after an actual export exists. Keep any failed or coarsely rounded output as evidence; do not edit it to make the comparison pass.

Status: **native acceptance incomplete; saved file preserved; crash cause unresolved.**
