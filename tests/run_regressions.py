#!/usr/bin/env python3
"""Repair regressions for the v3.1 review findings (R1-R12) plus the 18 independent expected-output fixtures.
Usage: python3 run_regressions.py [path/to/pointfile_units.py] [workdir]. Asserts exit codes and exact bytes."""
import importlib.util, json, os, pathlib, subprocess, sys, tempfile
from fractions import Fraction
HERE = pathlib.Path(__file__).resolve().parent
TOOL = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else (HERE.parent / "pointfile_units.py" if (HERE.parent / "pointfile_units.py").exists() else HERE / "pointfile_units.py")
W = pathlib.Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else pathlib.Path(tempfile.mkdtemp(prefix="pfu-reg."))
spec = importlib.util.spec_from_file_location("pfu", TOOL); app = importlib.util.module_from_spec(spec); spec.loader.exec_module(app)
res = []; skipped = []
def check(name, ok, detail=""):
    res.append(ok); print(("PASS  " if ok else "FAIL  ") + name + (("  " + str(detail)[:160]) if detail and not ok else ""))
def cli(*args):
    p = subprocess.run([sys.executable, str(TOOL)] + list(args), capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout + p.stderr
def conv(name, src, fmt="ENZ", conversion="Custom", custom="1", extra=()):
    a = W / (name + ".src"); b = W / (name + ".out"); a.write_bytes(src)
    args = ["convert", "--in", str(a), "--out", str(b), "--format", fmt, "--conversion", conversion, "--delimiter", "whitespace", "--header", "no"]
    if conversion == "Custom": args += ["--custom-factor", custom]
    rc, out = cli(*args, *extra); return a, b, rc, out
S = {"format": "ENZ", "delimiter": "whitespace", "header": "no"}
# R1 verifier enforces exact rounding and lexical grammar
r = app.verify_bytes(b"1 2 3\n", b"1.4000 2.0000 3.0000\n", S, Fraction(1), 4); check("R1 wrong rounding rejected", not r["pass"] and any("nearest-ties-to-even" in f for f in r["failures"]))
r = app.verify_bytes(b"1 2 3\n", b"14000e-4 2.0000 3.0000\n", S, Fraction(1), 4); check("R1 non-fixed output rejected", not r["pass"])
r = app.verify_bytes(b"1 2 3\n", b"1.0000 2.0000 3.0000\n", S, Fraction(1), 4); check("R1 correct candidate accepted", r["pass"], r["failures"])
# R3 control validation
a, b, rc, out = conv("r3short", b"A 10 999 888\n", "PENZD", extra=["--control-point", "A 10 0"]); check("R3 short control refused", rc == 2 and "1 expected value" in out and not b.exists())
a, b, rc, out = conv("r3long", b"A 10 999 888\n", "PENZD", extra=["--control-point", "A 10 999 888 5 0"]); check("R3 extra value refused", rc == 2 and "4 expected value" in out)
a, b, rc, out = conv("r3dup", b"A 999 999 999\nA 10 20 30\n", "PENZD", extra=["--control-point", "A 10 20 30 0"]); check("R3 duplicate id refused", rc == 2 and "ambiguous" in out)
a, b, rc, out = conv("r3neg", b"A 10 20 30\n", "PENZD", extra=["--control-point", "A 10 20 30 -1"]); check("R3 negative tolerance refused", rc == 2 and "negative tolerance" in out)
a, b, rc, out = conv("r3ok", b"A 10 20 30\n", "PENZD", extra=["--control-point", "A 10 20 30 0"]); check("R3 full control passes and lists fields", rc == 0 and json.loads((W / "r3ok.out.manifest.json").read_text())["control_points"][0]["checked_fields"] == [1, 2, 3])
# R4/R6 standalone verify replays and rejects contradictions; accepts browser-style string factors
mp = W / "r3ok.out.manifest.json"; m = json.loads(mp.read_text())
rc, out = cli("verify", "--source", str(a), "--output", str(b), "--manifest", str(mp)); check("R4 verify pass lists rechecked claims", rc == 0 and "control point(s) from the manifest" in out)
m2 = dict(m); m2["control_points"] = [dict(m["control_points"][0], expected=["999", "999", "999"])]; (W / "m_ctl.json").write_text(json.dumps(m2))
rc, out = cli("verify", "--source", str(a), "--output", str(b), "--manifest", str(W / "m_ctl.json")); check("R4 mutated control display -> unsupported record", rc == 3 and "UNSUPPORTED" in out and "contradiction" in out)
m3 = json.loads(json.dumps(m)); m3["control_points"][0]["expected"] = ["999", "999", "999"]; m3["control_points"][0]["expected_exact"] = ["999", "999", "999"]; (W / "m_ctl2.json").write_text(json.dumps(m3))
rc, out = cli("verify", "--source", str(a), "--output", str(b), "--manifest", str(W / "m_ctl2.json")); check("R4 mutated control exact fails on replay", rc == 2 and "outside tolerance" in out)
m4 = json.loads(json.dumps(m)); m4["units"].update(conversion="MetersToIntlFeet", source_unit="m", target_unit="ft"); (W / "m_fac.json").write_text(json.dumps(m4))
rc, out = cli("verify", "--source", str(a), "--output", str(b), "--manifest", str(W / "m_fac.json")); check("R4 named factor contradiction refused", rc == 2 and "implies factor 1250/381" in out)
m5 = json.loads(json.dumps(m)); m5["units"]["factor_numerator"] = "1"; m5["units"]["factor_denominator"] = "1"; (W / "m_str.json").write_text(json.dumps(m5))
rc, out = cli("verify", "--source", str(a), "--output", str(b), "--manifest", str(W / "m_str.json")); check("R6 string factors accepted", rc == 0)
(W / "m_bad.json").write_text("{not json"); rc, out = cli("verify", "--source", str(a), "--output", str(b), "--manifest", str(W / "m_bad.json")); check("R4 malformed JSON -> UNSUPPORTED, no traceback", rc == 3 and "UNSUPPORTED" in out and "Traceback" not in out)
# R5 cleanup ownership
orig = app.exclusive_write; sentinel = W / "r5.out.manifest.json"
def contested(path, data):
    if pathlib.Path(path) == sentinel: sentinel.write_text("OTHER PROCESS DATA")
    return orig(path, data)
app.exclusive_write = contested
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    (W / "r5.src").write_bytes(b"1 2 3\n"); rc = app.main(["convert", "--in", str(W / "r5.src"), "--out", str(W / "r5.out"), "--format", "ENZ", "--conversion", "Custom", "--custom-factor", "1", "--header", "no"])
app.exclusive_write = orig
check("R5 competing sidecar left alone, own files removed, structured refusal", sentinel.exists() and sentinel.read_text() == "OTHER PROCESS DATA" and not (W / "r5.out").exists() and rc == 2 and "REFUSED" in buf.getvalue())
# R7 exact ranges
a, b, rc, out = conv("r7", b"9007199254740993 1 2\n"); m = json.loads((W / "r7.out.manifest.json").read_text()); check("R7 range report exact", m["ranges"]["0"] == ["9007199254740993.0000", "9007199254740993.0000"], m["ranges"])
# R10 run id depends on output and settings
a1, b1, _, _ = conv("r10a", b"1 2 3\n", custom="1"); a2, b2, _, _ = conv("r10b", b"1 2 3\n", custom="2")
ma = json.loads((W / "r10a.out.manifest.json").read_text()); mb = json.loads((W / "r10b.out.manifest.json").read_text()); check("R10 run ids differ by factor", ma["run_id"] != mb["run_id"])
# R11 / R12 precision search
a, b, rc, out = conv("r11", b"0.12345678901 1 2\n"); check("R11 11-dp source accepted on auto", rc == 0 and b.read_bytes().startswith(b"0.123456789010"))
a, b, rc, out = conv("r12", b"1 2 3\n", custom="1/3", extra=["--anchor", "0:0.33332:"]); check("R12 anchor passes after raising precision", rc == 0 and b.read_bytes().startswith(b"0.33333"))
a, b, rc, out = conv("r12b", b"1 2 3\n", custom="1/3", extra=["--anchor", "0:0.5:"]); check("R12 impossible anchor refused with accurate range message", rc == 2 and "every precision from" in out and "anchor field 0 failed" in out)
# R9 double BOM (second U+FEFF is content and must survive)
a, b, rc, out = conv("r9", b"\xef\xbb\xbf\xef\xbb\xbf# c\n1 2 3\n"); check("R9 stray U+FEFF refused by name, nothing written", rc == 2 and "U+FEFF" in out and not b.exists())
a, b, rc, out = conv("r9b", "1 2\u00a03\n".encode("utf-8")); check("R9 Unicode space is content, refused loudly", rc == 2 and "REFUSED" in out and not b.exists())
# N1 settings validator
a, b, rc, out = conv("n1a", b"1 10 20\n", "CUSTOM", custom="2", extra=["--coords", "0", "--id-field", "0"]); check("N1 identifier == coordinate refused", rc == 2 and "both the identifier and a coordinate" in out and not b.exists())
a, b, rc, out = conv("n1b", b"A 2 3\n", "CUSTOM", custom="2", extra=["--coords=-1"]); check("N1 negative index refused", rc == 2 and "nonnegative" in out)
a, b, rc, out = conv("n1c", b"A 2 3\n", "CUSTOM", extra=["--coords", "1", "--id-field", "99"]); check("N1 identifier beyond the row refused per row, no traceback", rc == 2 and "Traceback" not in out)
a, b, rc, out = conv("n1d", b"A 2 3\n", "CUSTOM", extra=["--coords", "1.5"]); check("N1 fractional index refused", rc == 2 and "nonnegative integers" in out)
# N4 malformed inputs are refusals, never tracebacks
a, b, rc, out = conv("n4a", b"1 2 3\n", custom="1/0"); check("N4 zero factor denominator refused", rc == 2 and "Traceback" not in out and "zero" in out)
a, b, rc, out = conv("n4ok", b"1 2 3\n"); mp = W / "n4ok.out.manifest.json"; base = json.loads(mp.read_text())
def mut(name, fn):
    m = json.loads(json.dumps(base)); fn(m); pth = W / (name + ".json"); pth.write_text(json.dumps(m)); return cli("verify", "--source", str(a), "--output", str(b), "--manifest", str(pth))
for name, fn, needle in [("null root", None, "root must be an object"), ("anchors null element", lambda m: m.update(anchors=[None]), "each anchor must be an object"),
                         ("zero denominator", lambda m: m["units"].update(factor_denominator="0"), "denominator is zero"),
                         ("null control coordinate", lambda m: m.update(control_points=[{"id": "A", "expected": [None, None, None], "expected_exact": [None, None, None], "tolerance": "0", "pass": True}]), "null expected value"),
                         ("bool decimals", lambda m: m["rounding"].update(decimals=True), "unsupported type bool")]:
    if fn is None:
        (W / "null.json").write_text("null"); rc, out = cli("verify", "--source", str(a), "--output", str(b), "--manifest", str(W / "null.json"))
    else:
        rc, out = mut(name.replace(" ", "_"), fn)
    check("N4 manifest %s -> explicit UNSUPPORTED outcome" % name, rc == 3 and "UNSUPPORTED" in out and "Traceback" not in out and needle in out, out[-200:])
# N3 consistency: custom_factor_input and recorded statistics must match observations
rc, out = mut("n3a", lambda m: m["units"].update(custom_factor_input="999")); check("N3 custom_factor_input contradiction refused", rc == 2 and "custom_factor_input" in out)
rc, out = mut("n3b", lambda m: m.update(counts={"data": 999999, "blank": 0, "header": 0, "comment": 0}, ranges={"0": ["999", "999"]}, max_error="999", content_fingerprint="0000000000000000")); check("N3 fabricated statistics refused", rc == 2 and "recorded counts" in out and "content_fingerprint" in out)
rc, out = cli("verify", "--source", str(a), "--output", str(b), "--manifest", str(mp)); check("N3 two verdicts printed on pass", rc == 0 and "fresh verification" in out and "internally consistent" in out)
# N6 ASCII digits only
a, b, rc, out = conv("n6", "\u0661 \u0662 \u0663\n".encode("utf-8")); check("N6 Unicode digits refused", rc == 2 and not b.exists())
# N7 fingerprint covers anchors; execution id unique
a1, b1, _, _ = conv("n7a", b"1 2 3\n", extra=["--anchor", "0:0:10"]); a2, b2, _, _ = conv("n7b", b"1 2 3\n", extra=["--anchor", "0:0:100"])
m1 = json.loads((W / "n7a.out.manifest.json").read_text()); m2 = json.loads((W / "n7b.out.manifest.json").read_text())
check("N7 fingerprint differs by anchor settings", m1["content_fingerprint"] != m2["content_fingerprint"] and m1["run_id"] != m2["run_id"] and m1["schema"] == "pointfile-units-report/3")
# N8 cleanup checks identity, not pathname
orig = app.exclusive_write; owned = W / "n8.out"; man = pathlib.Path(str(owned) + ".manifest.json")
def replace_then_fail(path, data):
    if pathlib.Path(path) == man:
        r = W / "other.tmp"; r.write_bytes(b"UNRELATED REPLACEMENT"); r.replace(owned); raise OSError("synthetic later write failure")
    return orig(path, data)
app.exclusive_write = replace_then_fail; (W / "n8.src").write_bytes(b"1 2 3\n")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    rc = app.main(["convert", "--in", str(W / "n8.src"), "--out", str(owned), "--format", "ENZ", "--conversion", "Custom", "--custom-factor", "1", "--header", "no"])
app.exclusive_write = orig
check("N8 replaced file at owned path left alone", owned.exists() and owned.read_bytes() == b"UNRELATED REPLACEMENT" and rc == 2)
# N9 auto precision finds a valid lower precision
a, b, rc, out = conv("n9", b"12345678901234567890123456789012345678 1 2\n"); check("N9 38-digit integer accepted on auto", rc == 0 and b.read_bytes().startswith(b"12345678901234567890123456789012345678"))
# ---- round 4 (review of v3.2) ----
a, b, rc, out = conv("q4base", b"A 1 2 3\n", "PENZD", extra=["--anchor", "1:0:10", "--control-point", "A 1 2 3 0"]); check("Q4 base run with anchor+control", rc == 0, out[-200:])
q4 = json.loads((W / "q4base.out.manifest.json").read_text(encoding="utf-8"))
def q4mut(name, fn):
    m = json.loads(json.dumps(q4)); fn(m); pth = W / ("q4_" + name + ".json"); pth.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8"); return cli("verify", "--source", str(a), "--output", str(b), "--manifest", str(pth))
for name, fn in [("anchor_observation", lambda m: m["anchors"][0].update(observed_min="999", observed_max="999")),
                 ("control_observation", lambda m: m["control_points"][0].update(written=["999", "999", "999"], line=999, checked_fields=[63])),
                 ("file_metadata", lambda m: (m["source"].update(bytes=999, encoding="utf-16"), m["output"].update(bytes=999, encoding="utf-16"))),
                 ("checks_and_failures", lambda m: (m["checks"].update(non_coordinate_preservation="fail"), m.update(failures=["Non-coordinate content changed."])))]:
    rc, out = q4mut(name, fn); check("Q4#2 %s mutation refused" % name, rc in (2, 3) and ("differs from observed" in out or "manifest:" in out) and "Traceback" not in out, out[-200:])
rc, out = q4mut("max_error_at_scalar", lambda m: m.update(max_error_at=1)); check("Q4#8 max_error_at scalar -> UNSUPPORTED, no traceback", rc == 3 and "Traceback" not in out and "max_error_at" in out)
rc, out = q4mut("tool_null", lambda m: m.update(tool=None)); check("Q4#8 tool null -> UNSUPPORTED, no traceback", rc == 3 and "Traceback" not in out)
rc, out = q4mut("unknown_key", lambda m: m.update(extra_field=1)); check("Q4 unknown top-level key -> UNSUPPORTED (schema 3 exact key set)", rc == 3 and "unknown top-level" in out)
def sorted_obj(o):
    if isinstance(o, dict): return {k: sorted_obj(o[k]) for k in sorted(o)}
    if isinstance(o, list): return [sorted_obj(x) for x in o]
    return o
rc, out = q4mut("sorted_keys", lambda m: m.update(sorted_obj(json.loads(json.dumps(m))))); check("Q4#3b key order does not change the verdict", rc == 0, out[-300:])
rc, out = q4mut("custom_input_1_1_999", lambda m: m["units"].update(custom_factor_input="1/1/999")); check("Q4#6 custom_factor_input 1/1/999 refused", rc == 2 and "custom_factor_input" in out)
# #7 lifecycle invariant: every successful conversion re-verifies with its own manifest at numeric boundaries
for name, src, factor, extra in [("q7a", b"1e-30 0 0\n", "1" + "0" * 39 + "e30", ["--decimals", "4"]), ("q7b", b"A 1e20 0 0\n", "1e20", ["--control-point", "A 10000000000e30 0 0 0"]), ("q7c", b"1 2 3\n", "1/3", [])]:
    fmt = "PENZD" if src.startswith(b"A ") else "ENZ"
    a2, b2, rc, out = conv(name, src, fmt, custom=factor, extra=extra)
    ok = rc == 0
    if ok: rc2, out2 = cli("verify", "--source", str(a2), "--output", str(b2), "--manifest", str(W / (name + ".out.manifest.json"))); ok = rc2 == 0
    check("Q4#7 lifecycle invariant %s: convert succeeds and its own manifest re-verifies" % name, ok, out[-200:] if rc else out2[-200:])
# #3 Unicode reference: Python manifest fingerprint must match the browser's canonical form (checked in the browser suite too)
a3, b3, rc, out = conv("q3uni", b"1 2 3\n", extra=["--source-unit-reference", "caf\u00e9 survey notes / \u6e2c\u91cf \U0001F600"]); check("Q4#3 Unicode reference converts", rc == 0, out[-200:])
rc, out = cli("verify", "--source", str(a3), "--output", str(b3), "--manifest", str(W / "q3uni.out.manifest.json")); check("Q4#3 Unicode manifest self-verifies in Python", rc == 0)
cf = json.loads((HERE / "canonical-fixtures.json").read_text(encoding="utf-8"))["cases"]; okc = all(app.canonical_json(c["input"]) == c["canonical"] for c in cf); check("Q4#3 canonical-form contract fixtures (%d)" % len(cf), okc)
# #4 cleanup reports retained paths accurately when removal fails (simulated: os.remove raises)
orig_rm = os.remove; orig_w = app.exclusive_write; side = W / "q4c.out.manifest.json"
def collide(path, data):
    if pathlib.Path(path) == side: side.write_text("OTHER")
    return orig_w(path, data)
def deny(p): raise PermissionError(32, "The process cannot access the file because it is being used by another process", str(p))
app.exclusive_write = collide; app.os.remove = deny; (W / "q4c.src").write_bytes(b"1 2 3\n"); buf = io.StringIO()
with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
    rc = app.main(["convert", "--in", str(W / "q4c.src"), "--out", str(W / "q4c.out"), "--format", "ENZ", "--conversion", "Custom", "--custom-factor", "1", "--header", "no"])
app.exclusive_write = orig_w; app.os.remove = orig_rm
check("Q4#4 failed removal is reported as RETAINED, not claimed removed", rc == 2 and "RETAINED" in buf.getvalue() and "were removed" not in buf.getvalue(), buf.getvalue()[-200:])
# #5 console: a stdout that cannot encode must not change the exit status
class Bad(io.StringIO):
    def write(self, t):
        if any(ord(ch) > 127 for ch in t): raise UnicodeEncodeError("charmap", t, 0, 1, "character maps to <undefined>")
        return super().write(t)
bad = Bad(); (W / "q5.src").write_bytes(b"1 2 3\n"); real = sys.stdout; sys.stdout = bad
try: rc = app.main(["convert", "--in", str(W / "q5.src"), "--out", str(W / "q5.out"), "--format", "ENZ", "--conversion", "Custom", "--custom-factor", "1", "--header", "no", "--source-unit-reference", "\u6e2c\u91cf notes"])
finally: sys.stdout = real
check("Q4#5 undisplayable console keeps exit 0 and says CONVERSION COMMITTED", rc == 0 and "CONVERSION COMMITTED" in bad.getvalue() and (W / "q5.out").exists())
# header default is explicit
a4, b4, rc, out = conv("q4hdr", b"bad bad bad\n1 2 3\n", custom="2"); check("Q4 default header policy is 'no': a bad first row is refused", rc == 2 and "line 1" in out)
# ---- round 5 (review of v3.3.1) ----
a, b, rc, out = conv("r5base", b"A 1 2 3\n", "PENZD", extra=["--anchor", "1:0:10", "--control-point", "A 1 2 3 0"]); r5 = json.loads((W / "r5base.out.manifest.json").read_text(encoding="utf-8"))
def r5mut(name, fn):
    m = json.loads(json.dumps(r5)); fn(m); pth = W / ("r5_" + name + ".json"); pth.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8"); return cli("verify", "--source", str(a), "--output", str(b), "--manifest", str(pth))
rc, out = r5mut("finest", lambda m: m["rounding"].update(finest_source_decimals=999)); check("R5-05 finest_source_decimals is an observation: mutation refused", rc == 2 and "finest_source_decimals" in out)
rc, out = r5mut("acceptance", lambda m: m["rounding"].update(acceptance="anything goes")); check("R5-05 acceptance prose contradiction -> unsupported", rc == 3 and "acceptance" in out)
rc, out = r5mut("comment", lambda m: m["grammar"].update(comment_prefix=";")); check("R5-05 comment_prefix ';' -> unsupported", rc == 3 and "comment_prefix" in out)
rc, out = r5mut("policy", lambda m: m["grammar"].update(identifier_policy="silently-renumber")); check("R5-05 unknown grammar key -> unsupported", rc == 3 and "unknown field" in out)
rc, out = r5mut("lower", lambda m: (m["source"].update(sha256=m["source"]["sha256"].upper()), m["output"].update(sha256=m["output"]["sha256"].upper()))); check("R5-07 hash spelling is case-insensitive", rc == 0)
m2 = json.loads(json.dumps(r5)); m2["schema"] = "pointfile-units-report/2"; m2["max_error_at"] = 1; (W / "r5_s2.json").write_text(json.dumps(m2)); rc, out = cli("verify", "--source", str(a), "--output", str(b), "--manifest", str(W / "r5_s2.json")); check("R5-07 schema-2 record with scalar max_error_at -> UNSUPPORTED, no traceback", rc == 3 and "Traceback" not in out)
rc, out = cli("verify", "--source", str(a), "--output", str(b), "--manifest", str(W / "r5base.out.manifest.json"), "--result", str(W / "r5.result.json")); rr = json.loads((W / "r5.result.json").read_text()); check("R5-07 verify prints producer/verifier builds and writes a re-verification record", rc == 0 and "producer build" in out and rr["schema"] == "pointfile-units-reverification/1" and rr["files_pass"] and rr["report_consistent"] and len(rr["record_file_sha256"]) == 64)
big_tol = "1" * 40 + "e30"; a5, b5, rc, out = conv("r5tol", b"A 1 2 3\n", "PENZD", extra=["--control-point", "A 1 2 3 " + big_tol]); ok5 = rc == 0
if ok5: rc2, out2 = cli("verify", "--source", str(a5), "--output", str(b5), "--manifest", str(W / "r5tol.out.manifest.json")); ok5 = rc2 == 0
check("R5-04 max entered tolerance (40 digits e30) converts and re-verifies", ok5, out[-200:] if rc else out2[-200:])
a6, b6, rc, out = conv("r5tol128", b"A 1 2 3\n", "PENZD", extra=["--control-point", "A 1 2 3 " + "1" * 128 + "e30"]); check("R5-04 128-digit entered tolerance refused at entry (uniform 40-digit entry limit)", rc == 2 and "40 digits" in out and not b6.exists())
a7, b7, rc, out = conv("r5anc", b"1 2 3\n", extra=["--anchor", "0:" + "1" * 40 + "e30:"]); check("R5-04 max entered anchor bound converts (or refuses) without a later replay failure", rc in (0, 2) and (rc == 2 or cli("verify", "--source", str(a7), "--output", str(b7), "--manifest", str(W / "r5anc.out.manifest.json"))[0] == 0))
# ---- round 6 (review of v3.3.2) ----
import hashlib, shutil
a, b, rc, out = conv("r6base", b"A 1 2 3\n", "PENZD", extra=["--anchor", "1:0:10", "--control-point", "A 1 2 3 0"]); mp6 = W / "r6base.out.manifest.json"
def hashes(*ps): return [hashlib.sha256(pathlib.Path(x).read_bytes()).hexdigest() if pathlib.Path(x).exists() else None for x in ps]
# R6-01: --result may never alias an input or an existing file, under any spelling; verdict stands, exit 4
before = hashes(a, b, mp6)
for label, dest in [("source", str(a)), ("output", str(b)), ("manifest", str(mp6)), ("relative spelling", os.path.relpath(str(mp6), os.getcwd())), ("case variant", os.path.join(os.path.dirname(str(mp6)), os.path.basename(str(mp6)).upper()))]:
    # Ask the filesystem itself, BEFORE the run, whether this spelling already names the manifest. os.path.normcase only
    # folds case on Windows, so it wrongly treats case-insensitive macOS (APFS/HFS+ default) as case-sensitive.
    alias_of_manifest = os.path.exists(dest) and os.path.samefile(dest, str(mp6))
    rc, out = cli("verify", "--source", str(a), "--output", str(b), "--manifest", str(mp6), "--result", dest)
    same = hashes(a, b, mp6) == before
    refused_ok = rc == 4 and "RESULT NOT WRITTEN" in out and "VERIFY PASS" in out
    if label == "case variant":
        if not alias_of_manifest:
            # case-sensitive filesystem: the upper-case spelling is a genuinely different path -> a fresh result file is created there, inputs unchanged
            check("R6-01 --result case variant on a case-sensitive filesystem: new file created, inputs unchanged, exit 0", same and rc == 0 and pathlib.Path(dest).exists() and pathlib.Path(dest).stat().st_size > 100, out[-160:])
        else:
            check("R6-01 --result case variant on a case-insensitive filesystem: refused, inputs unchanged, exit 4", same and refused_ok, out[-160:])
        continue
    check("R6-01 --result aliasing the %s: inputs unchanged, verdict stands, exit 4" % label, same and refused_ok, out[-160:])
pre = W / "r6_existing.json"; pre.write_text("PRE-EXISTING"); rc, out = cli("verify", "--source", str(a), "--output", str(b), "--manifest", str(mp6), "--result", str(pre)); check("R6-01 existing destination refused, untouched", rc == 4 and pre.read_text() == "PRE-EXISTING")
for label, mk in [("symlink", lambda t: os.symlink(str(mp6), t)), ("hard link", lambda t: os.link(str(mp6), t))]:
    t = W / ("r6_" + label.replace(" ", "") + ".json")
    try: mk(str(t))
    except (OSError, NotImplementedError): print("SKIP  R6-01 %s alias (link creation unsupported on this filesystem)" % label); skipped.append("R6-01 %s alias" % label); continue
    rc, out = cli("verify", "--source", str(a), "--output", str(b), "--manifest", str(mp6), "--result", str(t)); check("R6-01 %s alias of the manifest refused, manifest unchanged" % label, rc == 4 and hashes(mp6) == before[2:3], out[-160:])
orig_open = app.os.open
def appear(path, flags, *rest):
    if str(path).endswith("r6_race.json"): pathlib.Path(path).write_text("APPEARED"); 
    return orig_open(path, flags, *rest)
app.os.open = appear; buf = io.StringIO()
with contextlib.redirect_stdout(buf): rc = app.main(["verify", "--source", str(a), "--output", str(b), "--manifest", str(mp6), "--result", str(W / "r6_race.json")])
app.os.open = orig_open
check("R6-01 destination created after the precheck: exclusive create refuses, file kept as found", rc == 4 and (W / "r6_race.json").read_text() == "APPEARED" and "appeared between" in buf.getvalue())
rc, out = cli("verify", "--source", str(a), "--output", str(b), "--manifest", str(mp6), "--result", str(W / "r6_fresh.json")); fresh = json.loads((W / "r6_fresh.json").read_text()); check("R6-01 fresh destination gets the complete record; verification without --result stays read-only", rc == 0 and fresh["files_pass"] and hashes(a, b, mp6) == before)
# R6-03: the file digest is of the bytes received; whitespace changes it; canonical digest is stable and named
(W / "r6_pretty.json").write_text(json.dumps(json.loads(mp6.read_text()), indent=2)); (W / "r6_compact.json").write_text(json.dumps(json.loads(mp6.read_text()), separators=(",", ":")))
r63 = []
for st_ in ("pretty", "compact"):
    rc, out = cli("verify", "--source", str(a), "--output", str(b), "--manifest", str(W / ("r6_%s.json" % st_)), "--result", str(W / ("r6_%s.result.json" % st_))); r63.append(json.loads((W / ("r6_%s.result.json" % st_)).read_text()))
check("R6-03 record_file_sha256 equals sha256 of the received file; differs between spellings; canonical digest equal and named", r63[0]["record_file_sha256"] == hashlib.sha256((W / "r6_pretty.json").read_bytes()).hexdigest() and r63[1]["record_file_sha256"] == hashlib.sha256((W / "r6_compact.json").read_bytes()).hexdigest() and r63[0]["record_file_sha256"] != r63[1]["record_file_sha256"] and r63[0]["record_canonical_sha256"] == r63[1]["record_canonical_sha256"] and r63[0]["record_canonicalization"] == "canonical-json/1")
# R6-02: immutable historical records replay through named adapters
for d, names in [("v3.3.1-python", ["base", "cross-unicode"])]:
    for nm in names:
        base_p = HERE / "legacy-records" / d / nm
        rc, out = cli("verify", "--source", str(base_p) + ".src", "--output", str(base_p) + ".out", "--manifest", str(base_p) + ".out.manifest.json", "--result", str(W / ("r6_legacy_%s.json" % nm))); lr = json.loads((W / ("r6_legacy_%s.json" % nm)).read_text())
        check("R6-02 immutable %s/%s record verifies via a named adapter" % (d, nm), rc == 0 and lr["adapter"] and "legacy adapter A" in lr["adapter"] and hashlib.sha256((pathlib.Path(str(base_p) + ".out.manifest.json")).read_bytes()).hexdigest() == lr["record_file_sha256"], out[-200:])
for d, nm, want_adapter, want_note in [("v3.2.0-browser", "cross", "legacy adapter A", "legacy spelling"), ("v3.1.0-browser", "record", None, "adapter"), ("v3.3.2-python-handoff", "handoff", None, None)]:
    bp = HERE / "legacy-records" / d / nm; rc, out = cli("verify", "--source", str(bp) + ".src", "--output", str(bp) + ".out", "--manifest", str(bp) + ".out.manifest.json")
    check("R6-02 immutable %s/%s record verifies%s" % (d, nm, (" via " + want_adapter) if want_adapter else ""), rc == 0 and (want_adapter is None or want_adapter in out) and (want_note is None or want_note in out), out[-220:])
rc, out = q4mut("r6_acc", lambda m: m["rounding"].update(acceptance="some other sentence")); check("R6-02 unknown acceptance text stays unsupported", rc == 3)
# R6-04: exact nested shapes, typed traceability, bounds, duplicate keys
for name, fn, needle in [("anchor unknown key", lambda m: m["anchors"][0].update(unimplemented_selector="first-match"), "unknown field(s) in anchor"), ("control unknown key", lambda m: m["control_points"][0].update(unimplemented_selector="first-match"), "unknown field(s) in control point"),
                         ("source.path object", lambda m: m["source"].update(path={"not": "a filename"}), "source.path"), ("source.path missing", lambda m: m["source"].pop("path"), "missing field(s) in source"),
                         ("100000-char reference", lambda m: m["units"].update(source_unit_reference="X" * 100000), "longer than 2000")]:
    mm = json.loads(mp6.read_text()); fn(mm); mm["content_fingerprint"] = app.content_fingerprint(mm) if "path" in mm["source"] else mm["content_fingerprint"]; pth = W / ("r6_" + name.replace(" ", "_").replace(".", "_") + ".json"); pth.write_text(json.dumps(mm)); rc, out = cli("verify", "--source", str(a), "--output", str(b), "--manifest", str(pth))
    check("R6-04 %s -> UNSUPPORTED" % name, rc == 3 and needle in out, out[-160:])
dup = mp6.read_text().replace('"schema":', '"schema": "x", "schema":', 1); (W / "r6_dup.json").write_text(dup); rc, out = cli("verify", "--source", str(a), "--output", str(b), "--manifest", str(W / "r6_dup.json")); check("R6-04 duplicate key -> UNSUPPORTED", rc == 3 and "duplicate key" in out)
deep = json.loads(mp6.read_text()); x = deep; 
for i in range(12): x["warnings"] = x.get("warnings", []); x = {"a": x} if i else x
nested = json.loads(mp6.read_text()); nested["ranges"]["1"] = [[[[[[[[[["x"]]]]]]]]]]; (W / "r6_deep.json").write_text(json.dumps(nested)); rc, out = cli("verify", "--source", str(a), "--output", str(b), "--manifest", str(W / "r6_deep.json")); check("R6-04 nesting deeper than 8 -> UNSUPPORTED", rc == 3 and "nesting deeper" in out, out[-160:])
# ---- round 7 (review of v3.3.3) ----
for name, val in [("toString", "toString"), ("constructor", "constructor"), ("__proto__", "__proto__"), ("object", {}), ("array", []), ("null", None), ("boolean", True), ("number", 1)]:
    rc, out = q4mut("r7_acc_" + name, lambda m, v=val: m["rounding"].update(acceptance=v)); check("R7-01 acceptance %s -> UNSUPPORTED, no traceback" % name, rc == 3 and "Traceback" not in out, out[-160:])
for label, ch in [("ASCII", "x"), ("BMP", "\u6e2c"), ("astral", "\U0001F4CD")]:
    for n, want in [(1999, 0), (2000, 0), (2001, 3)]:
        rc, out = q4mut("r7_ref_%s_%d" % (label, n), lambda m, t=ch * n: (m["units"].update(source_unit_reference=t), m.update(content_fingerprint=app.content_fingerprint(m)))); check("R7-04 %s reference of %d scalar values -> exit %d" % (label, n, want), rc == want, out[-120:])
mlone = json.loads(json.dumps(q4)); mlone["units"]["source_unit_reference"] = "ok\ud800"; (W / "r7_lone.json").write_text(json.dumps(mlone, ensure_ascii=True), encoding="utf-8"); rc, out = cli("verify", "--source", str(a), "--output", str(b), "--manifest", str(W / "r7_lone.json")); check("R7-04 lone surrogate (JSON \\ud800 escape) in a reference -> UNSUPPORTED", rc == 3 and "surrogate" in out, out[-160:])
# R7-05: publication I/O failures are exit 4 with the verdict retained; inputs untouched; no partial artifact
rc, out = cli("verify", "--source", str(a), "--output", str(b), "--manifest", str(mp6), "--result", str(W / "does-not-exist" / "r.json")); check("R7-05 missing parent -> VERIFY PASS then exit 4, not 2", rc == 4 and "VERIFY PASS" in out and "RESULT NOT WRITTEN" in out and "could not be created" in out and hashes(a, b, mp6) == before)
orig_open2 = app.os.open
def deny_open(path, flags, *rest):
    if str(path).endswith("r7_perm.json"): raise PermissionError(13, "Permission denied", str(path))
    return orig_open2(path, flags, *rest)
app.os.open = deny_open; buf = io.StringIO()
with contextlib.redirect_stdout(buf): rc = app.main(["verify", "--source", str(a), "--output", str(b), "--manifest", str(mp6), "--result", str(W / "r7_perm.json")])
app.os.open = orig_open2
check("R7-05 permission denied at create -> exit 4, verdict retained, nothing written", rc == 4 and "VERIFY PASS" in buf.getvalue() and "PermissionError" in buf.getvalue() and not (W / "r7_perm.json").exists())
import builtins
orig_fdopen = app.os.fdopen
class BadFH:
    def __init__(self, fh): self.fh = fh
    def write(self, d): raise OSError(28, "No space left on device")
    def flush(self): pass
    def fileno(self): return self.fh.fileno()
    def __enter__(self): return self
    def __exit__(self, *x): self.fh.close()
def bad_fdopen(fd, mode="r", *rest, **kw):
    fh = orig_fdopen(fd, mode, *rest, **kw); return BadFH(fh)
app.os.fdopen = bad_fdopen; buf = io.StringIO()
with contextlib.redirect_stdout(buf): rc = app.main(["verify", "--source", str(a), "--output", str(b), "--manifest", str(mp6), "--result", str(W / "r7_write.json")])
app.os.fdopen = orig_fdopen
check("R7-05 write failure -> exit 4, partial file removed and reported, inputs unchanged", rc == 4 and "could not be written completely" in buf.getvalue() and "was removed" in buf.getvalue() and not (W / "r7_write.json").exists() and hashes(a, b, mp6) == before)
v2 = json.loads((HERE / "canonical-v2-fixtures.json").read_text(encoding="utf-8"))
ok2 = all(app.canonical_json_v2(c["input"]) == c["canonical"] for c in v2["cases"])
ref2 = True
for c in v2["refused"]:
    try: app.canonical_json_v2(json.loads(c["input_json"])); ref2 = False
    except app.Refuse: pass
check("R5-06 canonical-json/2 candidate: %d fixtures reproduce, %d refusals refuse" % (len(v2["cases"]), len(v2["refused"])), ok2 and ref2)
# independent expected outputs from both external reviewers (Decimal oracle, 160 digits, ties to even)
fx = json.loads((HERE / "independent-expected-outputs.json").read_text())["cases"] + json.loads((HERE / "independent-expected-outputs-2.json").read_text())["cases"]; ok = 0
for i, c in enumerate(fx):
    a = W / ("ind%d.src" % i); b = W / ("ind%d.out" % i); a.write_text(c["source"], newline="")
    rc, out = cli("convert", "--in", str(a), "--out", str(b), "--format", "ENZ", "--conversion", c["conversion"], "--decimals", str(c["decimals"]), "--header", "no")
    if rc == 0 and b.read_text() == c["expected"]: ok += 1
check("independent oracle fixtures exact, both reviewers (%d/%d)" % (ok, len(fx)), ok == len(fx))
print("regressions: passed %d failed %d skipped %d%s" % (sum(res), len(res) - sum(res), len(skipped), ("  (" + "; ".join(skipped) + ")") if skipped else "")); sys.exit(0 if all(res) else 1)
