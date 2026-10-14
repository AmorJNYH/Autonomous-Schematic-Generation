import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from schematic_layout.native_geometry import SVG

def svg(rule):
 return '<svg width="10mm" height="10mm" viewBox="0 0 10 10"><path d="M 1,1 L 4,1 L 4,4 Z" style="fill:red;fill-rule:'+rule+';stroke:none"/></svg>'
class FillRuleTests(unittest.TestCase):
 def test_evenodd_foreground_remains_in_equality(self):
  a,b=SVG(svg('evenodd')),SVG(svg('nonzero'))
  self.assertNotEqual(a.primitives,b.primitives)
  self.assertTrue(a.primitives)
 def test_fill_does_not_become_qualified_target_stroke(self):
  self.assertRaises(ValueError,SVG(svg('evenodd')).segments)
 def test_unknown_fill_rule_still_refuses(self):
  self.assertRaises(ValueError,SVG,svg('inherit'))
