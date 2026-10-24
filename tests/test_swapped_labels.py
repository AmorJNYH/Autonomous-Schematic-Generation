"""Two parts whose Reference/Value blocks read as well swapped (R6 redraw: R602/R603 on 07_PD) fail the build."""
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from schematic_layout.field_placer import swapped_label_pairs
from schematic_layout.geometry import Box
from schematic_layout.pages import page_intents
from schematic_layout.recipes import DOWN, LEFT, Sheet


def part(ref, body, reference, value):
    """A scene symbol reduced to what the check reads: body box and Reference/Value boxes."""
    field = lambda box: SimpleNamespace(box=lambda: Box(*box))
    return SimpleNamespace(ref=ref, body=Box(*body), fields=[('Reference', field(reference)), ('Value', field(value))])


class SwappedLabelTests(unittest.TestCase):
    def test_r6_cs_legs_read_either_way(self):
        # Original R6 07_PD: R602's block below it, R603's at its upper-right corner, both between the legs.
        r602 = part('R602', (138.303, 118.237, 143.637, 120.523),
                    (138.303, 121.793, 143.637, 123.063), (138.303, 123.571, 143.637, 124.841))
        r603 = part('R603', (138.303, 125.857, 143.637, 128.143),
                    (144.437, 121.717, 149.771, 122.987), (144.437, 123.387, 149.771, 124.657))
        self.assertEqual([('R602', 'R603')], swapped_label_pairs([r602, r603]))

    def test_staggered_legs_each_label_by_its_own_body(self):
        # Redrawn R6: R602 moved left with its block above, R603 moved right with its block above.
        r602 = part('R602', (135.763, 118.237, 141.097, 120.523),
                    (135.763, 113.919, 141.097, 115.189), (135.763, 115.697, 141.097, 116.967))
        r603 = part('R603', (145.923, 125.857, 151.257, 128.143),
                    (145.923, 121.539, 151.257, 122.809), (145.923, 123.317, 151.257, 124.587))
        self.assertEqual([], swapped_label_pairs([r602, r603]))

    def test_a_label_near_a_part_that_has_its_own_label_is_not_reported(self):
        # Both blocks above their parts: R2's block is nearer R1's body, but R1's own block sits above R1.
        r1 = part('R1', (64.643, 72.517, 69.977, 74.803), (65.977, 68.199, 68.644, 69.469), (64.643, 69.977, 69.977, 71.247))
        r2 = part('R2', (64.643, 80.137, 69.977, 82.423), (65.977, 75.819, 68.644, 77.089), (64.643, 77.597, 69.977, 78.867))
        self.assertEqual([], swapped_label_pairs([r1, r2]))


class BuildRejectsSwappedLabelsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from schematic_layout.generate import Libraries, library_dirs
        try:
            Libraries(library_dirs()).load('Device:R')
        except ValueError:
            raise unittest.SkipTest('KiCad symbol libraries are not installed')

    def sheet(self):
        comp = lambda ref, lib, value: {'ref': ref, 'lib_id': lib, 'value': value, 'footprint': '', 'fields': {'Circuit': 'p'}}
        intent = {'schema_version': 1,
                  'components': [comp('J1', 'Connector_Generic:Conn_01x04', 'J1'), comp('R1', 'Device:R', '100R'),
                                 comp('R2', 'Device:R', '100R'), comp('C1', 'Device:C', '10n')],
                  'nets': {'CS_P': ['J1.1', 'R1.1', 'C1.1'], 'CS_N': ['J1.4', 'R2.1', 'C1.2'], 'GND': ['R1.2', 'R2.2']},
                  'no_connect': ['J1.2', 'J1.3'], 'external_supply': []}
        page = page_intents(intent, rails={'GND': 'power:GND'})['p']
        s = Sheet(page['intent'], rails=page['rails'], external=page['external'])
        s.place('J1', (101.6, 76.2))
        cp, cn = s.stub('J1.1', 10), s.stub('J1.4', 10)
        s.shunt(cp, 'R1', LEFT, gap=10)
        s.shunt(cn, 'R2', LEFT, gap=10)
        s.series(cp, ['C1'], DOWN, gap=1)
        s.connect('C1.2', cn)
        return s

    def test_build_runs_the_check(self):
        self.assertEqual([], self.sheet().build('p', draft=True)[1]['draft_failures'])
        with mock.patch('schematic_layout.recipes.swapped_label_pairs', return_value=[('R1', 'R2')]):
            failures = self.sheet().build('p', draft=True)[1]['draft_failures']
            self.assertTrue(any('read as well swapped' in f for f in failures), failures)
            with self.assertRaisesRegex(ValueError, 'read as well swapped'):
                self.sheet().build('p')


if __name__ == '__main__':
    unittest.main()
