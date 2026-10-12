"""Explicit name-span planning without changes to construction acceptance."""
import copy
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from schematic_layout.recipes import G, RIGHT, Sheet, label_geometry
from schematic_layout.sexpr import dump


def intent(net='NODE'):
    return {'schema_version': 1, 'design_id': 'name-span-query', 'title': 'query',
            'components': [{'ref': r, 'lib_id': 'Device:R', 'value': '10k', 'footprint': ''}
                           for r in ('R1', 'R2')],
            'nets': [{'name': 'IN', 'pins': ['R1.1']},
                     {'name': net, 'pins': ['R1.2', 'R2.1']},
                     {'name': 'OUT', 'pins': ['R2.2']}], 'no_connect': []}


class NameRunStepsTests(unittest.TestCase):
    def test_unknown_net_and_alias_do_not_create_a_name(self):
        sheet = Sheet(intent('A{slash}B'))
        for net in ('MISSING', 'A/B', None, 123):
            with self.subTest(net=net), self.assertRaisesRegex(ValueError, 'declared logical net'):
                sheet.name_run_steps(net)
        self.assertEqual([], sheet.names)
        self.assertEqual({}, sheet.placements)

    def test_font_must_be_finite_positive_numeric(self):
        sheet = Sheet(intent())
        for font in (0, -1, float('nan'), float('inf'), -float('inf'), True, None, '1', 10**1000):
            with self.subTest(font=repr(font)), self.assertRaisesRegex(ValueError, 'finite positive'):
                sheet.name_run_steps('NODE', font)
        with self.assertRaisesRegex(ValueError, 'not finite'):
            sheet.name_run_steps('NODE', 1e308)

    def test_minimal_grid_budget_tracks_font_and_raw_name(self):
        for net in ('N', 'LONG_NODE_NAME', 'A{slash}B', '节点'):
            sheet = Sheet(intent(net))
            for font in (0.5, 1, 1.27, 2):
                with self.subTest(net=net, font=font):
                    steps = sheet.name_run_steps(net, font)
                    need = label_geometry('local', net, (0, 0), RIGHT, font)[2].width + 2 * G
                    self.assertIsInstance(steps, int)
                    self.assertGreaterEqual(steps * G, need)
                    self.assertLess((steps - 1) * G, need)
            # A raw storage-looking literal retains its full estimator width;
            # this query makes no native encoding or CJK font qualification.
            if net == 'A{slash}B':
                self.assertGreater(sheet.name_run_steps(net), Sheet(intent('A/B')).name_run_steps('A/B'))

    def test_query_has_no_sheet_or_library_side_effect(self):
        sheet = Sheet(intent())
        before = copy.deepcopy({k: v for k, v in vars(sheet).items() if k != 'libraries'})
        library_before = copy.deepcopy(vars(sheet.libraries))
        for font in (1.0, 1.27):
            sheet.name_run_steps('NODE', font)
        self.assertEqual(before, {k: v for k, v in vars(sheet).items() if k != 'libraries'})
        self.assertEqual(library_before, vars(sheet.libraries))

    def test_existing_drawing_is_identical_when_query_is_unused(self):
        def draw(query):
            sheet = Sheet(intent(), external=['IN', 'OUT'])
            if query:
                sheet.name_run_steps('NODE', 1.27)
            sheet.put('R1', '1', (50.8, 50.8), RIGHT)
            sheet.justify('R1', 'first passive in a chain')
            sheet.label('R1.1', 'global', length=5)
            sheet.series('R1.2', ['R2'], RIGHT, gap=8)
            sheet.label('R2.2', 'global', length=5)
            sheet.justify('NODE', 'local test-chain name')
            sheet.name('NODE')
            if query:
                sheet.name_run_steps('NODE')
            return sheet.build('query')
        baseline, baseline_report = draw(False)
        queried, queried_report = draw(True)
        self.assertEqual(dump(baseline), dump(queried))
        self.assertEqual(baseline_report, queried_report)


if __name__ == '__main__':
    unittest.main()
