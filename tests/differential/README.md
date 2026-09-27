# Differential run: PointTruth engine vs pointfile_units.py

`corpus.py` writes 83 adversarial cases (`corpus.json`). `run_pt.cjs` runs them through a `PointTruth.html` placed in the
same directory (any build exposing `globalThis.PointTruth.convert`); `run_py.py` runs them through `pointfile_units.py`;
`compare.py` tabulates agreement (outcome class and bytes). Run from this directory:

    python3 corpus.py && node run_pt.cjs && python3 run_py.py && python3 compare.py

Result on 2026-09-22 against PointTruth 1.1.0-rc.1 and pointfile_units.py 3.3.4: 80/83 agree; the three divergences are
policy (quote inside an unquoted CSV field, duplicate identifiers, empty identifier), none arithmetic. Decode outputs with
`ignoreBOM: true` when comparing text — a plain `TextDecoder` strips the BOM and reports a false divergence.
