import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from schematic_layout.geometry import Box,TextField
from schematic_layout.scene import Scene,Symbol,read_scene
from schematic_layout.qa import check_scene
from schematic_layout.sexpr import parse

FRAME={'kind':'sheet','id':'sheet-uuid','qualified':True,'interior':[40,40,80,80],
       'box':[39.9,39.9,80.1,80.1],
       'segments':[[[40,40],[80,40],.2],[[80,40],[80,80],.2],[[80,80],[40,80],.2],[[40,80],[40,40],.2]]}
def scene(): return Scene(Box(0,0,297,210),native_frames=[FRAME])
def codes(s): return check_scene(s,reserved=[])['counts']
def ink(id,pts,owner='owner'):
    xs=[p[0] for p in pts];ys=[p[1] for p in pts]
    return {'id':id,'symbol_uuid':owner,'segments':[[pts[0],pts[1],.2]],
            'box':[min(xs)-.1,min(ys)-.1,max(xs)+.1,max(ys)+.1],'page_stroke_upper_mm':.2}

class NativeQATests(unittest.TestCase):
    def test_foreign_frame_crossing_error(self):
        s=scene();s.wires=[((30,60),(50,60))]
        self.assertIn('wire_sheet_frame',codes(s))
    def test_wire_inside_structure_is_not_annotation(self):
        s=scene();s.wires=[((50,60),(70,60))]
        self.assertIn('wire_sheet_frame',codes(s))
    def test_caption_inside_frame_legal(self):
        s=scene();s.labels=[('text',TextField('ARCH',60,60))]
        self.assertEqual({},codes(s))
    def test_foreign_field_on_frame_rejected(self):
        s=scene();s.labels=[('text',TextField('FOREIGN',40,60))]
        self.assertIn('native_frame_object',codes(s))
    def test_native_frame_page_extent(self):
        s=scene();s.page=Box(0,0,70,70)
        self.assertIn('off_page',codes(s))
    def test_real_pin_name_overlap_same_owner(self):
        s=Scene(Box(0,0,297,210),native_pin_texts=[ink('1',[[50,60],[70,60]]),ink('2',[[60,50],[60,70]])])
        self.assertIn('native_pin_text_overlap',codes(s))
    def test_own_background_inside_and_separated_names_legal(self):
        s=Scene(Box(0,0,297,210),native_pin_texts=[ink('1',[[50,60],[70,60]]),ink('2',[[50,65],[70,65]])])
        s.symbols=[Symbol('X1','SELF',1,parse('(symbol (uuid "owner"))'),Box(40,40,80,80),[],[])]
        self.assertEqual({},codes(s))
    def test_foreign_body_and_wire_not_owner_exempt(self):
        s=Scene(Box(0,0,297,210),native_pin_texts=[ink('1',[[50,60],[70,60]])])
        s.symbols=[Symbol('X2','SELF',1,parse('(symbol (uuid "foreign"))'),Box(55,55,65,65),[],[])]
        s.wires=[((60,50),(60,70))]
        self.assertIn('native_pin_text_body',codes(s));self.assertIn('native_pin_wire_text',codes(s))
    def test_true_overlap_fail_before_unknown_gap(self):
        s=Scene(Box(0,0,297,210),native_pin_texts=[ink('1',[[50,60],[70,60]]),ink('2',[[60,50],[60,70]])],gaps=['number unknown'])
        self.assertEqual('FAIL',check_scene(s,reserved=[])['status'])
    def test_gap_removal_needs_matching_source_identity(self):
        root=parse('(kicad_sch (paper "A4") (sheet (uuid "different")))')
        s=read_scene(root,{'frames':[FRAME],'gaps':[]})
        self.assertIn('Unsupported sheet object: sheet',s.gaps)
    def test_identical_foreign_outline_is_not_owner_exempt(self):
        s=scene();s.native_frames.append({**FRAME,'id':'foreign','kind':'rectangle'})
        self.assertIn('native_frame_overlap',codes(s))
    def test_wide_wire_center_outside_frame_still_caught(self):
        s=scene();s.native_stroke_upper_mm=1.0;s.wires=[((39.6,50),(39.6,70))]
        self.assertIn('wire_sheet_frame',codes(s))
    def test_own_foreground_ink_still_rejects(self):
        s=Scene(Box(0,0,297,210),native_pin_texts=[ink('1',[[50,60],[70,60]])],native_owner_outlines=[{'id':'own-edge','segments':[[[60,50],[60,70],.2]]}])
        self.assertIn('native_pin_text_outline',codes(s))

if __name__=='__main__': unittest.main()
