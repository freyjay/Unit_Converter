# Public note

Each prepared case keeps its source, import file, expected output, case description and checker inputs. The conversion records, reports and logs made when the import files were prepared contain local file paths, so they are kept privately and listed with their SHA-256 in `docs/PUBLIC-EVIDENCE-MAP.json`. To recreate a record, convert the case's source with `pointfile_units.py` as described in `QUICK-START.md`; the import file will come out identical, since its hash is pinned in `prepared-cases.json`.
