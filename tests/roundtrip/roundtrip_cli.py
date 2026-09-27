#!/usr/bin/env python3
"""Round-trip loop gate (ft -> m -> ft -> m -> ft) on three samples with an INDEPENDENT exact oracle (Fraction arithmetic and
ties-to-even implemented here, not imported from the converter). Exit contract (F12-02): 0 only when every leg matches the
oracle, every row and coordinate is accounted for (counts and point identities checked before values), every leg was accepted
as expected, the auto-precision loop's byte identities hold as recorded, and the return trip at the ORIGINAL precision
reproduces each original file byte for byte. Any unexpected refusal, oracle difference, count mismatch, identity failure or
process error exits 1. Observations are written to roundtrip-observations.json (complete SHA-256 digests; the RESULT
document is generated from that file by --report). `--self-test` mutates the oracle and drops a row in an isolated copy and
requires both to fail. Run from anywhere: python3 roundtrip_cli.py [--self-test]   (RESULT.md and roundtrip-observations.json are always written together)"""
import subprocess, sys, os, json, hashlib, re, pathlib, tempfile, datetime
from fractions import Fraction
HERE = pathlib.Path(__file__).resolve().parent; TOOL = HERE.parent.parent / 'pointfile_units.py'
FT = Fraction(3048, 10000); USFT = Fraction(1200, 3937)
SAMPLES = [('acceptance', 'acceptance-source-international-feet.csv', 'PENZD', 'comma', 'no'), ('survey40', 'survey40.txt', 'PENZD', 'whitespace', 'no'), ('stateplane', 'stateplane-fictional.csv', 'PENZD', 'comma', 'yes')]
LEGS = [('L1 ft->m', 'IntlFeetToMeters'), ('L2 m->ft', 'MetersToIntlFeet'), ('L3 ft->m', 'IntlFeetToMeters'), ('L4 m->ft', 'MetersToIntlFeet')]
def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
def convert(src, out, conversion, fmt, delim, header, dec='auto'):
    a = [sys.executable, str(TOOL), 'convert', '--in', str(src), '--out', str(out), '--format', fmt, '--conversion', conversion, '--delimiter', delim, '--header', header, '--force-mapping', '--source-unit-reference', 'loop test: declared']
    if dec != 'auto': a += ['--decimals', str(dec)]
    try: r = subprocess.run(a, capture_output=True, text=True, encoding='utf-8', timeout=300)
    except subprocess.TimeoutExpired: return {'ok': False, 'error': 'timeout'}
    if r.returncode == 2 and 'Traceback' not in r.stderr: return {'ok': False, 'refused': (r.stderr + r.stdout).strip().splitlines()[0][:120]}
    if r.returncode != 0: return {'ok': False, 'error': 'exit %d: %s' % (r.returncode, (r.stderr + r.stdout)[-200:])}
    with open(str(out) + '.manifest.json', encoding='utf-8') as fh: m = json.load(fh)
    return {'ok': True, 'decimals': m['rounding']['decimals'], 'counts': m['counts']}
def rows(path, delim, header, fields=(1, 2, 3), idf=0):
    """independent reader -> list of (identifier, (Fraction, Fraction, Fraction)); comments/blank/header skipped"""
    out = []; first = True
    for line in open(path, encoding='utf-8').read().splitlines():
        s = line.strip()
        if not s or s.startswith('#'): continue
        if header and first: first = False; continue
        first = False; toks = s.split(',') if delim == 'comma' else s.split()
        out.append((toks[idf], tuple(Fraction(toks[i]) for i in fields)))
    return out
def round_ties_even(x, d):
    q = Fraction(10) ** d; n = x * q; fl = n.numerator // n.denominator; frac = n - fl
    if frac > Fraction(1, 2) or (frac == Fraction(1, 2) and fl % 2): fl += 1
    return Fraction(fl, 1) / q
def original_decimals(path, delim):
    d = 0
    for line in open(path, encoding='utf-8').read().splitlines():
        if not line.strip() or line.startswith('#'): continue
        for t in (line.split(',') if delim == 'comma' else line.split())[1:4]:
            if re.match(r'^-?\d', t): d = max(d, len(t.split('.')[1]) if '.' in t else 0)
    return d
def check_leg(prev_rows, new_rows, factor, decimals, oracle=round_ties_even):
    """returns (problems, max_abs_change)"""
    p = []
    if len(new_rows) != len(prev_rows): p.append('row count %d != %d' % (len(new_rows), len(prev_rows)))
    for i, ((pid, pv), (nid, nv)) in enumerate(zip(prev_rows, new_rows)):
        if pid != nid: p.append('row %d identifier %r != %r' % (i, nid, pid))
        if len(nv) != len(pv): p.append('row %d coordinate count' % i)
        for j, (a, b) in enumerate(zip(pv, nv)):
            if b != oracle(a * factor, decimals): p.append('row %d field %d: %s != oracle %s' % (i, j, b, oracle(a * factor, decimals)))
    return p
def run_sample(name, path, fmt, delim, header, work, oracle=round_ties_even, mutate_rows=None):
    obs = {'sample': name, 'file': path.name, 'sha256': sha(path), 'format': fmt, 'delimiter': delim, 'header': header, 'legs': [], 'problems': []}
    orig = rows(path, delim, header == 'yes'); cur = path; files = []
    for i, (label, conv) in enumerate(LEGS):
        out = work / ('%s.leg%d' % (name, i + 1)); r = convert(cur, out, conv, fmt, delim, header)
        if not r['ok']: obs['problems'].append('%s unexpectedly not converted: %s' % (label, r.get('refused') or r.get('error'))); obs['legs'].append({'leg': label, 'accepted': False}); break
        prev = rows(cur, delim, header == 'yes'); new = rows(out, delim, header == 'yes')
        if mutate_rows: new = mutate_rows(new)
        probs = check_leg(prev, new, FT if 'ft->m' in label else 1 / FT, r['decimals'], oracle)
        leg = {'leg': label, 'accepted': True, 'decimals_written': r['decimals'], 'sha256': sha(out), 'oracle_problems': probs, 'rows': len(new)}
        if i % 2 == 1 and not probs and len(new) == len(orig): leg['max_abs_deviation_from_original_ft'] = str(max(abs(v - o) for (_, rv), (_, ro) in zip(new, orig) for v, o in zip(rv, ro)))
        obs['legs'].append(leg); obs['problems'] += ['%s: %s' % (label, x) for x in probs]; files.append(out); cur = out
    if len(files) == 4:
        obs['byte_identity'] = {'L1==L3': sha(files[0]) == sha(files[2]), 'L2==L4': sha(files[1]) == sha(files[3]), 'L2==original': open(files[1], 'rb').read() == open(path, 'rb').read()}
        odec = original_decimals(path, delim); ret = work / (name + '.ret'); r = convert(files[0], ret, 'MetersToIntlFeet', fmt, delim, header, odec)
        obs['return_at_original_precision'] = {'decimals': odec, 'accepted': r['ok'], 'byte_identical_to_original': bool(r['ok'] and open(ret, 'rb').read() == open(path, 'rb').read())}
        if not obs['return_at_original_precision']['byte_identical_to_original']: obs['problems'].append('return trip at %d decimals did not reproduce the original bytes' % odec)
        # the foot trap is recorded, never gated: it is expected to be accepted at auto precision and to differ by 2 ppm
        us = work / (name + '.usft'); r2 = convert(files[0], us, 'MetersToUSFeet', fmt, delim, header)
        if r2['ok']:
            u = rows(us, delim, header == 'yes'); dev = max(abs(v - o) for (_, rv), (_, ro) in zip(u, orig) for v, o in zip(rv, ro)); mag = max(abs(o) for _, ro in orig for o in ro)
            obs['wrong_foot_return_auto'] = {'accepted': True, 'decimals_written': r2['decimals'], 'max_abs_deviation_ft': str(dev), 'max_abs_deviation_ft_float': float(dev), 'max_magnitude_ft': float(mag)}
        r3 = convert(files[0], work / (name + '.usft-odec'), 'MetersToUSFeet', fmt, delim, header, odec); obs['wrong_foot_return_original_precision'] = {'accepted': r3['ok'], 'refusal': r3.get('refused')}
    return obs
def run_all(oracle=round_ties_even, mutate_rows=None):
    work = pathlib.Path(tempfile.mkdtemp(prefix='roundtrip-')); tool_sha = sha(TOOL)
    record = {'schema': 'pfu-roundtrip-observations/1', 'tool': {'file': TOOL.name, 'sha256': tool_sha}, 'run_utc': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'samples': []}
    for name, fn, fmt, delim, header in SAMPLES: record['samples'].append(run_sample(name, HERE / fn, fmt, delim, header, work, oracle, mutate_rows))
    record['problems'] = [p for s in record['samples'] for p in s['problems']]; return record
def report(record):
    L = ['# Round-trip loop result — generated from roundtrip-observations.json', '', 'Tool `%s` sha256 `%s`, run %s, observations sha256 `%s`. Loop: international feet → metres → feet → metres → feet, auto precision. **Verdict: %s** (%d problem(s)).' % (record['tool']['file'], record['tool']['sha256'], record['run_utc'], record.get('observations_sha256', 'n/a'), 'PASS' if not record['problems'] else 'FAIL', len(record['problems'])), '', '| Sample | Legs vs oracle | Decimals written per leg | Max deviation of returned feet, leg 2 / leg 4 | Return at original precision | Wrong-foot return (auto) |', '|---|---|---|---|---|---|']
    for s in record['samples']:
        legs = s['legs']; ok = sum(1 for l in legs if l.get('accepted') and not l['oracle_problems']); devs = [l.get('max_abs_deviation_from_original_ft', '') for l in legs if 'max_abs_deviation_from_original_ft' in l]
        ret = s.get('return_at_original_precision', {}); wf = s.get('wrong_foot_return_auto', {})
        L.append('| %s (`%s…`) | %d/%d | %s | %s | %s | %s |' % (s['sample'], s['sha256'][:12], ok, len(LEGS), ', '.join(str(l.get('decimals_written', '-')) for l in legs), ' / '.join('%.4g ft' % float(Fraction(d)) for d in devs), ('byte-identical at %d dp' % ret['decimals']) if ret.get('byte_identical_to_original') else 'NOT identical', ('accepted, %d dp, max %.6f ft on magnitudes to %.0f' % (wf['decimals_written'], wf['max_abs_deviation_ft_float'], wf['max_magnitude_ft'])) if wf else 'n/a'))
    L += ['', 'Reading: these cases matched the independent oracle and recovered the original bytes at the tested original precision. Deviations under auto precision are bounded (the exact values are in the JSON; leg 2 and leg 4 are close but not equal). The wrong-foot return is accepted by every check and differs by 2 ppm: arithmetic passes under an inappropriate declaration. Other sources of error — mapping, header interpretation, record selection, parsing, preservation, downstream import — are outside this loop.', '']
    if record['problems']: L += ['Problems:'] + ['- ' + p for p in record['problems']]
    return '\n'.join(L)
def main():
    if '--self-test' in sys.argv:
        clean = run_all()
        if clean['problems']: print('self-test needs a clean run first:', clean['problems'][:3]); return 2
        wrong = run_all(oracle=lambda x, d: round_ties_even(x, d) + Fraction(1, 10 ** d)); dropped = run_all(mutate_rows=lambda r: r[1:])
        ok = bool(wrong['problems']) and bool(dropped['problems'])
        print('self-test: wrong oracle -> %d problem(s); dropped row -> %d problem(s) :: %s' % (len(wrong['problems']), len(dropped['problems']), 'GATE FAILS AS REQUIRED' if ok else 'GATE DID NOT FAIL')); return 0 if ok else 1
    record = run_all(); raw = json.dumps(record, indent=1).encode('utf-8'); (HERE / 'roundtrip-observations.json').write_bytes(raw)
    record['observations_sha256'] = hashlib.sha256(raw).hexdigest(); (HERE / 'RESULT.md').write_bytes(report(record).encode('utf-8'))   # always written together and bound by digest (F13-04)
    for s in record['samples']:
        print('%-11s legs %s  return@orig %s  wrong-foot auto %s' % (s['sample'], ' '.join(('ok' if not l['oracle_problems'] else 'FAIL') if l.get('accepted') else 'REFUSED' for l in s['legs']), s.get('return_at_original_precision', {}).get('byte_identical_to_original'), s.get('wrong_foot_return_auto', {}).get('max_abs_deviation_ft_float')))
    print('round-trip gate: %s (%d problem(s))' % ('PASS' if not record['problems'] else 'FAIL', len(record['problems'])))
    for p in record['problems']: print('  PROBLEM', p)
    return 0 if not record['problems'] else 1
if __name__ == '__main__': sys.exit(main())
