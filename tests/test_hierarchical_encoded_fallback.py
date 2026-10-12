"""Readable direction for a strictly qualified encoded-slash fallback only."""
import copy
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from schematic_layout.sexpr import form,Atom,first,dump
from schematic_layout.scene import read_scene,text_field,_encoded_hierarchical_readable,HierarchicalLabelText,Symbol,Pin
from schematic_layout.geometry import TextField,Box
from schematic_layout.qa import check_scene

def label(angle=180,font=1.27,name='P0.14{slash}AIN1'):
    return form('hierarchical_label',name,form('shape',Atom('bidirectional')),form('at',152.4,101.6,angle),
                form('effects',form('font',form('size',font,font)),form('justify',Atom('right' if angle in (180,270) else 'left'))),form('uuid','fixed-label'))
def scene(*nodes):return read_scene(form('kicad_sch',form('paper','A4'),form('lib_symbols'),*nodes))

class EncodedHierarchicalFallbackTests(unittest.TestCase):
    def test_twelve_native_direction_font_styles_keep_raw_and_extent(self):
        for a in (0,90,180,270):
            for size in (.889,1,1.27):
                with self.subTest(angle=a,font=size):
                    n=label(a,size);raw=dump(n);old=text_field(n,label=True);s=scene(n);f=s.labels[0][1]
                    self.assertIs(type(f),TextField)
                    self.assertEqual(f.angle,a%180)
                    for key in ('text','x','y','font_mm','justify','bold'):self.assertEqual(getattr(f,key),getattr(old,key))
                    self.assertAlmostEqual(f.box().width,old.box().width)
                    self.assertAlmostEqual(f.box().height,old.box().height)
                    self.assertEqual(dump(n),raw)
                    self.assertEqual(s.gaps,['Hierarchical label text style needs native review','hierarchical_label: outline and attached fields need render review'])
                    if a==180:self.assertLessEqual(f.box().x_max,f.x+1e-8)
                    if a==270:self.assertGreaterEqual(f.box().y_min,f.y-1e-8)
    def unchanged(self,n):
        self.assertFalse(_encoded_hierarchical_readable(n))
        before=text_field(n,label=True);s=scene(n)
        self.assertEqual(s.labels[0][1],before)
        self.assertEqual(len(s.gaps),2)
    def test_unqualified_names_retain_fallback(self):
        for name in ('N_{slash}','~{RESET}{slash}X','${X}{slash}A','A{space}B{slash}C','中文{slash}A','A\\{slash}B','@A{slash}B','A^{slash}B'):
            with self.subTest(name=name):self.unchanged(label(name=name))
    def test_angles_justifications_and_shapes_reject(self):
        for a in (-90,540,179.999,45):self.unchanged(label(a))
        for just in (('right','mirror'),('right','right'),('unknown',)):
            n=label();first(first(n,'effects'),'justify')[1:]=[Atom(t) for t in just];self.unchanged(n)
        n=label();first(n,'shape')[1]=Atom('unknown');self.unchanged(n)
    def test_duplicate_extra_nodes_reject(self):
        for key in ('shape','at','effects','uuid'):
            n=label();n.append(copy.deepcopy(first(n,key)));self.unchanged(n)
        n=label();n.append(form('property','X','Y'));self.unchanged(n)
    def test_font_and_effect_styles_reject(self):
        for attr in (Atom('bold'),Atom('italic'),form('face',''),form('thickness',.1),form('size',1.27,1.27),form('color',0,0,0,1)):
            n=label();first(first(n,'effects'),'font').append(attr);self.unchanged(n)
        for attr in (form('hide',Atom('yes')),form('justify',Atom('right')),form('line_spacing',1)):
            n=label();first(n,'effects').append(attr);self.unchanged(n)
        for size in (.8,1.1):self.unchanged(label(font=size))
        n=label();first(first(first(n,'effects'),'font'),'size')[2]=1.;self.unchanged(n)
    def test_explicit_zero_thickness_and_same_name_distinct_objects(self):
        n=label();first(first(n,'effects'),'font').append(form('thickness',0))
        other=label(270);first(other,'at')[1]=100;first(other,'uuid')[1]='other';first(first(other,'effects'),'font').append(Atom('bold'))
        s=scene(n,other);self.assertEqual(s.labels[0][1].angle,0);self.assertEqual(s.labels[1][1].angle,270)
        self.assertEqual(s.labels[1][1].x,100);self.assertEqual(len(s.gaps),4)
    def test_plain_hierarchical_and_other_label_kinds_keep_original_paths(self):
        n=label(name='PLAIN');s=scene(n);self.assertIsInstance(s.labels[0][1],HierarchicalLabelText)
        for kind in ('label','global_label','text'):
            n=label();n[0]=Atom(kind);self.assertFalse(_encoded_hierarchical_readable(n))
    def test_foreign_wire_pin_and_body_still_caught_all_directions(self):
        for a in (0,90,180,270):
            for kind in ('wire','pin','body'):
                with self.subTest(angle=a,obstacle=kind):
                    s=scene(label(a));box=s.labels[0][1].box();x,y=box.center
                    if kind=='wire':
                        s.wires=[((x-2,y),(x+2,y))];code='wire_text'
                    elif kind=='pin':
                        s.symbols=[Symbol('FOREIGN','test:foreign',1,[],None,
                                          [Pin('FOREIGN.1',(x,y-2),(x,y+2),(0,1),'passive')],[])]
                        code='text_pin_overlap'
                    else:
                        s.symbols=[Symbol('FOREIGN','test:foreign',1,[],Box(x-1,y-1,x+1,y+1),[],[])]
                        code='text_body_overlap'
                    findings=check_scene(s)['findings']
                    self.assertTrue(any(f['code']==code and 'hierarchical_label:0:P0.14{slash}AIN1' in f['objects'] for f in findings),findings)
    def test_guard_rejects_incomplete_nonfinite_structure(self):
        for key in ('shape','at','effects','uuid'):
            n=label();n.remove(first(n,key));self.assertFalse(_encoded_hierarchical_readable(n))
        for x in ('nan','inf','-inf'):
            n=label();first(n,'at')[1]=Atom(x);self.assertFalse(_encoded_hierarchical_readable(n))
        n=label();first(n,'at').append(0);self.assertFalse(_encoded_hierarchical_readable(n))

if __name__=='__main__':unittest.main()
