"""Local terminal corridor eligibility; neither owner nor model exemptions."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from schematic_layout.sexpr import parse,first,all_nodes,form
from schematic_layout.scene import read_scene,transform
from schematic_layout.qa import check_scene
from schematic_layout.native_circle_contacts import candidate_profiles,contact_corridor,refine_wire_contacts

def fixture(angle=0,mirror='',case='legal'):
    shapes='(rectangle (start -1.27 3.81) (end 1.27 -3.81) (stroke (width .01) (type default)) (fill (type background)))'
    shapes+=''.join(f'(circle (center 0 {y}) (radius .635) (stroke (width .0006) (type default)) (fill (type none)))' for y in (2.54,0,-2.54))
    pins=''.join(f'(pin passive line (at 0 {y} 0) (length 0) (name "~" (effects (font (size 1 1)))) (number "{i}" (effects (font (size 1 1)))))' for i,y in enumerate((2.54,0,-2.54),1))
    pair={'legal':((0,0),(5.08,0)),'foreign':((-5.08,0),(5.08,0)),'through-gap':((-5.08,1.27),(5.08,1.27)),'neighbor':((0,0),(0,7.62))}[case]
    a,b=[transform(p,(50.8,50.8),angle,mirror) for p in pair]
    return parse(f'(kicad_sch (version 20250114) (uuid "root") (paper "A4") (lib_symbols (symbol "Probe:Rings" (pin_names hide) (pin_numbers hide) (symbol "Rings_0_1" {shapes}) (symbol "Rings_1_1" {pins}))) (wire (pts (xy {a[0]} {a[1]}) (xy {b[0]} {b[1]})) (stroke (width 0) (type default))) (symbol (lib_id "Probe:Rings") (at 50.8 50.8 {angle}) (unit 1) {"(mirror "+mirror+")" if mirror else ""} (uuid "placed") (property "Reference" "J1" (at 50.8 50.8 0) (effects (font (size 1 1)) hide))))')

class RingContactTests(unittest.TestCase):
    def profile(self,tree):
        scene=read_scene(tree);profiles=candidate_profiles(tree,scene)
        self.assertEqual(1,len(profiles));return scene,profiles[0]

    def circles(self,p,width=.0847):
        return [{'center':c['center'],'radius':c['radius'],'width':width} for c in p['circles']]

    def test_direction_matrix_is_a_local_exact_pin_exit(self):
        for a in (0,90,180,270):
            for m in ('','x','y'):
                scene,p=self.profile(fixture(a,m))
                self.assertTrue(contact_corridor(p,*scene.wires[0],.16,self.circles(p)))

    def test_foreign_through_pin_and_interterminal_gap_reject(self):
        for case in ('foreign','through-gap','neighbor'):
            scene,p=self.profile(fixture(case=case))
            self.assertFalse(contact_corridor(p,*scene.wires[0],.16,self.circles(p)))

    def test_wide_neighbors_and_missing_native_circle_reject(self):
        scene,p=self.profile(fixture())
        self.assertFalse(contact_corridor(p,*scene.wires[0],3,self.circles(p,3)))
        self.assertFalse(contact_corridor(p,*scene.wires[0],.16,self.circles(p)[:-1]))

    def test_unknown_or_mixed_profile_keeps_old_protection(self):
        for mutation in ('filled','visible-number','nonpassive','nonzero','mixed','negative-radius','duplicate-number','unknown-stroke','unknown-symbol-flag'):
            tree=fixture();lib=first(first(tree,'lib_symbols'),'symbol');placed=first(tree,'symbol');graphics=all_nodes(lib,'symbol')[0];pins=all_nodes(all_nodes(lib,'symbol')[1],'pin')
            if mutation=='filled':first(first(graphics,'rectangle'),'fill')[1][1]='outline'
            elif mutation=='visible-number':lib.remove(first(lib,'pin_numbers'))
            elif mutation=='nonpassive':pins[0][1]='input'
            elif mutation=='nonzero':first(pins[0],'length')[1]='2.54'
            elif mutation=='mixed':graphics.append(form('polyline',form('pts',form('xy',0,0),form('xy',1,1)),form('stroke',form('width',.2),form('type','default')),form('fill',form('type','none'))))
            elif mutation=='negative-radius':first(first(graphics,'circle'),'radius')[1]='-1'
            elif mutation=='duplicate-number':first(pins[1],'number')[1]='1'
            elif mutation=='unknown-stroke':first(first(graphics,'circle'),'stroke').append(form('unknown',1))
            else:placed.append(form('exclude_from_sim','yes'))
            self.assertFalse(candidate_profiles(tree,read_scene(tree)),mutation)

    def test_missing_project_and_export_failure_cannot_add_gap_or_remove_findings(self):
        import tempfile
        from schematic_layout.sexpr import dump
        with tempfile.TemporaryDirectory(dir='/tmp/codex-work') as tmp:
            p=Path(tmp)/'control.kicad_sch';p.write_text(dump(fixture()))
            original=check_scene(read_scene(fixture()));out=refine_wire_contacts(p,original,cli='/does/not/exist')
            self.assertEqual(original['findings'],out['findings'])
            self.assertEqual(original['status'],out['status'])
            self.assertEqual(original['coverage']['gaps'],out['coverage']['gaps'])

if __name__=='__main__':unittest.main()
