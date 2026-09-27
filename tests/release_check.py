from pathlib import Path
#!/usr/bin/env python3
"""Release gate: build the deliverable ZIP, extract it into a clean directory whose name contains spaces,
and run the full suite from THAT copy with no access to the development tree."""
import os, pathlib, shutil, subprocess, sys, tempfile, zipfile, hashlib, json
ROOT = pathlib.Path(__file__).resolve().parent.parent
REQUIRED = [
    "tests/review-evidence/round-12/Test-Results.md",
    "tests/review-evidence/round-12/Review.md",
    "docs/history/RESPONSE-TO-REVIEW-12.md",
    "tests/capacity/results/linux-chromium-64mib-producer-open-copy-on-3.3.6.json",
    "tests/capacity/results/linux-chromium-64mib-producer-open-copy-off-3.3.6.json",
    "tests/review-evidence/round-11/Test-Results.md",
    "tests/review-evidence/round-11/Review.md",
    "docs/history/RESPONSE-TO-REVIEW-11.md",
    "tests/roundtrip/roundtrip-observations.json",
    "tests/roundtrip/RESULT.md",
    "tests/windows/results-template.json",
    "docs/WINDOWS-TEST-RUNSHEET.md",
    "tests/roundtrip/survey40.txt",
    "tests/roundtrip/acceptance-source-international-feet.csv",
    "tests/roundtrip/stateplane-fictional.csv",
    "tests/roundtrip/roundtrip_cli.py",
    "tests/review-evidence/round-10/Partner-Note.md",
    "tests/review-evidence/round-10/Review.md",
    "docs/history/RESPONSE-TO-REVIEW-10.md",
    "docs/FEATURE-INVENTORY.md",
    "tests/capacity/results/superseded-3.3.5/linux-chromium-64mib-producer-open.kernel-log-excerpt.txt",
    "tests/capacity/results/superseded-3.3.5/linux-chromium-64mib-producer-closed.json",
    "tests/capacity/results/superseded-3.3.5/linux-chromium-64mib-producer-open.json",
    "tests/capacity/results/superseded-3.3.5/linux-chromium-16mib.json",
    "tests/capacity/results/superseded-3.3.5/README.md",
    "tests/capacity/results/linux-chromium-64mib-producer-closed-3.3.6.json",
    "tests/capacity/results/linux-chromium-64mib-producer-open-3.3.6.json",
    "tests/capacity/results/linux-chromium-16mib-3.3.6.json",
        "tests/review-evidence/round-9/Review.md",
    "docs/history/RESPONSE-TO-REVIEW-9.md",
    "tests/capacity/measure_lifecycle.py",
    "tests/differential/run_adapter_vectors.py","Point-File-Unit-Converter.html", "pointfile_units.py", "docs/history/Point-File-Units-HANDOFF-v3.md", "README.md",
            "tests/make_fixtures.py", "tests/run_python_tests.sh", "tests/run_regressions.py", "tests/run_browser_tests.py",
            "tests/run_all_tests.py", "tests/release_check.py", "tests/independent-expected-outputs.json", "tests/independent-expected-outputs-2.json", "tests/canonical-fixtures.json", "tests/canonical-v2-fixtures.json", "tests/adapter-vectors.json", "tests/differential/README.md", "tests/differential/corpus.py", "tests/differential/run_pt.cjs", "tests/differential/run_py.py", "tests/differential/compare.py", "docs/history/FOLDING-RISKS-AND-TRUTH.md", "docs/history/INTERCHANGE-CONTRACT.md", "docs/history/INTERCHANGE-CONTRACT-DRAFT2.md", "docs/history/RESPONSE-TO-REVIEW-4.md", "docs/history/RESPONSE-TO-REVIEW-5.md", "docs/history/RESPONSE-TO-REVIEW-6.md", "docs/history/INTERCHANGE-CONTRACT-DRAFT2.1.md", "docs/history/RESPONSE-TO-REVIEW-7.md", "docs/history/CIVIL3D-ACCEPTANCE-RUNSHEET.md", "docs/history/ARCHITECTURE-OPTIONS-RESPONSE.md", "tests/pointtruth-audit/results/rc1/run-record.json", "tests/pointtruth-audit/results/rc1/audit_pt.log", "tests/pointtruth-audit/results/rc1/audit_pt2.log", "tests/pointtruth-audit/results/rc1/ui-audit.log", "docs/history/STATUS.md", "docs/history/status-manual.json", "docs/history/tools/status_ledger.py",
            "tests/legacy-records/README.md", "tests/legacy-records/v3.3.1-python/base.src", "tests/legacy-records/v3.3.1-python/base.out", "tests/legacy-records/v3.3.1-python/base.out.manifest.json",
            "tests/legacy-records/v3.3.1-python/cross-unicode.src", "tests/legacy-records/v3.3.1-python/cross-unicode.out", "tests/legacy-records/v3.3.1-python/cross-unicode.out.manifest.json",
            "tests/legacy-records/v3.2.0-browser/cross.src", "tests/legacy-records/v3.2.0-browser/cross.out", "tests/legacy-records/v3.2.0-browser/cross.out.manifest.json",
            "tests/legacy-records/v3.1.0-browser/record.src", "tests/legacy-records/v3.1.0-browser/record.out", "tests/legacy-records/v3.1.0-browser/record.out.manifest.json",
            "tests/legacy-records/v3.3.2-python-handoff/handoff.src", "tests/legacy-records/v3.3.2-python-handoff/handoff.out", "tests/legacy-records/v3.3.2-python-handoff/handoff.out.manifest.json",
            "tests/pointtruth-audit/README.md", "tests/pointtruth-audit/audit_pt.cjs", "tests/pointtruth-audit/audit_pt2.cjs", "tests/pointtruth-audit/ui-audit.py",
            "tests/pointtruth-audit/results/run-record.json", "tests/pointtruth-audit/results/audit_pt.log", "tests/pointtruth-audit/results/audit_pt2.log", "tests/pointtruth-audit/results/ui-audit.log"]
REQUIRED += ["tests/test_utility_repairs.py", "tests/test_browser_paths.py", "docs/history/ADVISOR-CANDIDATE-2026-09-24.md", "tests/differential/PointTruth.html"]
REQUIRED += ['START-HERE-MAC.md','GITHUB-PUSH.md','LICENSE-NOTE.md','requirements-browser.txt',
             '.gitattributes','.gitignore','docs/PROVENANCE.json','docs/CURRENT-STATUS.md','docs/README.md','docs/TEST-GATE-MAP.md','docs/history/README.md','QUICK-START.md','LICENSE','scripts/build_consumer_release.py','scripts/update_package_contents.py','tests/test_consumer_release.py','tests/test_exposure_scan.py','tests/test_evidence_archives.py','tests/test_candidate_determinism.py','tests/test_payload_identity.py','tests/test_public_profile.py','docs/PAYLOAD-IDENTITY.md','scripts/compare_runs.py','docs/EVIDENCE-ARCHIVES.json','scripts/scan_exposure.py','docs/EXPOSURE-INVENTORY.md',
             'scripts/check.py','scripts/check_repository.py','.github/workflows/checks.yml']
OPTIONAL = ['tests/review-evidence','scripts','.github','acceptance','evidence','docs/history']

# Public profile: a published copy declares its private areas in docs/PUBLIC-PROFILE.json. Required files inside those
# areas are then not required, and the areas must be ABSENT (a published copy that still contains them is refused).
# A private repository has no profile file, so every required file stays required there.
def apply_public_profile(required, root):
    prof = pathlib.Path(root) / 'docs' / 'PUBLIC-PROFILE.json'
    if not prof.is_file(): return list(required)
    areas = json.loads(prof.read_text(encoding='utf-8'))['private_areas']
    present = [a for a in areas if (pathlib.Path(root) / a).exists()]
    if present: raise SystemExit('public profile: private areas are present in this tree: %s' % ', '.join(present))
    # the profile and the evidence map travel with every candidate built from a public tree, so an extracted
    # candidate applies the same profile as its source
    own = [f for f in ('docs/PUBLIC-PROFILE.json', 'docs/PUBLIC-EVIDENCE-MAP.json') if (pathlib.Path(root) / f).is_file()]
    return [r for r in required if not any(r.startswith(a) for a in areas)] + [f for f in own if f not in required]
REQUIRED = apply_public_profile(REQUIRED, ROOT)
# Archives kept as evidence are not inputs to a tested candidate: each would be packed again into the next candidate
# (a 3.66 MB Windows candidate doubled the next one to 7.28 MB). They stay where they are and are verified against
# docs/EVIDENCE-ARCHIVES.json by tests/test_evidence_archives.py (also run by scripts/check_repository.py).
CANDIDATE_EXCLUDE = ['evidence/*.zip', 'tests/review-evidence/*.zip']
def excluded_from_candidate(name):
    import fnmatch, pathlib as _pl
    n = _pl.PureWindowsPath(name).as_posix()
    return any(fnmatch.fnmatchcase(n.casefold(), pat.casefold()) for pat in CANDIDATE_EXCLUDE)

def build_inventory(required, optional_dirs, root, walker=None):
    """F12-01: one inventory keyed by normalized (as_posix), case-folded name. The same file reached twice is kept once; two
    DISTINCT files whose names collide case-insensitively are refused. `walker` is injectable so the Windows behaviour
    (backslash-separated relative paths) can be tested on any OS."""
    import pathlib as _pl
    def norm(name): return _pl.PureWindowsPath(name).as_posix()   # accepts both separators on every OS
    inv = {}   # casefolded -> (archive name, source path)
    def add(name, src):
        n = norm(name); k = n.casefold()
        if k in inv and inv[k][0] != n: raise SystemExit("case-colliding archive names: %r and %r" % (inv[k][0], n))
        inv.setdefault(k, (n, src))
    for r in required:
        if excluded_from_candidate(r): raise SystemExit('required file %r matches CANDIDATE_EXCLUDE' % r)
        add(r, root / r)
    for o in optional_dirs:
        for rel in (walker(o) if walker else [str(f.relative_to(root)) for f in sorted((root / o).rglob("*")) if f.is_file()] if (root / o).is_dir() else []):
            if not excluded_from_candidate(rel): add(rel, root / rel)
    return [v for _, v in sorted(inv.items())]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write_record(path, record):
    raw = json.dumps(record, indent=2, ensure_ascii=False).encode('utf-8')
    pending = path.with_name(path.name + '.pending')
    pending.write_bytes(raw)
    os.replace(pending, path)

# Deterministic candidate (proposal 1+2+4): the archive envelope carries no machine state, so the same commit gives
# the same bytes on every OS. (1) fixed time, platform byte and permissions, (2) stored, not compressed, so the zlib
# version cannot matter, (4) a content digest recorded next to the archive hash as a container-independent identity.
CANDIDATE_TIME = (1980, 1, 1, 0, 0, 0)
EXECUTABLE_PATTERNS = ['*.sh']   # case-sensitive POSIX-name policy; never use host case normalization
def entry_mode(name):
    import fnmatch
    return 0o100755 if any(fnmatch.fnmatchcase(name, p) for p in EXECUTABLE_PATTERNS) else 0o100644
def put_entry(archive, name, data):
    info = zipfile.ZipInfo(name, date_time=CANDIDATE_TIME)
    info.create_system = 3; info.external_attr = entry_mode(name) << 16; info.compress_type = zipfile.ZIP_STORED
    archive.writestr(info, data)
# Payload identity, format unit-converter-payload/1 (specified in docs/PAYLOAD-IDENTITY.md). It identifies the files
# inside a canonical candidate, independently of the ZIP container. It is not the identity of the delivered bytes (that
# is the archive SHA-256), and neither says anything about test outcomes.
PAYLOAD_FORMAT = 'unit-converter-payload/1'
MODE_RULE = 'unit-converter-mode-rule/1'   # '*.sh' matched case-sensitively -> 100755; every other file -> 100644
class PayloadError(ValueError):
    pass
def _check_member_path(name):
    parts = name.split('/')
    if (not name or name.startswith('/') or name.endswith('/') or '\\' in name or '\x00' in name
            or any(p in ('', '.', '..') for p in parts) or (len(parts[0]) >= 2 and parts[0][1] == ':')):
        raise PayloadError('invalid member path: %r' % name)
def payload_encoding(path, check_modes=True):
    """The exact bytes that are hashed: UTF-8 JSON, keys sorted, no spaces, no BOM, no final newline; files sorted by
    the UTF-8 bytes of their path. Raises PayloadError for duplicate, case-colliding or invalid names, directory or
    non-regular entries, and (check_modes=True, required for canonical candidates) a stored mode that differs from
    the declared rule."""
    files, exact, folded = [], set(), {}
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            # Validate the original spelling before ZipInfo can hide NULs or rewrite Windows separators.
            name = info.orig_filename; _check_member_path(name)
            if name != info.filename: raise PayloadError('member path altered by ZIP reader: %r' % name)
            if name in exact: raise PayloadError('duplicate member: %r' % name)
            exact.add(name)
            if name.casefold() in folded: raise PayloadError('case-colliding members: %r and %r' % (folded[name.casefold()], name))
            folded[name.casefold()] = name
            stored = info.external_attr >> 16
            if info.is_dir() or (stored & 0o170000) not in (0, 0o100000): raise PayloadError('not a regular file: %r' % name)
            if check_modes and stored != entry_mode(name):
                raise PayloadError('stored mode %06o differs from %s (%06o): %r' % (stored, MODE_RULE, entry_mode(name), name))
            data = archive.read(info)   # read by entry, never by name: a hidden duplicate cannot be read twice
            files.append({'path': name, 'mode': '%06o' % entry_mode(name), 'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)})
    files.sort(key=lambda f: f['path'].encode('utf-8'))
    return json.dumps({'format': PAYLOAD_FORMAT, 'mode_rule': MODE_RULE, 'files': files}, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
def payload_identity(path, check_modes=True):
    encoding = payload_encoding(path, check_modes)
    return {'format': PAYLOAD_FORMAT, 'mode_rule': MODE_RULE, 'digest': hashlib.sha256(encoding).hexdigest(), 'members': json.loads(encoding)['files'].__len__(), 'modes_checked': bool(check_modes)}

def build_archive(path, inventory):
    with zipfile.ZipFile(path, 'w') as archive:
        for name, src in inventory:
            if name == 'PACKAGE-CONTENTS.sha256':
                continue  # Regenerate from the actual archived bytes, never copy a stale shipping inventory.
            put_entry(archive, name, Path(src).read_bytes())
    # Reopen so Windows ZipInfo.orig_filename uses serialized '/' paths as well.
    with zipfile.ZipFile(path, 'r') as archive:
        checksums = '\n'.join(hashlib.sha256(archive.read(name)).hexdigest() + '  ' + name
                              for name in sorted(archive.namelist())) + '\n'
    with zipfile.ZipFile(path, 'a') as archive:
        put_entry(archive, 'PACKAGE-CONTENTS.sha256', checksums.encode('utf-8'))
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(n.casefold() for n in names)):
            raise ValueError('Archive has duplicate or case-colliding entries')
        if archive.testzip() is not None:
            raise ValueError('Archive CRC failure')
    # Every file the delivered checksum index lists must survive the rebuild: an omission is a failure, never a quiet
    # difference (a rebuilt 288-member archive from a 289-member delivery dropped docs/README.md unnoticed).
    delivered = dict(inventory).get('PACKAGE-CONTENTS.sha256')
    if delivered is not None and Path(delivered).is_file():
        listed = {line.split('  ', 1)[1] for line in Path(delivered).read_text(encoding='utf-8').splitlines() if '  ' in line}
        dropped = sorted(listed - set(names))
        if dropped: raise ValueError('Release build dropped delivered files: ' + ', '.join(dropped))
    return len(names)

def publish_candidate(root, inventory, out, partial=False, runner=None, builder=None):
    """Test the candidate's extracted bytes before promotion. A partial gate has its own filename.

    ZIP and sidecar cannot be replaced atomically as a pair: consumers must validate
    the sidecar SHA against the archive. Uncatchable termination may leave a named
    candidate/checkpoint, never an unchecked replacement at the accepted path.
    """
    import datetime, uuid
    runner = runner or subprocess.run
    builder = builder or build_archive
    tag = uuid.uuid4().hex
    candidate = root / (out.stem + '.candidate-' + tag + '.zip')
    checkpoint = candidate.with_suffix('.json')
    record = {'schema': 'pfu-release-check-record/2', 'candidate': candidate.name,
              'target': out.name, 'mode': 'partial' if partial else 'release',
              'full_release_accepted': False, 'outcome': 'RUNNING',
              'previous_archive_sha256': sha(out) if out.exists() else None,
              'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'active_stage': 'build', 'promoted': False}
    code = 1
    try:
        write_record(checkpoint, record)
        record['members'] = builder(candidate, inventory)
        record['archive_sha256'] = sha(candidate)
        record['payload_identity'] = payload_identity(candidate)   # strict: a candidate that violates the contract is refused
        record['active_stage'] = 'extracted_tests'
        write_record(checkpoint, record)
        with tempfile.TemporaryDirectory(prefix='release check ') as tmp:
            extracted = pathlib.Path(tmp) / 'extracted copy with spaces'
            extracted.mkdir()
            with zipfile.ZipFile(candidate) as archive:
                archive.extractall(extracted)
            env = dict(os.environ, PFU_SLOW='0' if partial else '1')
            result = runner([sys.executable, str(extracted / 'tests/run_all_tests.py')]
                            + (['--allow-skip','--skip-browser'] if partial else ['--require-browser']),
                            cwd=extracted, env=env)
            code = result.returncode
        if code != 0:
            raise RuntimeError('Extracted tests exited %s' % code)
        # Reject mutation of the archive during the test: only tested bytes can be promoted.
        if sha(candidate) != record['archive_sha256']:
            raise RuntimeError('Candidate archive changed during testing')
        record.update(outcome='PASS', active_stage='promotion',
                      full_release_accepted=not partial, test_exit=0)
        write_record(checkpoint, record)
        os.replace(candidate, out)
        record.update(promoted=True, active_stage=None, archive=out.name)
        write_record(checkpoint, record)
        write_record(out.with_suffix(out.suffix + '.record.json'), record)
        print(('PARTIAL developer' if partial else 'FULL release') + ' gate PASS:', out.name)
        return 0, record
    except (Exception, KeyboardInterrupt) as exc:
        code = 130 if isinstance(exc, KeyboardInterrupt) else (code if code > 0 else 1)
        record.update(outcome='INTERRUPTED' if code == 130 else 'FAIL',
                      full_release_accepted=False, test_exit=code,
                      error=type(exc).__name__ + ': ' + str(exc))
        # Failed bytes never take the previous deliverable's name. Retain diagnosis.
        if candidate.exists():
            failed = root / (out.stem + '.failed-' + tag + '.zip')
            try:
                os.replace(candidate, failed)
                record['retained_candidate'] = failed.name
                record['retained_candidate_sha256'] = sha(failed)
            except OSError as retain_error:
                record['retention_error'] = str(retain_error)
        try:
            write_record(checkpoint, record)
        except OSError as record_error:
            print('Could not persist failure record:', record_error, file=sys.stderr)
        print('Gate failed:', record['error'], file=sys.stderr)
        return code, record

def validate_tree(root):
    obs = root / 'tests/roundtrip/roundtrip-observations.json'
    report = root / 'tests/roundtrip/RESULT.md'
    if obs.exists() and report.exists() and sha(obs) not in report.read_text(encoding='utf-8'):
        raise ValueError('RESULT.md is not bound to saved observation bytes; rerun tests/roundtrip/roundtrip_cli.py')
    missing = [name for name in REQUIRED if not (root / name).is_file()]
    if missing:
        raise ValueError('MISSING from tree: ' + repr(missing))

def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--partial', action='store_true')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args(argv)
    try:
        validate_tree(ROOT)
        if args.self_test:
            return subprocess.run([sys.executable, str(ROOT / 'tests/test_utility_repairs.py'), 'ReleaseTests']).returncode
        inventory = build_inventory(REQUIRED, OPTIONAL, ROOT)
        # Advisor candidate is not a partner release. Partial checks cannot overwrite a full-gate ZIP.
        name = 'point-file-unit-converter-v3.3.6-team-candidate'
        out = ROOT / (name + ('-partial' if args.partial else '') + '.zip')
        return publish_candidate(ROOT, inventory, out, args.partial)[0]
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
