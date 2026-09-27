#!/usr/bin/env bash
# Runs the v3 Python engine through the audit reproductions and the original matrix.
# Usage: cd tests && bash run_python_tests.sh   (needs python3; writes into ./work)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$HERE/../pointfile_units.py" ]; then TOOL="$HERE/../pointfile_units.py"; elif [ -f "$HERE/pointfile_units.py" ]; then TOOL="$HERE/pointfile_units.py"; else echo "pointfile_units.py not found next to or above $HERE" >&2; exit 3; fi
W="$(mktemp -d "${TMPDIR:-/tmp}/pfu-tests.XXXXXX")"; trap 'rm -rf "$W"' EXIT
cd "$W" || exit 3
python3 "$HERE/make_fixtures.py" >/dev/null
P=(python3 "$TOOL"); pass=0; fail=0
# expect NAME WANT ARGS...  : output must contain WANT; exit status must be 0 when WANT is a pass phrase, 2 when it is a refusal
expect(){ local name="$1" want="$2"; shift 2; local out rc=0; out=$("${P[@]}" "$@" 2>&1) || rc=$?
  local wantrc=0; case "$want" in "checks passed"|"VERIFY PASS"|"Control point 6 : pass") wantrc=0;; *) wantrc=2;; esac
  # substring test, not a pipe: grep -q under pipefail can fail after matching (echo gets SIGPIPE)
  if [[ "$out" == *"$want"* ]] && [ "$rc" -eq "$wantrc" ]; then echo "PASS  $name"; pass=$((pass+1)); else echo "FAIL  $name (exit $rc, wanted $wantrc)"; echo "$out" | head -4 | sed 's/^/      /'; fail=$((fail+1)); fi; }
expect "T1 PENZD ft->m passes"            "checks passed" convert --in penzd.txt --out penzd_m.txt --format PENZD --conversion IntlFeetToMeters
expect "T2 round trip m->ft passes"       "checks passed" convert --in penzd_m.txt --out penzd_back.txt --format PENZD --conversion MetersToIntlFeet
if diff <(awk '{printf "%.4f %.4f %.4f\n",$2,$3,$4}' penzd.txt) <(awk '{printf "%.4f %.4f %.4f\n",$2,$3,$4}' penzd_back.txt) >/dev/null; then echo "PASS  T2 source reconstructed at 4 dp"; pass=$((pass+1)); else echo "FAIL  T2 reconstruction"; fail=$((fail+1)); fi
expect "3.1 non-finite refused"           "exponent exceeds" convert --in nonfinite.txt --out a.txt --format ENZ --conversion IntlFeetToMeters
expect "3.2 sci notation keeps precision" "checks passed" convert --in sci.txt --out b.txt --format ENZ --conversion IntlFeetToMeters
expect "3.3 one bad row refused"          "line 100: field 2 is not numeric" convert --in onebad.txt --out c.txt --format PENZD --conversion IntlFeetToMeters
expect "3.4 gapped ids with explicit PENZD" "checks passed" convert --in gapped.txt --out d.txt --format PENZD --conversion IntlFeetToMeters
expect "3.8 big integer exact"            "checks passed" convert --in bigint.txt --out e.txt --format ENZ --conversion Custom --custom-factor 1
grep -q '^9007199254740993.0000' e.txt && { echo "PASS  3.8 value preserved"; pass=$((pass+1)); } || { echo "FAIL  3.8 value"; fail=$((fail+1)); }
expect "3.6 custom x2"                    "checks passed" convert --in gapped.txt --out f.txt --format PENZD --conversion Custom --custom-factor 2
expect "3.6 exact reciprocal 1/2"         "checks passed" convert --in f.txt --out f_back.txt --format PENZD --conversion Custom --custom-factor 1/2
expect "3.7 mixed newlines preserved"     "checks passed" convert --in mixednl.txt --out g.txt --format PENZD --conversion IntlFeetToMeters
cmp <(tr -d '0-9.' < mixednl.txt) <(tr -d '0-9.' < g.txt) >/dev/null && { echo "PASS  3.7 non-numeric bytes identical"; pass=$((pass+1)); } || { echo "FAIL  3.7 bytes"; fail=$((fail+1)); }
expect "3.7 spaces preserved"             "checks passed" convert --in spaces.txt --out h.txt --format PENZD --conversion IntlFeetToMeters
expect "3.7 latin-1 refused"              "not valid UTF-8" convert --in latin1.txt --out i.txt --format PENZD --conversion IntlFeetToMeters
expect "4.6 quoted csv"                   "checks passed" convert --in quoted.csv --out j.csv --format PENZD --conversion IntlFeetToMeters
expect "4.5 decimal comma (ws) refused"   "REFUSED" convert --in deccomma.txt --out k.txt --format PENZD --conversion IntlFeetToMeters
expect "4.5 decimal comma (csv) refused"  "found 8" convert --in deccomma2.csv --out l.csv --format PENZD --conversion IntlFeetToMeters
expect "integer coordinates need --force-mapping" "mapping warning" convert --in intcoords.txt --out m.txt --format ENZ --conversion IntlFeetToMeters
expect "tie at 0 decimals refused"        "verification failed" convert --in tie.txt --out n.txt --format PENZD --conversion Custom --custom-factor 1 --decimals 0
expect "negatives"                        "checks passed" convert --in neg.txt --out o.txt --format PENZD --conversion Custom --custom-factor 1
expect "anchor miss refused"              "anchor field 3 failed" convert --in penzd.txt --out p.txt --format PENZD --conversion IntlFeetToMeters --anchor 3:0:20
expect "control point pass"               "Control point 6 : pass" convert --in penzd.txt --out q.txt --format PENZD --conversion IntlFeetToMeters --control-point "6 6065.5576 6187.6131 30.48 0.001"
expect "output == source refused"         "output path is the source" convert --in penzd.txt --out penzd.txt --format PENZD --conversion IntlFeetToMeters
expect "existing output refused"          "already exists" convert --in penzd.txt --out penzd_m.txt --format PENZD --conversion IntlFeetToMeters
expect "csv header auto (explicit opt-in)" "checks passed" convert --in lf.csv --out lf_ft.csv --format ENZ --conversion MetersToIntlFeet --header auto
expect "bom preserved"                    "checks passed" convert --in bom.txt --out bom_m.txt --format PENZD --conversion IntlFeetToMeters
head -c3 bom_m.txt | od -An -tx1 | grep -q "ef bb bf" && { echo "PASS  bom bytes"; pass=$((pass+1)); } || { echo "FAIL  bom bytes"; fail=$((fail+1)); }
expect "verify subcommand pass"           "VERIFY PASS" verify --source penzd.txt --output penzd_m.txt --manifest penzd_m.txt.manifest.json
cp penzd_m.txt tampered.txt; sed -i '3s/"GRND"/"GRNX"/' tampered.txt
expect "verify detects tampering"         "bytes outside coordinate fields changed" verify --source penzd.txt --output tampered.txt --manifest penzd_m.txt.manifest.json
echo "== repair regressions (exact outputs, exit codes) =="
rg=0; python3 "$HERE/run_regressions.py" "$TOOL" "$W" || rg=1
echo; echo "baseline assertions: passed $pass failed $fail   (repair regressions reported above, counted separately)"; [ "$fail" -eq 0 ] && [ "$rg" -eq 0 ]
