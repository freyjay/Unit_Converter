# Civil 3D six-point export check — PASSED

Verified 24 September 2026 at 13:05 UTC. Product under test: PFU 3.3.6 Python, package r3. Native application identified by its window as Civil 3D 2027. The user operated the metric test session, `Drawing1.dwg`; the separate imperial practice drawing was excluded.

**The observed Civil 3D export contains exactly the same 325 bytes as both the converter's output and the expected fixture.** This is a successful result for this specific six-point case.

| Check | Result |
|---|---|
| Point count | 6, with no missing or extra IDs |
| IDs | 101, 102, 110, 150, 201, 901 — exact matches |
| Raw descriptions | All 6 match exactly |
| Coordinate comparisons | All 18 match exactly as exported decimal values |
| Output precision | 8 decimal places in every E/N/Z token |
| Maximum coordinate difference | 0 m, within the unchanged 0.000001 m tolerance |
| File preservation | Export byte-identical to converter output and expected fixture |
| Separate arithmetic check | Each source coordinate multiplied by exact rational 381/1250 equals the exported value |
| Drawing window after export | Drawing1 remained open |

## Observed point values

| Point | Easting (m) | Northing (m) | Elevation (m) | Raw description |
|---|---:|---:|---:|---|
| 101 | 6052.49214696 | 6175.38686688 | 30.57320784 | PT_BASE |
| 102 | 6058.04633448 | 6159.31299504 | 30.81311592 | PT_CHECK |
| 110 | 304800.00000000 | 609600.00000000 | 0.00000000 | UNIT_CHECK |
| 150 | -30.48000000 | 76.20000000 | -1.52400000 | NEGATIVE_TEST |
| 201 | 37.62960216 | 233.30370408 | 0.03810000 | AXIS_CHECK |
| 901 | 0.00000000 | 3.04800000 | 0.30480000 | ORIGIN_CHECK |

## Evidence and reproducibility

- Original observed output: `civil3d-export.txt`. It was read, not rewritten by the assistant.
- Retained byte-identical evidence copy: `evidence/civil3d-export-observed.txt`.
- Machine-readable comparison: `evidence/native-export-comparison.json`.
- Detailed per-coordinate rational check and provenance: `evidence/native-export-verification.json`.
- Native workflow observations and limitations: `operator-record.json`.
- The earlier saved drawing was backed up before retry at `evidence/pre-recovery/Drawing1.dwg`.

Shared SHA-256 for the observed export, converter output, import alias and expected fixture:

`6a858d7e2b8a7574498b180fde57826c0b96ef87515deea45fdc06424b5b1412`

The standard checker completed with exit code 0 and no failures:

```powershell
python .\check_export.py --app .\pointfile_units.py --converted .\converted-meters.csv --observed .\civil3d-export.txt
```

The additional arithmetic check parsed source and export tokens as exact fractions and compared each exported coordinate with the corresponding source coordinate multiplied by `381/1250`. It did not call the converter's arithmetic functions. This is a separate computation, not a claim of review by an independent author.

## What this establishes

This case exercised international-feet source values converted by the Python CLI, a byte-identical `.txt` import copy, user-operated Civil 3D import, and a native PENZD export reported by the user with all three coordinate precisions set to 8. The exported decimal coordinates, point IDs, descriptions and complete file bytes match the expected result.

Native operation provenance rests on the user's actions, supplied screenshots, local file appearance and observed application window. The experimental MCP connector did not successfully read native COGO objects; this result must not be presented as MCP-controlled or independently recorded execution of every native action.

The exact export does not imply mathematically exact internal CAD floating-point storage, correctness for every possible input, or correctness of a real survey. Source units are declared for a fictional fixture. Civil Drawing Settings, exact product build, and the template were not independently inspected. The browser-produced download route and broader unit/format/size cases remain separate tests.

## Retry and remaining work

An earlier native session closed after an error report while editing or reopening point-file format settings. The user tentatively recalled reopening Modify to confirm precision. The cause was not established. The later retry produced this passing export while Drawing1 remained open; that does not prove the earlier crash is fixed.

The subsequent Save operation was confirmed on disk at 13:08:54 UTC (06:08:54 PDT): Drawing1.dwg is now 1,046,760 bytes, SHA-256 `3091bd435b3b1a93a2e7f32540afa3ae81d73100f4fb623b57847d18ff3535db`. Drawing1.bak exactly matches the previous saved DWG. The verified export remains unchanged. This confirms the drawing was written; the persisted internal format settings have not been independently read back. See `evidence/qsave-file-check.json`.

Lessons for packaging: distinguish import data clearly from reports; provide explicit PENZD column previews; treat a green format-match check as insufficient evidence of correct mapping; record export precision; and verify actual exported files mechanically. Keep failed attempts and successful retries in the same evidence trail without merging their conclusions.
