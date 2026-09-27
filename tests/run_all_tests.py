#!/usr/bin/env python3
"""One command for the whole suite, no shell required (Windows-friendly).
Runs: fixture generation, the 30 baseline CLI assertions (same cases as run_python_tests.sh), the repair regressions,
and the browser suite if Playwright is installed. Exit 0 only when everything that ran passed."""
import os, pathlib, re, shlex, subprocess, sys, tempfile
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent if (HERE.parent / "pointfile_units.py").exists() else HERE
TOOL = ROOT / "pointfile_units.py"
W = pathlib.Path(tempfile.mkdtemp(prefix="pfu-all."))
subprocess.run([sys.executable, str(HERE / "make_fixtures.py")], cwd=W, check=True, capture_output=True)
pass_ = fail = 0
def run(args):
    p = subprocess.run([sys.executable, str(TOOL)] + args, cwd=W, capture_output=True, text=True, encoding="utf-8"); return p.returncode, p.stdout + p.stderr
print("== baseline assertions (from run_python_tests.sh) ==")
for line in (HERE / "run_python_tests.sh").read_text(encoding="utf-8").splitlines():
    if line.startswith("cp penzd_m.txt tampered.txt;"):
        raw = (W / "penzd_m.txt").read_bytes().splitlines(keepends=True); raw[2] = raw[2].replace(b'"GRND"', b'"GRNX"'); (W / "tampered.txt").write_bytes(b"".join(raw)); continue
    if not line.startswith("expect "): continue
    parts = shlex.split(line); name, want, args = parts[1], parts[2], parts[3:]
    wantrc = 0 if want in ("checks passed", "VERIFY PASS", "Control point 6 : pass") else 2
    rc, out = run(args); ok = want in out and rc == wantrc
    pass_ += ok; fail += (not ok); print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else "  (exit %d)" % rc))
# the four shell-tool checks from run_python_tests.sh, in Python
from decimal import Decimal
def extra(name, ok):
    global pass_, fail
    pass_ += ok; fail += (not ok); print(("PASS  " if ok else "FAIL  ") + name)
try:
    a = [l.split()[1:4] for l in (W / "penzd.txt").read_text().splitlines()]; b = [l.split()[1:4] for l in (W / "penzd_back.txt").read_text().splitlines()]
    extra("T2 source reconstructed at 4 dp", all("%.4f" % Decimal(x) == "%.4f" % Decimal(y) for ra, rb in zip(a, b) for x, y in zip(ra, rb)))
except OSError: extra("T2 source reconstructed at 4 dp", False)
extra("3.8 value preserved", (W / "e.txt").exists() and (W / "e.txt").read_bytes().startswith(b"9007199254740993.0000"))
extra("3.7 non-numeric bytes identical", (W / "g.txt").exists() and (W / "mixednl.txt").read_bytes().translate(None, b"0123456789.") == (W / "g.txt").read_bytes().translate(None, b"0123456789."))
extra("bom bytes", (W / "bom_m.txt").exists() and (W / "bom_m.txt").read_bytes().startswith(b"\xef\xbb\xbf"))
print("baseline: passed %d failed %d" % (pass_, fail))
print("== repair regressions ==")
rg = subprocess.run([sys.executable, str(HERE / "run_regressions.py"), str(TOOL), str(W)]); rgok = rg.returncode == 0
print("== browser suite ==")
if '--skip-browser' in sys.argv:
    if '--require-browser' in sys.argv:
        raise SystemExit('--skip-browser and --require-browser cannot be combined')
    bran = False; brok = True
    print('browser suite deliberately skipped: core-only check, not full release acceptance')
else:
    try:
        import playwright  # noqa
        br = subprocess.run([sys.executable, str(HERE / "run_browser_tests.py")]); brok = br.returncode == 0; bran = True
    except ImportError:
        bran = False
        if "--require-browser" in sys.argv:
            print("playwright not installed: browser suite REQUIRED but unavailable -> FAIL (pip install playwright && playwright install chromium)"); brok = False
        else:
            print("playwright not installed: browser suite skipped (partial developer check; a release requires it)"); brok = True
# ---- differential gate and adapter vectors (round 9) ----
import shutil
DIFF = HERE / "differential"; pt_html = os.environ.get("PT_HTML") or (str(DIFF / "PointTruth.html") if (DIFF / "PointTruth.html").exists() else None)
avok = subprocess.run([sys.executable, str(DIFF / "run_adapter_vectors.py")], env=dict(os.environ, **({"PT_HTML": pt_html} if pt_html else {}))).returncode == 0
print("adapter vectors:", "pass" if avok else "FAIL")
print("== utility failure controls (synthetic drivers; no browser) ==")
utok = subprocess.run([sys.executable, str(HERE / "test_utility_repairs.py")]).returncode == 0
print("utility failure controls:", "pass" if utok else "FAIL")
bpok = subprocess.run([sys.executable, str(HERE / "test_browser_paths.py")]).returncode == 0
print("browser path check (executed, with negative controls):", "pass" if bpok else "FAIL")
crok = subprocess.run([sys.executable, str(HERE / "test_consumer_release.py")]).returncode == 0
print("consumer release (members, identity, reproducible, refusal, native bytes):", "pass" if crok else "FAIL")
exok = subprocess.run([sys.executable, str(HERE / "test_exposure_scan.py")]).returncode == 0
print("exposure scanner (plain, escaped, slash forms; masking):", "pass" if exok else "FAIL")
eaok = subprocess.run([sys.executable, str(HERE / "test_evidence_archives.py")]).returncode == 0
print("evidence archives (excluded from candidates, listed with hashes):", "pass" if eaok else "FAIL")
cdok = subprocess.run([sys.executable, str(HERE / "test_candidate_determinism.py")]).returncode == 0
print("candidate determinism (times, permissions, platform, time zone):", "pass" if cdok else "FAIL")
piok = subprocess.run([sys.executable, str(HERE / "test_payload_identity.py")]).returncode == 0
print("payload identity contract (pinned reference, mutations, equivalence, comparison):", "pass" if piok else "FAIL")
ppok = subprocess.run([sys.executable, str(HERE / "test_public_profile.py")]).returncode == 0
print("public profile (private areas absent and not required):", "pass" if ppok else "FAIL")
rtok = subprocess.run([sys.executable, str(HERE / "roundtrip" / "roundtrip_cli.py")]).returncode == 0 and subprocess.run([sys.executable, str(HERE / "roundtrip" / "roundtrip_cli.py"), "--self-test"]).returncode == 0; print("round-trip gate (with mutation proof):", "pass" if rtok else "FAIL")
if pt_html:
    if pt_html != str(DIFF / "PointTruth.html"): shutil.copyfile(pt_html, DIFF / "PointTruth.html")
    steps = [[sys.executable, "corpus.py"], ["node", "run_pt.cjs"], [sys.executable, "run_py.py"], [sys.executable, "compare.py"], [sys.executable, "compare.py", "--self-test"]]
    dfok = all(subprocess.run(c, cwd=DIFF).returncode == 0 for c in steps); print("differential gate (with mutation proof):", "pass" if dfok else "FAIL")
else:
    dfok = "--require-browser" not in sys.argv; print("differential gate: SKIPPED (no PointTruth.html; set PT_HTML)" + ("" if dfok else " -> FAIL: required for a release"))
print("\nSUMMARY: baseline %d/%d; regressions %s; round-trip %s; adapter vectors %s; differential %s; browser %s" % (pass_, pass_ + fail, "pass" if rgok else "FAIL", "pass" if rtok else "FAIL", "pass" if avok else "FAIL", ("pass" if dfok else "FAIL") if pt_html else "skipped", ("pass" if brok else "FAIL") if bran else ("skipped (FAIL: required)" if "--require-browser" in sys.argv else "skipped")))
sys.exit(0 if fail == 0 and rgok and brok and avok and dfok and rtok and utok and bpok and crok and exok and eaok and cdok and piok and ppok else 1)
