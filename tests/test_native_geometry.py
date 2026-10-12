"""Reject-first bounds/attribution controls; native jobs have separate receipts."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from schematic_layout.native_geometry import SVG, removal, ink_gap

def svg(paths, text='FIELD', width='.2'):
    companion='<text opacity="0">'+text+'</text>' if text else ''
    return '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="100mm" viewBox="0 0 100 100"><g fill="none" stroke="#000" stroke-width="'+width+'" stroke-linecap="round" stroke-linejoin="round"><g class="stroked-text">'+companion+''.join('<path d="'+d+'"/>' for d in paths)+'</g></g></svg>'

class NativeInkTests(unittest.TestCase):
    def test_real_crossing_and_separated_same_owner(self):
        a=SVG(svg(['M 10,10 L 20,10'])).segments()
        b=SVG(svg(['M 15,5 L 15,15'])).segments()
        c=SVG(svg(['M 15,11 L 20,11'])).segments()
        self.assertLess(ink_gap(a,b),0)
        self.assertGreater(ink_gap(a,c),0)

    def test_all_removed_glyphs_are_union_not_nearest_match(self):
        result=removal(SVG(svg(['M 10,10 L 20,10','M 70,70 L 80,70'])),SVG(svg([],text='')))
        self.assertEqual('FIELD',result['literal'])
        self.assertGreater(result['box'][2],80)

    def test_extra_primitive_refuses_attribution(self):
        with self.assertRaises(ValueError):
            removal(SVG(svg(['M 10,10 L 20,10'])),SVG(svg(['M 80,80 L 90,90'],text='')))

    def test_zero_removal_refuses(self):
        with self.assertRaises(ValueError): removal(SVG(svg([])),SVG(svg([])))

    def test_filled_or_curved_deleted_font_refuses(self):
        for old in (svg(['M 10,10 C 11,11 12,12 13,13']), svg(['M 10,10 L 20,10']).replace('fill="none"','fill="#000"')):
            with self.assertRaises(ValueError): removal(SVG(old),SVG(svg([],text='')))

    def test_duplicate_literal_deletion_refuses(self):
        old=svg(['M 10,10 L 20,10']).replace('<text opacity="0">FIELD</text>','<text opacity="0">FIELD</text><text opacity="0">FIELD</text>')
        with self.assertRaises(ValueError): removal(SVG(old),SVG(svg([],text='')))

    def test_transform_and_nonfinite_refuse(self):
        for old in (svg(['M 10,10 L 20,10']).replace('class="stroked-text"','class="stroked-text" transform="rotate(90)"'), svg(['M 10,10 L 20,10'],width='nan')):
            with self.assertRaises(ValueError): SVG(old)

    def test_coordinate_units_cannot_be_assumed(self):
        with self.assertRaises(ValueError): SVG(svg([]).replace('width="100mm"','width="100px"'))

if __name__=='__main__': unittest.main()
