#!/usr/bin/env python3
"""Check portable layout, pinned CI references and package contracts without a browser."""
from pathlib import Path
import ast, hashlib, json, re, sys

ROOT=Path(__file__).resolve().parent.parent
REQUIRED=['Point-File-Unit-Converter.html','pointfile_units.py','README.md','START-HERE-MAC.md',
          'GITHUB-PUSH.md','.gitignore','.gitattributes','.github/workflows/checks.yml',
          'requirements-browser.txt','docs/CURRENT-STATUS.md','docs/PROVENANCE.json','LICENSE-NOTE.md',
          'tests/test_utility_repairs.py','acceptance/civil3d-completed/civil3d-export.txt',
          'acceptance/next-native-tests/prepared-cases.json','tests/differential/PointTruth.html']
# Public profile (see tests/release_check.py): in a published copy, required files in declared private areas are not
# required, and any private path that is present is an error.
_PROFILE=ROOT/'docs'/'PUBLIC-PROFILE.json'
PRIVATE=json.loads(_PROFILE.read_text(encoding='utf-8'))['private_areas'] if _PROFILE.is_file() else []
REQUIRED=[n for n in REQUIRED if not any(n.startswith(a) for a in PRIVATE)]
if _PROFILE.is_file():
    REQUIRED += ['docs/PUBLIC-PROFILE.json', 'docs/PUBLIC-EVIDENCE-MAP.json']

def main():
    present=[a for a in PRIVATE if (ROOT/a).exists()]
    if present:raise ValueError('Public profile: private paths present: '+repr(present))
    missing=[n for n in REQUIRED if not (ROOT/n).is_file()]
    if missing:raise ValueError('Missing repository files: '+repr(missing))
    names=[p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file()
           and not any(part in {'.git','.checks','.venv','__pycache__'} for part in p.relative_to(ROOT).parts)]
    if len(names)!=len(set(n.casefold() for n in names)):raise ValueError('Case-colliding paths')
    html=(ROOT/'Point-File-Unit-Converter.html').read_bytes()
    scripts=re.findall(rb'<script\b[^>]*>[\s\S]*?</script>',html)
    provenance=json.loads((ROOT/'docs/PROVENANCE.json').read_bytes())
    if [hashlib.sha256(s).hexdigest() for s in scripts]!=provenance['application_script_sha256']:
        raise ValueError('Application scripts differ from the declared candidate; review and update provenance deliberately')
    if hashlib.sha256(html).hexdigest()!=provenance['html_sha256']:raise ValueError('HTML differs from declared package')
    if ('PAGE TEXT %s' % provenance.get('html_text_revision','?')).encode() not in html:raise ValueError('Visible page-text revision does not match PROVENANCE.json html_text_revision')
    sys.path.insert(0,str(ROOT/'tests')); import test_evidence_archives as _ea
    _problems=_ea.verify_present(ROOT)
    if _problems:raise ValueError('Evidence archives: '+'; '.join(_problems))
    if hashlib.sha256((ROOT/'pointfile_units.py').read_bytes()).hexdigest()!=provenance['python_sha256']:raise ValueError('Python engine differs from declared package')
    attributes=(ROOT/'.gitattributes').read_text(encoding='utf-8')
    if '* -text' not in attributes:raise ValueError('Byte-preserving Git attributes absent')
    workflow=(ROOT/'.github/workflows/checks.yml').read_text(encoding='utf-8')
    refs=re.findall(r'uses:\s+(actions/[\w-]+)@([^\s]+)',workflow)
    pins=json.loads((ROOT/'.github/action-pins.json').read_bytes())   # configuration, kept next to the workflow; the original evidence copy stays in evidence/current-package/
    if not refs or any(not re.fullmatch('[a-f0-9]{40}',pin) or pin!=pins[repo.split('/')[1]]['commit'] for repo,pin in refs):
        raise ValueError('CI actions must match recorded immutable commits')
    browser=(ROOT/'tests/run_browser_tests.py').read_text(encoding='utf-8')
    sys.path.insert(0,str(ROOT/'tests')); import test_browser_paths
    import tempfile
    with tempfile.TemporaryDirectory(prefix='uri check ') as _work: problems=test_browser_paths.check_runner_source(browser if isinstance(browser,str) else browser.decode('utf-8'),_work)
    if problems:raise ValueError('Browser runner navigation paths fail when executed: '+'; '.join(problems))
    for name in ['scripts/check.py','scripts/check_repository.py','tests/run_all_tests.py','tests/run_browser_tests.py','tests/release_check.py']:
        ast.parse((ROOT/name).read_text(encoding='utf-8'),filename=name)
    print(json.dumps({'passed':True,'casefold_unique':True,'action_references_checked':len(refs),
                      'html_sha256':provenance['html_sha256'],'scope':'Static repository checks; not macOS/browser/CI execution'},indent=2))
    return 0
if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,ValueError,KeyError) as exc:print(str(exc),file=sys.stderr);sys.exit(1)
