#!/usr/bin/env python3
"""Capacity measurement as a lifecycle, with a record (pfu-capacity-record/4). Stages, each timed with its own monotonic timer
and each recorded before it starts: generate -> browser_context -> load -> convert_verify -> download_from_producer ->
save_handoff -> embedded_identity -> reopen -> download_from_reopened. Failures keep the failing stage, its elapsed time and the
original error; cleanup problems are recorded separately and fail the lifecycle without replacing the original data error. The run-level verdict covers startup through shutdown, including record writes. Memory: a
sampled sum of PSS (RSS where PSS is unreadable) for browser processes that are DESCENDANTS OF THIS RUNNER, 0.5 s interval,
Linux /proc only; the metric is named as such in the record and is not a physical-headroom claim (F13-02).
Usage: python3 measure_lifecycle.py --sizes 16,64 --out DIR [--close-producer] [--bypass-csp] [--full-diagnostics] [--desc-len N]
[--multibyte]     |     python3 measure_lifecycle.py --self-test   (fake driver: injected failures at load, convert, download,
and in cleanup; asserts every failed run returns nonzero, retains the original error, and persists outcome/stage/elapsed;
plus a synthetic /proc attribution test for the sampler)."""
import argparse, hashlib, json, os, pathlib, platform, random, subprocess, sys, time, datetime, threading, tempfile
ROOT = pathlib.Path(__file__).resolve().parent.parent.parent; APP = ROOT / "Point-File-Unit-Converter.html"; SELF = pathlib.Path(__file__).resolve()
NAV_WATCHDOG_MS = 30 * 60 * 1000
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def log(msg): print(time.strftime("%H:%M:%S"), msg, file=sys.stderr, flush=True)
def gen(path, mib, desc_len, multibyte):
    random.seed(mib); target = mib * 1024 * 1024; parts = []; size = 0; i = 0; desc = ("測量" * (desc_len // 2 + 1))[:desc_len] if multibyte else "G" * desc_len
    while size < target:
        i += 1; line = '%d %.4f %.4f %.4f "%s"\n' % (i, 19800 + random.random() * 400, 20200 + random.random() * 900, 95 + random.random() * 7, desc); b = len(line.encode("utf-8"))
        if size + b > target: break
        parts.append(line); size += b
    with open(path, "w", encoding="utf-8", newline="") as fh: fh.write("".join(parts))
    return len(parts), size
def mem_available_mib(proc="/proc"):
    try:
        for l in open(proc + "/meminfo"):
            if l.startswith("MemAvailable"): return int(l.split()[1]) // 1024
    except Exception: return None
# ---- memory sampler: descendants of root_pid only ----
def _read(proc, pid, name):
    try: return pathlib.Path(proc, str(pid), name).read_bytes()
    except Exception: return None
def descendant_browser_pids(proc, root_pid):
    parents = {}; cmds = {}
    for pid in os.listdir(proc):
        if not pid.isdigit(): continue
        st = _read(proc, pid, "status")
        if st is None: continue
        for l in st.decode("utf-8", "replace").splitlines():
            if l.startswith("PPid:"): parents[int(pid)] = int(l.split()[1]); break
        cmds[int(pid)] = _read(proc, pid, "cmdline") or b""
    def is_desc(p):
        seen = 0
        while p and p != root_pid and seen < 64: p = parents.get(p, 0); seen += 1
        return p == root_pid
    return [p for p in cmds if p != root_pid and is_desc(p) and any(k in cmds[p] for k in (b"headless_shell", b"chrome", b"chromium"))]
def sample_tree_snapshot(proc, root_pid):
    contributors = []
    missing = []
    for pid in descendant_browser_pids(proc, root_pid):
        value, metric = None, 'pss'
        roll = _read(proc, pid, 'smaps_rollup')
        if roll:
            for line in roll.decode('utf-8', 'replace').splitlines():
                if line.startswith('Pss:'): value = int(line.split()[1]); break
        if value is None:
            metric = 'rss'
            status = _read(proc, pid, 'status') or b''
            for line in status.decode('utf-8', 'replace').splitlines():
                if line.startswith('VmRSS:'): value = int(line.split()[1]); break
        if value is None:
            missing.append(pid)
        else:
            contributors.append({'pid': pid, 'metric': metric, 'kib': value})
    metrics = {item['metric'] for item in contributors}
    metric = next(iter(metrics)) if len(metrics) == 1 else ('mixed_pss_rss' if metrics else 'no_readable_browser_processes')
    return {'mib': sum(item['kib'] for item in contributors) / 1024,
            'metric': metric, 'contributors': contributors, 'missing_pids': missing,
            'monotonic': time.monotonic()}

def sample_tree_mib(proc, root_pid):
    sample = sample_tree_snapshot(proc, root_pid)
    return sample['mib'], sample['metric']

def record_peak(mem, sample):
    # Peak provenance belongs to the same sample as the maximum, never the last sample.
    if sample['contributors'] and (mem.get('peak_browser_tree_mib') is None or sample['mib'] > mem['peak_browser_tree_mib']):
        mem['peak_browser_tree_mib'] = sample['mib']
        mem['peak_sample'] = sample
        mem['metric_used'] = sample['metric']

def start_sampler(mem, proc='/proc', root_pid=None):
    root_pid = root_pid or os.getpid()
    state = {'stop': False}
    mem['metric'] = 'Sampled sum of PSS with per-process RSS fallback for descendant browser processes, 0.5 s interval, Linux /proc. Mixed values and shared RSS are not physical headroom.'
    if not pathlib.Path(proc).is_dir():
        mem.update(available=False, reason='Linux /proc unavailable on this platform', peak_browser_tree_mib=None)
        return state
    mem['available'] = True
    event = threading.Event()
    state['event'] = event
    def run():
        while not state['stop']:
            try: record_peak(mem, sample_tree_snapshot(proc, root_pid))
            except Exception as exc:
                mem['sampling_error'] = str(exc)
                return
            event.wait(0.5)
    state['thread'] = threading.Thread(target=run, daemon=True)
    state['thread'].start()
    return state
def kernel_log_excerpt():
    try:
        r = subprocess.run(["dmesg"], capture_output=True, text=True, timeout=10); lines = [l for l in r.stdout.splitlines() if "Out of memory" in l or "oom-kill" in l or "Killed process" in l]; return lines[-6:] if lines else None
    except Exception: return None
def embedded_record(handoff_path):
    h = handoff_path.read_text(encoding="utf-8"); i = h.index('<script id="savedPackage" type="application/json">') + len('<script id="savedPackage" type="application/json">'); j = h.index('</script>', i)
    pkg = json.loads(h[i:j]); import base64
    return pkg["recordText"].encode("utf-8"), hashlib.sha256(base64.b64decode(pkg["outputBase64"], validate=True)).hexdigest()
# ---- drivers: the real one wraps Playwright; the fake one injects failures for --self-test ----
class PlaywrightDriver:
    def __init__(self, a):
        from playwright.sync_api import sync_playwright, Error as PWError
        self.PWError = PWError; self.a = a; self.ctx = None
        self.pw = sync_playwright().start()
        try:
            self.b = self.pw.chromium.launch(); self.version = "Chromium " + self.b.version
        except (Exception, KeyboardInterrupt) as original:
            try: self.pw.stop()
            except Exception as cleanup: original.add_note('Playwright startup cleanup: ' + str(cleanup))
            raise
    def new_context(self, entry):
        self.ctx = self.b.new_context(bypass_csp=self.a.bypass_csp, accept_downloads=True)
        if self.a.full_diagnostics: self.ctx.add_init_script("window.PFU_TEST_FULL_DIAGNOSTICS=true")
        self.pg = self.ctx.new_page(); self.pg.on("crash", lambda: entry["producer"].update(crashed=True)); self.pg.goto(APP.resolve().as_uri()); self.pg.wait_for_timeout(500)
    def _wait(self, pg, prefixes, timeout):
        t0 = time.monotonic(); st = ""
        while time.monotonic() - t0 < timeout:
            try: st = pg.text_content("#hdrStatus") or ""
            except self.PWError as ex: return "PAGE GONE: " + str(ex)[:80]
            if any(st.startswith(p) for p in prefixes): return st
            pg.wait_for_timeout(500)
        return st + " (timeout)"
    def load(self, src):
        self.pg.set_input_files("#fileInput", str(src)); st = self._wait(self.pg, ["loaded", "refused"], 600)
        if not st.startswith("loaded"): raise RuntimeError("load: " + st)
        return {"status": st[:40]}
    def convert(self):
        pg = self.pg; pg.select_option("#format", "PENZD"); pg.select_option("#header", "no"); pg.select_option("#mode", "units"); pg.select_option("#from", "ft"); pg.select_option("#to", "m"); pg.check("#confirm"); pg.click("#convertBtn"); st = self._wait(pg, ["checks passed", "refused"], 3600)
        if not st.startswith("checks passed"): raise RuntimeError("convert: " + st)
        return {"status": st[:40]}
    def download(self, pg, button, dest):
        with pg.expect_download(timeout=3600000) as d: pg.click(button)
        d.value.save_as(str(dest))
    def download_producer(self, o0, m0): self.download(self.pg, "#dlBtn", o0); self.download(self.pg, "#dlManBtn", m0)
    def save_handoff(self, hp): self.download(self.pg, "#dlHandoffBtn", hp)
    def close_producer(self): self.pg.close()
    def reopen(self, hp, entry):
        self.pg2 = self.ctx.new_page(); self.pg2.on("crash", lambda: entry["reopened"].update(crashed=True))
        try: self.pg2.goto(hp.resolve().as_uri(), timeout=NAV_WATCHDOG_MS)
        except self.PWError as ex: entry["reopened"]["navigation_failed"] = True; raise RuntimeError("reopen navigation failed: " + str(ex)[:120])
        st = self._wait(self.pg2, ["handoff verified", "handoff failed"], 3600)
        if not st.startswith("handoff verified"): raise RuntimeError("reopen: " + st)
        return {"status": st[:40]}
    def download_reopened(self, o2, m2): self.download(self.pg2, "#dlBtn", o2); self.download(self.pg2, "#dlManBtn", m2)
    def close_context(self):
        if self.ctx is not None:
            self.ctx.close()
            self.ctx = None
    def close(self):
        errors = []
        try: self.b.close()
        except Exception as exc: errors.append('browser.close: ' + str(exc))
        try: self.pw.stop()
        except Exception as exc: errors.append('playwright.stop: ' + str(exc))
        if errors: raise RuntimeError('; '.join(errors))
class FakeDriver:
    """no browser: writes plausible artifacts, fails where told"""
    def __init__(self, fail_at=None, fail_cleanup=False): self.fail_at = fail_at; self.version = "fake"; self.fail_cleanup = fail_cleanup
    def _maybe(self, stage):
        if self.fail_at == stage: raise RuntimeError("injected failure at " + stage)
    def new_context(self, entry): self._maybe("browser_context")
    def load(self, src): self._maybe("load"); return {"status": "loaded"}
    def convert(self): self._maybe("convert_verify"); return {"status": "checks passed"}
    def download_producer(self, o0, m0): self._maybe("download_from_producer"); o0.write_bytes(b"1 3.0480 6.0960 9.1440 \"G\"\n"); m0.write_text('{"fake":1}', encoding="utf-8")
    def save_handoff(self, hp):
        self._maybe("save_handoff"); import base64
        hp.write_text('<html><script id="savedPackage" type="application/json">' + json.dumps({"format": "pfu-handoff/3", "sourceBase64": base64.b64encode(b"x").decode(), "outputBase64": base64.b64encode(b"1 3.0480 6.0960 9.1440 \"G\"\n").decode(), "recordText": '{"fake":1}'}) + '</script></html>', encoding="utf-8")
    def close_producer(self): pass
    def reopen(self, hp, entry): self._maybe("reopen"); return {"status": "handoff verified"}
    def download_reopened(self, o2, m2): self._maybe("download_from_reopened"); o2.write_bytes(b"1 3.0480 6.0960 9.1440 \"G\"\n"); m2.write_text('{"fake":1}', encoding="utf-8")
    def close_context(self):
        if self.fail_cleanup: raise RuntimeError("injected cleanup failure")
    def close(self): pass
# ---- one size, one lifecycle ----
class RecordWriteError(RuntimeError):
    pass

def write_record(path, record):
    pending = path.with_name(path.name + '.pending')
    pending.write_bytes(json.dumps(record, indent=2, default=str, allow_nan=False).encode('utf-8'))
    os.replace(pending, path)

def run_size(drv, a, mib, out, rec, checkpoint, proc='/proc'):
    entry = {'mib_requested': mib, 'steps': {}, 'producer': {'crashed': False},
             'reopened': {'crashed': False, 'navigation_failed': False},
             'outcome': 'RUNNING', 'data_outcome': 'NOT RUN', 'cleanup_errors': []}
    rec['sizes'].append(entry)
    started = time.monotonic()
    src = out / ('src_%d.txt' % mib); hp = out / ('handoff_%d.html' % mib)
    o0 = out / ('converted_%d.out' % mib); m0 = out / ('converted_%d.manifest.json' % mib)
    o2 = out / ('reopened_%d.out' % mib); m2 = out / ('reopened_%d.manifest.json' % mib)
    entry['memory'] = {'available_mib_at_start': mem_available_mib(proc), 'peak_browser_tree_mib': None}
    sampler = start_sampler(entry['memory'], proc)
    context_attempted = False
    prod, emb = {}, {}

    def step(name, fn):
        t = time.monotonic()
        entry['active_stage'] = {'name': name, 'started_monotonic': t}
        try:
            checkpoint()
            result = fn()
            entry['steps'][name] = dict(result or {}, seconds=round(time.monotonic() - t, 3))
            checkpoint()
        except (Exception, KeyboardInterrupt):
            entry['steps'][name] = {'failed': True, 'seconds': round(time.monotonic() - t, 3)}
            raise
        entry.pop('active_stage', None)
        return result

    try:
        def generate():
            rows, size = gen(src, mib, a.desc_len, a.multibyte)
            entry.update(rows=rows, source_bytes=size, source_sha256=sha(src),
                         note_size='Generated at most the target; not an exact limit boundary.')
            return {'rows': rows}
        step('generate', generate)
        context_attempted = True
        step('browser_context', lambda: drv.new_context(entry))
        step('load', lambda: drv.load(src))
        step('convert_verify', drv.convert)
        def download_producer():
            drv.download_producer(o0, m0)
            prod.update(output_bytes=o0.stat().st_size, output_sha256=sha(o0), manifest_sha256=sha(m0))
            return dict(prod)
        step('download_from_producer', download_producer)
        def save_handoff():
            drv.save_handoff(hp)
            return {'bytes': hp.stat().st_size, 'sha256': sha(hp)}
        step('save_handoff', save_handoff)
        def embedded_identity():
            rt, osha = embedded_record(hp)
            emb.update(record_text_sha256=hashlib.sha256(rt).hexdigest(), embedded_output_sha256=osha,
                       record_text_equals_producer_manifest_download=hashlib.sha256(rt).hexdigest() == prod['manifest_sha256'],
                       embedded_output_equals_producer_output_download=osha == prod['output_sha256'])
            return dict(emb)
        step('embedded_identity', embedded_identity)
        if a.close_producer:
            step('close_producer', drv.close_producer)
            entry['producer']['closed_before_reopen'] = True
        step('reopen', lambda: drv.reopen(hp, entry))
        def download_reopened():
            drv.download_reopened(o2, m2)
            return {'output_identical_to_producer_download': sha(o2) == prod['output_sha256'],
                    'manifest_identical_to_producer_download': sha(m2) == prod['manifest_sha256'],
                    'manifest_identical_to_embedded_record_text': sha(m2) == emb['record_text_sha256']}
        identities = step('download_from_reopened', download_reopened)
        ok = all(identities.values()) and emb['record_text_equals_producer_manifest_download'] and emb['embedded_output_equals_producer_output_download'] and not entry['producer']['crashed'] and not entry['reopened']['crashed']
        entry['data_outcome'] = 'PASSED' if ok else 'FAILED'
        if not ok:
            entry.update(error='identity or crash check failed', failed_stage='identity_verdict')
    except (Exception, KeyboardInterrupt) as exc:
        entry.update(data_outcome='FAILED', error=type(exc).__name__ + ': ' + str(exc),
                     failed_stage=entry.pop('active_stage', {}).get('name'),
                     interrupted=isinstance(exc, KeyboardInterrupt))
        crashed = entry['producer']['crashed'] or entry['reopened']['crashed']
        kernel = kernel_log_excerpt() if crashed else None
        entry['failure_cause'] = {'label': 'renderer crash event observed; cause not established' if crashed else 'unknown; see original error', 'kernel_log_excerpt': kernel}
    finally:
        # Persist data verdict while the full lifecycle is still RUNNING.
        def persist():
            try:
                checkpoint()
            except Exception as exc:
                entry['record_write_error'] = str(exc)
                print('Capacity record write failed: ' + str(exc), file=sys.stderr)
        persist()
        t = time.monotonic()
        if context_attempted:
            try:
                drv.close_context()
            except (Exception, KeyboardInterrupt) as exc:
                entry['cleanup_errors'].append(type(exc).__name__ + ': ' + str(exc))
                if isinstance(exc, KeyboardInterrupt): entry['interrupted'] = True
        sampler['stop'] = True
        if sampler.get('event'): sampler['event'].set()
        if sampler.get('thread'): sampler['thread'].join(timeout=2)
        if sampler.get('thread') and sampler['thread'].is_alive():
            entry['cleanup_errors'].append('Memory sampler did not stop within 2 seconds')
        for path in (hp, src, o0, o2):
            try:
                if path.exists() and path.stat().st_size > 20 * 1024 * 1024: path.unlink()
            except OSError as exc:
                entry['cleanup_errors'].append('unlink %s: %s' % (path.name, exc))
        entry['steps']['cleanup'] = {'seconds': round(time.monotonic() - t, 3), 'failed': bool(entry['cleanup_errors'])}
        if entry['cleanup_errors']:
            entry['cleanup_error'] = '; '.join(entry['cleanup_errors'])
            entry.setdefault('failed_stage', 'cleanup')
        entry['outcome'] = 'PASSED' if entry['data_outcome'] == 'PASSED' and not entry['cleanup_errors'] and not entry.get('record_write_error') else 'FAILED'
        entry['total_elapsed_seconds'] = round(time.monotonic() - started, 3)
        persist()
        if entry.get('record_write_error'): entry['outcome'] = 'FAILED'
    return entry

def main(argv=None, driver_factory=None, record_writer=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--sizes', default='16'); ap.add_argument('--out')
    ap.add_argument('--desc-len', type=int, default=6); ap.add_argument('--multibyte', action='store_true')
    ap.add_argument('--close-producer', action='store_true'); ap.add_argument('--bypass-csp', action='store_true')
    ap.add_argument('--full-diagnostics', action='store_true'); ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args(argv)
    if a.self_test:
        return subprocess.run([sys.executable, str(ROOT / 'tests/test_utility_repairs.py'), 'CapacityTests']).returncode
    if not a.out: ap.error('--out is required')
    try:
        sizes = [int(x) for x in a.sizes.split(',')]
        if not sizes or min(sizes) < 1 or len(set(sizes)) != len(sizes) or a.desc_len < 0:
            raise ValueError('Sizes must be distinct positive integers; description length must be nonnegative')
    except ValueError as exc:
        ap.error(str(exc))
    out = pathlib.Path(a.out)
    try:
        out.mkdir(parents=True, exist_ok=False)
    except OSError as exc:
        print('Cannot create new capacity output directory: ' + str(exc), file=sys.stderr)
        return 1
    rec = {'schema': 'pfu-capacity-record/4', 'runner': {'file': SELF.name, 'sha256': sha(SELF)},
           'app': {'file': APP.name, 'sha256': sha(APP)},
           'environment': {'os': platform.platform(), 'python': platform.python_version(), 'memory_total_mib': None},
           'parameters': vars(a) | {'navigation_watchdog_ms': NAV_WATCHDOG_MS},
           'run_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'sizes': [], 'steps': {}, 'errors': [], 'outcome': 'RUNNING', 'exit_code': None}
    path = out / 'capacity-record.json'
    writer = record_writer or write_record
    factory = driver_factory or PlaywrightDriver
    drv = None

    def checkpoint():
        try:
            writer(path, rec)
        except Exception as exc:
            raise RecordWriteError(str(exc)) from exc

    def failure(stage, exc):
        rec['errors'].append({'stage': stage, 'error': type(exc).__name__ + ': ' + str(exc), 'notes': getattr(exc, '__notes__', [])})
        if isinstance(exc, KeyboardInterrupt): rec['interrupted'] = True
        print('Capacity %s failed: %s: %s' % (stage, type(exc).__name__, exc), file=sys.stderr)

    try:
        # A launch failure must leave a record. This checkpoint precedes initialization.
        rec['active_stage'] = 'startup'
        checkpoint()
        t = time.monotonic()
        try:
            drv = factory(a)
            rec['environment']['browser'] = drv.version
        finally:
            rec['steps']['startup'] = {'seconds': round(time.monotonic() - t, 3), 'failed': drv is None}
        rec['active_stage'] = 'sizes'
        checkpoint()
        for mib in sizes:
            entry = run_size(drv, a, mib, out, rec, checkpoint)
            print(json.dumps({'mib': mib, 'data_outcome': entry['data_outcome'], 'outcome': entry['outcome'], 'failed_stage': entry.get('failed_stage')}))
            if entry.get('interrupted'):
                rec['interrupted'] = True
                break
    except (Exception, KeyboardInterrupt) as exc:
        failure(rec.get('active_stage', 'unknown'), exc)
    finally:
        if drv is not None:
            rec['active_stage'] = 'shutdown'
            try: checkpoint()
            except Exception as exc: failure('record_write_before_shutdown', exc)
            t = time.monotonic()
            try:
                drv.close()
                rec['steps']['shutdown'] = {'failed': False}
            except (Exception, KeyboardInterrupt) as exc:
                rec['steps']['shutdown'] = {'failed': True}
                failure('shutdown', exc)
            rec['steps']['shutdown']['seconds'] = round(time.monotonic() - t, 3)
        rec['active_stage'] = None
        rec['data_outcome'] = 'PASSED' if len(rec['sizes']) == len(sizes) and all(e['data_outcome'] == 'PASSED' for e in rec['sizes']) else 'FAILED'
        success = not rec['errors'] and len(rec['sizes']) == len(sizes) and all(e['outcome'] == 'PASSED' for e in rec['sizes'])
        rec['outcome'] = 'PASSED' if success else 'FAILED'
        rec['exit_code'] = 0 if success else (130 if rec.get('interrupted') else 1)
        try:
            checkpoint()
        except Exception as exc:
            failure('final_record_write', exc)
            rec.update(outcome='FAILED', exit_code=1)
            # A transient final-write error may be recoverable; preserve it rather than declaring success.
            try: checkpoint()
            except Exception as retry_error: failure('final_record_write_retry', retry_error)
    print('record:', path, 'outcome:', rec['outcome'])
    return rec['exit_code']

if __name__ == '__main__':
    sys.exit(main())
