"""Page fit, occupancy and part-group diagnostics of the readability gate (HR-11)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / 'scripts'), str(HERE / 'fixtures' / 'drawing')]
from recipe_board import draw
from schematic_layout.generate import Libraries, library_dirs
from schematic_layout.readability import gate, measure
from schematic_layout.sexpr import dump, parse

CLI = HERE.parent / 'scripts' / 'check_schematic_readability.py'


class PageFitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            Libraries(library_dirs()).load('Regulator_Switching:LM2596S-ADJ')
        except ValueError:
            raise unittest.SkipTest('KiCad symbol libraries are not installed')
        cls.good, cls.report = draw().build('recipe_board')
        cls.text = dump(cls.good) + '\n'

    def test_a4_page_fits_a4(self):
        m = self.report['readability']
        self.assertEqual('A4', m['paper'])
        self.assertEqual('A4', m['fits_paper'])
        self.assertFalse(m['oversized_paper'])
        self.assertEqual('PASS', m['gate']['status'])
        self.assertTrue(0 < m['cell_coverage'] <= 1, m['cell_coverage'])
        self.assertTrue(0 < m['occupancy'] <= 1, m['occupancy'])
        self.assertGreater(m['longest_segment_mm'], 0)

    def test_parts_joined_only_by_labels_or_rails_are_separate_groups(self):
        m = self.report['readability']
        # The buck block, the LDO block (joined to it only through the +5V rail
        # symbols) and the USB lanes that meet at the connector.
        self.assertEqual(m['part_groups'], len(m['part_group_refs']))
        self.assertEqual(3, m['part_groups'])
        self.assertIn(['C5', 'C6', 'D3', 'R3', 'U2'], m['part_group_refs'])
        self.assertIn(['D4', 'D5', 'J2', 'R4', 'R5'], m['part_group_refs'])

    def test_same_drawing_on_a3_is_oversized(self):
        root = parse(self.text.replace('(paper "A4")', '(paper "A3")'))
        m = measure(root)
        self.assertEqual('A3', m['paper'])
        self.assertEqual('A4', m['fits_paper'])
        self.assertTrue(m['oversized_paper'])
        result = gate(m)
        self.assertEqual('FAIL', result['status'])
        self.assertTrue(any('fits A4' in r and 'A3' in r for r in result['reasons']), result)
        self.assertEqual('PASS', gate(m, allow_oversized_paper=True)['status'])

    def test_cli_waiver_for_oversized_paper(self):
        with tempfile.TemporaryDirectory() as tmp:
            sch = Path(tmp) / 'wide.kicad_sch'
            sch.write_text(self.text.replace('(paper "A4")', '(paper "A3")'))
            run = lambda *a: subprocess.run([sys.executable, str(CLI), str(sch), *a], capture_output=True, text=True)
            self.assertEqual(2, run().returncode)
            waivers = Path(tmp) / 'w.json'
            waivers.write_text(json.dumps({'wide.kicad_sch': {'oversized_paper': True, 'reason': 'test only'}}))
            done = run('--waivers', str(waivers))
            self.assertEqual(0, done.returncode, done.stdout)
            self.assertTrue(json.loads(done.stdout)['sheets']['wide.kicad_sch']['oversized_paper'])


if __name__ == '__main__':
    unittest.main()
