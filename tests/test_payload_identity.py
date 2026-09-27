#!/usr/bin/env python3
"""Payload identity contract, unit-converter-payload/1 (docs/PAYLOAD-IDENTITY.md): a pinned reference example, the
mutations that must change or refuse it, and the container changes that must not change it."""
from pathlib import Path
from unittest import mock
import fnmatch, hashlib, importlib.util, ntpath, posixpath, tempfile, unittest, warnings, zipfile
ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('release_for_payload', ROOT / 'tests' / 'release_check.py'); rc = importlib.util.module_from_spec(spec); spec.loader.exec_module(rc)
REFERENCE = [('a.txt', b'alpha\n'), ('tools/run.sh', b'#!/bin/sh\necho ok\n')]
EXPECTED_ENCODING = b'{"files":[{"mode":"100644","path":"a.txt","sha256":"b6a98d9ce9a2d9149288fa3df42d377c3e42737afdcdaf714e33c0a100b51060","size":6},{"mode":"100755","path":"tools/run.sh","sha256":"b4d644d4279594903f1a9911956432d9473041f2984fc6014c14d7402c7d126c","size":18}],"format":"unit-converter-payload/1","mode_rule":"unit-converter-mode-rule/1"}'
EXPECTED_DIGEST = 'a5b3383eb7f61d8bde978eddd1f8385f85eb891fa077b4fd4ad2126178287440'
def make(entries, compress=zipfile.ZIP_STORED, modes=None, raw=None):
    """entries: [(name, data)]; modes: {name: mode} overriding the declared rule; raw: extra ZipInfo objects"""
    path = Path(tempfile.mkdtemp()) / 'p.zip'
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')   # zipfile warns on the deliberately duplicated names below
        with zipfile.ZipFile(path, 'w') as z:
            for name, data in entries:
                i = zipfile.ZipInfo(name, date_time=rc.CANDIDATE_TIME); i.create_system = 3; i.compress_type = compress
                i.external_attr = (modes or {}).get(name, rc.entry_mode(name)) << 16; z.writestr(i, data)
            for info, data in (raw or []): z.writestr(info, data)
    return path
class ReferenceExample(unittest.TestCase):
    def test_encoding_is_pinned(self): self.assertEqual(rc.payload_encoding(make(REFERENCE)), EXPECTED_ENCODING)
    def test_digest_is_pinned(self):
        pid = rc.payload_identity(make(REFERENCE))
        self.assertEqual((pid['format'], pid['mode_rule'], pid['digest'], pid['members']), ('unit-converter-payload/1', 'unit-converter-mode-rule/1', EXPECTED_DIGEST, 2))
    def test_encoding_has_no_bom_and_no_final_newline(self):
        e = rc.payload_encoding(make(REFERENCE)); self.assertFalse(e.startswith(b'\xef\xbb\xbf')); self.assertFalse(e.endswith(b'\n'))
class MustChangeOrRefuse(unittest.TestCase):
    ref = property(lambda self: rc.payload_identity(make(REFERENCE))['digest'])
    def test_renamed_file_changes_digest(self): self.assertNotEqual(rc.payload_identity(make([('b.txt', b'alpha\n'), REFERENCE[1]]))['digest'], self.ref)
    def test_changed_payload_changes_digest(self): self.assertNotEqual(rc.payload_identity(make([('a.txt', b'alphA\n'), REFERENCE[1]]))['digest'], self.ref)
    def test_stored_mode_mismatch_is_refused(self):
        with self.assertRaisesRegex(rc.PayloadError, 'stored mode 100755 differs'): rc.payload_identity(make(REFERENCE, modes={'a.txt': 0o100755}))
    def test_hidden_duplicate_is_refused(self):
        with self.assertRaisesRegex(rc.PayloadError, 'duplicate member'): rc.payload_identity(make(REFERENCE + [('a.txt', b'changed\n')]))
    def test_case_collision_is_refused(self):
        with self.assertRaisesRegex(rc.PayloadError, 'case-colliding'): rc.payload_identity(make(REFERENCE + [('A.txt', b'x')]))
    def test_invalid_paths_are_refused(self):
        for bad in ('../x', '/abs', 'c:/x', 'a\\\\b', 'a//b', 'a/./b'):
            with self.subTest(bad=bad), self.assertRaisesRegex(rc.PayloadError, 'invalid member path'): rc.payload_identity(make(REFERENCE + [(bad, b'x')]))
    def test_directory_and_symlink_entries_are_refused(self):
        d = zipfile.ZipInfo('dir/'); d.external_attr = 0o040755 << 16
        s = zipfile.ZipInfo('link'); s.external_attr = 0o120777 << 16; s.create_system = 3
        for extra, why in ((d, 'invalid member path|not a regular file'), (s, 'not a regular file')):
            with self.subTest(entry=extra.filename), self.assertRaisesRegex(rc.PayloadError, why): rc.payload_identity(make(REFERENCE, raw=[(extra, b'')]))
class MustNotChange(unittest.TestCase):
    def test_other_container_same_payload(self):
        a, b = make(REFERENCE), make(list(reversed(REFERENCE)), compress=zipfile.ZIP_DEFLATED)
        self.assertNotEqual(hashlib.sha256(a.read_bytes()).hexdigest(), hashlib.sha256(b.read_bytes()).hexdigest())
        self.assertEqual(rc.payload_identity(a)['digest'], rc.payload_identity(b)['digest'])
    def test_declared_mode_identity_when_modes_not_checked(self):
        # for archives from other writers (modes_checked False) the identity is explicitly a declared-mode identity
        pid = rc.payload_identity(make(REFERENCE, modes={'a.txt': 0o100600}), check_modes=False)
        self.assertEqual((pid['digest'], pid['modes_checked']), (EXPECTED_DIGEST, False))
    def test_rules_do_not_depend_on_the_host(self):
        built = make(REFERENCE)   # build first: only the host's case rule is swapped, not its whole path module
        for host in (ntpath, posixpath):
            with self.subTest(host=host.__name__), mock.patch.object(fnmatch.os.path, 'normcase', host.normcase):
                self.assertEqual(rc.entry_mode('tools/RUN.SH'), 0o100644); self.assertEqual(rc.entry_mode('tools/run.sh'), 0o100755)
                self.assertTrue(rc.excluded_from_candidate('evidence/a/ARCHIVE.ZIP'))
                self.assertEqual(rc.payload_identity(built)['digest'], EXPECTED_DIGEST)
spec2 = importlib.util.spec_from_file_location('compare_runs', ROOT / 'scripts' / 'compare_runs.py'); cr = importlib.util.module_from_spec(spec2); spec2.loader.exec_module(cr)
class CompareRuns(unittest.TestCase):
    def rec(self, archive='a' * 64, digest='d' * 64, fmt='unit-converter-payload/1', commit='c' * 40, dirty=0):
        r = {'schema': 'pointtruth-team-check/1', 'suite': 'core', 'outcome': 'PASS',
             'runs': [{'name': 'fixture', 'outcome': 'PASS', 'exit_code': 0}],
             'git': {'commit': commit, 'modified_or_untracked_entries': dirty}, 'tested_partial_sha256': archive}
        if fmt: r['tested_payload_identity'] = {'format': fmt, 'mode_rule': rc.MODE_RULE,
                                              'digest': digest, 'members': 2, 'modes_checked': True}
        return r
    def test_all_identical(self): self.assertTrue(cr.compare([self.rec(), self.rec()])['ok'])
    def test_missing_identity_is_unavailable_not_a_match(self):
        v = cr.compare([self.rec(), self.rec(fmt=None)]); self.assertEqual(v['payload'], 'UNAVAILABLE'); self.assertFalse(v['ok'])
    def test_unsupported_format_is_unavailable(self): self.assertEqual(cr.compare([self.rec(), self.rec(fmt='bare-digest')])['payload'], 'UNAVAILABLE')
    def test_different_payload(self): self.assertEqual(cr.compare([self.rec(), self.rec(digest='e' * 64)])['payload'], 'DIFFERENT')
    def test_different_archive_or_dirty_tree_fails(self):
        self.assertFalse(cr.compare([self.rec(), self.rec(archive='b' * 64)])['ok']); self.assertFalse(cr.compare([self.rec(), self.rec(dirty=3)])['ok'])
class RawZipNames(unittest.TestCase):
    def test_original_names_are_checked_before_reader_normalization(self):
        # Patch bytes after writing: ZipInfo normalizes these names before it writes them on Windows.
        for before, after in ((b'aXtail.txt', b'a\x00tail.txt'), (b'a/b.txt', b'a\\b.txt')):
            with self.subTest(raw_name=after):
                p = make([(before.decode('ascii'), b'fixture')])
                raw = p.read_bytes(); self.assertEqual(raw.count(before), 2)
                p.write_bytes(raw.replace(before, after))
                with self.assertRaisesRegex(rc.PayloadError, 'invalid member path|altered by ZIP reader'):
                    rc.payload_identity(p)

class CompareValidation(unittest.TestCase):
    rec = CompareRuns.rec
    def test_invalid_identity_fields_are_unavailable(self):
        for field, value in [('format', []), ('mode_rule', 'unknown/2'), ('digest', 'not-a-sha256'),
                             ('members', -1), ('members', True), ('modes_checked', False), ('modes_checked', 1)]:
            r = self.rec(); r['tested_payload_identity'][field] = value
            with self.subTest(field=field, value=value):
                verdict = cr.compare([r, r]); self.assertFalse(verdict['ok']); self.assertEqual(verdict['payload'], 'UNAVAILABLE')
    def test_failed_or_incomplete_runs_are_not_accepted(self):
        import copy
        for field, value in [('outcome', 'FAIL'), ('outcome', 'RUNNING'), ('suite', 'browser'), ('runs', []),
                             ('runs', [{'name': 'fixture', 'outcome': 'FAIL', 'exit_code': 1}])]:
            r = copy.deepcopy(self.rec()); r[field] = value
            with self.subTest(field=field, value=value): self.assertFalse(cr.compare([r, r])['ok'])
    def test_missing_or_malformed_records_are_not_accepted(self):
        for r in [None, [], {}, {'git': []}]:
            with self.subTest(record=r): self.assertFalse(cr.compare([r, r])['ok'])
        self.assertFalse(cr.compare([])['ok']); self.assertFalse(cr.compare([self.rec()])['ok'])
    def test_invalid_archive_and_commit_hashes_are_not_accepted(self):
        self.assertFalse(cr.compare([self.rec(archive=''), self.rec(archive='')])['ok'])
        self.assertFalse(cr.compare([self.rec(commit='same'), self.rec(commit='same')])['ok'])
    def test_member_count_disagreement_is_not_identical(self):
        a, b = self.rec(), self.rec(); b['tested_payload_identity']['members'] = 3
        self.assertFalse(cr.compare([a, b])['ok'])

class SavedArtifacts(unittest.TestCase):
    rec = CompareRuns.rec
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.raw = make(REFERENCE).read_bytes()
        import io
        self.record = self.rec(archive=hashlib.sha256(self.raw).hexdigest())
        self.record['tested_payload_identity'] = rc.payload_identity(io.BytesIO(self.raw))
        self.dirs = [self.root / 'a', self.root / 'b']
        for d in self.dirs:
            d.mkdir(); (d / 'tested-partial.zip').write_bytes(self.raw)
        self.save_records()
    def save_records(self):
        import json
        for d in self.dirs: (d / 'run-record.json').write_text(json.dumps(self.record), encoding='utf-8')
    def command(self, *flags):
        import io, contextlib
        out = io.StringIO()
        with contextlib.redirect_stdout(out): code = cr.main([*flags, *(str(d) for d in self.dirs)])
        return code, out.getvalue()
    def test_valid_saved_archives_are_verified(self):
        code, out = self.command(); self.assertEqual(code, 0, out); self.assertIn('artifacts: VERIFIED', out)
    def test_missing_saved_archive_fails(self):
        (self.dirs[1] / 'tested-partial.zip').unlink()
        code, out = self.command(); self.assertNotEqual(code, 0); self.assertIn('archive is missing', out)
    def test_corrupt_saved_archive_fails(self):
        (self.dirs[1] / 'tested-partial.zip').write_bytes(b'corrupt')
        code, out = self.command(); self.assertNotEqual(code, 0); self.assertIn('SHA-256 mismatch', out)
    def test_recomputed_payload_must_match_the_record(self):
        self.record['tested_payload_identity']['digest'] = 'f' * 64; self.save_records()
        code, out = self.command(); self.assertNotEqual(code, 0); self.assertIn('payload identity mismatch', out)
    def test_records_only_mode_labels_absent_verification(self):
        for d in self.dirs: (d / 'tested-partial.zip').unlink()
        code, out = self.command('--records-only'); self.assertEqual(code, 0); self.assertIn('artifacts: NOT CHECKED', out)
if __name__ == '__main__': unittest.main(verbosity=1)
