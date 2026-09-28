#!/usr/bin/env python3
"""Build the consumer release: the app, the CLI, the quick-start guide, the LICENSE and license note, plus their checksums.
Refuses to build unless the app and CLI bytes equal docs/PROVENANCE.json and the app shows the declared page-text
revision. Reproducible: fixed member order, timestamps and permissions, so identical inputs give identical ZIP bytes.
Usage: python3 scripts/build_consumer_release.py [--out DIR]   (default DIR: dist/)"""
from pathlib import Path
import argparse, hashlib, json, sys, zipfile
ROOT = Path(__file__).resolve().parent.parent
MEMBERS = ['Point-File-Unit-Converter.html', 'START-HERE.html', 'pointfile_units.py', 'QUICK-START.md', 'LICENSE', 'LICENSE-NOTE.md']
def sha(b): return hashlib.sha256(b).hexdigest()
def build(root, out_dir):
    root = Path(root); pv = json.loads((root / 'docs' / 'PROVENANCE.json').read_text(encoding='utf-8')); data = {m: (root / m).read_bytes() for m in MEMBERS}
    if sha(data['Point-File-Unit-Converter.html']) != pv['html_sha256']: raise SystemExit('refused: Point-File-Unit-Converter.html does not match PROVENANCE.json html_sha256')
    if sha(data['pointfile_units.py']) != pv['python_sha256']: raise SystemExit('refused: pointfile_units.py does not match PROVENANCE.json python_sha256')
    rev = pv.get('html_text_revision')
    if not rev or ('PAGE TEXT ' + rev).encode() not in data['Point-File-Unit-Converter.html']: raise SystemExit('refused: visible page-text revision does not match PROVENANCE.json')
    prefix = 'Unit_Converter-%s' % (pv.get('release_revision') or rev); data['CHECKSUMS.sha256'] = ''.join('%s  %s\n' % (sha(data[m]), m) for m in MEMBERS).encode('utf-8')
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True); out = out_dir / (prefix + '.zip'); tmp = out.with_suffix('.zip.partial')
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        for m in MEMBERS + ['CHECKSUMS.sha256']:
            info = zipfile.ZipInfo(prefix + '/' + m, date_time=(1980, 1, 1, 0, 0, 0)); info.create_system = 3; info.external_attr = 0o644 << 16; info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data[m])
    with zipfile.ZipFile(tmp) as z:
        if z.testzip() is not None: raise SystemExit('refused: CRC failure in the built release')
    tmp.replace(out); return out
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default=str(ROOT / 'dist')); a = ap.parse_args()
    out = build(ROOT, a.out); print('%s  sha256 %s' % (out, sha(out.read_bytes()))); return 0
if __name__ == '__main__': sys.exit(main())
