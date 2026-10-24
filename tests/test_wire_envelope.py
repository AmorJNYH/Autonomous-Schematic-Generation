"""Sheet.build and the geometry gate judge wires with one rule: 5 mm page margin, title block, no wire through a body."""
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / 'scripts'), str(HERE / 'fixtures' / 'drawing')]
from schematic_layout.geometry import Box
from schematic_layout.qa import FRAME_MARGIN_MM, check_scene, title_block, wire_findings
from schematic_layout.scene import Pin, Scene, Symbol

A4 = Box(0, 0, 297, 210)


def scene(*wires):
    body = Box(100, 100, 110, 104)
    pins = [Pin('R1.1', (97.46, 102), (100, 102), (-1, 0), 'passive'),
            Pin('R1.2', (112.54, 102), (110, 102), (1, 0), 'passive')]
    return Scene(A4, symbols=[Symbol('R1', 'Device:R', 1, [], body, pins, [])], wires=list(wires))


class WireEnvelopeTests(unittest.TestCase):
    def codes(self, *wires):
        named = [('w%d' % i, a, b) for i, (a, b) in enumerate(wires)]
        return [f['code'] for f in wire_findings(scene(), named)]

    def test_margin_is_five_mm(self):
        self.assertEqual(5.0, FRAME_MARGIN_MM)
        self.assertEqual([], self.codes(((20, 8), (60, 8))))            # 8 mm: inside the frame clearance
        self.assertEqual(['off_page'], self.codes(((20, 3), (60, 3))))  # 3 mm: too close to the edge

    def test_title_block_and_body(self):
        self.assertEqual(title_block(A4), Box(177, 165, 292, 205))
        self.assertEqual(['reserved_region'], self.codes(((150, 180), (200, 180))))
        self.assertEqual(['wire_body'], self.codes(((105, 90), (105, 120))))
        self.assertEqual([], self.codes(((112.54, 102), (130, 102))))  # the pin's own exit is not a traversal

    def test_gate_reports_the_same_findings(self):
        wires = [((20, 3), (60, 3)), ((150, 180), (200, 180)), ((105, 90), (105, 120)), ((20, 8), (60, 8))]
        gate = check_scene(scene(*wires))['findings']
        shared = wire_findings(scene(), [('wire:%d' % i, a, b) for i, (a, b) in enumerate(wires)])
        pick = lambda fs: sorted((f['code'], tuple(f['objects'])) for f in fs
                                 if f['code'] in ('off_page', 'reserved_region', 'wire_body'))
        self.assertEqual(pick(shared), pick(gate))


class BuildUsesTheSameRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from schematic_layout.generate import Libraries, library_dirs
        try:
            Libraries(library_dirs()).load('Regulator_Switching:LM2596S-ADJ')
        except ValueError:
            raise unittest.SkipTest('KiCad symbol libraries are not installed')

    def test_a_wire_in_the_old_12_mm_band_builds_and_one_at_3_mm_does_not(self):
        from recipe_board import draw
        for y, ok in ((8, True), (3, False)):
            with self.subTest(y=y):
                sheet = draw()
                start = sheet.point('J1.1')
                sheet.wire(start, (start[0], y), net=sheet._net('J1.1'))
                sheet.wire((start[0], y), start, net=sheet._net('J1.1'))
                if ok:
                    try:
                        sheet.build('recipe_board', draft=True)
                    except ValueError as error:
                        self.assertNotIn('leaves the drawing area', str(error))
                else:
                    with self.assertRaisesRegex(ValueError, 'leaves the drawing area'):
                        sheet.build('recipe_board', draft=True)


if __name__ == '__main__':
    unittest.main()
