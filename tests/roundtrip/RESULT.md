# Round-trip loop result — generated from roundtrip-observations.json

Tool `pointfile_units.py` sha256 `b6589870c4c2e587d3ef5bf21496db19a598d6adb449903e1b0ea61cb2f326cf`, run 2026-09-24T13:39:29Z, observations sha256 `60e1f222d737a5e9d7311145728d6be0345e462c8c0d368475947213467e3685`. Loop: international feet → metres → feet → metres → feet, auto precision. **Verdict: PASS** (0 problem(s)).

| Sample | Legs vs oracle | Decimals written per leg | Max deviation of returned feet, leg 2 / leg 4 | Return at original precision | Wrong-foot return (auto) |
|---|---|---|---|---|---|
| acceptance (`7a2d5c2798af…`) | 4/4 | 6, 8, 10, 12 | 1.57e-06 ft / 1.57e-06 ft | byte-identical at 4 dp | accepted, 8 dp, max 4.000000 ft on magnitudes to 2000000 |
| survey40 (`91cc849675bd…`) | 4/4 | 6, 8, 10, 12 | 1.57e-06 ft / 1.57e-06 ft | byte-identical at 4 dp | accepted, 8 dp, max 0.042306 ft on magnitudes to 21153 |
| stateplane (`dfea76c9e761…`) | 4/4 | 4, 6, 8, 10 | 0.000157 ft / 0.000157 ft | byte-identical at 2 dp | accepted, 6 dp, max 13.009116 ft on magnitudes to 6504584 |

Reading: these cases matched the independent oracle and recovered the original bytes at the tested original precision. Deviations under auto precision are bounded (the exact values are in the JSON; leg 2 and leg 4 are close but not equal). The wrong-foot return is accepted by every check and differs by 2 ppm: arithmetic passes under an inappropriate declaration. Other sources of error — mapping, header interpretation, record selection, parsing, preservation, downstream import — are outside this loop.
