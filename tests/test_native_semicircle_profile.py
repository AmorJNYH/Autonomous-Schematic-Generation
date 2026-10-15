"""Reject-first finite circular-A controls; identity paths remain linear."""
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from schematic_layout import native_geometry as ng
from schematic_layout.native_circle_contacts import _hits,_validate_foreground

STYLE='fill:none;stroke:#000000;stroke-width:.1;stroke-linecap:round;stroke-linejoin:round'
def svg(d,style=STYLE,extra=''):
    return '<svg width="30mm" height="30mm" viewBox="0 0 30 30"><path d="'+d+'" style="'+style+'" '+extra+'/></svg>'

class SemicircleRejectFirst(unittest.TestCase):
    def test_source_conductor_identity_never_accepts_arc(self):
        for d in ('M9 10 A1 1 0 0 0 11 10','M9 10 L9 10 A1 1 0 1 1 11 10'):
            with self.assertRaises(ValueError):ng.linear_path(d)

    def test_nonprofile_numeric_grammar_paint_and_transform_never_qualify(self):
        paths=('M9 10 a1 1 0 0 0 11 10','M9 10 A1 2 0 0 0 11 10',
               'M9 10 A1 1 90 0 0 11 10','M9 10 A0 0 0 0 0 11 10',
               'M9 10 A-1 -1 0 0 0 11 10','M9 10 A1 1 0 2 0 11 10',
               'M9 10 A1 1 0 0 .5 11 10','M9 10 A1 1 0 0 1.0 11 10',
               'M9 10 A1 1 0 0 0 9 10',
               'M9 10 A1 1 0 0 0 12 10','M9 10 A1e999 1e999 0 0 0 11 10',
               'M9 10 A1 1 0 0 0 NaN 10','M9 10 A1 1 0 0 0 11',
               'A1 1 0 0 0 11 10','M9 10 A1 1 0 0 0 11 10 C0 0 1 1 2 2',
               'M9 10 A1 1 0 0 0 11 10 A','M9 10 A1 1 0 0 0 11 10 Z Z',
               'M0 0 A10000 10000 0 0 0 20000 0')
        for d in paths:
            with self.subTest(d=d),self.assertRaises(ValueError):ng.SVG(svg(d))
        d='M9 10 A1 1 0 0 0 11 10'
        for style,extra in ((STYLE.replace('fill:none','fill:#000000'),''),(STYLE,'transform="translate(1 1)"'),(STYLE,'class="stroked-text"'),(STYLE+';stroke-dasharray:1,nan','')):
            with self.subTest(style=style,extra=extra),self.assertRaises(ValueError):
                native=ng.SVG(svg(d,style,extra));_validate_foreground(native)

    def test_true_arc_interior_hits_even_when_endpoint_chord_and_bbox_perimeter_miss(self):
        native=ng.SVG(svg('M9 10 A1 1 0 0 0 11 10'));o=next(iter(native.objects.values()))
        segments=native.segments()
        # Either SVG sweep convention: samples of both candidates find which
        # half is covered, then test its interior, not its bounding perimeter.
        covered=[p for p in ((10,9),(10,11)) if _hits(o,p,p,.01)]
        self.assertEqual(1,len(covered));y=covered[0][1];sign=y-10
        point=(10+math.sqrt(.5),10+sign*math.sqrt(.5))
        self.assertTrue(_hits(o,point,point,.01))
        self.assertLessEqual(ng.ink_gap(segments,[[list(point),list(point),.01]]),0)
        self.assertGreater(ng.point_segment(point,(9,10),(11,10)),.5)

    def test_stroke_plus_near_tangent_and_foreign_dash_are_protected(self):
        for dash in ('',';stroke-dasharray:1,1'):
            native=ng.SVG(svg('M9 10 A1 1 0 0 0 11 10',STYLE+dash));_validate_foreground(native);o=next(iter(native.objects.values()))
            # .0499 beyond actual curve: centerlines disjoint, width touches.
            hit=[y for y in (8.9501,11.0499) if _hits(o,(10,y),(10,y),.0001)]
            self.assertEqual(1,len(hit))
            if dash:
                with self.assertRaises(ValueError):native.segments()

    def test_both_sweeps_largeflags_oblique_diameter_and_all_consumers_cover_samples(self):
        for large in (0,1):
            for sweep in (0,1):
                for a,b,r in (((9,10),(11,10),1),((10,9),(10,11),1),((7,6),(13,14),5)):
                    d=f'M{a[0]} {a[1]} A{r} {r} 0 {large} {sweep} {b[0]} {b[1]}'
                    native=ng.SVG(svg(d));o=next(iter(native.objects.values()));segments=native.segments();box=ng.bounds(segments)
                    center=((a[0]+b[0])/2,(a[1]+b[1])/2);theta=math.atan2(a[1]-center[1],a[0]-center[0]);direction=1 if sweep else -1
                    for i in range(301):
                        t=theta+direction*math.pi*i/300;p=(center[0]+r*math.cos(t),center[1]+r*math.sin(t))
                        self.assertTrue(_hits(o,p,p,.0001),(d,p))
                        self.assertLessEqual(ng.ink_gap(segments,[[list(p),list(p),.0001]]),0)
                        self.assertTrue(box[0]<=p[0]<=box[2] and box[1]<=p[1]<=box[3])

    def test_equality_hidden_fulltext_and_unsupported_glyph_remain_guarded(self):
        a=ng.SVG(svg('M9 10 A1 1 0 0 0 11 10'))
        b=ng.SVG(svg('M9 10 A1 1 0 0 1 11 10'))
        self.assertNotEqual(a.primitives,b.primitives)
        with self.assertRaises(ValueError):a.segments(glyph=True)
        with self.assertRaises(ValueError):ng.removal(a,b)

if __name__=='__main__':unittest.main()
