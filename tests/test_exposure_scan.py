#!/usr/bin/env python3
"""The exposure scanner must find every spelling of a local user path. Samples are assembled at run time, so this file
does not itself contain a matching path."""
from pathlib import Path
import importlib.util, unittest
ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('scan_exposure', ROOT / 'scripts' / 'scan_exposure.py'); sx = importlib.util.module_from_spec(spec); spec.loader.exec_module(sx)
B = '\\'; U = 'Users'; NAME = 'Sample'
class ExposureScan(unittest.TestCase):
    def kinds(self, text): return {k for k, _ in sx.scan_text(text)}
    def test_windows_plain(self): self.assertIn('windows-user-path', self.kinds('C:' + B + U + B + NAME + B + 'Documents'))
    def test_windows_json_escaped(self): self.assertIn('windows-user-path', self.kinds('"C:' + B * 2 + U + B * 2 + NAME + B * 2 + 'x"'))
    def test_windows_forward_slashes(self): self.assertIn('windows-user-path', self.kinds('C:/' + U + '/' + NAME + '/x'))
    def test_macos_and_linux(self): self.assertEqual(self.kinds('/' + U + '/' + NAME + '/x and /home/' + NAME + '/y'), {'macos-user-path', 'linux-home-path'})
    def test_usernames_are_masked(self): self.assertTrue(all(NAME not in who for _, who in sx.scan_text('C:' + B + U + B + NAME + B + 'x')))
    def test_scanner_does_not_flag_itself(self): self.assertEqual(sx.scan_text((ROOT / 'scripts' / 'scan_exposure.py').read_text(encoding='utf-8')), [])
    def test_clean_text(self): self.assertEqual(sx.scan_text('metres = feet * 381/1250'), [])
if __name__ == '__main__': unittest.main(verbosity=1)
