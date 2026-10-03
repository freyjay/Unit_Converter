#!/usr/bin/env python3
"""Portable team check; use a temporary copy so tests do not rewrite committed evidence."""
from pathlib import Path
import argparse, datetime, hashlib, importlib.util, json, os, platform, shutil, subprocess, sys, tempfile, time

ROOT = Path(__file__).resolve().parent.parent

def ignore_runtime(directory, names):
    skipped = {'.git','.checks','.venv','venv','__pycache__','node_modules','.DS_Store'}
    return [n for n in names if n in skipped or n.endswith('.pyc') or n.startswith('.env') or
            (Path(directory).resolve()==ROOT and (n.startswith('point-file-unit-converter-') and ('.zip' in n or '.candidate-' in n)))]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=['core','browser'], default='core')
    args = parser.parse_args()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    out = ROOT/'.checks'/(stamp+'-'+args.suite); out.mkdir(parents=True)
    record = {'schema':'pointtruth-team-check/1','suite':args.suite,'outcome':'RUNNING',
              'started_utc':stamp,'environment':{'platform':platform.platform(),'python':sys.version},
              'application_hashes':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in
                                   ['Point-File-Unit-Converter.html','pointfile_units.py']},
              'runs':[],'native_cad_execution':False,'full_release_acceptance':False,
              'tool_hashes':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in
                             ['scripts/check.py','scripts/check_repository.py','tests/run_all_tests.py','tests/run_browser_tests.py',
                              'tests/test_browser_paths.py','tests/release_check.py','tests/capacity/measure_lifecycle.py'] if (ROOT/n).exists()},
              'settings':{'suite':args.suite,'PYTHONUTF8':'0','PYTHONIOENCODING':'utf-8','PFU_SLOW':'0 (slow 16 MiB lifecycle skipped)',
                          'browser_csp':'regression suite: diagnostic (CSP bypass, test diagnostics on); lifecycle runs: normal CSP' if args.suite=='browser' else 'n/a'},
              'provenance_note':'environment, tool_hashes and settings are recorded during this run'}
    try:
        import importlib.metadata as _md; record['environment']['playwright_package']=_md.version('playwright')
    except Exception: record['environment']['playwright_package']=None
    try:
        rev=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,timeout=20)
        if rev.returncode==0:
            dirty=subprocess.run(['git','status','--porcelain'],cwd=ROOT,capture_output=True,text=True,timeout=20).stdout
            record['git']={'commit':rev.stdout.strip(),'modified_or_untracked_entries':len([l for l in dirty.splitlines() if l.strip()])}
    except Exception: pass
    def save(): (out/'run-record.json').write_bytes(json.dumps(record,indent=2).encode('utf-8'))
    save()
    env = dict(os.environ,PYTHONUTF8='0',PYTHONIOENCODING='utf-8',PFU_SLOW='0')
    env.pop('PT_HTML',None)
    def run(name, command, cwd, timeout=1800):
        started=time.monotonic(); print('Running '+name,flush=True)
        entry={'name':name,'command':[str(x) for x in command],'outcome':'RUNNING'}
        record['runs'].append(entry); save()
        with (out/(name+'.log')).open('w',encoding='utf-8') as log:
            result=subprocess.run(entry['command'],cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
        entry.update(exit_code=result.returncode,seconds=round(time.monotonic()-started,3),outcome='PASS' if result.returncode==0 else 'FAIL');save()
        if result.returncode: raise RuntimeError(name+' failed; see '+str(out/(name+'.log')))
    try:
        if shutil.which('node') is None: raise RuntimeError('Node.js 24 is required for the JavaScript comparison tests')
        record['environment']['node']=subprocess.check_output(['node','--version'],text=True).strip()
        if args.suite=='browser' and importlib.util.find_spec('playwright') is None:
            raise RuntimeError('Browser dependencies missing: see docs/BROWSER-TESTS.md; browser checks cannot be skipped')
        with tempfile.TemporaryDirectory(prefix='PointTruth team checks ') as tmp:
            copy=Path(tmp)/'repository copy with spaces'
            shutil.copytree(ROOT,copy,ignore=ignore_runtime)
            run('repository-structure',[sys.executable,copy/'scripts/check_repository.py'],copy)
            if args.suite=='core':
                run('extracted-package-core',[sys.executable,copy/'tests/release_check.py','--partial'],copy)
                run('next-fixture-checker',[sys.executable,copy/'acceptance/next-native-tests/test_checker.py'],copy)
                artifact=copy/'point-file-unit-converter-v3.3.9-team-candidate-partial.zip'
                shutil.copyfile(artifact,out/'tested-partial.zip')
                shutil.copyfile(artifact.with_suffix('.zip.record.json'),out/'tested-partial.zip.record.json')
                record['tested_partial_sha256']=hashlib.sha256(artifact.read_bytes()).hexdigest()
                record['tested_payload_identity']=json.loads(artifact.with_suffix('.zip.record.json').read_text(encoding='utf-8')).get('payload_identity')
                record['scope']='Python/Node and utility controls only; browser deliberately skipped; supplied CAD files only'
            else:
                run('browser-regressions-diagnostic-csp',[sys.executable,copy/'tests/run_browser_tests.py'],copy)
                for closed in [False,True]:
                    label='producer-closed' if closed else 'producer-open'
                    command=[sys.executable,copy/'tests/capacity/measure_lifecycle.py','--sizes','1','--out',out/label]
                    if closed: command.append('--close-producer')
                    run('normal-csp-'+label,command,copy)
                    try: record['environment']['browser']=json.loads((out/label/'capacity-record.json').read_text(encoding='utf-8'))['environment'].get('browser'); save()
                    except Exception: pass
                record['scope']='Chromium diagnostic regression suite plus normal-CSP 1 MiB save/reopen/download lifecycle with producer open and closed; not a capacity limit measurement'
        record['outcome']='PASS'
    except (Exception,KeyboardInterrupt) as exc:
        record.update(outcome='FAIL',error=type(exc).__name__+': '+str(exc))
        print(record['error'],file=sys.stderr)
    record['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
    print('Results: '+str(out));print('Outcome: '+record['outcome'])
    return 0 if record['outcome']=='PASS' else 1

if __name__=='__main__':sys.exit(main())
