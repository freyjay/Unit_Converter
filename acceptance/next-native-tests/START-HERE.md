# Prepared next native cases — NOT RUN in Civil 3D

Each case has two fictional points. The current PFU CLI produced the clearly named `IMPORT-...txt` file; exact rational arithmetic independently generated `expected.txt`, which matches every byte. The converter's separate `verify` command also passed. These are prepared inputs, not observed CAD exports.

| Case folder | Import AND export format | Target drawing units to confirm | What it tests |
|---|---|---|---|
| `us-survey-feet-to-meters` | PENZD (comma delimited) | Metres | U.S. survey foot factor 1200/3937; large coordinates expose a wrong-foot declaration |
| `meters-to-international-feet` | PENZD (comma delimited) | International feet | Reverse direction and negative values; confirm the actual foot definition in Drawing Settings |
| `pnezd-international-feet-to-meters` | PNEZD (comma delimited) | Metres | Northing/Easting column order, with deliberately different axis values |

For each case, create a separate empty drawing. Preserve the already-passing `Drawing1.dwg` and leave the practice drawing alone. Record the exact running Civil 3D build, template, Drawing Settings units and any coordinate-system assignment. The launch shortcut name is not enough to establish units. Unit conversion is already applied to the import file; do not apply a second native transformation.

1. Import only the case's `IMPORT-...txt`, with the exact format in the table. Preview point number, E/N order, elevation and raw description. A green format-match status is insufficient.
2. Keep elevation adjustment, coordinate transformation and data expansion off for this isolated test. No read limit or sampling. Confirm exactly two points with the IDs shown in the input.
3. Export with the same format and 8 decimals for each of the three coordinate columns. Save as `civil3d-observed.txt` inside that case folder. Record the actual destination; a report `.txt` is not point data.
4. Save the case drawing under a new name. Retain screenshots/settings and any errors; do not relabel an interrupted attempt as a pass.
5. From this folder, run for the selected case (change the folder name for the other cases):

```powershell
python .\check-export.py --case .\us-survey-feet-to-meters --observed .\us-survey-feet-to-meters\civil3d-observed.txt
```

Exit 0 means supplied files match this case within the declared tolerance; exit 1 means a comparison failed; exit 2 means parsing or file access failed. Point IDs and raw descriptions must match exactly. Coordinate tolerance is 0.000001 m, or its exact international-foot equivalent for the reverse case. A file comparison alone does not authenticate the export's origin.

The checker was exercised with synthetic success, dropped/duplicate IDs, swapped axes, altered descriptions, altered coordinates and malformed numbers. Those controls do not count as native CAD tests. The saved six-point case is the only completed native import/export evidence in this handoff.
