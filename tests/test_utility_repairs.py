#!/usr/bin/env python3
"""Failure controls for utility publication and complete capacity-run verdicts.

These use a synthetic driver, not a browser; they establish failure handling,
not browser functionality or CAD acceptance. Run directly on Windows/macOS/Linux.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

HERE = Path(__file__).resolve().parent

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

release = load('release_under_test', HERE / 'release_check.py')
capacity = load('capacity_under_test', HERE / 'capacity/measure_lifecycle.py')

class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='utility release with spaces ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.script = self.root / 'runner.py'
        self.script.write_bytes(b'print("synthetic runner")\n')
        self.inventory = [('tests/run_all_tests.py', self.script)]
        self.out = self.root / 'accepted.zip'
        with zipfile.ZipFile(self.out, 'w') as z:
            z.writestr('previous.txt', b'previous accepted artifact')
        self.before = self.out.read_bytes()
        self.sidecar = self.out.with_suffix('.zip.record.json')
        self.sidecar.write_bytes(b'previous accepted record')

    def publish(self, **kw):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return release.publish_candidate(self.root, self.inventory, self.out, **kw)

    def unchanged(self):
        self.assertEqual(self.before, self.out.read_bytes())
        self.assertEqual(b'previous accepted record', self.sidecar.read_bytes())

    def test_inventory_normalizes_overlap(self):
        inv = release.build_inventory(['tests/review-evidence/a.md'], ['tests/review-evidence'], self.root,
                walker=lambda _: ['tests\\review-evidence\\a.md', 'tests\\review-evidence\\b.md'])
        self.assertEqual([n for n, _ in inv], ['tests/review-evidence/a.md', 'tests/review-evidence/b.md'])

    def test_case_collision_refused(self):
        with self.assertRaisesRegex(SystemExit, 'case-colliding'):
            release.build_inventory(['A.md', 'a.md'], [], self.root)

    def test_archive_inventory_binds_saved_members_not_stale_source_index(self):
        stale = self.root / 'stale.txt'
        stale.write_bytes(b'not a current inventory')
        candidate = self.root / 'inventory-test.zip'
        release.build_archive(candidate, self.inventory + [('PACKAGE-CONTENTS.sha256', stale)])
        with zipfile.ZipFile(candidate) as archive:
            lines = archive.read('PACKAGE-CONTENTS.sha256').decode().splitlines()
            self.assertEqual(len(lines), 1)
            digest, name = lines[0].split('  ', 1)
            self.assertEqual(name, 'tests/run_all_tests.py')
            self.assertEqual(digest, hashlib.sha256(archive.read(name)).hexdigest())

    def test_actual_rejected_subprocess_preserves_previous(self):
        self.script.write_bytes(b'import sys\nsys.exit(23)\n')
        code, record = self.publish()
        self.assertEqual(code, 23)
        self.assertEqual(record['outcome'], 'FAIL')
        self.assertFalse(record['promoted'])
        self.assertTrue((self.root / record['retained_candidate']).exists())
        self.unchanged()

    def test_actual_passing_subprocess_promotes_tested_bytes(self):
        self.script.write_bytes(b'from pathlib import Path\nassert " " in str(Path.cwd())\n')
        code, record = self.publish()
        self.assertEqual(code, 0)
        self.assertTrue(record['promoted'])
        self.assertTrue(record['full_release_accepted'])
        self.assertEqual(record['archive_sha256'], hashlib.sha256(self.out.read_bytes()).hexdigest())
        self.assertEqual(json.loads(self.sidecar.read_bytes())['archive_sha256'], record['archive_sha256'])
        with zipfile.ZipFile(self.out) as z:
            self.assertEqual(z.read('tests/run_all_tests.py'), self.script.read_bytes())

    def test_subprocess_launch_error(self):
        def fail(*args, **kwargs): raise OSError('injected launch failure')
        code, record = self.publish(runner=fail)
        self.assertNotEqual(code, 0)
        self.assertIn('injected launch failure', record['error'])
        self.unchanged()

    def test_build_failure_preserves_previous(self):
        def fail(path, inventory):
            path.write_bytes(b'incomplete ZIP')
            raise OSError('injected build failure')
        code, record = self.publish(builder=fail)
        self.assertNotEqual(code, 0)
        self.assertEqual(record['active_stage'], 'build')
        self.unchanged()

    def test_interrupted_build_preserves_previous(self):
        def fail(path, inventory):
            path.write_bytes(b'incomplete ZIP')
            raise KeyboardInterrupt('injected interrupt')
        code, record = self.publish(builder=fail)
        self.assertEqual((code, record['outcome']), (130, 'INTERRUPTED'))
        self.unchanged()

    def test_interrupted_gate_preserves_previous(self):
        def fail(*args, **kwargs): raise KeyboardInterrupt()
        code, record = self.publish(runner=fail)
        self.assertEqual(code, 130)
        self.unchanged()

    def test_archive_mutation_during_gate_is_refused(self):
        def mutate(*args, **kwargs):
            next(self.root.glob('*.candidate-*.zip')).write_bytes(b'not the archive tested')
            return types.SimpleNamespace(returncode=0)
        code, record = self.publish(runner=mutate)
        self.assertNotEqual(code, 0)
        self.assertIn('changed during testing', record['error'])
        self.unchanged()

    def test_record_write_failure_blocks_promotion(self):
        with patch.object(release, 'write_record', side_effect=PermissionError('injected storage failure')):
            code, record = self.publish()
        self.assertNotEqual(code, 0)
        self.assertFalse(record['promoted'])
        self.unchanged()

    def test_partial_is_labelled_partial(self):
        code, record = self.publish(partial=True, runner=lambda *a, **k: types.SimpleNamespace(returncode=0))
        self.assertEqual(code, 0)
        self.assertEqual(record['mode'], 'partial')
        self.assertFalse(record['full_release_accepted'])

    def test_main_selects_separate_partial_filename(self):
        with patch.object(release, 'ROOT', self.root), patch.object(release, 'validate_tree'), patch.object(release, 'build_inventory', return_value=[]), patch.object(release, 'publish_candidate', return_value=(0, {})) as publish:
            self.assertEqual(release.main(['--partial']), 0)
            partial = publish.call_args.args[2]
            self.assertEqual(release.main([]), 0)
            full = publish.call_args.args[2]
        self.assertNotEqual(partial, full)
        self.assertIn('-partial.zip', partial.name)
        self.unchanged()


class CapacityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='utility capacity ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.count = 0
        self.generate = capacity.gen
        def tiny(path, *args):
            path.write_bytes(b'1 10 20 30 G\n')
            return 1, path.stat().st_size
        self.gen_patch = patch.object(capacity, 'gen', tiny)
        self.gen_patch.start(); self.addCleanup(self.gen_patch.stop)

    def execute(self, factory=None, writer=None, args=()):
        self.count += 1
        out = self.root / ('run-%d' % self.count)
        stderr = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stderr):
            code = capacity.main(['--out', str(out), '--sizes', '1', *args],
                                 driver_factory=factory or (lambda a: capacity.FakeDriver()), record_writer=writer)
        path = out / 'capacity-record.json'
        record = json.loads(path.read_bytes()) if path.exists() else None
        return code, record, stderr.getvalue()

    def test_complete_success(self):
        code, rec, _ = self.execute()
        self.assertEqual(code, 0)
        self.assertEqual(rec['outcome'], 'PASSED')
        self.assertEqual(rec['data_outcome'], 'PASSED')
        self.assertFalse(rec['steps']['shutdown']['failed'])

    def test_exact_size_fixture_reports_actual_row_count(self):
        path = self.root / 'exact-one-mib.txt'
        claimed_rows, size = self.generate(path, 1, 8, False)
        self.assertEqual(size, 1048576)
        actual_rows = len(path.read_bytes().splitlines())
        self.assertEqual(actual_rows, 22409)
        self.assertEqual(claimed_rows, actual_rows)

    def test_operational_failure_stages(self):
        for stage in ('browser_context', 'load', 'convert_verify', 'download_from_producer', 'save_handoff', 'reopen', 'download_from_reopened'):
            with self.subTest(stage=stage):
                code, rec, _ = self.execute(lambda a: capacity.FakeDriver(fail_at=stage))
                entry = rec['sizes'][0]
                self.assertNotEqual(code, 0)
                self.assertEqual(rec['outcome'], 'FAILED')
                self.assertEqual(entry['failed_stage'], stage)
                self.assertIn('injected failure at ' + stage, entry['error'])
                self.assertTrue(entry['steps'][stage]['failed'])
                self.assertGreaterEqual(entry['steps'][stage]['seconds'], 0)

    def test_generation_failure(self):
        with patch.object(capacity, 'gen', side_effect=OSError('injected generation failure')):
            code, rec, _ = self.execute()
        self.assertNotEqual(code, 0)
        self.assertEqual(rec['sizes'][0]['failed_stage'], 'generate')

    def test_embedded_read_failure(self):
        with patch.object(capacity, 'embedded_record', side_effect=ValueError('injected embedded failure')):
            code, rec, _ = self.execute()
        self.assertNotEqual(code, 0)
        self.assertEqual(rec['sizes'][0]['failed_stage'], 'embedded_identity')

    def test_identity_mismatch_fails(self):
        class Changed(capacity.FakeDriver):
            def download_reopened(self, output, manifest):
                super().download_reopened(output, manifest)
                output.write_bytes(b'changed')
        code, rec, _ = self.execute(lambda a: Changed())
        self.assertNotEqual(code, 0)
        self.assertEqual(rec['sizes'][0]['failed_stage'], 'identity_verdict')

    def test_cleanup_only_retains_data_pass_but_fails_lifecycle(self):
        code, rec, _ = self.execute(lambda a: capacity.FakeDriver(fail_cleanup=True))
        self.assertNotEqual(code, 0)
        self.assertEqual(rec['data_outcome'], 'PASSED')
        self.assertEqual(rec['outcome'], 'FAILED')
        self.assertEqual(rec['sizes'][0]['failed_stage'], 'cleanup')

    def test_cleanup_does_not_mask_original_error(self):
        code, rec, _ = self.execute(lambda a: capacity.FakeDriver(fail_at='load', fail_cleanup=True))
        entry = rec['sizes'][0]
        self.assertNotEqual(code, 0)
        self.assertIn('injected failure at load', entry['error'])
        self.assertIn('injected cleanup failure', entry['cleanup_error'])

    def test_startup_failure_has_record(self):
        def fail(a): raise RuntimeError('injected startup failure')
        code, rec, _ = self.execute(fail)
        self.assertNotEqual(code, 0)
        self.assertEqual(rec['outcome'], 'FAILED')
        self.assertEqual(rec['errors'][0]['stage'], 'startup')
        self.assertIn('injected startup failure', rec['errors'][0]['error'])
        self.assertTrue(rec['steps']['startup']['failed'])

    def test_shutdown_failure_has_record(self):
        class Fail(capacity.FakeDriver):
            def close(self): raise RuntimeError('injected shutdown failure')
        code, rec, _ = self.execute(lambda a: Fail())
        self.assertNotEqual(code, 0)
        self.assertEqual(rec['data_outcome'], 'PASSED')
        self.assertEqual(rec['outcome'], 'FAILED')
        self.assertEqual(rec['errors'][0]['stage'], 'shutdown')

    def test_original_failure_and_shutdown_failure_both_survive(self):
        class Fail(capacity.FakeDriver):
            def close(self): raise RuntimeError('injected shutdown failure')
        code, rec, _ = self.execute(lambda a: Fail(fail_at='load'))
        self.assertNotEqual(code, 0)
        self.assertIn('injected failure at load', rec['sizes'][0]['error'])
        self.assertIn('injected shutdown failure', rec['errors'][0]['error'])

    def test_record_storage_unavailable_nonzero_stderr(self):
        def fail(path, rec): raise PermissionError('injected record storage unavailable')
        code, rec, stderr = self.execute(writer=fail)
        self.assertNotEqual(code, 0)
        self.assertIsNone(rec)
        self.assertIn('injected record storage unavailable', stderr)

    def test_final_write_failure_persists_failed_retry(self):
        failed = False
        def writer(path, record):
            nonlocal failed
            if record['outcome'] == 'PASSED' and not failed:
                failed = True
                raise OSError('injected final write failure')
            capacity.write_record(path, record)
        code, rec, stderr = self.execute(writer=writer)
        self.assertNotEqual(code, 0)
        self.assertEqual(rec['outcome'], 'FAILED')
        self.assertIn('injected final write failure', stderr)

    def test_midrun_write_failure_prevents_false_pass(self):
        failed = False
        def writer(path, record):
            nonlocal failed
            if record['sizes'] and record['sizes'][0].get('active_stage', {}).get('name') == 'load' and not failed:
                failed = True
                raise OSError('injected checkpoint failure')
            capacity.write_record(path, record)
        code, rec, _ = self.execute(writer=writer)
        self.assertNotEqual(code, 0)
        self.assertEqual(rec['outcome'], 'FAILED')
        self.assertIn('injected checkpoint failure', rec['sizes'][0]['error'])

    def test_interrupt_is_nonzero_and_recorded(self):
        class Interrupt(capacity.FakeDriver):
            def load(self, src): raise KeyboardInterrupt('injected interrupt')
        code, rec, _ = self.execute(lambda a: Interrupt())
        self.assertEqual(code, 130)
        self.assertTrue(rec['interrupted'])
        self.assertEqual(rec['outcome'], 'FAILED')

    def test_close_producer_is_timed_failure_stage(self):
        class Fail(capacity.FakeDriver):
            def close_producer(self): raise RuntimeError('injected close producer failure')
        code, rec, _ = self.execute(lambda a: Fail(), args=['--close-producer'])
        self.assertNotEqual(code, 0)
        self.assertEqual(rec['sizes'][0]['failed_stage'], 'close_producer')

    def test_sampler_excludes_unrelated_processes_and_records_peak_contributors(self):
        proc = self.root / 'proc'; proc.mkdir()
        def make(pid, parent, cmd, rss, pss=None):
            d = proc / str(pid); d.mkdir()
            (d / 'status').write_bytes(('PPid:\t%d\nVmRSS:\t%d kB\n' % (parent, rss)).encode())
            (d / 'cmdline').write_bytes(cmd)
            if pss is not None: (d / 'smaps_rollup').write_bytes(('Pss:\t%d kB\n' % pss).encode())
        make(1000, 1, b'python chromium-results', 900000)
        make(1001, 1000, b'node', 5000)
        make(1002, 1001, b'headless_shell', 102400, 51200)
        make(1003, 1002, b'chrome renderer', 25600)
        make(2000, 1, b'chrome unrelated', 500000)
        sample = capacity.sample_tree_snapshot(str(proc), 1000)
        self.assertEqual(sample['mib'], 75)
        self.assertEqual(sample['metric'], 'mixed_pss_rss')
        self.assertEqual({p['pid'] for p in sample['contributors']}, {1002, 1003})
        mem = {'peak_browser_tree_mib': None}
        capacity.record_peak(mem, sample)
        capacity.record_peak(mem, dict(mib=10, metric='rss', contributors=[{'pid': 9999}], missing_pids=[], monotonic=0))
        self.assertEqual(mem['metric_used'], 'mixed_pss_rss')
        self.assertEqual(mem['peak_sample'], sample)

    def test_memory_unavailable_is_explicit(self):
        mem = {}
        capacity.start_sampler(mem, str(self.root / 'missing-proc'))
        self.assertFalse(mem['available'])
        self.assertIsNone(mem['peak_browser_tree_mib'])

class DeliveredFileSurvivalTests(unittest.TestCase):
    def test_build_refuses_to_drop_a_delivered_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / 'docs').mkdir(); (root / 'a.txt').write_text('a', encoding='utf-8'); (root / 'docs' / 'README.md').write_text('index', encoding='utf-8')
            (root / 'PACKAGE-CONTENTS.sha256').write_text(''.join(hashlib.sha256((root / n).read_bytes()).hexdigest() + '  ' + n + '\n' for n in ['a.txt', 'docs/README.md']), encoding='utf-8')
            full = [('PACKAGE-CONTENTS.sha256', root / 'PACKAGE-CONTENTS.sha256'), ('a.txt', root / 'a.txt'), ('docs/README.md', root / 'docs' / 'README.md')]
            self.assertEqual(release.build_archive(root / 'ok.zip', full), 3)
            with self.assertRaisesRegex(ValueError, 'dropped delivered files: docs/README.md'):
                release.build_archive(root / 'bad.zip', [x for x in full if x[0] != 'docs/README.md'])
    def test_docs_index_is_required(self):
        self.assertIn('docs/README.md', release.REQUIRED)

if __name__ == '__main__':
    unittest.main(verbosity=2)
