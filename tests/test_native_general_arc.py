"""General circular-A arcs: minor/major extent, sweep side and envelopes."""
import itertools
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from schematic_layout import native_geometry as ng
from schematic_layout.native_geometry import SVG,ink_gap,ARC_SERIALIZATION_MM
from schematic_layout.native_circle_contacts import _hits
from test_native_semicircle_profile import svg

def true_arc(a,b,r,large,sweep,samples=200):
    # Independent SVG F.6.5 endpoint-to-centre conversion.
    x1,y1=(a[0]-b[0])/2,(a[1]-b[1])/2
    k=math.sqrt(max(0,(r*r-x1*x1-y1*y1)/(x1*x1+y1*y1)))*(1 if large!=sweep else -1)
    c=(k*y1+(a[0]+b[0])/2,-k*x1+(a[1]+b[1])/2)
    t0=math.atan2(a[1]-c[1],a[0]-c[0]);t1=math.atan2(b[1]-c[1],b[0]-c[0]);dt=t1-t0
    if sweep and dt<0:dt+=2*math.pi
    if not sweep and dt>0:dt-=2*math.pi
    return c,dt,[(c[0]+r*math.cos(t0+dt*i/samples),c[1]+r*math.sin(t0+dt*i/samples)) for i in range(samples+1)]

def covered(native,obj,p):
    return _hits(obj,p,p,.0001) and ink_gap(native.segments(),[[list(p),list(p),.0001]])<=0

class GeneralCircularArc(unittest.TestCase):
    CASES=(((9,10),(10,11),1),((233.68,64.77),(233.68,62.23),1.586),
           ((50.9,51.3),(51.1,51.2),.1765),((7,6),(13,14),6.5))

    def test_minor_and_major_arcs_cover_true_curve_and_leave_complement_clear(self):
        for (a,b,r),large,sweep in itertools.product(self.CASES,(0,1),(0,1)):
            d=f'M{a[0]} {a[1]} A{r} {r} 0 {large} {sweep} {b[0]} {b[1]}'
            with self.subTest(d=d):
                native=SVG(svg(d));obj=next(iter(native.objects.values()))
                c,dt,points=true_arc(a,b,r,large,sweep)
                self.assertEqual(large==1,abs(dt)>math.pi)
                for p in points:self.assertTrue(covered(native,obj,p),p)
                # The complementary arc's midpoint is a different circle point;
                # covering it would mean wrong centre side, sweep or extent.
                t=math.atan2(a[1]-c[1],a[0]-c[0])+dt/2+math.pi
                q=(c[0]+r*math.cos(t),c[1]+r*math.sin(t))
                self.assertFalse(_hits(obj,q,q,.0001))
                self.assertGreater(ink_gap(native.segments(),[[list(q),list(q),.0001]]),0)

    def test_serialization_rounding_of_nonsemicircle_arcs_is_covered(self):
        eps=ARC_SERIALIZATION_MM
        for (a,b,r),large,sweep in itertools.product(self.CASES,(0,1),(0,1)):
            native=SVG(svg(f'M{a[0]} {a[1]} A{r} {r} 0 {large} {sweep} {b[0]} {b[1]}'))
            obj=next(iter(native.objects.values()))
            for dx,dy,dr in ((eps,eps,eps),(-eps,eps,-eps),(0,-eps,eps),(eps,0,-eps)):
                a2=(a[0]+dx,a[1]+dy);b2=(b[0]-dx,b[1]-dy);r2=r+dr
                if math.dist(a2,b2)>2*r2:continue
                for p in true_arc(a2,b2,r2,large,sweep,60)[2]:
                    self.assertTrue(covered(native,obj,p),(a,b,r,large,sweep,dx,dy,dr,p))

    def test_beyond_diameter_zero_chord_and_kicad_winding_profile(self):
        for d in ('M9 10 A1 1 0 0 0 11.0001 10','M9 10 A1 1 0 1 1 9 10'):
            with self.subTest(d=d),self.assertRaises(ValueError):SVG(svg(d))
        # KiCad 10.0.6 transformer winding export: chord 2.54 < diameter 3.172.
        native=SVG(svg('M233.6800 64.7700 A1.5860 1.5860 0.0 1 0 233.6800 62.2300'))
        self.assertTrue(native.segments())

class ScopedUnsupportedArc(unittest.TestCase):
    def test_scoped_svg_keeps_unsupported_arc_in_equality_but_not_ink(self):
        page=('<svg width="30mm" height="30mm" viewBox="0 0 30 30">'
              '<path d="M9 10 A1 1 0 0 0 12 10" style="fill:none;stroke:#000000;stroke-width:.1;stroke-linecap:round;stroke-linejoin:round"/>'
              '<path d="M1 1 L5 1" style="fill:none;stroke:#000000;stroke-width:.1;stroke-linecap:round;stroke-linejoin:round"/></svg>')
        with self.assertRaises(ValueError):SVG(page)
        native=SVG(page,scoped=True)
        self.assertEqual(1,len(native.unsupported));self.assertEqual(2,sum(native.primitives.values()))
        bad=next(iter(native.unsupported));good=next(k for k in native.primitives if k!=bad)
        self.assertTrue(native.segments({good:1}))
        with self.assertRaises(ValueError):native.segments({bad:1})
        with self.assertRaises(ValueError):native.segments()
        with self.assertRaises(ValueError):_hits(native.objects[bad],(10,9),(10,9),.01)

class OneUnsupportedArcDoesNotBlankBoard(unittest.TestCase):
    def test_unsupported_arc_on_child_gaps_only_that_page(self):
        import json,tempfile
        from unittest import mock
        from schematic_layout.native import find_cli
        from schematic_layout.scratch import scratch_base
        from schematic_layout.sexpr import form as f,Atom as A,dump,parse
        from schematic_layout.native_geometry_context import prepare_geometry_context,page_context_from_job
        from schematic_layout.scene import read_scene
        from schematic_layout.qa import check_scene
        from test_native_geometry_context import fixture,uid
        cli=find_cli()
        if not cli:self.skipTest('KiCad native tool missing')
        base=scratch_base()/'native-geometry-tests';base.mkdir(parents=True,exist_ok=True)
        real=ng.stroke_path
        def reject_arcs(d,width):
            if 'A' in d:raise ValueError('simulated unsupported circular-A profile')
            return real(d,width)
        with tempfile.TemporaryDirectory(prefix='asg-scoped-arc-',dir=base) as tmp:
            folder=Path(tmp);root,child=fixture('clear')
            child.append(f('arc',f('start',50.9,51.3),f('mid',51.7,50.5),f('end',52.5,50.5),
                f('stroke',f('width',.1524),f('type',A('default'))),f('fill',f('type',A('none'))),f('uuid',uid('scoped-arc'))))
            (folder/'native.kicad_sch').write_text(dump(root)+'\n');(folder/'child.kicad_sch').write_text(dump(child)+'\n')
            (folder/'native.kicad_pro').write_text(json.dumps({'meta':{'filename':'native.kicad_pro','version':1}}))
            with mock.patch.object(ng,'stroke_path',reject_arcs):
                ctx=prepare_geometry_context(folder/'native.kicad_sch',None,cli,folder/'context')
                self.assertEqual('PASS',ctx['status'],ctx['gaps'])
                reports={}
                for name in ('native.kicad_sch','child.kicad_sch'):
                    page=page_context_from_job(ctx,folder/name)
                    reports[name]=check_scene(read_scene(parse((folder/name).read_text()),page),reserved=[])
            self.assertEqual('PASS',reports['native.kicad_sch']['status'],reports['native.kicad_sch'])
            self.assertEqual('INSUFFICIENT',reports['child.kicad_sch']['status'])
            self.assertTrue(any(g.startswith('native arc ink unsupported: simulated') for g in reports['child.kicad_sch']['coverage']['gaps']))
            self.assertFalse(any('arc ink' in g for g in reports['native.kicad_sch']['coverage']['gaps']))

if __name__=='__main__':unittest.main()
