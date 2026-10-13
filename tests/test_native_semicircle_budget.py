"""Reject-first controls for closure/subpath inclusion in the arc path budget."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from schematic_layout.native_geometry import SVG,stroke_path,ARC_SEGMENT_BUDGET
from test_native_semicircle_profile import svg

class SemicircleWholePathBudget(unittest.TestCase):
    def test_full_budget_open_semicircle_and_exact_budget_with_closure_are_legal(self):
        self.assertEqual(4096,ARC_SEGMENT_BUDGET)
        for d in ('M -2719 0 A 2719 2719 0 0 1 2719 0',
                  'M -2718 0 A 2718 2718 0 0 1 2718 0 Z'):
            self.assertEqual(4096,len(stroke_path(d,.1)))
            self.assertEqual(4096,len(SVG(svg(d)).segments()))

    def test_final_closure_over_budget_rejects_helper_and_real_svg_consumer(self):
        d='M -2719 0 A 2719 2719 0 0 1 2719 0 Z'
        with self.assertRaisesRegex(ValueError,'budget'):stroke_path(d,.1)
        with self.assertRaisesRegex(ValueError,'budget'):SVG(svg(d)).segments()

    def test_repeated_closure_subpath_and_prior_linear_segment_cannot_bypass_total_budget(self):
        cases=('M -2719 0 A 2719 2719 0 0 1 2719 0 Z Z',
               'M -2718 0 A 2718 2718 0 0 1 2718 0 Z M 0 0 L 1 0',
               'M -2720 0 L -2719 0 A 2719 2719 0 0 1 2719 0',
               'M -2719 0 L -2718 0 A 2718 2718 0 0 1 2718 0 Z')
        for d in cases:
            with self.subTest(d=d),self.assertRaises(ValueError):stroke_path(d,.1)
            with self.subTest(consumer=d),self.assertRaises(ValueError):SVG(svg(d)).segments()

    def test_radius_and_token_overflow_still_reject(self):
        for d in ('M -2720 0 A 2720 2720 0 0 1 2720 0',
                  'M -1 0 A 1 1 0 0 1 1 0 '+'M 1 0 '*7000):
            with self.assertRaisesRegex(ValueError,'budget'):stroke_path(d,.1)
            with self.assertRaisesRegex(ValueError,'budget'):SVG(svg(d)).segments()

if __name__=='__main__':unittest.main()
