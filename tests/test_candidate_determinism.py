#!/usr/bin/env python3
"""The tested candidate must not depend on the machine that builds it (proposal 1+2+4). Builds the real release
inventory under each variation that previously changed the bytes and requires identical archives and digests."""
from pathlib import Path
from unittest import mock
import importlib.util, os, shutil, tempfile, time, unittest, zipfile
ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('release_for_determinism', ROOT / 'tests' / 'release_check.py'); rc = importlib.util.module_from_spec(spec); spec.loader.exec_module(rc)
class CandidateDeterminism(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.base = Path(cls.tmp.name) / 'tree'
        shutil.copytree(ROOT, cls.base, ignore=shutil.ignore_patterns('.git', '.checks', '__pycache__', 'dist', '*.zip.partial'))
        cls.ref = cls.build(cls.base)
    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    @classmethod
    def build(cls, root, platform=None):
        out = Path(tempfile.mkdtemp(dir=cls.tmp.name)) / 'c.zip'; inv = rc.build_inventory(rc.REQUIRED, rc.OPTIONAL, root)
        if platform:
            with mock.patch.object(zipfile.sys, 'platform', platform): rc.build_archive(out, inv)
        else: rc.build_archive(out, inv)
        return out
    def variant(self, change):
        d = Path(tempfile.mkdtemp(dir=self.tmp.name)) / 'tree'; shutil.copytree(self.base, d); change(d); return self.build(d)
    def same(self, other):
        self.assertEqual(other.read_bytes(), self.ref.read_bytes()); self.assertEqual(rc.payload_identity(other)['digest'], rc.payload_identity(self.ref)['digest'])
    def test_repeat_build(self): self.same(self.build(self.base))
    def test_file_times(self): self.same(self.variant(lambda d: [os.utime(p, (1e9, 1e9)) for p in d.rglob('*') if p.is_file()]))
    def test_permissions(self): self.same(self.variant(lambda d: [os.chmod(p, 0o600) for p in d.rglob('*') if p.is_file()]))
    def test_windows_platform(self): self.same(self.build(self.base, platform='win32'))
    @unittest.skipUnless(hasattr(time, 'tzset'), 'time.tzset is unavailable; clock-independence and envelope checks still run')
    def test_time_zone(self):
        old = os.environ.get('TZ')
        try:
            os.environ['TZ'] = 'America/Los_Angeles'; time.tzset()
            self.same(self.build(self.base))
        finally:
            (os.environ.pop('TZ') if old is None else os.environ.__setitem__('TZ', old)); time.tzset()
    def test_envelope_is_fixed(self):
        with zipfile.ZipFile(self.ref) as z:
            for i in z.infolist():
                self.assertEqual((i.date_time, i.create_system, i.compress_type), (rc.CANDIDATE_TIME, 3, zipfile.ZIP_STORED), i.filename)
                self.assertEqual(i.external_attr >> 16, rc.entry_mode(i.filename), i.filename)
    def test_digest_tracks_content(self):
        d = self.variant(lambda t: (t / 'README.md').write_bytes((t / 'README.md').read_bytes() + b' '))
        self.assertNotEqual(rc.payload_identity(d)['digest'], rc.payload_identity(self.ref)['digest'])
    def test_name_rules_ignore_host_case_normalization(self):
        import fnmatch, ntpath, posixpath
        normalizers = (ntpath.normcase, posixpath.normcase)
        for normalizer in normalizers:
            with self.subTest(normalizer=normalizer.__module__):
                with mock.patch.object(fnmatch.os.path, 'normcase', normalizer):
                    self.assertEqual(rc.entry_mode('tools/RUN.SH'), 0o100644)
                    self.assertEqual(rc.entry_mode('tools/run.sh'), 0o100755)
                    self.assertTrue(rc.excluded_from_candidate('evidence/a/ARCHIVE.ZIP'))
    def test_builder_does_not_read_source_clock_metadata(self):
        with mock.patch.object(zipfile.time, 'localtime', side_effect=AssertionError('local clock read')):
            with mock.patch.object(zipfile.ZipInfo, 'from_file', side_effect=AssertionError('filesystem metadata read')):
                self.same(self.build(self.base))
if __name__ == '__main__': unittest.main(verbosity=1)
