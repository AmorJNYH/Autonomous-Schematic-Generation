"""O7 spacing cap and HR-01 block-local join labels in the structure audit."""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / 'scripts'), str(HERE / 'fixtures' / 'drawing')]
from recipe_board import EXTERNAL, INTENT, RAILS, draw
from schematic_layout.generate import Libraries, library_dirs
from schematic_layout.recipes import DOWN, LEFT, MAX_SPACING_STEPS, RIGHT, Sheet


def need_libraries(*ids):
    try:
        for lib_id in ids:
            Libraries(library_dirs()).load(lib_id)
    except ValueError:
        raise unittest.SkipTest('KiCad symbol libraries are not installed')


class SpacingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_libraries('Regulator_Switching:LM2596S-ADJ')

    def test_recipes_record_spacing_beyond_the_cap(self):
        s = Sheet(INTENT, rails=RAILS, external=EXTERNAL)
        s.place('J1', (20.32, 50.8))
        s.stub('J1.1', MAX_SPACING_STEPS)                     # at the cap: fine
        s.stub('J1.2', MAX_SPACING_STEPS + 1)
        s.series('J1.1', ['F1', 'D1'], RIGHT, gap=20)
        s.shunt('D1.1', 'C2', DOWN, gap=3, rail=False)
        s.put('U1', '1', (152.4, 50.8), RIGHT)
        s.bank('U1.1', ['C1'], LEFT, pitch=30, gap=14)
        s.power('U1.5', length=13)
        s.label('U1.4', 'global', length=15)
        kinds = {(sub, kind): steps for sub, kind, steps in s.spacing}
        self.assertEqual(kinds, {('J1.2', 'stub'): 13, ('F1', 'gap'): 20, ('D1', 'gap'): 20, ('C1', 'pitch'): 30,
                                 ('C1', 'gap'): 14, ('U1.5', 'length'): 13, ('U1.4', 'length'): 15})

    def test_measured_pitch_is_never_a_finding(self):
        s = Sheet(INTENT, rails=RAILS, external=EXTERNAL)
        s.place('U1', (120.65, 50.8))
        s.bank('U1.1', ['C1', 'C2'], LEFT)
        self.assertEqual([], s.spacing)

    def test_audit_lists_oversized_spacing_until_it_is_justified(self):
        s = draw()
        s.spacing.append(('R1', 'gap', 20))
        _, report = s.build('recipe_board')
        found = [f for f in report['structure']['findings'] if f['rule'] == 'spacing']
        self.assertEqual('FAIL', report['structure']['status'])
        self.assertEqual(['R1'], [f['subject'] for f in found])
        self.assertIn('exceeds %d' % MAX_SPACING_STEPS, found[0]['detail'])
        s = draw()
        s.spacing.append(('R1', 'gap', 20))
        s.justify('R1', 'long value text needs the run')
        _, report = s.build('recipe_board')
        self.assertEqual('PASS', report['structure']['status'])
        self.assertTrue(any(d['rule'] == 'spacing' for d in report['structure']['deviations']))


class BlockTests(unittest.TestCase):
    INTENT = {'schema_version': 1, 'design_id': 'blocks', 'title': 'blocks', 'components': [
        {'ref': 'R1', 'lib_id': 'Device:R', 'value': '10k', 'footprint': ''},
        {'ref': 'R2', 'lib_id': 'Device:R', 'value': '1k', 'footprint': ''}],
        'nets': [{'name': 'TOP_OUT', 'pins': ['R1.1']}, {'name': 'MID', 'pins': ['R1.2', 'R2.1']},
                 {'name': 'LOW', 'pins': ['R2.2']}], 'no_connect': []}

    @classmethod
    def setUpClass(cls):
        need_libraries('Device:R')

    def test_blocks_must_name_known_parts_once(self):
        with self.assertRaisesRegex(ValueError, 'unknown part R9'):
            Sheet(self.INTENT, rails={}, external=['TOP_OUT', 'LOW'], blocks={'a': ['R9']})
        with self.assertRaisesRegex(ValueError, "R1 is in blocks 'a' and 'b'"):
            Sheet(self.INTENT, rails={}, external=['TOP_OUT', 'LOW'], blocks={'a': ['R1'], 'b': ['R1']})

    def joined(self, blocks):
        s = Sheet(self.INTENT, rails={}, external=['TOP_OUT', 'LOW'], blocks=blocks)
        s.put('R1', '1', (50.8, 50.8), DOWN)
        s.put('R2', '1', (101.6, 50.8), DOWN)
        for ref in ('R1', 'R2'):
            s.justify(ref, 'explicitly placed test part')
        s.label('R1.1', 'global', length=2)
        s.label('R2.2', 'global', length=2)
        s.label('R1.2', 'local', length=3, reason='block boundary')
        s.label('R2.1', 'local', length=3, reason='block boundary')
        _, report = s.build('blocks')
        return s, report

    def test_join_label_across_two_blocks_is_accepted(self):
        s, report = self.joined({'sense': ['R1'], 'load': ['R2']})
        self.assertEqual({'MID': {'R1', 'R2'}}, s.label_parts)
        self.assertEqual('PASS', report['structure']['status'], report['structure'])
        self.assertEqual({'sense': ['R1'], 'load': ['R2']}, report['structure']['blocks'])

    def test_join_label_inside_one_block_is_a_finding(self):
        _, report = self.joined({'divider': ['R1', 'R2']})
        found = [f for f in report['structure']['findings'] if f['subject'] == 'MID']
        self.assertEqual(1, len(found), report['structure'])
        self.assertIn("block 'divider' only", found[0]['detail'])
        self.assertIn('HR-01', found[0]['detail'])

    def test_without_blocks_nothing_changes(self):
        _, report = self.joined(None)
        self.assertEqual('PASS', report['structure']['status'])
        self.assertEqual({}, report['structure']['blocks'])


if __name__ == '__main__':
    unittest.main()
