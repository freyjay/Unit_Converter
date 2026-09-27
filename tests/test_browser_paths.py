#!/usr/bin/env python3
"""Executed critical-path check for the browser runner's file URIs (core gate; no browser needed).

Why: a static check ("the file contains .as_uri()") passed a runner whose tamper-refusal navigation raised TypeError
(`Path(os).resolve().as_uri().path.join(...)`). This check executes instead of pattern-matching:
  1. the runner's module-level file_uri(), ROOT and APP definitions are executed as written (with __file__ set to the
     runner), and APP must resolve to this package's Point-File-Unit-Converter.html;
  2. file_uri is executed on a real file whose path contains spaces and '#'; the URI must encode them and map back;
  3. every page.goto(...) must be APP or file_uri(<expr>), and every <expr> is evaluated (free names bound to such a
     path, `os` to the real module) and passed through file_uri, so a broken expression raises here, not in a browser;
  4. the check must also pass where Playwright is not installed (the core gate never needs a browser);
  5. negative controls, each of which must be reported: the reproduced navigation defect, a well-shaped but broken
     file_uri(os) navigation, APP=file_uri(os), and APP pointing at the wrong file.
All temporary folders are removed. This supplements browser execution; it cannot replace it."""
import ast, os, sys, tempfile, pathlib, urllib.parse, urllib.request
RUNNER = pathlib.Path(__file__).resolve().parent / 'run_browser_tests.py'
EXPECTED_APP = RUNNER.parent.parent / 'Point-File-Unit-Converter.html'

def uri_to_path(uri): return urllib.request.url2pathname(urllib.parse.urlparse(uri).path)

def module_prefix(tree, src):
    """the module-level statements up to and including the APP assignment, restricted to imports, file_uri, and
    simple assignments (the runner's setup), so they can be executed without starting a browser"""
    keep = []
    for n in tree.body:
        if isinstance(n, (ast.Import, ast.ImportFrom)): keep.append(n)
        elif isinstance(n, ast.FunctionDef) and n.name == 'file_uri': keep.append(n)
        elif isinstance(n, ast.Assign) and all(isinstance(t, ast.Name) and t.id in ('HERE', 'ROOT', 'APP') for t in n.targets): keep.append(n)
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'APP' for t in n.targets): break
    return keep

def check_runner_source(src, work):
    problems = []; tree = ast.parse(src)
    if not any(isinstance(n, ast.FunctionDef) and n.name == 'file_uri' for n in tree.body): return ['no module-level file_uri(path) helper']
    if not any(isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'APP' for t in n.targets) for n in tree.body): return ['no module-level APP assignment']
    ns = {'__file__': str(RUNNER), '__name__': 'runner_setup_under_test'}
    for node in module_prefix(tree, src):
        code = compile(ast.Module(body=[node], type_ignores=[]), str(RUNNER), 'exec')
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            try: exec(code, ns)
            except ImportError: pass   # e.g. Playwright on a machine without the browser suite; file_uri/ROOT/APP must not need it
            continue
        try: exec(code, ns)
        except Exception as ex: return ['runner setup (file_uri/ROOT/APP) fails when executed: %s: %s' % (type(ex).__name__, ex)]
    file_uri = ns['file_uri']; app = ns.get('APP')
    try:
        if not (isinstance(app, str) and app.startswith('file:///') and os.path.samefile(uri_to_path(app), EXPECTED_APP)): problems.append('APP does not resolve to %s: %r' % (EXPECTED_APP.name, app))
    except OSError as ex: problems.append('APP does not resolve to an existing file: %r (%s)' % (app, ex))
    base = pathlib.Path(work) / 'dir with spaces #1'; base.mkdir(exist_ok=True); target = base / 'page #2.html'; target.write_text('x', encoding='utf-8')
    uri = file_uri(target)
    if not uri.startswith('file:///') or '%23' not in uri or '%20' not in uri or '#' in uri: problems.append('file_uri does not encode spaces and # as expected: ' + uri)
    elif not os.path.samefile(uri_to_path(uri), target): problems.append('file_uri does not map back to the same file: ' + uri)
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'goto'): continue
        a = n.args[0] if n.args else None; seg = ast.get_source_segment(src, a) if a is not None else '<none>'
        if isinstance(a, ast.Name) and a.id == 'APP': continue
        if not (isinstance(a, ast.Call) and isinstance(a.func, ast.Name) and a.func.id == 'file_uri' and len(a.args) == 1):
            problems.append('line %d: navigation does not go through file_uri(): %s' % (n.lineno, seg)); continue
        inner = a.args[0]; names = {x.id for x in ast.walk(inner) if isinstance(x, ast.Name)}
        env = {name: str(target) for name in names}; env.update(os=os, Path=pathlib.Path)
        try: file_uri(eval(compile(ast.Expression(inner), 'goto-arg', 'eval'), {'__builtins__': __builtins__}, env))
        except Exception as ex: problems.append('line %d: navigation expression fails when executed: %s (%s: %s)' % (n.lineno, seg, type(ex).__name__, ex))
    return problems

def main():
    src = RUNNER.read_text(encoding='utf-8'); ok = True
    with tempfile.TemporaryDirectory(prefix='uri check ') as work:
        real = check_runner_source(src, work); print('runner %s: %s' % (RUNNER.name, 'PASS' if not real else 'FAIL')); [print('  ' + p) for p in real]; ok &= not real
        nav = next(l for l in src.splitlines() if "t2.html')" in l and 'goto(' in l); ind = nav[:len(nav) - len(nav.lstrip())]
        app = next(l for l in src.splitlines() if l.startswith('APP='))
        controls = [('reproduced defect Path(os)...path.join', src.replace(nav, ind + "pg3.goto(Path(os).resolve().as_uri().path.join(W,'t2.html')); t0=time.time()")),
                    ('well-shaped but broken file_uri(os) navigation', src.replace(nav, ind + 'pg3.goto(file_uri(os)); t0=time.time()')),
                    ('APP=file_uri(os)', src.replace(app, 'APP=file_uri(os)')),
                    ('APP pointing at the wrong file', src.replace(app, "APP=file_uri(Path(ROOT)/'README.md')"))]
        for label, mutated in controls:
            assert mutated != src, label
            found = check_runner_source(mutated, work); print('negative control, %s: %s' % (label, 'detected' if found else 'NOT DETECTED')); ok &= bool(found)
        saved = {k: sys.modules.get(k) for k in ('playwright', 'playwright.sync_api')}
        sys.modules['playwright'] = None; sys.modules['playwright.sync_api'] = None   # simulate a machine without Playwright
        try: without = check_runner_source(src, work)
        finally:
            for k, v in saved.items():
                if v is None: sys.modules.pop(k, None)
                else: sys.modules[k] = v
        print('without Playwright installed: %s' % ('PASS' if not without else 'FAIL ' + '; '.join(without))); ok &= not without
    print('browser path check:', 'PASS' if ok else 'FAIL'); return 0 if ok else 1

if __name__ == '__main__': sys.exit(main())
