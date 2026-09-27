#!/usr/bin/env python3
"""Differential comparator with complete expectations (F11-01). Exit 0 only when every case matches its expectation exactly.
   ok       -> both converted; identical bytes (Base64) and identical written precision
   refuse   -> both refused (kind 'refusal'); PointTruth's code and the Python category equal the values pinned for the case
   policy:X -> X is one of corpus.json's enumerated policies; PointTruth refused with the pinned code; Python converted to the
               pinned bytes at the pinned precision
Any ERROR kind, missing or extra result, duplicate id, unknown policy id, or other combination fails.
`--self-test` mutates copies of the results and requires the comparator to fail for each mutation, including every exception
path the review found open: policy bytes, policy precision, policy refusal code, unknown policy id, and a refusal code changed
to an unenumerated value. It works on copies and writes nothing."""
import json, pathlib, sys, copy, base64
HERE = pathlib.Path(__file__).resolve().parent

def load(name):
    with open(HERE / name, encoding='utf-8') as fh: return json.load(fh)

def evaluate(corpus, pt, py):
    C = corpus['cases']; POL = corpus['policies']; problems = []; tally = {'ok': 0, 'refuse': 0, 'policy': 0}
    names = [c['name'] for c in C]
    if len(names) != len(set(names)): problems.append('duplicate case ids')
    for extra in (set(pt) | set(py)) - set(names): problems.append('%s: result present for a case not in the corpus' % extra)
    for c in C:
        n = c['name']; a = pt.get(n); b = py.get(n)
        if a is None or b is None: problems.append('%s: missing result (%s)' % (n, 'pointtruth' if a is None else 'python')); continue
        bad = False
        for side, x in (('pointtruth', a), ('python', b)):
            if not x.get('ok') and x.get('kind') != 'refusal': problems.append('%s: %s ERROR %s %s' % (n, side, x.get('code'), str(x.get('msg', ''))[:80])); bad = True
        if bad: continue
        e = c['expect']
        if e == 'ok':
            if not (a['ok'] and b['ok']): problems.append('%s: expected both ok; pointtruth %s python %s' % (n, 'ok' if a['ok'] else a.get('code'), 'ok' if b['ok'] else b.get('code')))
            elif a['bytes_b64'] != b['bytes_b64'] or a['decimals'] != b['decimals']: problems.append('%s: bytes or written precision differ' % n)
            else: tally['ok'] += 1
        elif e == 'refuse':
            if a['ok'] or b['ok']: problems.append('%s: expected both refuse; pointtruth %s python %s' % (n, 'ok' if a['ok'] else a.get('code'), 'ok' if b['ok'] else b.get('code')))
            elif a.get('code') != c.get('pt_code'): problems.append('%s: pointtruth refusal code %s, pinned %s' % (n, a.get('code'), c.get('pt_code')))
            elif b.get('code') != c.get('py_category'): problems.append('%s: python refusal category %s, pinned %s' % (n, b.get('code'), c.get('py_category')))
            else: tally['refuse'] += 1
        elif e.startswith('policy:'):
            pid = e[len('policy:'):]; pol = POL.get(pid)
            if pol is None: problems.append('%s: unknown policy id %r (enumerated: %s)' % (n, pid, ', '.join(sorted(POL)))); continue
            if pol['case'] != n: problems.append('%s: policy %s is pinned to case %s' % (n, pid, pol['case'])); continue
            if a['ok'] or not b['ok']: problems.append('%s: policy %s expects pointtruth to refuse and python to convert; got pointtruth %s python %s' % (n, pid, 'ok' if a['ok'] else a.get('code'), 'ok' if b['ok'] else b.get('code'))); continue
            if a.get('code') != pol['pt_code']: problems.append('%s: policy %s pointtruth code %s, pinned %s' % (n, pid, a.get('code'), pol['pt_code'])); continue
            exp_b64 = base64.b64encode(pol['py_output'].encode('utf-8')).decode('ascii')
            if b['bytes_b64'] != exp_b64: problems.append('%s: policy %s python output differs from the hand-derived expectation' % (n, pid)); continue
            if b['decimals'] != pol['py_decimals']: problems.append('%s: policy %s python precision %s, pinned %s' % (n, pid, b['decimals'], pol['py_decimals'])); continue
            tally['policy'] += 1
        else: problems.append('%s: unknown expectation %r' % (n, e))
    return problems, tally

def self_test(corpus, pt, py):
    base, _ = evaluate(corpus, pt, py)
    if base: print('self-test requires a clean run first; problems:', base[:3]); return 2
    C = corpus['cases']; POL = corpus['policies']
    first_ok = next(c['name'] for c in C if c['expect'] == 'ok'); first_ref = next(c['name'] for c in C if c['expect'] == 'refuse')
    pol_id, pol = next(iter(POL.items())); pol_case = pol['case']
    def mut(label, fpt=None, fpy=None, fc=None):
        p = copy.deepcopy(pt); q = copy.deepcopy(py); k = copy.deepcopy(corpus)
        if fpt: fpt(p)
        if fpy: fpy(q)
        if fc: fc(k)
        probs, _ = evaluate(k, p, q); print('  %-58s -> %d problem(s) %s' % (label, len(probs), 'FAILS AS REQUIRED' if probs else 'NOT DETECTED')); return bool(probs)
    results = [
        mut('ok case: corrupted output bytes', fpt=lambda p: p[first_ok].update(bytes_b64='V1JPTkc=')),
        mut('ok case: written precision changed', fpy=lambda q: q[first_ok].update(decimals=q[first_ok]['decimals'] + 1)),
        mut('all cases: simulated crashes on both sides', fpt=lambda p: [p[n].update(ok=False, kind='error', code='EXCEPTION') for n in p], fpy=lambda q: [q[n].update(ok=False, kind='error', code='EXIT1') for n in q]),
        mut('missing result', fpt=lambda p: p.pop(first_ok)),
        mut('refuse case: pointtruth code changed to EIO', fpt=lambda p: p[first_ref].update(code='EIO')),
        mut('refuse case: python category changed', fpy=lambda q: q[first_ref].update(code='OTHER')),
        mut('policy case: python output corrupted', fpy=lambda q: q[pol_case].update(bytes_b64=base64.b64encode(b'WRONG OUTPUT\n').decode())),
        mut('policy case: python precision changed to 12', fpy=lambda q: q[pol_case].update(decimals=12)),
        mut('policy case: pointtruth refusal code changed', fpt=lambda p: p[pol_case].update(code='SIZE')),
        mut('policy case: pointtruth converts instead of refusing', fpt=lambda p: p[pol_case].update(ok=True, bytes_b64=py[pol_case]['bytes_b64'], decimals=py[pol_case]['decimals'])),
        mut('policy case: expectation renamed to an unknown policy id', fc=lambda k: [c.update(expect='policy:nonexistent-policy-profile') for c in k['cases'] if c['name'] == pol_case]),
        mut('extra result for a case not in the corpus', fpt=lambda p: p.update({'phantom-case': {'ok': True, 'bytes_b64': '', 'decimals': 4}})),
    ]
    ok = all(results); print('mutation self-test: %d/%d mutations detected :: %s' % (sum(results), len(results), 'COMPARATOR FAILS AS REQUIRED' if ok else 'COMPARATOR DID NOT FAIL')); return 0 if ok else 1

def main():
    corpus = load('corpus.json'); pt = load('pt.json'); py = load('py.json')
    if '--self-test' in sys.argv: return self_test(corpus, pt, py)
    problems, tally = evaluate(corpus, pt, py)
    print('differential: %d identical outputs, %d refused by both (codes pinned), %d named policy differences (bytes pinned), %d problem(s)' % (tally['ok'], tally['refuse'], tally['policy'], len(problems)))
    for p in problems: print('  PROBLEM', p)
    return 0 if not problems else 1

if __name__ == '__main__': sys.exit(main())
