#!/usr/bin/env python3
"""Compare core records and verify their saved archives. Use --records-only for labelled claim comparison.

Usage: python scripts/compare_runs.py [--records-only] RUN_DIR_OR_RECORD RUN_DIR_OR_RECORD ...
Default success requires valid passing core records, one clean commit, matching recorded identities, and each
adjacent tested-partial.zip matching its recorded SHA-256 and recomputed strict payload identity.
This checks artifact identity and reported outcomes; it does not authenticate who ran the tests.
"""
import argparse, hashlib, importlib.util, io, json, re, sys, zipfile
from pathlib import Path
SUPPORTED = {'unit-converter-payload/1'}
MODE_RULE = 'unit-converter-mode-rule/1'

def load(p):
    p = Path(p)
    return json.loads((p / 'run-record.json' if p.is_dir() else p).read_text(encoding='utf-8'))

def is_hash(value, lengths=(64,)):
    return isinstance(value, str) and len(value) in lengths and re.fullmatch('[0-9a-f]+', value) is not None

def valid_identity(p):
    return (isinstance(p, dict) and isinstance(p.get('format'), str) and p['format'] in SUPPORTED
            and p.get('mode_rule') == MODE_RULE and is_hash(p.get('digest'))
            and type(p.get('members')) is int and p['members'] >= 0 and p.get('modes_checked') is True)

def record_problems(r):
    if not isinstance(r, dict): return ['record is not an object']
    problems = []
    if r.get('schema') != 'pointtruth-team-check/1': problems.append('unsupported run-record schema')
    if r.get('suite') != 'core' or r.get('outcome') != 'PASS': problems.append('a passing core run is required')
    runs = r.get('runs')
    if not isinstance(runs, list) or not runs or any(not isinstance(x, dict) or x.get('outcome') != 'PASS'
            or type(x.get('exit_code')) is not int or x['exit_code'] != 0 for x in runs):
        problems.append('component runs are absent, incomplete or failed')
    git = r.get('git') if isinstance(r.get('git'), dict) else {}
    if not is_hash(git.get('commit'), (40, 64)): problems.append('invalid commit identity')
    if type(git.get('modified_or_untracked_entries')) is not int or git['modified_or_untracked_entries'] != 0:
        problems.append('a clean recorded tree is required')
    if not is_hash(r.get('tested_partial_sha256')): problems.append('invalid archive SHA-256')
    if not valid_identity(r.get('tested_payload_identity')):
        problems.append('payload identity is unsupported, malformed or not mode-checked')
    return problems

def compare(records):
    """Compare validated record claims only. main() separately checks artifacts unless --records-only is explicit."""
    problems = [{'record': i, 'problems': record_problems(r)} for i, r in enumerate(records)]
    problems = [p for p in problems if p['problems']]
    if len(records) < 2: problems.append({'record': None, 'problems': ['at least two records are required']})
    rows = [r if isinstance(r, dict) else {} for r in records]
    git = [r.get('git') if isinstance(r.get('git'), dict) else {} for r in rows]
    commits = [g.get('commit') for g in git]
    same_commit = (len(commits) >= 2 and all(is_hash(c, (40, 64)) for c in commits)
                   and len(set(commits)) == 1 and all(type(g.get('modified_or_untracked_entries')) is int
                   and g['modified_or_untracked_entries'] == 0 for g in git))
    archives = [r.get('tested_partial_sha256') for r in rows]
    archive = 'UNAVAILABLE' if not archives or not all(is_hash(a) for a in archives) else (
        'IDENTICAL' if len(set(archives)) == 1 else 'DIFFERENT')
    pids = [r.get('tested_payload_identity') for r in rows]
    payload = 'UNAVAILABLE'
    if pids and all(valid_identity(p) for p in pids):
        payload = 'IDENTICAL' if len({(p['format'], p['mode_rule'], p['digest'], p['members']) for p in pids}) == 1 else 'DIFFERENT'
    return {'same_clean_commit': same_commit, 'archive': archive, 'payload': payload, 'problems': problems,
            'ok': not problems and same_commit and archive == payload == 'IDENTICAL'}

def verify_artifact(location, record):
    """Verify one snapshot of saved bytes without extracting or executing the archive's contents."""
    path = Path(location)
    archive = (path if path.is_dir() else path.parent) / 'tested-partial.zip'
    if not archive.is_file(): raise ValueError('tested archive is missing: ' + str(archive))
    raw = archive.read_bytes()
    if hashlib.sha256(raw).hexdigest() != record['tested_partial_sha256']:
        raise ValueError('saved archive SHA-256 mismatch: ' + str(archive))
    spec = importlib.util.spec_from_file_location('release_for_comparison', Path(__file__).resolve().parent.parent / 'tests/release_check.py')
    release = importlib.util.module_from_spec(spec); spec.loader.exec_module(release)
    observed = release.payload_identity(io.BytesIO(raw), check_modes=True)
    if observed != record['tested_payload_identity']:
        raise ValueError('saved archive payload identity mismatch: ' + str(archive))
    return observed

def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--records-only', action='store_true', help='compare recorded claims; explicitly do not verify artifacts')
    parser.add_argument('records', nargs='+')
    args = parser.parse_args(argv)
    if len(args.records) < 2: print('At least two run records are required.'); return 2
    try:
        recs = [load(a) for a in args.records]
        result = compare(recs)
        print('same clean commit: %s | recorded archive digests: %s | recorded payload identities: %s' %
              (result['same_clean_commit'], result['archive'], result['payload']))
        for entry in result['problems']:
            print('record %s: %s' % (entry['record'], '; '.join(entry['problems'])))
        if args.records_only:
            print('artifacts: NOT CHECKED (--records-only); this is not artifact acceptance')
            return 0 if result['ok'] else 1
        if not result['ok']: print('artifacts: NOT VERIFIED; record comparison failed'); return 1
        for location, record in zip(args.records, recs): verify_artifact(location, record)
        print('artifacts: VERIFIED (%d) | reported core outcomes: PASS' % len(recs))
        return 0
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print('comparison failed: ' + str(exc)); return 1

if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
