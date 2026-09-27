#!/usr/bin/env python3
"""Evidence archives: never nested into tested candidates, never unaccounted for.
- every *.zip under evidence/ or tests/review-evidence/ that is present must be listed in docs/EVIDENCE-ARCHIVES.json
  with the same SHA-256 and size (run in the repository by scripts/check_repository.py; in an extracted candidate the
  archives are absent by design, so nothing is found and nothing is skipped silently: the exclusion is tested instead);
- the release inventory contains none of them, and no required file matches the exclusion;
- every entry has a well-formed hash and at least one retention place."""
from pathlib import Path
import fnmatch, hashlib, importlib.util, json, re, sys, unittest
ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('release_for_archives', ROOT / 'tests' / 'release_check.py'); rc = importlib.util.module_from_spec(spec); spec.loader.exec_module(rc)
def manifest(root=ROOT): return json.loads((Path(root) / 'docs' / 'EVIDENCE-ARCHIVES.json').read_text(encoding='utf-8'))
def present_archives(root=ROOT):
    root = Path(root); return sorted(p.relative_to(root).as_posix() for d in ('evidence', 'tests/review-evidence') if (root / d).is_dir() for p in (root / d).rglob('*') if p.is_file() and p.suffix.casefold() == '.zip')
def verify_present(root=ROOT):
    """problems with archives on disk vs the manifest (used by scripts/check_repository.py)"""
    listed = {a['in_repository']: a for a in manifest(root)['archives'] if a['in_repository']}; problems = []
    for rel in present_archives(root):
        a = listed.get(rel); data = (Path(root) / rel).read_bytes()
        if a is None: problems.append('archive not listed in docs/EVIDENCE-ARCHIVES.json: ' + rel)
        elif hashlib.sha256(data).hexdigest() != a['sha256'] or (a['bytes'] is not None and len(data) != a['bytes']): problems.append('archive differs from its manifest entry: ' + rel)
    return problems
class EvidenceArchives(unittest.TestCase):
    def test_present_archives_match_manifest(self): self.assertEqual(verify_present(), [])
    def test_release_inventory_contains_no_evidence_archive(self):
        names = [n for n, _ in rc.build_inventory(rc.REQUIRED, rc.OPTIONAL, ROOT)]
        self.assertEqual([n for n in names if rc.excluded_from_candidate(n)], [])
        self.assertFalse(any(rc.excluded_from_candidate(r) for r in rc.REQUIRED))
    def test_exclusion_matches_nested_paths_and_windows_separators(self):
        self.assertTrue(rc.excluded_from_candidate('evidence/a/b/tested-partial.zip')); self.assertTrue(rc.excluded_from_candidate('tests\\review-evidence\\r\\x.zip'))
        self.assertFalse(rc.excluded_from_candidate('evidence/a/run-record.json')); self.assertFalse(rc.excluded_from_candidate('acceptance/x.zip'))
    def test_entries_are_well_formed(self):
        for a in manifest()['archives']:
            self.assertRegex(a['sha256'], r'^[0-9a-f]{64}$', a['id']); self.assertTrue(a['retained_at'], a['id'])
    def test_unlisted_archive_is_reported(self):
        import tempfile, shutil
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / 'docs').mkdir(); shutil.copyfile(ROOT / 'docs' / 'EVIDENCE-ARCHIVES.json', Path(t) / 'docs' / 'EVIDENCE-ARCHIVES.json')
            (Path(t) / 'evidence' / 'x').mkdir(parents=True); (Path(t) / 'evidence' / 'x' / 'stray.zip').write_bytes(b'PK')
            self.assertEqual(verify_present(t), ['archive not listed in docs/EVIDENCE-ARCHIVES.json: evidence/x/stray.zip'])
    def test_uppercase_archive_is_reported_and_excluded(self):
        import tempfile, shutil
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / 'docs').mkdir(); shutil.copyfile(ROOT / 'docs' / 'EVIDENCE-ARCHIVES.json', Path(t) / 'docs' / 'EVIDENCE-ARCHIVES.json')
            (Path(t) / 'evidence' / 'x').mkdir(parents=True)
            (Path(t) / 'evidence' / 'x' / 'stray.ZIP').write_bytes(b'PK')
            self.assertEqual(present_archives(t), ['evidence/x/stray.ZIP'])
            self.assertEqual(verify_present(t), ['archive not listed in docs/EVIDENCE-ARCHIVES.json: evidence/x/stray.ZIP'])
            self.assertTrue(rc.excluded_from_candidate('evidence/x/stray.ZIP'))
if __name__ == '__main__': unittest.main(verbosity=1)
