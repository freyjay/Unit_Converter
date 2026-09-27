#!/usr/bin/env python3
"""Regenerate PACKAGE-CONTENTS.sha256: one 'sha256  posix/path' line per file in the release inventory, sorted.
The file list comes from tests/release_check.py (REQUIRED + OPTIONAL), the same list the release builder packages, so
workspace files that are not part of the package (editor and assistant settings, project templates, .git) are never
indexed, and the builder's check that no indexed file is dropped stays consistent. Usage:
python3 scripts/update_package_contents.py"""
from pathlib import Path
import hashlib, importlib.util, sys
ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('release_inventory', ROOT / 'tests' / 'release_check.py'); rc = importlib.util.module_from_spec(spec); spec.loader.exec_module(rc)
def lines(root=ROOT):
    inv = rc.build_inventory(rc.REQUIRED, rc.OPTIONAL, Path(root))
    keep = sorted((name, src) for name, src in inv if name != 'PACKAGE-CONTENTS.sha256' and '__pycache__' not in name and not name.endswith(('.pyc', '.pyo')))
    return ['%s  %s' % (hashlib.sha256(Path(src).read_bytes()).hexdigest(), name) for name, src in keep]
def main():
    out = lines(); (ROOT / 'PACKAGE-CONTENTS.sha256').write_bytes(('\n'.join(out) + '\n').encode('utf-8'))
    print('PACKAGE-CONTENTS.sha256: %d files (release inventory)' % len(out)); return 0
if __name__ == '__main__': sys.exit(main())
