#!/usr/bin/env python3
"""Public profile (docs/PUBLIC-PROFILE.json): without it every required file stays required; with it, required files
in the declared private areas are dropped, and a tree that still contains a private area is refused."""
from pathlib import Path
import importlib.util, json, shutil, tempfile, unittest
ROOT = Path(__file__).resolve().parent.parent
def load(root):
    spec = importlib.util.spec_from_file_location('rc_profile_%d' % id(root), Path(root) / 'tests' / 'release_check.py'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
class PublicProfile(unittest.TestCase):
    def tree(self, profile=None, areas=()):
        t = Path(tempfile.mkdtemp()); (t / 'tests').mkdir(); (t / 'docs').mkdir(); shutil.copyfile(ROOT / 'tests' / 'release_check.py', t / 'tests' / 'release_check.py')
        if profile is not None: (t / 'docs' / 'PUBLIC-PROFILE.json').write_text(json.dumps(profile), encoding='utf-8')
        for a in areas: (t / a).mkdir(parents=True, exist_ok=True)
        return t
    def test_private_tree_keeps_every_required_file(self):
        here = load(ROOT); base = load(self.tree())
        if not (ROOT / 'docs' / 'PUBLIC-PROFILE.json').exists(): self.assertEqual(here.REQUIRED, base.REQUIRED)
        self.assertTrue(any(r.startswith('tests/review-evidence/') for r in base.REQUIRED))
    def test_public_tree_drops_private_areas(self):
        m = load(self.tree({'private_areas': ['tests/review-evidence/', 'docs/history/', 'evidence/']}))
        self.assertFalse(any(r.startswith(('tests/review-evidence/', 'docs/history/', 'evidence/')) for r in m.REQUIRED))
        self.assertIn('pointfile_units.py', m.REQUIRED)
    def test_profile_travels_with_the_candidate(self):
        t = self.tree({'private_areas': ['evidence/']}); (t / 'docs' / 'PUBLIC-EVIDENCE-MAP.json').write_text('{}', encoding='utf-8')
        m = load(t); self.assertIn('docs/PUBLIC-PROFILE.json', m.REQUIRED); self.assertIn('docs/PUBLIC-EVIDENCE-MAP.json', m.REQUIRED)
    def test_public_tree_with_a_private_area_present_is_refused(self):
        with self.assertRaisesRegex(SystemExit, 'private areas are present'): load(self.tree({'private_areas': ['evidence/']}, areas=['evidence']))
class RepositoryCheckProfile(unittest.TestCase):
    def load_repo_check(self, profile):
        t = Path(tempfile.mkdtemp()); (t / 'scripts').mkdir(); (t / 'docs').mkdir(); shutil.copyfile(ROOT / 'scripts' / 'check_repository.py', t / 'scripts' / 'check_repository.py')
        if profile is not None: (t / 'docs' / 'PUBLIC-PROFILE.json').write_text(json.dumps(profile), encoding='utf-8')
        spec = importlib.util.spec_from_file_location('cr_%d' % id(t), t / 'scripts' / 'check_repository.py'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
    def test_private_workflow_files_required_only_without_profile(self):
        self.assertIn('GITHUB-PUSH.md', self.load_repo_check(None).REQUIRED)
        self.assertNotIn('GITHUB-PUSH.md', self.load_repo_check({'private_areas': ['GITHUB-PUSH.md', 'START-HERE-MAC.md']}).REQUIRED)
if __name__ == '__main__': unittest.main(verbosity=1)
