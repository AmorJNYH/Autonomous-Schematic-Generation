"""run_regression.py measures real deliveries and fails when a board gets worse than its baseline."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'scripts'))
sys.path.insert(0, str(HERE))
from test_design_report import Delivery  # noqa: E402
import run_regression  # noqa: E402


class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.d = Delivery()
        self.tmp = tempfile.TemporaryDirectory()
        self.boards = Path(self.tmp.name) / 'boards.json'
        self.baseline = Path(self.tmp.name) / 'baseline.json'
        self.boards.write_text(json.dumps({'schema_version': 1, 'boards': [
            {'id': 'b1', 'path': str(self.d.root), 'title': 'b1'},
            {'id': 'gone', 'path': str(Path(self.tmp.name) / 'missing')}]}))

    def tearDown(self):
        self.tmp.cleanup()
        self.d.tmp.cleanup()

    def test_new_then_pass_then_fail(self):
        r = run_regression.run(self.boards, self.baseline)
        self.assertEqual(('NEW', 'NEW', 'SKIPPED'), (r['status'], r['boards']['b1']['status'], r['boards']['gone']['status']))
        r = run_regression.run(self.boards, self.baseline, update=True)
        self.assertEqual('UPDATED', r['status'])
        base = json.loads(self.baseline.read_text())
        self.assertEqual(['b1'], list(base['boards']))
        self.assertEqual(0, base['boards']['b1']['report_problems'])
        self.assertEqual('PASS', run_regression.run(self.boards, self.baseline)['status'])
        (self.d.record / 'page-plan.json').unlink()
        r = run_regression.run(self.boards, self.baseline)
        self.assertEqual('FAIL', r['status'])
        self.assertTrue(any(x.startswith('report problems 0 -> ') for x in r['boards']['b1']['reasons']), r['boards']['b1'])

    def test_gate_getting_worse_fails(self):
        run_regression.run(self.boards, self.baseline, update=True)
        summary = json.loads((self.d.record / 'summary.json').read_text())
        summary['gates']['erc']['status'] = 'FAIL'
        self.d.write('summary.json', summary)
        r = run_regression.run(self.boards, self.baseline)
        self.assertIn('gate erc PASS -> FAIL', r['boards']['b1']['reasons'])


if __name__ == '__main__':
    unittest.main()
