# Civil 3D test resumed — 24 September 2026

**Latest result — 2026-09-24:** the retry produced `civil3d-export.txt`. All six IDs/descriptions and all 18 coordinates passed; the 325-byte export is byte-identical to the converter output and expected fixture. See [EXPORT-RESULT.md](EXPORT-RESULT.md). Native operation was user-performed; mechanical file verification was performed by the assistant. The earlier crash cause remains unresolved. Instructions and incident notes below retain the prior sequence.


**File-picker clarification:** use **`IMPORT-THIS-POINTS-METERS.txt`** in this folder. It contains exactly the same 325 bytes as `converted-meters.csv`; its SHA-256 is `6a858d7e2b8a7574498b180fde57826c0b96ef87515deea45fdc06424b5b1412`. This clearly named copy is provided for text-file selection and its provenance is recorded in `operator-record.json`. Use **PENZD (comma delimited)**. Do not import `converted-meters.csv.report.txt`, which contains the human-readable verification report. References below to importing `converted-meters.csv` also apply to this byte-identical copy. The converter and expected values have not changed.

The owner reports Civil 3D activation is restored and has opened a blank metric drawing. User screenshots show the native Import Points dialog. Live desktop capture still fails (`SetIsBorderRequired … 0x80004002`); the assistant is working through background file checks and a newly registered read-only MCP connector. A successful native point read through that connector remains pending.

**Current status:** six-point export verification passed, and the final Save operation is confirmed on disk. The original export remains unchanged. Keep the drawing, export and verification evidence. Do not re-import. Broader release qualification and the earlier crash investigation remain separate.

**Fresh CLI conversion: PASSED. Separate verification: PASSED. Native workflow: USER-OPERATED. Native export file verification: PASSED.** No drawing or points were created by the assistant. This folder preserves a new attempt separately from the earlier evidence.

The operator needs to perform these native steps:

1. Create a **new empty metric Civil 3D drawing**. Record the template, metre units and Civil 3D build from About. The points are fictional and have no real-world CRS; do not assign a transformation to make them fit a site.
2. Use **`IMPORTPOINTS` at the Civil 3D command line**. Select **`converted-meters.csv` in this folder**. Choose **PENZD (comma delimited)**: point number, Easting, Northing, elevation, raw description. Confirm the preview's axis order. Preserve IDs and turn off elevation adjustments, coordinate transformations and coordinate expansion. In this otherwise empty drawing, leave **Add Points to Point Group** unchecked and verify that exactly the six test points exist after import. A dedicated group is optional if needed to isolate these points. See [Autodesk's import instructions](https://help.autodesk.com/cloudhelp/2027/ENG/Civil3D-UserGuide/files/GUID-3CB9DB32-05E8-4B0E-BBC9-5A58BCDE2D12.htm).
3. Import and inspect **six** points: **101, 102, 110, 150, 201, 901**. Point **110** should be **E 304800, N 609600, Z 0 m**. Point **150** should be **E −30.48, N 76.2, Z −1.524 m**. The test drawing has been saved here as `Drawing1.dwg`; retain that name. Retain screenshots of import settings and point properties.
4. Export **only the six test points** as PENZD comma, no header, **raw descriptions**, with **at least six coordinate decimals**, and no coordinate transformation. Exporting all points is appropriate only after verifying that the drawing contains exactly those six; otherwise isolate them in a dedicated group. Save here as **`civil3d-export.txt`**. Do not edit the export. See [Autodesk's export guidance](https://help.autodesk.com/cloudhelp/2026/ENG/Civil3D-UserGuide/files/GUID-8AAC3D4F-57D9-4DBB-9B92-D3DFE444AB38.htm).
5. Tell the assistant the export is ready, or give its location if saved elsewhere. It will compare all six IDs, raw descriptions and E/N/Z values and save the result. Record failures without correcting the export to fit the expected result.

The comparison can also be run from this folder:

```powershell
python .\check_export.py --app .\pointfile_units.py --converted .\converted-meters.csv --observed .\civil3d-export.txt
```

The generated input exactly matches the independent expected file, SHA-256 `6a858d7e2b8a7574498b180fde57826c0b96ef87515deea45fdc06424b5b1412`. The native export tolerance is **0.000001 m** for E/N/Z and exact agreement for IDs and raw descriptions. That tolerance concerns CAD representation/export; conversion remains byte-exact.

Keep the DWG, unedited export, screenshots and product/template/settings details. A file comparison alone cannot prove the file came from Civil 3D. This acceptance case is the PFU Python output → Civil 3D route; browser download/handoff and wider format/capacity tests remain separate.
