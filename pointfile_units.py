#!/usr/bin/env python3
"""
pointfile_units.py  -  exact-arithmetic unit conversion for survey point files (v3.3.8)

Guarantee (scope-honest):
  The tool converts explicitly selected coordinate fields using explicitly confirmed units.
  It calculates with exact rational arithmetic, rounds by a declared policy (nearest, ties to even),
  and verifies the serialized candidate bytes against the original source with an independent verifier.
  It rejects unexpected data rows and unsupported representations.
  Passing checks establishes arithmetic fidelity and the declared preservation properties.
  Source units, column meaning, coordinate reference, and survey suitability need independent confirmation.

Standard library only. Python 3.8+.

  convert  --in FILE --out FILE --format PENZD --conversion IntlFeetToMeters [options]
  verify   --source FILE --output FILE --manifest FILE.manifest.json
"""
import argparse, hashlib, json, os, re, sys, datetime
from fractions import Fraction

VERSION = "3.3.8"
MAX_DIGITS = 40          # digits in one numeric token
MAX_EXP = 30             # |exponent| in one numeric token
MAX_DECIMALS = 12        # written decimals ceiling
MAX_EXPANDED_DIGITS = 128  # written tokens, manifest rationals, control/anchor values: anything derived from a 40-digit mantissa,
                           # a +/-30 exponent, a 40/40-digit factor and up to 12 written decimals fits well inside this
MAX_OUT_DIGITS = MAX_EXPANDED_DIGITS
MIN_DECIMALS = 4
MAX_FILE_BYTES = 256 * 1024 * 1024
WS = " \t\r\n\x0b\x0c"          # whitespace is ASCII only; Unicode spaces and U+FEFF are content

# ----------------------------------------------------------------------------- units
FACTORS = {
    "IntlFeetToMeters": (Fraction(381, 1250), "ft", "m"),
    "MetersToIntlFeet": (Fraction(1250, 381), "m", "ft"),
    "USFeetToMeters":   (Fraction(1200, 3937), "usft", "m"),
    "MetersToUSFeet":   (Fraction(3937, 1200), "m", "usft"),
    "USFeetToIntlFeet": (Fraction(1200, 3937) / Fraction(381, 1250), "usft", "ft"),
    "IntlFeetToUSFeet": (Fraction(381, 1250) / Fraction(1200, 3937), "ft", "usft"),
}
FORMATS = {   # coords = zero-based field indexes scaled; id = identifier field or None; min/max field counts
    "PENZD": {"coords": [1, 2, 3], "id": 0, "min": 4, "max": 5},
    "PNEZD": {"coords": [1, 2, 3], "id": 0, "min": 4, "max": 5},
    "ENZ":   {"coords": [0, 1, 2], "id": None, "min": 3, "max": 4},
    "NEZ":   {"coords": [0, 1, 2], "id": None, "min": 3, "max": 4},
    "XYZ":   {"coords": [0, 1, 2], "id": None, "min": 3, "max": 4},
}
TOKEN_RE = re.compile(r'^([+-]?)([0-9]*)(?:\.([0-9]*))?(?:[eE]([+-]?[0-9]+))?$')   # ASCII digits only (N6); Unicode digits are content


class Refuse(Exception):
    pass


def parse_token(s, max_digits=MAX_DIGITS):
    """Exact parse. Returns (Fraction, quantum_exponent) or None if not numeric syntax. Raises Refuse on limits."""
    m = TOKEN_RE.match(s)
    if not m:
        return None
    sign, ip, fp, ex = m.groups()
    fp = fp or ""
    if ip == "" and fp == "":
        return None
    if len(ip) + len(fp) > max_digits:
        raise Refuse("numeric token exceeds %d digits: %s" % (max_digits, s[:50]))
    e = int(ex) if ex else 0
    if abs(e) > MAX_EXP:
        raise Refuse("numeric token exponent exceeds +/-%d: %s" % (MAX_EXP, s))
    qexp = e - len(fp)
    val = Fraction(int((ip or "0") + fp)) * (Fraction(10) ** qexp)
    if sign == "-":
        val = -val
    return val, qexp


def parse_factor(conversion, custom):
    if conversion == "Custom":
        if not custom:
            raise Refuse("Custom conversion needs --custom-factor (decimal or a/b).")
        if "/" in custom:
            a, b = custom.split("/", 1)
            a, b = a.strip(), b.strip()
            if not (re.fullmatch(r"[0-9]+", a) and re.fullmatch(r"[0-9]+", b)):
                raise Refuse("custom factor a/b must use positive ASCII integers")
            if len(a) > MAX_DIGITS or len(b) > MAX_DIGITS:
                raise Refuse("custom factor components exceed %d digits" % MAX_DIGITS)
            if int(b) == 0:
                raise Refuse("custom factor denominator must not be zero")
            f = Fraction(int(a), int(b))
        else:
            p = parse_token(custom.strip())
            if p is None:
                raise Refuse("custom factor is not a valid decimal: %r" % custom)
            f = p[0]
        if f <= 0:
            raise Refuse("custom factor must be > 0")
        return f, "in", "out"
    if conversion not in FACTORS:
        raise Refuse("unknown conversion %r" % conversion)
    return FACTORS[conversion]


def round_half_even(fr, decimals):
    """Converter rounding: Fraction.__round__ (ties to even)."""
    return round(fr * (10 ** decimals))


def nearest_floor(fr):
    """Verifier rounding: floor interval and exact distance to its endpoints. A different procedure for the same rule,
    so a mistake in one is not silently confirmed by the other."""
    lo = fr.numerator // fr.denominator          # floor for any sign
    delta = fr - lo
    if delta * 2 < 1:
        return lo
    if delta * 2 > 1:
        return lo + 1
    return lo if lo % 2 == 0 else lo + 1


def serialize(n, decimals):
    sign = "-" if n < 0 else ""
    a = abs(n)
    if decimals == 0:
        return sign + str(a)
    ip, fp = divmod(a, 10 ** decimals)
    return sign + str(ip) + "." + str(fp).zfill(decimals)


def ratstr(fr):
    return str(fr.numerator) if fr.denominator == 1 else "%d/%d" % (fr.numerator, fr.denominator)


def quantize(fr, qexp):
    q = Fraction(10) ** qexp
    return nearest_floor(fr / q) * q


# ----------------------------------------------------------------------------- grammar
def split_lines(text):
    """[(content, ending), ...] preserving each line's own ending."""
    parts = re.split(r'(\r\n|\n|\r)', text)
    out = []
    for i in range(0, len(parts), 2):
        content = parts[i]
        ending = parts[i + 1] if i + 1 < len(parts) else ""
        if i + 1 >= len(parts) and content == "" and out:
            break   # trailing newline: no phantom last line
        out.append((content, ending))
    return out


def tokenize(line, delimiter):
    """Fields with spans. Each: dict(start,end,vstart,vend,value,quoted). Raises Refuse on bad quoting."""
    fields = []
    if delimiter == "whitespace":
        for m in re.finditer(r'[^ \t\r\n\x0b\x0c]+', line):
            raw = m.group(0)
            if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"' and '"' not in raw[1:-1]:
                fields.append(dict(start=m.start(), end=m.end(), vstart=m.start() + 1, vend=m.end() - 1,
                                   value=raw[1:-1], quoted=True))
            else:
                fields.append(dict(start=m.start(), end=m.end(), vstart=m.start(), vend=m.end(),
                                   value=raw, quoted=False))
        return fields
    # comma: fields separated by ',', optional surrounding spaces, optional "quoted" with "" escapes
    i, n = 0, len(line)
    while True:
        start = i
        while i < n and line[i] in " \t":
            i += 1
        if i < n and line[i] == '"':
            j = i + 1
            buf = []
            escaped = False
            while True:
                if j >= n:
                    raise Refuse("unterminated quote")
                if line[j] == '"':
                    if j + 1 < n and line[j + 1] == '"':
                        buf.append('"'); escaped = True; j += 2; continue
                    break
                buf.append(line[j]); j += 1
            vstart, vend = i + 1, j
            j += 1
            k = j
            while k < n and line[k] in " \t":
                k += 1
            if k < n and line[k] != ",":
                raise Refuse("text after closing quote")
            fields.append(dict(start=start, end=k, vstart=vstart, vend=vend, value="".join(buf),
                               quoted=True, escaped=escaped))
            i = k
        else:
            j = i
            while j < n and line[j] != ",":
                j += 1
            raw = line[i:j]
            rs = raw.rstrip(" \t")
            vstart = i
            vend = i + len(rs)
            fields.append(dict(start=start, end=j, vstart=vstart, vend=vend, value=rs, quoted=False))
            i = j
        if i >= n:
            break
        i += 1   # skip comma
        if i >= n:   # trailing comma: one empty field
            fields.append(dict(start=i, end=i, vstart=i, vend=i, value="", quoted=False))
            break
    return fields


def classify(lines, settings):
    """Yield (index, kind) with kind in blank/comment/header/data. Header policy applied here."""
    header_done = False
    for idx, (content, _e) in enumerate(lines):
        stripped = content.strip(WS)
        if stripped == "":
            yield idx, "blank"; continue
        if stripped.startswith("#"):
            yield idx, "comment"; continue
        if not header_done:
            header_done = True
            pol = settings["header"]
            if pol == "yes":
                yield idx, "header"; continue
            if pol == "auto":
                try:
                    fields = tokenize(content, settings["delimiter"])
                    if not any(parse_token(f["value"]) is not None for f in fields):
                        yield idx, "header"; continue
                except Refuse:
                    pass
        yield idx, "data"


def validate_settings(settings):
    """N1: the single validator for a settings dict. Returns the same dict (normalised) or raises Refuse."""
    if not isinstance(settings, dict):
        raise Refuse("settings must be a mapping")
    fmt = settings.get("format")
    if fmt not in list(FORMATS) + ["CUSTOM"]:
        raise Refuse("unknown format %r" % (fmt,))
    if settings.get("delimiter") not in ("whitespace", "comma"):
        raise Refuse("delimiter must be whitespace or comma, got %r" % (settings.get("delimiter"),))
    if settings.get("header") not in ("auto", "yes", "no"):
        raise Refuse("header policy must be auto, yes or no, got %r" % (settings.get("header"),))
    if fmt == "CUSTOM":
        coords = settings.get("coords")
        if not isinstance(coords, list) or not coords:
            raise Refuse("CUSTOM format needs a nonempty list of coordinate field indexes")
        for c in coords:
            if isinstance(c, bool) or not isinstance(c, int) or c < 0 or c > 63:
                raise Refuse("coordinate field indexes must be nonnegative integers (0..63), got %r" % (c,))
        if len(set(coords)) != len(coords):
            raise Refuse("coordinate field indexes must be unique: %r" % (coords,))
        idf = settings.get("id")
        if idf is not None:
            if isinstance(idf, bool) or not isinstance(idf, int) or idf < 0 or idf > 63:
                raise Refuse("identifier field index must be a nonnegative integer (0..63), got %r" % (idf,))
            if idf in coords:
                raise Refuse("field %d cannot be both the identifier and a coordinate" % idf)
        settings["id"] = idf
    return settings


def format_spec(settings):
    fmt = settings["format"]
    if fmt == "CUSTOM":
        coords = settings["coords"]
        idf = settings.get("id")
        need = max(coords + ([idf] if idf is not None else [])) + 1   # row must reach the identifier too (N1)
        return {"coords": coords, "id": idf, "min": need, "max": None}
    return FORMATS[fmt]


def check_field_count(fields, spec, delimiter):
    n = len(fields)
    if n < spec["min"]:
        return "expected at least %d fields, found %d" % (spec["min"], n)
    if delimiter == "comma" and spec["max"] is not None and n > spec["max"]:
        return "expected at most %d fields, found %d (unquoted comma in a description, or decimal commas?)" % (spec["max"], n)
    return None


# ----------------------------------------------------------------------------- converter
def refuse_stray_bom(text, what):
    i = text.find("\ufeff")
    if i >= 0:
        raise Refuse("%s contains U+FEFF (a byte-order mark) inside the content at line %d; only one leading BOM is supported" % (what, text.count("\n", 0, i) + 1))
    if "\0" in text:
        raise Refuse("%s contains a NUL byte; binary or UTF-16 files are not supported" % what)


def convert_text(text, settings, factor, decimals):
    """Returns (candidate_text, info). info has counts, per-token records. Raises Refuse with every problem listed."""
    validate_settings(settings)
    refuse_stray_bom(text, "source")
    lines = split_lines(text)
    spec = format_spec(settings)
    errors, out, counts = [], [], {"data": 0, "header": 0, "comment": 0, "blank": 0}
    id_values = []
    for idx, kind in classify(lines, settings):
        content, ending = lines[idx]
        counts[kind] += 1
        if kind != "data":
            out.append(content + ending); continue
        try:
            fields = tokenize(content, settings["delimiter"])
        except Refuse as ex:
            errors.append((idx + 1, str(ex))); continue
        fc = check_field_count(fields, spec, settings["delimiter"])
        if fc:
            errors.append((idx + 1, fc)); continue
        repl = []
        for c in spec["coords"]:
            f = fields[c]
            if f.get("escaped"):
                errors.append((idx + 1, "coordinate field %d contains escaped quotes" % c)); break
            try:
                p = parse_token(f["value"])
            except Refuse as ex:
                errors.append((idx + 1, str(ex))); break
            if p is None:
                errors.append((idx + 1, "field %d is not numeric: %r" % (c, f["value"][:40]))); break
            val, _q = p
            n = round_half_even(val * factor, decimals)
            repl.append((f["vstart"], f["vend"], serialize(n, decimals)))
        else:
            if spec["id"] is not None:
                id_values.append(fields[spec["id"]]["value"])
            new = content
            for vs, ve, s in sorted(repl, reverse=True):
                new = new[:vs] + s + new[ve:]
            out.append(new + ending)
            continue
        # error path falls here
    if errors:
        raise Refuse("unparsed or invalid data rows (%d):\n" % len(errors) +
                     "\n".join("  line %d: %s" % e for e in errors))
    if counts["data"] == 0:
        raise Refuse("no data rows were converted: every line was blank, comment, or header")
    return "".join(out), {"counts": counts, "ids": id_values}


# ----------------------------------------------------------------------------- verifier (independent)
def validate_controls(control, spec):
    """R3: exactly one expected value per coordinate field, nonnegative tolerance, unique control ids."""
    seen = set()
    for cp in control or []:
        if spec["id"] is None:
            raise Refuse("control points need a format with an identifier field")
        if len(cp["values"]) != len(spec["coords"]):
            raise Refuse("control point %s gives %d expected value(s); the format has %d coordinate fields" %
                         (cp["id"], len(cp["values"]), len(spec["coords"])))
        if cp["tol"] < 0:
            raise Refuse("control point %s has a negative tolerance" % cp["id"])
        if cp["id"] in seen:
            raise Refuse("control point %s is listed more than once" % cp["id"])
        seen.add(cp["id"])


def verify_bytes(src_bytes, out_bytes, settings, factor, decimals, anchors=None, control=None):
    """Independent of the converter. Returns report dict; report['pass'] is the verdict."""
    rep = {"pass": False, "failures": [], "max_error": None, "max_error_at": None,
           "counts": {}, "ranges": {}, "anchors": [], "control_points": [], "warnings": []}
    fails = rep["failures"]
    try:
        validate_settings(settings)
        validate_controls(control, format_spec(settings))
        src_bom = src_bytes.startswith(b"\xef\xbb\xbf")
        out_bom = out_bytes.startswith(b"\xef\xbb\xbf")
        if src_bom != out_bom:
            fails.append("BOM mismatch (source %s, output %s)" % (src_bom, out_bom))
        try:
            src = src_bytes[3:].decode("utf-8", "strict") if src_bom else src_bytes.decode("utf-8", "strict")
            out = out_bytes[3:].decode("utf-8", "strict") if out_bom else out_bytes.decode("utf-8", "strict")
        except UnicodeDecodeError as ex:
            fails.append("invalid UTF-8: %s" % ex); return rep
        refuse_stray_bom(src, "source"); refuse_stray_bom(out, "output")
        sl, ol = split_lines(src), split_lines(out)
        if len(sl) != len(ol):
            fails.append("record count differs: source %d lines, output %d" % (len(sl), len(ol))); return rep
        spec = format_spec(settings)
        coords = spec["coords"]
        counts = {"data": 0, "header": 0, "comment": 0, "blank": 0}
        rng = {c: [None, None] for c in coords}
        max_err, max_at = Fraction(0), None
        kinds = dict(classify(sl, settings))
        ids = {}
        id_count = {}
        for idx in range(len(sl)):
            sc, se = sl[idx]; oc, oe = ol[idx]
            kind = kinds[idx]; counts[kind] += 1
            if se != oe:
                fails.append("line %d: line ending changed" % (idx + 1))
            if kind != "data":
                if sc != oc:
                    fails.append("line %d: %s line altered" % (idx + 1, kind))
                continue
            try:
                sf = tokenize(sc, settings["delimiter"]); of = tokenize(oc, settings["delimiter"])
            except Refuse as ex:
                fails.append("line %d: %s" % (idx + 1, ex)); continue
            if len(sf) != len(of):
                fails.append("line %d: field count changed %d -> %d" % (idx + 1, len(sf), len(of))); continue
            fc = check_field_count(sf, spec, settings["delimiter"])
            if fc:
                fails.append("line %d: %s" % (idx + 1, fc)); continue
            # non-coordinate bytes: blank the coordinate value spans in both and compare
            def blank(line, fields):
                s = line
                for c in sorted(coords, reverse=True):
                    f = fields[c]; s = s[:f["vstart"]] + "\0" + s[f["vend"]:]
                return s
            if blank(sc, sf) != blank(oc, of):
                fails.append("line %d: bytes outside coordinate fields changed" % (idx + 1)); continue
            if spec["id"] is not None:
                idv = sf[spec["id"]]["value"]
                id_count[idv] = id_count.get(idv, 0) + 1
                if idv not in ids:
                    ids[idv] = (idx, of)
            for c in coords:
                ps = parse_token(sf[c]["value"]); po = parse_token(of[c]["value"], MAX_OUT_DIGITS)
                if ps is None:
                    fails.append("line %d field %d: source not numeric" % (idx + 1, c)); continue
                if po is None:
                    fails.append("line %d field %d: written value not numeric: %r" % (idx + 1, c, of[c]["value"][:40])); continue
                sval, qexp = ps; wval, wq = po
                expected = serialize(nearest_floor(sval * factor * (10 ** decimals)), decimals)   # second procedure
                if of[c]["value"] != expected:
                    fails.append("line %d field %d: written %r, exact nearest-ties-to-even result is %r" % (idx + 1, c, of[c]["value"][:40], expected))
                if wq != -decimals:
                    fails.append("line %d field %d: written with %d decimals, expected %d" % (idx + 1, c, -wq, decimals))
                reverse = wval / factor
                err = abs(reverse - sval)
                q = Fraction(10) ** qexp
                if err * 2 > q:
                    fails.append("line %d field %d: reverse error %s exceeds half quantum %s" % (idx + 1, c, err, q / 2))
                if quantize(reverse, qexp) != sval:
                    fails.append("line %d field %d: source not reconstructed at its quantum" % (idx + 1, c))
                if err > max_err:
                    max_err, max_at = err, (idx + 1, c)
                r = rng[c]
                if r[0] is None or wval < r[0]: r[0] = wval
                if r[1] is None or wval > r[1]: r[1] = wval
        rep["counts"] = counts
        rep["ranges"] = {str(c): [None if v is None else serialize(round_half_even(v, decimals), decimals) for v in rng[c]] for c in coords}
        rep["max_error"] = str(max_err); rep["max_error_at"] = max_at
        if counts["data"] == 0:
            fails.append("no data rows")
        # anchors on written values
        for a in (anchors or []):
            c, lo, hi = a["field"], a["min"], a["max"]
            if c not in rng:
                fails.append("anchor field %d is not a coordinate field" % c); continue
            if lo is not None and hi is not None and lo > hi:
                fails.append("anchor field %d: min > max" % c); continue
            omin, omax = rng[c]
            ok = True
            if omin is None: ok = False
            if lo is not None and omin is not None and omin < lo: ok = False
            if hi is not None and omax is not None and omax > hi: ok = False
            rep["anchors"].append({"field": c, "min": a.get("min_text"), "max": a.get("max_text"),
                                   "min_exact": None if lo is None else ratstr(lo), "max_exact": None if hi is None else ratstr(hi),
                                   "observed_min": None if omin is None else serialize(round_half_even(omin, decimals), decimals),
                                   "observed_max": None if omax is None else serialize(round_half_even(omax, decimals), decimals), "pass": ok})
            if not ok:
                fails.append("anchor field %d failed: observed [%s, %s] vs [%s, %s]" % (c, omin, omax, lo, hi))
        # control points on written values
        for cp in (control or []):
            entry = {"id": cp["id"], "expected": cp.get("values_text") or [ratstr(v) for v in cp["values"]],
                     "expected_exact": [ratstr(v) for v in cp["values"]], "tolerance": cp.get("tol_text") or ratstr(cp["tol"]),
                     "tolerance_exact": ratstr(cp["tol"]), "checked_fields": list(coords), "pass": False}
            if id_count.get(cp["id"], 0) > 1:
                entry["note"] = "identifier occurs %d times; ambiguous" % id_count[cp["id"]]
                rep["control_points"].append(entry)
                fails.append("control point %s is ambiguous: identifier occurs %d times in the source" % (cp["id"], id_count[cp["id"]])); continue
            hit = ids.get(cp["id"])
            if hit is None:
                entry["note"] = "id not found"; rep["control_points"].append(entry)
                fails.append("control point %s not found" % cp["id"]); continue
            idx, of = hit
            ok = True; got = []
            for c, exp in zip(coords, cp["values"]):
                w = parse_token(of[c]["value"], MAX_EXPANDED_DIGITS)[0]   # written tokens use the expanded limit (round-4 #7)
                got.append(of[c]["value"])
                if abs(w - exp) > cp["tol"]:
                    ok = False
            entry["written"] = got; entry["line"] = idx + 1; entry["pass"] = ok
            rep["control_points"].append(entry)
            if not ok:
                fails.append("control point %s outside tolerance" % cp["id"])
        # advisory: integer coordinate column that steps by exactly 1
        for c in coords:
            seq = True; prev = None; n = 0
            for idx in range(len(sl)):
                if kinds[idx] != "data": continue
                try:
                    p = parse_token(tokenize(sl[idx][0], settings["delimiter"])[c]["value"])
                except (Refuse, IndexError):
                    p = None
                if p is None: continue
                v = p[0]; n += 1
                if v.denominator != 1 or (prev is not None and v - prev != 1):
                    seq = False; break
                prev = v
            if seq and n >= 10:
                rep["warnings"].append("coordinate field %d is consecutive integers over %d rows: looks like point numbers; confirm the mapping" % (c, n))
    except Refuse as ex:
        fails.append(str(ex))
    rep["pass"] = not fails
    return rep


# ----------------------------------------------------------------------------- run
def sha256(b):
    return hashlib.sha256(b).hexdigest().lower()   # one spelling everywhere (R5-07); comparisons normalise to lowercase


def choose_and_convert(src_bytes, settings, factor, decimals_opt, anchors, control):
    bom = src_bytes.startswith(b"\xef\xbb\xbf")
    try:
        text = (src_bytes[3:] if bom else src_bytes).decode("utf-8", "strict")
    except UnicodeDecodeError as ex:
        raise Refuse("source is not valid UTF-8 (%s). Only UTF-8/ASCII is supported; transcode explicitly first." % ex)
    # source quantum survey (to pick decimals)
    lines = split_lines(text)
    spec = format_spec(settings)
    finest = 0
    for idx, kind in classify(lines, settings):
        if kind != "data": continue
        try:
            fields = tokenize(lines[idx][0], settings["delimiter"])
        except Refuse:
            continue
        for c in spec["coords"]:
            if c < len(fields):
                p = parse_token(fields[c]["value"])
                if p is not None and -p[1] > finest:
                    finest = -p[1]
    validate_controls(control, spec)
    if decimals_opt == "auto":
        # Policy (N9): prefer the band [max(4, finest+2) .. 12]; if nothing there passes, accept any lower
        # precision down to 0 that passes every check. Auto seeks any valid representation, preferring the band.
        start = min(max(MIN_DECIMALS, finest + 2), MAX_DECIMALS)
        candidates = list(range(start, MAX_DECIMALS + 1)) + list(range(start - 1, -1, -1))
    else:
        candidates = [int(decimals_opt)]
    best = None; tried = []
    for d in candidates:
        cand, info = convert_text(text, settings, factor, d)
        cand_bytes = (b"\xef\xbb\xbf" if bom else b"") + cand.encode("utf-8")
        rep = verify_bytes(src_bytes, cand_bytes, settings, factor, d, anchors, control)
        tried.append(d)
        if rep["pass"]:
            return (d, cand_bytes, rep, info, finest)
        if best is None or len(rep["failures"]) < len(best[2]["failures"]):
            best = (d, cand_bytes, rep, info, finest)   # report the closest miss, not the last one tried
        # no early exit: a bound on a rounded written value can pass at a higher precision (R12)
    d, cand_bytes, rep, info, finest = best
    where = "at %d decimals" % d if len(tried) == 1 else "at every precision from %d down to %d decimals (closest: %d)" % (max(tried), min(tried), d)
    raise Refuse("verification failed %s:\n  " % where
                 + "\n  ".join(rep["failures"][:50]) + ("\n  ... %d more" % (len(rep["failures"]) - 50) if len(rep["failures"]) > 50 else ""))


def canonical_json(obj):
    """Canonical serialization shared with the browser package: keys sorted recursively, no whitespace,
    every scalar as a string, arrays in order. Both packages must produce identical bytes for equal content."""
    def norm(x):
        if isinstance(x, dict):   # key order = UTF-16 code-unit order, which is what JavaScript's default sort uses
            return {str(k): norm(x[k]) for k in sorted(x, key=lambda k: str(k).encode("utf-16-be"))}
        if isinstance(x, (list, tuple)):
            return [norm(v) for v in x]
        if x is None:
            return None
        if isinstance(x, bool):
            return "true" if x else "false"   # JSON spelling; JavaScript String(true) agrees
        return str(x)
    return json.dumps(norm(obj), sort_keys=False, separators=(",", ":"), ensure_ascii=True)   # already ordered by norm()


SAFE_INT = 2 ** 53 - 1


def canonical_json_v2(obj):
    """Contract draft 2 candidate (`canonical-json/2`): a TYPED, bounded domain.
    null -> null; booleans -> true/false; integers within +/-(2^53-1) -> bare digits; strings -> escaped as in v1;
    floats, non-finite values, integers outside the safe range and strings with unpaired surrogates are refused
    (Refuse), never normalised. Keys sorted by UTF-16 code-unit order. Not yet the wire format: schema 3 uses v1."""
    def wf(t):
        i = 0
        while i < len(t):
            c = ord(t[i])
            if 0xD800 <= c <= 0xDBFF:
                if i + 1 < len(t) and 0xDC00 <= ord(t[i + 1]) <= 0xDFFF: i += 2; continue
                raise Refuse("canonical: unpaired surrogate in string")
            if 0xDC00 <= c <= 0xDFFF:
                raise Refuse("canonical: unpaired surrogate in string")
            i += 1
        return t
    def enc(x):
        if x is None: return "null"
        if isinstance(x, bool): return "true" if x else "false"
        if isinstance(x, int):
            if abs(x) > SAFE_INT: raise Refuse("canonical: integer outside the safe range: %d" % x)
            return str(x)
        if isinstance(x, float): raise Refuse("canonical: floating-point values are not in the record domain")
        if isinstance(x, str): return json.dumps(wf(x), ensure_ascii=True)
        if isinstance(x, (list, tuple)): return "[" + ",".join(enc(v) for v in x) + "]"
        if isinstance(x, dict):
            for k in x:
                if not isinstance(k, str): raise Refuse("canonical: non-string key")
            return "{" + ",".join(json.dumps(wf(k), ensure_ascii=True) + ":" + enc(x[k]) for k in sorted(x, key=lambda k: k.encode("utf-16-be", "surrogatepass"))) + "}"
        raise Refuse("canonical: unsupported type %s" % type(x).__name__)
    return enc(obj)


def content_fingerprint_legacy(m):
    """v3.3.0/v3.3.1 hashed the digest strings as recorded (uppercase). Accepted with a note; never produced."""
    canon = {"source_sha256": m["source"]["sha256"], "output_sha256": m["output"]["sha256"],
             "factor": [m["units"]["factor_numerator"], m["units"]["factor_denominator"]],
             "source_unit": m["units"]["source_unit"], "target_unit": m["units"]["target_unit"],
             "source_unit_reference": m["units"]["source_unit_reference"],
             "decimals": m["rounding"]["decimals"], "grammar": m["grammar"],
             "anchors": [{"field": a["field"], "min": a.get("min_exact"), "max": a.get("max_exact")} for a in m["anchors"]],
             "control_points": [{"id": c["id"], "expected": c.get("expected_exact"), "tolerance": c.get("tolerance_exact")} for c in m["control_points"]],
             "build": m["tool"]["build"]}
    return sha256(canonical_json(canon).encode("utf-8"))[:16].lower()


def content_fingerprint(m):
    """N7: identity of the complete verification configuration and both artifacts (not a unique execution id)."""
    canon = {"source_sha256": str(m["source"]["sha256"]).lower(), "output_sha256": str(m["output"]["sha256"]).lower(),
             "factor": [m["units"]["factor_numerator"], m["units"]["factor_denominator"]],
             "source_unit": m["units"]["source_unit"], "target_unit": m["units"]["target_unit"],
             "source_unit_reference": m["units"]["source_unit_reference"],
             "decimals": m["rounding"]["decimals"], "grammar": m["grammar"],
             "anchors": [{"field": a["field"], "min": a.get("min_exact"), "max": a.get("max_exact")} for a in m["anchors"]],
             "control_points": [{"id": c["id"], "expected": c.get("expected_exact"), "tolerance": c.get("tolerance_exact")} for c in m["control_points"]],
             "build": m["tool"]["build"]}
    return sha256(canonical_json(canon).encode("utf-8"))[:16].lower()


def build_report(run_id, src_path, src_bytes, out_path, out_bytes, settings, conversion, custom, factor, uin, uout,
                 decimals, finest, rep, info, source_ref, scope):
    manifest = {
        "schema": "pointfile-units-report/3", "run_id": run_id, "content_fingerprint": None,
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool": {"name": "pointfile_units.py", "version": VERSION, "build": tool_build()},
        "source": {"path": src_path, "bytes": len(src_bytes), "sha256": sha256(src_bytes),
                   "encoding": "utf-8" + ("-bom" if src_bytes.startswith(b"\xef\xbb\xbf") else "")},
        "output": {"path": out_path, "bytes": len(out_bytes), "sha256": sha256(out_bytes),
                   "encoding": "utf-8" + ("-bom" if out_bytes.startswith(b"\xef\xbb\xbf") else "")},
        "units": {"conversion": conversion, "custom_factor_input": custom, "source_unit": uin, "target_unit": uout,
                  "factor_numerator": str(factor.numerator), "factor_denominator": str(factor.denominator),
                  "source_unit_reference": source_ref, "declared_not_checked": ["source_unit", "target_unit", "source_unit_reference"]},
        "grammar": {"format": settings["format"], "coordinate_fields": format_spec(settings)["coords"],
                    "id_field": format_spec(settings)["id"], "delimiter": settings["delimiter"],
                    "header_policy": settings["header"], "comment_prefix": "#"},
        "rounding": {"rule": "nearest, ties to even", "decimals": decimals, "finest_source_decimals": finest, "acceptance": ACCEPTANCE},
        "counts": rep["counts"], "checks": {"arithmetic_and_reconstruction": "pass" if rep["pass"] else "fail",
                                            "record_accounting": "pass" if rep["pass"] else "fail",
                                            "non_coordinate_preservation": "pass" if rep["pass"] else "fail"},
        "max_error": rep["max_error"], "max_error_at": rep["max_error_at"],
        "ranges": rep["ranges"], "anchors": rep["anchors"], "control_points": rep["control_points"],
        "warnings": rep["warnings"], "verification_scope": scope, "pass": rep["pass"], "failures": rep["failures"],
    }
    manifest["content_fingerprint"] = content_fingerprint(manifest)
    m = manifest
    txt = []
    A = txt.append
    A("POINT FILE UNIT CONVERSION - VERIFICATION REPORT")
    A("Status        : %s" % ("Arithmetic and preservation checks passed under the confirmed settings listed below." if m["pass"] else "FAILED"))
    A("Run           : %s   %s   tool %s build %s   content fingerprint %s" % (m["run_id"], m["timestamp_utc"], m["tool"]["version"], m["tool"]["build"], m["content_fingerprint"]))
    A("Scope         : %s" % scope)
    A("Source        : %s   %d bytes   %s   SHA-256 %s" % (m["source"]["path"], m["source"]["bytes"], m["source"]["encoding"], m["source"]["sha256"]))
    A("Output        : %s   %d bytes   %s   SHA-256 %s" % (m["output"]["path"], m["output"]["bytes"], m["output"]["encoding"], m["output"]["sha256"]))
    A("Units         : %s -> %s   (%s)   factor %d/%d   [declared by user, not checked]" % (uin, uout, conversion, factor.numerator, factor.denominator))
    A("Unit reference: %s" % (source_ref or "(none supplied)"))
    A("Grammar       : %s   coordinate fields %s   id field %s   delimiter %s   header policy %s   comments '#'" %
      (settings["format"], m["grammar"]["coordinate_fields"], m["grammar"]["id_field"], settings["delimiter"], settings["header"]))
    A("Rounding      : nearest, ties to even; %d decimals written; finest source quantum 10^-%d" % (decimals, finest))
    A("Acceptance    : reverse error <= half source quantum, and source value reconstructed at its own quantum")
    A("Records       : data %d   header %d   comment %d   blank %d" % (rep["counts"].get("data", 0), rep["counts"].get("header", 0), rep["counts"].get("comment", 0), rep["counts"].get("blank", 0)))
    A("Max error     : %s %s at line/field %s" % (rep["max_error"], uin, rep["max_error_at"]))
    A("Ranges (written values, %s):" % uout)
    for c, (lo, hi) in rep["ranges"].items():
        A("  field %s : %s to %s" % (c, lo, hi))
    for a in rep["anchors"]:
        A("Anchor field %d : bounds [%s, %s]  observed [%s, %s]  %s" % (a["field"], a["min"], a["max"], a["observed_min"], a["observed_max"], "pass" if a["pass"] else "FAIL"))
    for c in rep["control_points"]:
        A("Control point %s : %s" % (c["id"], "pass" if c["pass"] else "FAIL") + ("" if c["pass"] else "  " + json.dumps(c)))
    for w in rep["warnings"]:
        A("WARNING       : %s" % w)
    if rep["failures"]:
        A("Failures:")
        for f in rep["failures"]:
            A("  " + f)
    A("Hashes bind this report to those bytes. They do not certify the survey interpretation or the author.")
    return manifest, "\n".join(txt) + "\n"


def parse_anchors(items):
    out = []
    for s in items or []:
        p = s.split(":")
        if len(p) != 3:
            raise Refuse("anchor must be field:min:max (blank allowed), got %r" % s)
        c = int(p[0])
        lo = None if p[1].strip() == "" else parse_token(p[1].strip())
        hi = None if p[2].strip() == "" else parse_token(p[2].strip())
        if (p[1].strip() and lo is None) or (p[2].strip() and hi is None):
            raise Refuse("anchor bound is not numeric: %r" % s)
        out.append({"field": c, "min": None if lo is None else lo[0], "max": None if hi is None else hi[0],
                    "min_text": p[1].strip() or None, "max_text": p[2].strip() or None})
    return out


def parse_control(items):
    out = []
    for s in items or []:
        p = [x.strip() for x in re.split(r'[,\s]+', s.strip()) if x.strip()]
        if len(p) < 3:
            raise Refuse("control point must be id v1 [v2 v3] tol, got %r" % s)
        vals = []
        for v in p[1:-1]:
            t = parse_token(v)   # entered values: 40-digit mantissa, exponent within +/-30 (the same limit at every entry point)
            if t is None: raise Refuse("control point value not numeric: %r" % v)
            vals.append(t[0])
        t = parse_token(p[-1])
        if t is None: raise Refuse("control point tolerance not numeric: %r" % p[-1])
        out.append({"id": p[0], "values": vals, "tol": t[0], "values_text": p[1:-1], "tol_text": p[-1]})
    return out


def exclusive_write(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data); fh.flush(); os.fsync(fh.fileno())
    except Exception:
        try: os.remove(path)
        except OSError: pass
        raise


def cmd_convert(a):
    settings = {"format": a.format, "delimiter": a.delimiter, "header": a.header}
    if a.format == "CUSTOM":
        if not a.coords:
            raise Refuse("--format CUSTOM needs --coords, e.g. 1,2,3")
        parts = [x.strip() for x in a.coords.split(",")]
        if not all(re.fullmatch(r"[0-9]+", x) for x in parts):
            raise Refuse("--coords must be nonnegative integers separated by commas, got %r" % a.coords)
        settings["coords"] = [int(x) for x in parts]
        if a.id_field is not None and not re.fullmatch(r"[0-9]+", a.id_field.strip()):
            raise Refuse("--id-field must be a nonnegative integer, got %r" % a.id_field)
        settings["id"] = None if a.id_field is None else int(a.id_field.strip())
    src_path = os.path.realpath(a.input)
    out_path = os.path.realpath(a.output)
    if same_file(out_path, src_path):
        raise Refuse("output path is the source (same file by identity or by normalised path). Refused.")
    if os.path.exists(out_path):
        raise Refuse("output already exists: %s. Refused (no overwrite)." % out_path)
    for extra in (out_path + ".report.txt", out_path + ".manifest.json"):
        if os.path.exists(extra):
            raise Refuse("report file already exists: %s" % extra)
    if os.path.getsize(src_path) > MAX_FILE_BYTES:
        raise Refuse("source exceeds %d MB limit" % (MAX_FILE_BYTES // (1024 * 1024)))
    with open(src_path, "rb") as fh:
        src_bytes = fh.read()
    factor, uin, uout = parse_factor(a.conversion, a.custom_factor)
    if a.delimiter == "auto":
        probe = (src_bytes[:4096]).decode("utf-8", "replace")
        settings["delimiter"] = "comma" if "," in probe else "whitespace"
    validate_settings(settings)
    anchors = parse_anchors(a.anchor)
    control = parse_control(a.control_point)
    decimals, cand_bytes, rep, info, finest = choose_and_convert(src_bytes, settings, factor, a.decimals, anchors, control)
    if rep["warnings"] and not a.force_mapping:
        raise Refuse("mapping warning (use --force-mapping to proceed):\n  " + "\n  ".join(rep["warnings"]))
    run_id = os.urandom(8).hex()   # unique execution id; content identity is content_fingerprint
    # release invariant (R5-04): the serialized record must re-verify against the candidate before anything is published
    pre_manifest, _txt = build_report(run_id, src_path, src_bytes, out_path, cand_bytes, settings, a.conversion, a.custom_factor, factor, uin, uout,
                                      decimals, finest, rep, info, a.source_unit_reference, "pre-publication self-replay")
    replay = verify_record(src_bytes, cand_bytes, load_record_text(json.dumps(pre_manifest, ensure_ascii=True)), tool_build(), record_bytes=json.dumps(pre_manifest, ensure_ascii=True).encode("utf-8"))
    if replay["unsupported"] is not None or not (replay["files_pass"] and replay["report_consistent"]):
        raise Refuse("the record this conversion would publish does not re-verify from its own serialized form; nothing written:\n  "
                     + "\n  ".join(([replay["unsupported"]] if replay["unsupported"] else []) + replay["fresh_failures"][:10] + replay["consistency_failures"][:10]))
    if a.dry_run:
        manifest, txt = build_report(run_id, src_path, src_bytes, "(dry run - not written)", cand_bytes, settings, a.conversion,
                                     a.custom_factor, factor, uin, uout, decimals, finest, rep, info, a.source_unit_reference, "candidate bytes (dry run)")
        preview = cand_bytes.decode("utf-8", "replace").splitlines()[:5]
        write_report_to_console(txt + "First lines of candidate:\n" + "\n".join("  " + l for l in preview) + "\n", committed=False)
        return 0
    # publish: exclusive create, re-read, verify the disk bytes, then bind the report.
    # Only files this run created are removed on failure (R5).
    created = {}   # path -> sha256 of what THIS run wrote; cleanup deletes only if the file still has that content (N8)
    def cleanup():
        """Returns (removed, retained). The read handle is closed before removal (Windows locks open files, round-4 #4)."""
        removed, retained = [], []
        for pth, h in created.items():
            try:
                with open(pth, "rb") as fh:
                    same = sha256(fh.read()) == h
            except OSError as ex:
                retained.append((pth, "could not read: %s" % ex)); continue
            if not same:
                retained.append((pth, "content is no longer what this run wrote")); continue
            try:
                os.remove(pth); removed.append(pth)
            except OSError as ex:
                retained.append((pth, "could not remove: %s" % ex))
        return removed, retained
    def cleanup_text(removed, retained):
        parts = []
        if removed: parts.append("removed this run's own file(s): %s" % ", ".join(os.path.basename(p) for p in removed))
        for p, why in retained: parts.append("RETAINED %s (%s)" % (os.path.basename(p), why))
        return "; ".join(parts) if parts else "nothing to clean up"
    try:
        exclusive_write(out_path, cand_bytes); created[out_path] = sha256(cand_bytes)
    except FileExistsError:
        raise Refuse("output appeared between preflight and creation: %s. Nothing overwritten." % out_path)
    try:
        with open(out_path, "rb") as fh:
            disk = fh.read()
        if disk != cand_bytes:
            raise Refuse("re-read output differs from the verified candidate")
        rep2 = verify_bytes(src_bytes, disk, settings, factor, decimals, anchors, control)
        if not rep2["pass"]:
            raise Refuse("disk verification failed:\n  " + "\n  ".join(rep2["failures"][:20]))
        with open(src_path, "rb") as fh:
            if sha256(fh.read()) != sha256(src_bytes):
                raise Refuse("source bytes changed during the run")
        manifest, txt = build_report(run_id, src_path, src_bytes, out_path, disk, settings, a.conversion, a.custom_factor,
                                     factor, uin, uout, decimals, finest, rep2, info, a.source_unit_reference, "reread disk bytes")
        mb = json.dumps(manifest, indent=2).encode("utf-8"); exclusive_write(out_path + ".manifest.json", mb); created[out_path + ".manifest.json"] = sha256(mb)
        tb = txt.encode("utf-8"); exclusive_write(out_path + ".report.txt", tb); created[out_path + ".report.txt"] = sha256(tb)
    except FileExistsError as ex:
        removed, retained = cleanup()
        raise Refuse("a report file appeared between preflight and creation (%s). Cleanup: %s. Anything not created by this run was left alone." % (ex.filename, cleanup_text(removed, retained)))
    except Exception:
        cleanup()
        raise
    write_report_to_console(txt, committed=True)
    return 0


def write_report_to_console(txt, committed):
    """A terminal that cannot display the report must not change the transaction result (round-4 #5)."""
    try:
        sys.stdout.write(txt); sys.stdout.flush()
    except (UnicodeEncodeError, OSError):
        try:
            sys.stdout.write(("CONVERSION COMMITTED; " if committed else "") + "the console could not display the full report in its encoding. The .report.txt and .manifest.json files on disk are authoritative.\n")
            sys.stdout.write(txt.encode("ascii", "backslashreplace").decode("ascii")); sys.stdout.flush()
        except (UnicodeEncodeError, OSError):
            pass


OBSERVED_FIELDS = ("counts", "ranges", "max_error", "max_error_at", "anchors", "control_points", "warnings", "checks", "failures",
                   "source_bytes", "source_encoding", "output_bytes", "output_encoding", "finest_source_decimals")


def observation_structure(rep, src_len, out_len, src_bom, out_bom, finest=None):
    """The mechanically observable part of a report, in a fixed shape shared with the browser package."""
    return {
        "finest_source_decimals": finest,
        "counts": rep["counts"], "ranges": rep["ranges"], "max_error": str(rep["max_error"]),
        "max_error_at": None if rep["max_error_at"] is None else [int(rep["max_error_at"][0]), int(rep["max_error_at"][1])],
        "anchors": [{"field": a["field"], "min": a.get("min"), "max": a.get("max"), "min_exact": a.get("min_exact"), "max_exact": a.get("max_exact"),
                     "observed_min": a.get("observed_min"), "observed_max": a.get("observed_max"), "pass": a["pass"]} for a in rep["anchors"]],
        "control_points": [{"id": c["id"], "expected": c.get("expected"), "expected_exact": c.get("expected_exact"), "tolerance": c.get("tolerance"),
                            "tolerance_exact": c.get("tolerance_exact"), "checked_fields": c.get("checked_fields"), "written": c.get("written"),
                            "line": c.get("line"), "note": c.get("note"), "pass": c["pass"]} for c in rep["control_points"]],
        "warnings": list(rep["warnings"]),
        "checks": {"arithmetic_and_reconstruction": "pass" if rep["pass"] else "fail", "record_accounting": "pass" if rep["pass"] else "fail",
                   "non_coordinate_preservation": "pass" if rep["pass"] else "fail"},
        "failures": list(rep["failures"]),
        "source_bytes": src_len, "source_encoding": "utf-8-bom" if src_bom else "utf-8",
        "output_bytes": out_len, "output_encoding": "utf-8-bom" if out_bom else "utf-8",
    }


def recorded_observation_structure(m):
    def anchor(a):
        return {"field": a.get("field"), "min": a.get("min"), "max": a.get("max"), "min_exact": a.get("min_exact"), "max_exact": a.get("max_exact"),
                "observed_min": a.get("observed_min"), "observed_max": a.get("observed_max"), "pass": a.get("pass")}
    def control(c):
        return {"id": c.get("id"), "expected": c.get("expected"), "expected_exact": c.get("expected_exact"), "tolerance": c.get("tolerance"),
                "tolerance_exact": c.get("tolerance_exact"), "checked_fields": c.get("checked_fields"), "written": c.get("written"),
                "line": c.get("line"), "note": c.get("note"), "pass": c.get("pass")}
    at = m.get("max_error_at")
    return {
        "finest_source_decimals": (m.get("rounding") or {}).get("finest_source_decimals"),
        "counts": m.get("counts"), "ranges": m.get("ranges"), "max_error": None if m.get("max_error") is None else str(m.get("max_error")),
        "max_error_at": None if at is None else [int(at[0]), int(at[1])],
        "anchors": [anchor(a) for a in m.get("anchors", [])], "control_points": [control(c) for c in m.get("control_points", [])],
        "warnings": m.get("warnings"), "checks": m.get("checks"), "failures": m.get("failures"),
        "source_bytes": m["source"].get("bytes"), "source_encoding": m["source"].get("encoding"),
        "output_bytes": m["output"].get("bytes"), "output_encoding": m["output"].get("encoding"),
    }


ACCEPTANCE = "reverse error <= half source quantum AND source reconstructed at its quantum; verifier recomputes the exact product with a floor-interval procedure"
# Known historical rule sentences under schema 3, by producer. Exact text only; anything else is unsupported (R6-02).
LEGACY_ACCEPTANCE = {
    "reverse error <= half source quantum AND source reconstructed at its quantum":
        "schema-3 legacy adapter A: pointfile_units.py 3.2.0-3.3.1 and Point-File-Unit-Converter.html 3.2.0 (acceptance text without the floor-interval clause; verified under the current rule)",
}
def legacy_adapter_for(acceptance):
    """Own-key, string-only lookup (R7-01). Returns the adapter name or None."""
    if not isinstance(acceptance, str):
        return None
    return LEGACY_ACCEPTANCE.get(acceptance)


RECORD_MAX_BYTES = 4 * 1024 * 1024
RECORD_MAX_DEPTH = 8
RECORD_MAX_ITEMS = 10000
TEXT_LIMITS = {"path": 1024, "reference": 2000, "short": 128, "list_item": 512}
ANCHOR_KEYS = {"required": {"field", "pass"}, "allowed": {"field", "min", "max", "min_exact", "max_exact", "observed_min", "observed_max", "pass"}}
CONTROL_KEYS = {"required": {"id", "pass"}, "allowed": {"id", "expected", "expected_exact", "tolerance", "tolerance_exact", "checked_fields", "written", "line", "note", "pass"}}
NESTED_KEYS = {
    "tool": {"required": {"name", "version", "build"}, "allowed": {"name", "version", "build"}},
    "source": {"required": {"path", "bytes", "sha256", "encoding"}, "allowed": {"path", "bytes", "sha256", "encoding"}},
    "output": {"required": {"path", "bytes", "sha256", "encoding"}, "allowed": {"path", "bytes", "sha256", "encoding"}},
    "units": {"required": {"conversion", "custom_factor_input", "source_unit", "target_unit", "factor_numerator", "factor_denominator", "source_unit_reference", "declared_not_checked"},
              "allowed": {"conversion", "custom_factor_input", "source_unit", "target_unit", "factor_numerator", "factor_denominator", "source_unit_reference", "declared_not_checked"}},
    "grammar": {"required": {"format", "coordinate_fields", "id_field", "delimiter", "header_policy", "comment_prefix"}, "allowed": {"format", "coordinate_fields", "id_field", "delimiter", "header_policy", "comment_prefix"}},
    "rounding": {"required": {"rule", "decimals", "finest_source_decimals", "acceptance"}, "allowed": {"rule", "decimals", "finest_source_decimals", "acceptance"}},
}


def finest_source_decimals(src_bytes, settings):
    """Observation: the finest decimal quantum among the source coordinate tokens (recomputed by the verifier, R5-05)."""
    bom = src_bytes.startswith(b"\xef\xbb\xbf")
    text = (src_bytes[3:] if bom else src_bytes).decode("utf-8", "strict")
    lines = split_lines(text); spec = format_spec(settings); finest = 0
    for idx, kind in classify(lines, settings):
        if kind != "data": continue
        try: fields = tokenize(lines[idx][0], settings["delimiter"])
        except Refuse: continue
        for c in spec["coords"]:
            if c < len(fields):
                try: p = parse_token(fields[c]["value"])
                except Refuse: p = None
                if p is not None and -p[1] > finest: finest = -p[1]
    return finest


def _frac_from_manifest(v, what):
    """Exact rational from a manifest value. Strings only (decimal or a/b); ints tolerated; everything else refused."""
    if isinstance(v, bool) or v is None:
        raise Refuse("manifest: %s is missing or not a number" % what)
    if isinstance(v, int):
        if len(str(abs(v))) > MAX_EXPANDED_DIGITS:
            raise Refuse("manifest: %s exceeds %d digits" % (what, MAX_EXPANDED_DIGITS))
        return Fraction(v)
    if isinstance(v, str):
        if "/" in v:
            parts = v.split("/")
            if len(parts) != 2:
                raise Refuse("manifest: %s is not an exact rational (expected a/b): %r" % (what, v))
            a, b = parts[0].strip(), parts[1].strip()
            if not (re.fullmatch(r"-?[0-9]+", a) and re.fullmatch(r"[0-9]+", b)):
                raise Refuse("manifest: %s is not an exact rational: %r" % (what, v))
            if len(a.lstrip("-")) > MAX_EXPANDED_DIGITS or len(b) > MAX_EXPANDED_DIGITS:
                raise Refuse("manifest: %s exceeds %d digits" % (what, MAX_EXPANDED_DIGITS))
            if int(b) == 0:
                raise Refuse("manifest: %s has a zero denominator" % what)
            return Fraction(int(a), int(b))
        p = parse_token(v.strip(), MAX_EXPANDED_DIGITS)
        if p is None:
            raise Refuse("manifest: %s is not numeric: %r" % (what, v[:40]))
        return p[0]
    raise Refuse("manifest: %s has unsupported type %s" % (what, type(v).__name__))


def _need(d, key, types, what):
    if not isinstance(d, dict) or key not in d:
        raise Refuse("manifest: %s.%s is missing" % (what, key))
    v = d[key]
    if isinstance(v, bool) and bool not in types:
        raise Refuse("manifest: %s.%s has unsupported type bool" % (what, key))
    if not isinstance(v, types):
        raise Refuse("manifest: %s.%s has unsupported type %s" % (what, key, type(v).__name__))
    return v


NON_INTEGER_NUMBER = re.compile(r'"(?:[^"\\]|\\.)*"|(?P<num>-?[0-9]+(?:\.[0-9]+)(?:[eE][+-]?[0-9]+)?|-?[0-9]+[eE][+-]?[0-9]+)')


def refuse_non_integer_numbers(text):
    """Typed domain (R5-06): a record may contain JSON integers and strings only. A float or exponent literal anywhere
    is unsupported, checked on the raw text because JSON.parse would erase the distinction in JavaScript."""
    for mo in NON_INTEGER_NUMBER.finditer(text):
        if mo.group("num"):
            raise Refuse("manifest: non-integer JSON number %r; exact quantities must be strings and counts must be integers" % mo.group("num"))


def check_bounds(obj, depth=0):
    """Record bounds (draft 2 §1): nesting depth and collection sizes. Returns the maximum depth seen."""
    if depth > RECORD_MAX_DEPTH:
        raise Refuse("manifest: nesting deeper than %d" % RECORD_MAX_DEPTH)
    if isinstance(obj, dict):
        if len(obj) > RECORD_MAX_ITEMS: raise Refuse("manifest: object with more than %d keys" % RECORD_MAX_ITEMS)
        return max([depth] + [check_bounds(v, depth + 1) for v in obj.values()])
    if isinstance(obj, list):
        if len(obj) > RECORD_MAX_ITEMS: raise Refuse("manifest: list with more than %d items" % RECORD_MAX_ITEMS)
        return max([depth] + [check_bounds(v, depth + 1) for v in obj])
    return depth


def load_record_text(raw):
    """Parse a record from its raw text with the typed-domain rules: size bound, no non-integer numbers, no duplicate keys."""
    if len(raw.encode("utf-8")) > RECORD_MAX_BYTES:
        raise Refuse("manifest: larger than %d bytes" % RECORD_MAX_BYTES)
    refuse_non_integer_numbers(raw)
    def pairs(items):
        d = {}
        for k, v in items:
            if k in d: raise Refuse("manifest: duplicate key %r" % k)
            d[k] = v
        return d
    try:
        m = json.loads(raw, object_pairs_hook=pairs)
    except ValueError as ex:
        raise Refuse("manifest: not valid JSON: %s" % ex)
    check_bounds(m)
    return m


def _text(v, what, limit):
    """Text bounds count Unicode scalar values (code points); JavaScript must count the same way (R7-04)."""
    if not isinstance(v, str):
        raise Refuse("manifest: %s must be a string" % what)
    if any(0xD800 <= ord(ch) <= 0xDFFF for ch in v):
        raise Refuse("manifest: %s contains an ill-formed surrogate" % what)
    if len(v) > limit:
        raise Refuse("manifest: %s longer than %d characters (Unicode scalar values)" % (what, limit))
    if any(ord(ch) < 0x20 and ch not in "\t" for ch in v):
        raise Refuse("manifest: %s contains control characters" % what)
    return v


def validate_manifest(m):
    """N4: structural validation of the whole manifest before any value is used. Returns normalised pieces."""
    if not isinstance(m, dict):
        raise Refuse("manifest: root must be an object")
    check_bounds(m)
    schema = _need(m, "schema", (str,), "root")
    if schema not in ("pointfile-units-report/1", "pointfile-units-report/2", "pointfile-units-report/3"):
        raise Refuse("manifest: unsupported schema %r" % schema)
    for sec in ("source", "output", "units", "grammar", "rounding"):
        _need(m, sec, (dict,), "root")
    for sec in ("source", "output"):
        _need(m[sec], "sha256", (str,), sec)
        if not re.fullmatch(r"[0-9A-Fa-f]{64}", m[sec]["sha256"]):
            raise Refuse("manifest: %s.sha256 is not a 64-hex digest" % sec)
    u = m["units"]
    conv = _need(u, "conversion", (str,), "units")
    if conv not in list(FACTORS) + ["Custom"]:
        raise Refuse("manifest: unknown conversion %r" % conv)
    if m["schema"] == "pointfile-units-report/3":
        for k in ("factor_numerator", "factor_denominator"):
            if not isinstance(u.get(k), str):
                raise Refuse("manifest: units.%s must be a string (exact quantities are strings in schema 3)" % k)
    fnum = _frac_from_manifest(u.get("factor_numerator"), "units.factor_numerator")
    fden = _frac_from_manifest(u.get("factor_denominator"), "units.factor_denominator")
    if fden == 0:
        raise Refuse("manifest: units.factor_denominator is zero")
    factor = fnum / fden
    if factor <= 0:
        raise Refuse("manifest: factor must be > 0")
    for k in ("source_unit", "target_unit"):
        _need(u, k, (str,), "units")
    if not isinstance(u.get("source_unit_reference", ""), str):
        raise Refuse("manifest: units.source_unit_reference must be a string")
    if u.get("custom_factor_input") is not None and not isinstance(u["custom_factor_input"], str):
        raise Refuse("manifest: units.custom_factor_input must be a string or null")
    g = m["grammar"]
    settings = {"format": _need(g, "format", (str,), "grammar"), "delimiter": _need(g, "delimiter", (str,), "grammar"),
                "header": _need(g, "header_policy", (str,), "grammar")}
    cf = _need(g, "coordinate_fields", (list,), "grammar")
    for c in cf:
        if isinstance(c, bool) or not isinstance(c, int):
            raise Refuse("manifest: grammar.coordinate_fields must be integers")
    idf = g.get("id_field")
    if idf is not None and (isinstance(idf, bool) or not isinstance(idf, int)):
        raise Refuse("manifest: grammar.id_field must be an integer or null")
    if settings["format"] == "CUSTOM":
        settings["coords"] = list(cf); settings["id"] = idf
    validate_settings(settings)
    if settings["format"] != "CUSTOM" and (list(cf) != FORMATS[settings["format"]]["coords"] or idf != FORMATS[settings["format"]]["id"]):
        raise Refuse("manifest contradiction: coordinate/id fields do not match format %s" % settings["format"])
    r = m["rounding"]
    if _need(r, "rule", (str,), "rounding") != "nearest, ties to even":
        raise Refuse("manifest: unsupported rounding rule %r" % r["rule"])
    if m["schema"] == "pointfile-units-report/3":
        acc = r.get("acceptance")
        if not isinstance(acc, str):
            raise Refuse("manifest: rounding.acceptance must be a string")
        if acc != ACCEPTANCE and legacy_adapter_for(acc) is None:
            raise Refuse("manifest contradiction: rounding.acceptance is neither the implemented rule text nor a known historical producer's text")
        fsd = r.get("finest_source_decimals")
        if not isinstance(fsd, int) or isinstance(fsd, bool) or fsd < 0:
            raise Refuse("manifest: rounding.finest_source_decimals must be a nonnegative integer")
        if g.get("comment_prefix") != "#":
            raise Refuse("manifest contradiction: grammar.comment_prefix %r is not the implemented '#'" % (g.get("comment_prefix"),))
        # exact nested key sets: an unknown semantic key is unsupported, not an annotation
        for sec, keys in NESTED_KEYS.items():
            if not isinstance(m.get(sec), dict):
                raise Refuse("manifest: %s must be an object" % sec)
            extra = sorted(set(m[sec]) - keys["allowed"]); missing = sorted(keys["required"] - set(m[sec]))
            if extra: raise Refuse("manifest: unknown field(s) in %s: %s" % (sec, ", ".join(extra)))
            if missing: raise Refuse("manifest: missing field(s) in %s: %s" % (sec, ", ".join(missing)))
    decimals = _need(r, "decimals", (int,), "rounding")
    if decimals < 0 or decimals > MAX_DECIMALS:
        raise Refuse("manifest: rounding.decimals must be 0..%d" % MAX_DECIMALS)
    anchors_raw = m.get("anchors", [])
    controls_raw = m.get("control_points", [])
    if not isinstance(anchors_raw, list) or not isinstance(controls_raw, list):
        raise Refuse("manifest: anchors and control_points must be lists")
    # shape rules that hold for every accepted schema (the legacy adapters validate what they access, R5-07)
    at = m.get("max_error_at")
    if at is not None and not (isinstance(at, list) and len(at) == 2 and all(isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in at)):
        raise Refuse("manifest: max_error_at must be null or [line, field] with nonnegative integers")
    if m.get("tool") is not None and not isinstance(m.get("tool"), dict):
        raise Refuse("manifest: tool must be an object or absent")
    for k in ("counts", "ranges", "checks"):
        if m.get(k) is not None and not isinstance(m.get(k), dict):
            raise Refuse("manifest: %s must be an object" % k)
    for k in ("warnings", "failures"):
        if m.get(k) is not None and not isinstance(m.get(k), list):
            raise Refuse("manifest: %s must be a list" % k)
    if m["schema"] == "pointfile-units-report/3":
        allowed = {"schema", "run_id", "content_fingerprint", "timestamp_utc", "tool", "source", "output", "units", "grammar", "rounding",
                   "counts", "checks", "max_error", "max_error_at", "ranges", "anchors", "control_points", "warnings", "verification_scope", "pass", "failures"}
        extra = sorted(set(m) - allowed)
        if extra:
            raise Refuse("manifest: unknown top-level field(s) %s (schema 3 defines an exact key set)" % ", ".join(extra))
        missing = sorted(allowed - set(m))
        if missing:
            raise Refuse("manifest: missing top-level field(s) %s" % ", ".join(missing))
        _need(m, "tool", (dict,), "root")
        for k in ("name", "version"):
            _text(_need(m["tool"], k, (str,), "tool"), "tool." + k, TEXT_LIMITS["short"])
        if not re.fullmatch(r"[0-9A-Fa-f]{16}", _need(m["tool"], "build", (str,), "tool")):
            raise Refuse("manifest: tool.build must be 16 hex characters")
        for sec in ("source", "output"):
            _text(_need(m[sec], "path", (str,), sec), sec + ".path", TEXT_LIMITS["path"])
        _text(m["units"].get("source_unit_reference", ""), "units.source_unit_reference", TEXT_LIMITS["reference"])
        dn = m["units"].get("declared_not_checked")
        if not isinstance(dn, list) or not all(isinstance(x, str) and len(x) <= TEXT_LIMITS["short"] for x in dn):
            raise Refuse("manifest: units.declared_not_checked must be a list of short strings")
        for k in ("run_id", "timestamp_utc", "verification_scope"):
            _text(m.get(k), k, TEXT_LIMITS["list_item"])
        _text(m["units"].get("source_unit"), "units.source_unit", TEXT_LIMITS["short"]); _text(m["units"].get("target_unit"), "units.target_unit", TEXT_LIMITS["short"])
        if m["units"].get("custom_factor_input") is not None: _text(m["units"]["custom_factor_input"], "units.custom_factor_input", TEXT_LIMITS["short"])
        for sec in ("source", "output"):
            b = _need(m[sec], "bytes", (int,), sec)
            if b < 0: raise Refuse("manifest: %s.bytes must be nonnegative" % sec)
            if _need(m[sec], "encoding", (str,), sec) not in ("utf-8", "utf-8-bom"):
                raise Refuse("manifest: %s.encoding must be utf-8 or utf-8-bom" % sec)
        at = m.get("max_error_at")
        if at is not None and not (isinstance(at, list) and len(at) == 2 and all(isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in at)):
            raise Refuse("manifest: max_error_at must be null or [line, field] with nonnegative integers")
        if not isinstance(m.get("max_error"), str): raise Refuse("manifest: max_error must be a string")
        cnt = _need(m, "counts", (dict,), "root")
        if set(cnt) != {"data", "header", "comment", "blank"} or not all(isinstance(cnt[k], int) and not isinstance(cnt[k], bool) and cnt[k] >= 0 for k in cnt):
            raise Refuse("manifest: counts must have integer data/header/comment/blank")
        rg = _need(m, "ranges", (dict,), "root")
        for k, v in rg.items():
            if not re.fullmatch(r"[0-9]+", str(k)) or not (isinstance(v, list) and len(v) == 2 and all(x is None or isinstance(x, str) for x in v)):
                raise Refuse("manifest: ranges must map field index to [min, max] strings or null")
        ch = _need(m, "checks", (dict,), "root")
        if set(ch) != {"arithmetic_and_reconstruction", "record_accounting", "non_coordinate_preservation"} or not all(ch[k] in ("pass", "fail") for k in ch):
            raise Refuse("manifest: checks must hold the three named statuses as pass/fail")
        if not isinstance(m.get("failures"), list) or not all(isinstance(x, str) and len(x) <= 2000 for x in m["failures"]):
            raise Refuse("manifest: failures must be a list of strings (each at most 2000 characters)")
        if not isinstance(m.get("warnings"), list) or not all(isinstance(x, str) and len(x) <= 2000 for x in m["warnings"]):
            raise Refuse("manifest: warnings must be a list of strings (each at most 2000 characters)")
        if not isinstance(m.get("pass"), bool): raise Refuse("manifest: pass must be a boolean")
        for k in ("run_id", "timestamp_utc", "verification_scope"):
            if not isinstance(m.get(k), str): raise Refuse("manifest: %s must be a string" % k)
        if m.get("content_fingerprint") is not None and not re.fullmatch(r"[0-9a-f]{16}", str(m.get("content_fingerprint"))):
            raise Refuse("manifest: content_fingerprint must be 16 lowercase hex characters or null")

    def agree(display, exact, what):
        for v in (display, exact):
            if v is not None and not isinstance(v, str):
                raise Refuse("manifest: %s must be a string or null (exact quantities are strings)" % what)
        if display is None and exact is None:
            return None
        d = None if display is None else _frac_from_manifest(display, what + " (display)")
        e = None if exact is None else _frac_from_manifest(exact, what + " (exact)")
        if d is not None and e is not None and d != e:
            raise Refuse("manifest contradiction: %s display value %r does not equal exact value %r" % (what, display, exact))
        return e if e is not None else d
    anchors = []
    for x in anchors_raw:
        if not isinstance(x, dict):
            raise Refuse("manifest: each anchor must be an object")
        extra = sorted(set(x) - ANCHOR_KEYS["allowed"]); missing = sorted(ANCHOR_KEYS["required"] - set(x))
        if extra: raise Refuse("manifest: unknown field(s) in anchor: %s" % ", ".join(extra))
        if missing: raise Refuse("manifest: missing field(s) in anchor: %s" % ", ".join(missing))
        fld = _need(x, "field", (int,), "anchor")
        lo = agree(x.get("min"), x.get("min_exact"), "anchor field %d min" % fld)
        hi = agree(x.get("max"), x.get("max_exact"), "anchor field %d max" % fld)
        if not isinstance(x.get("pass"), bool):
            raise Refuse("manifest: anchor field %d lacks a boolean pass" % fld)
        for k in ("observed_min", "observed_max"):
            if x.get(k) is not None and not isinstance(x.get(k), str):
                raise Refuse("manifest: anchor field %d %s must be a string or null" % (fld, k))
        anchors.append({"field": fld, "min": lo, "max": hi, "min_text": x.get("min"), "max_text": x.get("max"), "recorded_pass": x["pass"], "recorded": x})
    control = []
    for x in controls_raw:
        if not isinstance(x, dict):
            raise Refuse("manifest: each control point must be an object")
        extra = sorted(set(x) - CONTROL_KEYS["allowed"]); missing = sorted(CONTROL_KEYS["required"] - set(x))
        if extra: raise Refuse("manifest: unknown field(s) in control point: %s" % ", ".join(extra))
        if missing: raise Refuse("manifest: missing field(s) in control point: %s" % ", ".join(missing))
        cid = _text(_need(x, "id", (str,), "control point"), "control point id", TEXT_LIMITS["list_item"])
        if x.get("note") is not None: _text(x["note"], "control point note", TEXT_LIMITS["list_item"])
        disp, exact = x.get("expected"), x.get("expected_exact")
        if disp is None and exact is None:
            raise Refuse("manifest: control point %r lacks expected values" % cid)
        for lst, nm in ((disp, "expected"), (exact, "expected_exact")):
            if lst is not None and not isinstance(lst, list):
                raise Refuse("manifest: control point %r %s must be a list" % (cid, nm))
        n = len(exact if exact is not None else disp)
        if disp is not None and exact is not None and len(disp) != len(exact):
            raise Refuse("manifest contradiction: control point %r has %d display and %d exact expected values" % (cid, len(disp), len(exact)))
        vals = [agree(disp[i] if disp is not None else None, exact[i] if exact is not None else None, "control %s value %d" % (cid, i)) for i in range(n)]
        if any(v is None for v in vals):
            raise Refuse("manifest: control point %r has a null expected value" % cid)
        tol = agree(x.get("tolerance"), x.get("tolerance_exact"), "control %s tolerance" % cid)
        if tol is None:
            raise Refuse("manifest: control point %r lacks a tolerance" % cid)
        if not isinstance(x.get("pass"), bool):
            raise Refuse("manifest: control point %r lacks a boolean pass" % cid)
        if x.get("written") is not None and not (isinstance(x["written"], list) and all(isinstance(w, str) for w in x["written"])):
            raise Refuse("manifest: control point %r written must be a list of strings or absent" % cid)
        if x.get("line") is not None and (not isinstance(x["line"], int) or isinstance(x["line"], bool)):
            raise Refuse("manifest: control point %r line must be an integer or absent" % cid)
        if x.get("checked_fields") is not None and not (isinstance(x["checked_fields"], list) and all(isinstance(c, int) and not isinstance(c, bool) for c in x["checked_fields"])):
            raise Refuse("manifest: control point %r checked_fields must be a list of integers" % cid)
        control.append({"id": cid, "values": vals, "tol": tol, "values_text": disp, "tol_text": x.get("tolerance"), "recorded_pass": x["pass"], "recorded": x})
    return {"settings": settings, "factor": factor, "decimals": decimals, "anchors": anchors, "control": control, "conversion": conv}


def verify_record(src, out, m, verifier_build, verifier_version=VERSION, record_bytes=None):
    """Standalone re-verification as a function: used by `verify` and, before publication, by `convert` (R5-04).
    Returns a re-verification record. Never raises for a malformed record: that is an 'unsupported' outcome."""
    result = {"schema": "pointfile-units-reverification/1", "verifier": {"name": "pointfile_units.py", "version": verifier_version, "build": verifier_build},
              "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "record_schema": m.get("schema") if isinstance(m, dict) else None, "producer_build": None,
              "source_sha256": sha256(src), "output_sha256": sha256(out),
              "record_file_sha256": sha256(record_bytes) if record_bytes is not None else None,   # the bytes actually received (R6-03)
              "record_canonical_sha256": None, "record_canonicalization": "canonical-json/1",
              "adapter": None,
              "files_pass": None, "report_consistent": None, "unsupported": None, "fresh_failures": [], "consistency_failures": [], "rechecked": [], "not_checked": []}
    try:
        if isinstance(m, dict):
            result["record_canonical_sha256"] = sha256(canonical_json(m).encode("utf-8"))
    except Exception:
        result["record_canonical_sha256"] = None
    try:
        v = validate_manifest(m)
    except Refuse as ex:
        result["unsupported"] = str(ex); return result
    settings, factor, decimals, anchors, control, conv = v["settings"], v["factor"], v["decimals"], v["anchors"], v["control"], v["conversion"]
    result["producer_build"] = (m.get("tool") or {}).get("build")
    if legacy_adapter_for((m.get("rounding") or {}).get("acceptance")) is not None:
        result["adapter"] = legacy_adapter_for(m["rounding"]["acceptance"])
        result["not_checked"].append("rounding.acceptance text is a known historical producer's sentence; verified under the current rule (" + result["adapter"] + ")")
    fresh, consistency, rechecked = result["fresh_failures"], result["consistency_failures"], result["rechecked"]
    u = m["units"]
    if result["source_sha256"] != str(m["source"]["sha256"]).lower(): fresh.append("source hash differs from manifest")
    if result["output_sha256"] != str(m["output"]["sha256"]).lower(): fresh.append("output hash differs from manifest")
    rechecked.append("source and output SHA-256 against the files given (case-insensitive)")
    if conv in FACTORS:
        cf, cin, cout = FACTORS[conv]
        if factor != cf or u.get("source_unit") != cin or u.get("target_unit") != cout:
            consistency.append("conversion %s implies factor %d/%d (%s -> %s) but manifest states %s (%s -> %s)" %
                               (conv, cf.numerator, cf.denominator, cin, cout, ratstr(factor), u.get("source_unit"), u.get("target_unit")))
    else:
        inp = u.get("custom_factor_input")
        if inp is None: consistency.append("custom conversion without custom_factor_input")
        else:
            try: declared = parse_factor("Custom", inp)[0]
            except Refuse as ex: consistency.append("custom_factor_input is invalid: %s" % ex); declared = None
            if declared is not None and declared != factor:
                consistency.append("custom_factor_input %r equals %s but the exact factor recorded is %s" % (inp, ratstr(declared), ratstr(factor)))
    rechecked.append("declared conversion against the exact factor and unit labels")
    rechecked.append("field mapping against the declared format; display and exact fields of anchors and control points agree; fixed rule texts match the implementation")
    rep = verify_bytes(src, out, settings, factor, decimals, anchors, control)
    rechecked.append("record accounting, non-coordinate preservation, exact rounding (floor-interval procedure), reverse error and reconstruction for every coordinate")
    if anchors: rechecked.append("%d anchor bound(s) from the manifest" % len(anchors))
    if control: rechecked.append("%d control point(s) from the manifest" % len(control))
    fresh += rep["failures"]
    try: finest = finest_source_decimals(src, settings)
    except (Refuse, UnicodeDecodeError): finest = None
    observed = observation_structure(rep, len(src), len(out), src.startswith(b"\xef\xbb\xbf"), out.startswith(b"\xef\xbb\xbf"), finest)
    recorded = recorded_observation_structure(m)
    compared = []
    for key in OBSERVED_FIELDS:
        if m["schema"] != "pointfile-units-report/3" and recorded.get(key) is None and key not in ("counts", "ranges", "max_error", "max_error_at"):
            result["not_checked"].append("%s (absent in %s)" % (key, m["schema"])); continue
        compared.append(key)
        if canonical_json(observed.get(key)) != canonical_json(recorded.get(key)):
            consistency.append("recorded %s differs from observed: recorded %s, observed %s" % (key, json.dumps(recorded.get(key), ensure_ascii=True)[:160], json.dumps(observed.get(key), ensure_ascii=True)[:160]))
    if m.get("pass") is not True:
        consistency.append("manifest records pass=%r; a report of a failed run cannot be verified as a success" % (m.get("pass"),))
    if m["schema"] == "pointfile-units-report/3":
        try:
            fp = content_fingerprint(m)
            if m.get("content_fingerprint") != fp:
                if m.get("content_fingerprint") == content_fingerprint_legacy(m):
                    result["not_checked"].append("content_fingerprint matched only under the v3.3.1 legacy spelling rule (digests hashed as recorded)")
                else:
                    consistency.append("recorded content_fingerprint %r differs from recomputed %r" % (m.get("content_fingerprint"), fp))
        except (KeyError, TypeError) as ex:
            consistency.append("content_fingerprint could not be recomputed: %s" % ex)
        rechecked.append("recorded observation structure (%s) and content fingerprint against fresh observations" % ", ".join(compared))
    else:
        rechecked.append("recorded observation structure (%s) against fresh observations via the %s adapter (fingerprint not defined for that schema)" % (", ".join(compared), m["schema"]))
    result["files_pass"] = not fresh; result["report_consistent"] = not consistency
    return result


def print_reverification(res):
    if res["unsupported"] is not None:
        print("VERIFY UNSUPPORTED"); print("  " + res["unsupported"]); print("record schema: %s; verifier build %s" % (res["record_schema"], res["verifier"]["build"])); return
    ok = res["files_pass"] and res["report_consistent"]
    print("VERIFY %s" % ("PASS" if ok else "FAIL"))
    print("files pass a fresh verification under the manifest's settings: %s" % ("yes" if res["files_pass"] else "no"))
    for f in res["fresh_failures"]: print("  " + f)
    print("report is internally consistent with the fresh observations: %s" % ("yes" if res["report_consistent"] else "no"))
    for c in res["consistency_failures"]: print("  " + c)
    print("producer build: %s   verifier build: %s (%s %s)%s" % (res["producer_build"], res["verifier"]["build"], res["verifier"]["name"], res["verifier"]["version"], ("   adapter: " + res["adapter"]) if res.get("adapter") else ""))
    print("record file sha256: %s   record canonical sha256 (%s): %s" % (res["record_file_sha256"], res["record_canonicalization"], res["record_canonical_sha256"]))
    print("source sha256: %s   output sha256: %s" % (res["source_sha256"], res["output_sha256"]))
    print("rechecked: " + "; ".join(res["rechecked"]))
    if res["not_checked"]: print("not checked (record lacks the field): " + "; ".join(res["not_checked"]))
    print("not checked: which foot the survey used, its datum, or that the file belongs to the intended site")


def tool_build():
    return sha256(open(__file__, "rb").read())[:16]


def same_file(a, b):
    """Filesystem identity where the OS gives it (inode/device, which also covers hard links and symlinks), else
    normalised absolute path with the platform's case rule."""
    try:
        if os.path.exists(a) and os.path.exists(b) and os.path.samefile(a, b):
            return True
    except OSError:
        pass
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


class PublicationFailure(Exception):
    pass


def publish_result(path, res, inputs):
    """R6-01/R7-05: a verification result may only be written to a path that is not any input and does not exist.
    Exclusive creation is the final guard; the complete JSON is serialized before the file is created. Every expected
    filesystem failure inside this boundary is a PublicationFailure (exit 4), never a verification failure; a partial
    file created by this call is removed and the outcome is reported accurately."""
    for other in inputs:
        if same_file(path, other):
            raise PublicationFailure("--result %s is the same file as an input (%s); refused, nothing written" % (path, other))
    if os.path.lexists(path):
        raise PublicationFailure("--result %s already exists; refused, nothing written (choose a new name)" % path)
    data = json.dumps(res, indent=2, ensure_ascii=True).encode("utf-8")
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        raise PublicationFailure("--result %s appeared between the check and creation; refused, nothing overwritten" % path)
    except OSError as ex:
        raise PublicationFailure("--result %s could not be created (%s: %s); nothing written" % (path, type(ex).__name__, ex))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data); fh.flush(); os.fsync(fh.fileno())
    except OSError as ex:
        try:
            os.remove(path); retained = "the partial file created by this run was removed"
        except OSError as ex2:
            retained = "a partial file may remain at %s (%s)" % (path, ex2)
        raise PublicationFailure("--result %s could not be written completely (%s: %s); %s" % (path, type(ex).__name__, ex, retained))


def cmd_verify(a):
    try:
        with open(a.manifest, "rb") as fh:
            record_bytes = fh.read()
        raw = record_bytes.decode("utf-8", "strict")
    except (OSError, ValueError) as ex:
        raise Refuse("cannot read manifest: %s" % ex)
    try:
        m = load_record_text(raw)
    except Refuse as ex:
        print("VERIFY UNSUPPORTED"); print("  " + str(ex)); return 3
    try:
        with open(a.source, "rb") as fh: src = fh.read()
        with open(a.output, "rb") as fh: out = fh.read()
    except OSError as ex:
        raise Refuse("cannot read input: %s" % ex)
    res = verify_record(src, out, m, tool_build(), record_bytes=record_bytes)
    print_reverification(res)
    rc = 3 if res["unsupported"] is not None else (0 if (res["files_pass"] and res["report_consistent"]) else 2)
    if getattr(a, "result", None):
        try:
            publish_result(a.result, res, [a.source, a.output, a.manifest])
            print("result written: %s" % a.result)
        except PublicationFailure as ex:
            print("RESULT NOT WRITTEN: %s" % ex)
            print("(the verification verdict above stands: %s; only the result-file publication failed)" % ("PASS" if rc == 0 else "FAIL" if rc == 2 else "UNSUPPORTED"))
            return 4
    return rc


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")   # explicit console policy on every platform
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("convert")
    c.add_argument("--in", dest="input", required=True); c.add_argument("--out", dest="output", required=True)
    c.add_argument("--format", required=True, choices=list(FORMATS) + ["CUSTOM"])
    c.add_argument("--coords", help="CUSTOM: zero-based coordinate fields, e.g. 1,2,3")
    c.add_argument("--id-field", help="CUSTOM: zero-based identifier field")
    c.add_argument("--conversion", required=True, choices=list(FACTORS) + ["Custom"])
    c.add_argument("--custom-factor", help="decimal or a/b, for --conversion Custom")
    c.add_argument("--delimiter", default="auto", choices=["auto", "whitespace", "comma"])
    c.add_argument("--header", default="no", choices=["auto", "yes", "no"], help="first content line: no (default) = data; yes = header; auto = header only if it has no numeric token (explicit opt-in)")
    c.add_argument("--decimals", default="auto", help="auto or an integer <= %d" % MAX_DECIMALS)
    c.add_argument("--anchor", action="append", help="field:min:max in target units (repeatable; blank bound allowed)")
    c.add_argument("--control-point", action="append", help="'id v1 v2 v3 tol' in target units (repeatable)")
    c.add_argument("--source-unit-reference", default="", help="document establishing the source unit (recorded, not checked)")
    c.add_argument("--force-mapping", action="store_true", help="proceed despite a consecutive-integer coordinate warning")
    c.add_argument("--dry-run", action="store_true")
    v = sub.add_parser("verify")
    v.add_argument("--source", required=True); v.add_argument("--output", required=True); v.add_argument("--manifest", required=True)
    v.add_argument("--result", help="write a machine-readable re-verification record (JSON) to this path")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "convert":
            if a.decimals != "auto":
                if not re.fullmatch(r"[0-9]+", a.decimals) or int(a.decimals) > MAX_DECIMALS:
                    raise Refuse("--decimals must be auto or 0..%d" % MAX_DECIMALS)
            return cmd_convert(a)
        return cmd_verify(a)
    except Refuse as ex:
        sys.stderr.write("REFUSED: %s\n" % ex)
        return 2
    except (OSError, UnicodeDecodeError, ValueError, ZeroDivisionError) as ex:
        # expected input/filesystem failures become structured refusals; programming errors still traceback (N4)
        sys.stderr.write("REFUSED: %s: %s\n" % (type(ex).__name__, ex))
        return 2


if __name__ == "__main__":
    try:
        import signal
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)   # not available on Windows; a closed pipe is not an error
    except (AttributeError, ValueError):
        pass
    sys.exit(main())
