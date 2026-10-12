"""Reject first: only resolved finite fill-opacity equality is normalized."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from schematic_layout.native_geometry import SVG

def svg(parent='',child='',extra='',path='M 10 10 L 20 10',width='.2',cap='round',join='round',color='#000'):
    return f'<svg width="30mm" height="30mm" viewBox="0 0 30 30">{extra}<g style="fill:none;stroke:{color};stroke-width:{width};stroke-linecap:{cap};stroke-linejoin:{join};{parent}"><path style="{child}" d="{path}"/></g></svg>'

class StyleDefaultTests(unittest.TestCase):
    def test_resolved_default_and_numeric_one_equal(self):
        original=SVG(svg()).primitives
        for text in (svg(child='fill-opacity:1.0000'),svg(parent='fill-opacity:1'),svg(parent='fill-opacity:.5',child='fill-opacity:1.0000')):
            self.assertEqual(original,SVG(text).primitives)

    def test_actual_transparency_geometry_and_paint_remain_distinct(self):
        original=SVG(svg()).primitives
        for text in (svg(parent='fill-opacity:.5'),svg(parent='opacity:.5'),svg(parent='opacity:.5',child='opacity:.5'),svg(path='M 10 10 L 21 10'),svg(width='.4'),svg(cap='butt'),svg(join='bevel'),svg(color='#840000')):
            self.assertNotEqual(original,SVG(text).primitives)

    def test_unknown_and_nonfinite_do_not_receive_default(self):
        for text in (svg(child='fill-opacity:nan'),svg(child='fill-opacity:inf'),svg(child='mix-blend-mode:multiply'),svg(extra='<style>path { fill-opacity:.5 }</style>'),svg().replace('<path ','<path filter="url(#x)" ')):
            with self.assertRaises(ValueError):SVG(text)

if __name__=='__main__':unittest.main()
