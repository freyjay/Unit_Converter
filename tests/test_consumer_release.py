#!/usr/bin/env python3
"""Consumer release checks: exact members, checksums, identity with PROVENANCE.json, reproducible bytes, refusal of a
modified app, and the shipped CLI reproducing the natively accepted Civil 3D bytes from the extracted release."""
from pathlib import Path
import hashlib, importlib.util, json, shutil, subprocess, sys, tempfile, unittest, zipfile
ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('consumer_release', ROOT / 'scripts' / 'build_consumer_release.py'); rel = importlib.util.module_from_spec(spec); spec.loader.exec_module(rel)
ACCEPTED = 'acceptance/civil3d-completed'
def sha(b): return hashlib.sha256(b).hexdigest()
class ConsumerRelease(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.TemporaryDirectory(); self.out = Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def test_members_checksums_and_identity(self):
        with zipfile.ZipFile(rel.build(ROOT, self.out / 'a')) as z:
            pv = json.loads((ROOT / 'docs/PROVENANCE.json').read_text(encoding='utf-8')); prefix = 'Unit_Converter-%s/' % (pv.get('release_revision') or pv['html_text_revision'])
            self.assertEqual(sorted(z.namelist()), sorted(prefix + m for m in rel.MEMBERS + ['CHECKSUMS.sha256']))
            for line in z.read(prefix + 'CHECKSUMS.sha256').decode().splitlines():
                h, name = line.split('  ', 1); self.assertEqual(sha(z.read(prefix + name)), h, name)
            self.assertEqual(sha(z.read(prefix + 'Point-File-Unit-Converter.html')), pv['html_sha256']); self.assertEqual(sha(z.read(prefix + 'pointfile_units.py')), pv['python_sha256'])
    def test_reproducible(self):
        self.assertEqual(rel.build(ROOT, self.out / 'a').read_bytes(), rel.build(ROOT, self.out / 'b').read_bytes())
    def test_platform_metadata_is_fixed(self):
        # Python stamps ZIP entries with the building platform (0 on Windows, 3 elsewhere). The builder must pin it, so a
        # Windows build is byte-identical to a macOS/Linux build. Simulate Windows by patching the platform zipfile sees.
        from unittest import mock
        here = rel.build(ROOT, self.out / 'here')
        with zipfile.ZipFile(here) as z:
            self.assertTrue(all(i.create_system == 3 and i.external_attr == 0o644 << 16 for i in z.infolist()), 'unpinned metadata')
        with mock.patch.object(zipfile.sys, 'platform', 'win32'):
            self.assertEqual(zipfile.ZipInfo('probe').create_system, 0, 'the Windows simulation is not effective')
            windows = rel.build(ROOT, self.out / 'win').read_bytes()
        self.assertEqual(windows, here.read_bytes(), 'Windows-simulated build differs')
    def test_refuses_modified_app(self):
        copy = self.out / 'tree'; (copy / 'docs').mkdir(parents=True)
        for m in rel.MEMBERS: shutil.copyfile(ROOT / m, copy / m)
        shutil.copyfile(ROOT / 'docs/PROVENANCE.json', copy / 'docs/PROVENANCE.json')
        html = copy / 'Point-File-Unit-Converter.html'; html.write_bytes(html.read_bytes().replace(b'Point data for import', b'Point data for importt', 1))
        with self.assertRaises(SystemExit) as cm: rel.build(copy, self.out / 'x')
        self.assertIn('does not match PROVENANCE.json', str(cm.exception)); self.assertFalse(any((self.out / 'x').glob('*.zip')))
    def test_shipped_cli_reproduces_native_acceptance(self):
        with zipfile.ZipFile(rel.build(ROOT, self.out / 'a')) as z:
            z.extractall(self.out / 'ex')
        cli = next((self.out / 'ex').glob('*/pointfile_units.py'))
        dst = self.out / 'converted-meters.csv'
        r = subprocess.run([sys.executable, str(cli), 'convert', '--in', str(ROOT / ACCEPTED / 'source-international-feet.csv'), '--out', str(dst), '--format', 'PENZD', '--conversion', 'IntlFeetToMeters', '--delimiter', 'comma', '--header', 'no', '--decimals', '8', '--force-mapping', '--source-unit-reference', 'acceptance fixture: international feet'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[-300:])
        self.assertEqual(dst.read_bytes(), (ROOT / ACCEPTED / 'civil3d-export.txt').read_bytes(), 'shipped CLI output differs from the bytes Civil 3D exported')
if __name__ == '__main__': unittest.main(verbosity=2)
