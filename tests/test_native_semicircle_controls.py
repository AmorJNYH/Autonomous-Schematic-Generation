"""Actual native arc controls and source-rounding rejection envelopes."""
import itertools
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from test_native_circle_controls import native_fixture,uid
from schematic_layout.scratch import scratch_base
from schematic_layout.sexpr import form as f,Atom as A,dump
from schematic_layout.native import find_cli
from schematic_layout.native_geometry import SVG,ink_gap,ARC_SERIALIZATION_MM
from schematic_layout.native_geometry_context import sha
from schematic_layout.native_circle_contacts import refine_wire_contacts,_hits
from schematic_layout.scene import read_scene
from schematic_layout.qa import check_scene
from test_native_semicircle_profile import svg

class ArcUncertaintyControls(unittest.TestCase):
    def test_source_rounding_and_near_diameter_centre_shift_are_covered_by_each_consumer(self):
        eps=ARC_SERIALIZATION_MM
        for sweep,large in itertools.product((0,1),repeat=2):
            native=SVG(svg(f'M9 10 A1 1 0 {large} {sweep} 11 10'))
            obj=next(iter(native.objects.values()));ink=native.segments()
            for dx,dy,dr in ((eps,eps,eps),(-eps,eps,eps),(0,-eps,eps),(eps,0,0),(eps,0,-eps)):
                a=(9+dx,10+dy);b=(11-dx,10-dy);r=1+dr
                vx,vy=b[0]-a[0],b[1]-a[1];length=math.hypot(vx,vy)
                if length>2*r:continue
                h=math.sqrt(max(0,r*r-length*length/4));sign=1 if large!=sweep else -1
                c=((a[0]+b[0])/2-sign*h*vy/length,(a[1]+b[1])/2+sign*h*vx/length)
                theta=math.atan2(a[1]-c[1],a[0]-c[0]);end=math.atan2(b[1]-c[1],b[0]-c[0]);extent=end-theta
                if sweep and extent<0:extent+=2*math.pi
                if not sweep and extent>0:extent-=2*math.pi
                for j in range(101):
                    angle=theta+extent*j/100;p=(c[0]+r*math.cos(angle),c[1]+r*math.sin(angle))
                    self.assertTrue(_hits(obj,p,p,.0001),(sweep,large,dx,dy,dr,p))
                    self.assertLessEqual(ink_gap(ink,[[list(p),list(p),.0001]]),0)

    def test_budget_prior_linear_overflow_and_unknown_arc_paint_keep_rejection(self):
        for d in ('M-10000 0 A10000 10000 0 0 0 10000 0','M1e308 0 L9 10 A1 1 0 0 0 11 10','M10001 0 L9 10 A1 1 0 0 0 11 10'):
            with self.assertRaises(ValueError):SVG(svg(d))
        for extra in (';stroke-linecap:square',';stroke-linejoin:bevel',';opacity:.5',';stroke-opacity:.5',';stroke-dasharray:1,nan'):
            from test_native_semicircle_profile import STYLE
            with self.assertRaises(ValueError):SVG(svg('M9 10 A1 1 0 0 0 11 10',STYLE+extra))

class ActualNativeArcControls(unittest.TestCase):
    def test_actual_native_foreign_bulge_dash_far_gap_and_forged_source_binding(self):
        cli=find_cli()
        if not cli:self.skipTest('KiCad CLI unavailable')
        base=scratch_base()/'asg-semicircle-controls'
        base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as tmp:
            for case in ('foreign-arc','foreign-dash-arc','far-arc','filled-arc','nonsemicircle-arc'):
                folder=Path(tmp)/case;folder.mkdir();tree=native_fixture('legal')
                points=((140,100),(141,99),(142,100)) if case=='far-arc' else ((50.9,51.3),(51.7,50.5),(52.5,51.3))
                if case=='nonsemicircle-arc':points=((50.9,51.3),(51.7,50.5),(52.5,50.5))
                tree.append(f('arc',f('start',*points[0]),f('mid',*points[1]),f('end',*points[2]),f('stroke',f('width',.1524),f('type',A('dash' if case=='foreign-dash-arc' else 'default'))),f('fill',f('type',A('outline' if case=='filled-arc' else 'none'))),f('uuid',uid(case))))
                source=folder/'control.kicad_sch';source.write_text(dump(tree)+'\n');(folder/'control.kicad_pro').write_text('{"meta":{"version":1}}')
                digest=sha(source);old=check_scene(read_scene(tree))
                rejected=refine_wire_contacts(source,old,cli=cli,expected_source_sha256='forged')
                self.assertEqual(old['findings'],rejected['findings']);self.assertEqual(old['coverage'],rejected['coverage'])
                new=refine_wire_contacts(source,old,cli=cli,workdir=folder/'proof',expected_source_sha256=digest)
                self.assertEqual(digest,sha(source));self.assertEqual('FAIL',new['status']);self.assertIn('wire_body',new['counts'])
                self.assertEqual(old['coverage']['gaps'],new['coverage']['gaps'])
                if case in ('foreign-arc','foreign-dash-arc','nonsemicircle-arc'):
                    self.assertEqual('QUALIFIED',new['native_contact_qualification']['status']);self.assertFalse(new['native_contact_qualification']['removed'])
                elif case=='far-arc':
                    self.assertIn('hide measured',new['native_contact_qualification']['reason'])
                else:self.assertEqual('FALLBACK',new['native_contact_qualification']['status'])

if __name__=='__main__':unittest.main()
