"""Self-authored actual native controls; all output remains outside source."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from test_native_circle_contacts import fixture
from schematic_layout.sexpr import first,all_nodes,form as f,Atom as A,dump,set_node,parse
from schematic_layout.scene import read_scene
from schematic_layout.qa import check_scene
from schematic_layout.native_circle_contacts import refine_wire_contacts
from schematic_layout.native import find_cli
from schematic_layout.native_geometry_context import sha

def uid(n):return str(uuid.uuid5(uuid.NAMESPACE_URL,'ASG-ring-controls/'+n))
def native_fixture(case='legal',angle=0,mirror=''):
    tree=fixture(angle,mirror,case if case in ('foreign','through-gap','neighbor') else 'legal')
    set_node(tree,'uuid',uid('root'));tree.append(f('generator','eeschema'))
    symbol=first(tree,'symbol');set_node(symbol,'uuid',uid('symbol'))
    symbol.append(f('instances',f('project','control',f('path','/'+uid('root'),f('reference','J1'),f('unit',1)))))
    symbol.append(f('property','Value','Rings',f('at',50.8,50.8,0),f('effects',f('font',f('size',1,1)),A('hide'))))
    wire=first(tree,'wire');wire.append(f('uuid',uid('wire')));end=first(wire,'pts')[2][1:]
    tree.append(f('label','END',f('at',*end,0),f('effects',f('font',f('size',1,1)),f('justify',A('left'),A('bottom'))),f('uuid',uid('end'))))
    lib=first(first(tree,'lib_symbols'),'symbol');graph=all_nodes(lib,'symbol')[0]
    if case=='field':tree.append(f('text','BLOCK',f('at',53.34,50.8,0),f('effects',f('font',f('size',1.27,1.27))),f('uuid',uid('field'))))
    elif case=='far-field':
        prop=next(p for p in all_nodes(symbol,'property') if p[1]=='Value')
        prop[2]='hide';first(prop,'at')[1:]=[54.61,50.8,0];first(prop,'effects').remove('hide')
    elif case=='filled':first(first(graph,'rectangle'),'fill')[1][1]=A('outline')
    elif case=='visible-number':lib.remove(first(lib,'pin_numbers'))
    elif case=='wide-ring':
        for c in all_nodes(graph,'circle'):first(first(c,'stroke'),'width')[1]=3
    elif case=='wide-frame':first(first(first(graph,'rectangle'),'stroke'),'width')[1]=3
    elif case in ('wide-wire','tiny-ring'):
        # No glyphs can mask the issue: both endpoints are real passive pins.
        tree.remove(next(n for n in all_nodes(tree,'label') if n[1]=='END'))
        peer=copy.deepcopy(symbol);set_node(peer,'uuid',uid('peer'));first(peer,'at')[1]=58.42
        next(p for p in all_nodes(peer,'property') if p[1]=='Reference')[2]='J2'
        first(first(first(peer,'instances'),'project'),'path')[2][1]='J2'
        tree.append(peer);first(wire,'pts')[2][1:]=[58.42,50.8]
        if case=='wide-wire':first(first(wire,'stroke'),'width')[1]=2
        else:
            for c in all_nodes(graph,'circle'):first(c,'radius')[1]=.1
    elif case in ('identical-foreign-frame','foreign-filled-frame'):
        tree.append(f('rectangle',f('start',49.53,46.99),f('end',52.07,54.61),f('stroke',f('width',.01),f('type',A('default'))),f('fill',f('type',A('outline' if case=='foreign-filled-frame' else 'none'))),f('uuid',uid('foreign'))))
    elif case=='missing-own-circle-foreign':
        c=all_nodes(graph,'circle')[1];graph.remove(c)
        tree.append(f('circle',f('center',50.8,50.8),f('radius',.635),f('stroke',f('width',.0006),f('type',A('default'))),f('fill',f('type',A('none'))),f('uuid',uid('foreign-circle'))))
    elif case=='source-variable':tree.append(f('text','${UNKNOWN}',f('at',53.34,50.8,0),f('effects',f('font',f('size',1,1))),f('uuid',uid('variable'))))
    elif case=='dash-wire':first(wire,'stroke')[2][1]=A('dash')
    elif case=='foreign-dash':tree.append(f('polyline',f('pts',f('xy',51.7,48.26),f('xy',51.7,53.34)),f('stroke',f('width',.254),f('type',A('dash'))),f('fill',f('type',A('none'))),f('uuid',uid('dashed-foreign'))))
    elif case=='solid-wire':first(wire,'stroke')[2][1]=A('solid')
    elif case=='gap-only':tree.append(f('circle',f('center',150,100),f('radius',1),f('stroke',f('width',.254),f('type',A('default'))),f('fill',f('type',A('none'))),f('uuid',uid('gap'))))
    elif case=='warning-only':
        tree.append(f('text','ANNOT',f('at',150,100,0),f('effects',f('font',f('size',1,1))),f('uuid',uid('note'))))
        tree.append(f('polyline',f('pts',f('xy',140,100),f('xy',160,100)),f('stroke',f('width',.254),f('type',A('default'))),f('fill',f('type',A('none'))),f('uuid',uid('annotation'))))
    elif case=='crlf':pass
    return tree

class NativeCircleControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cli=find_cli()
        if not cls.cli:raise unittest.SkipTest('KiCad CLI unavailable')
        base=Path('/tmp/codex-work/asg-circle-tests');base.mkdir(exist_ok=True,parents=True)
        cls.temp=tempfile.TemporaryDirectory(dir=base);cls.base=Path(cls.temp.name);cls.rows={}
        cases=[(f'positive-{a}-{m or "none"}','legal',a,m) for a in (0,90,180,270) for m in ('','x','y')]
        cases += [(c,c,0,'') for c in ('foreign','through-gap','neighbor','field','filled','visible-number','wide-ring','wide-frame','identical-foreign-frame','foreign-filled-frame','missing-own-circle-foreign','source-variable','dash-wire','foreign-dash','solid-wire','crlf','gap-only','warning-only')]
        for name,case,a,m in cases:
            folder=cls.base/name;folder.mkdir();tree=native_fixture(case,a,m);source=folder/'control.kicad_sch'
            text=dump(tree)+'\n';source.write_bytes((text.replace('\n','\r\n') if case=='crlf' else text).encode())
            (folder/'control.kicad_pro').write_text(json.dumps({'meta':{'version':1},'schematic':{'drawing':{'default_line_thickness':6,'default_wire_thickness':6}}}))
            before={p.name:sha(p) for p in folder.iterdir() if p.is_file()}
            old=check_scene(read_scene(tree));new=refine_wire_contacts(source,old,cli=cls.cli,workdir=folder/'proof')
            if before!={n:sha(folder/n) for n in before}:raise AssertionError('original input drift')
            cls.rows[name]=(source,old,new)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_positive_rotation_mirror_default_and_solid_native_wire(self):
        for name,(_,old,new) in self.rows.items():
            if name.startswith('positive-') or name in ('solid-wire','crlf'):
                self.assertNotIn('wire_body',new['counts'],(name,new))
                self.assertEqual('PASS',new['status'],(name,new))

    def test_real_foreign_neighbor_field_and_unknown_profiles_keep_rejection(self):
        for name in ('foreign','through-gap','neighbor','field','filled','visible-number','wide-ring','wide-frame','identical-foreign-frame','foreign-filled-frame','missing-own-circle-foreign','source-variable','dash-wire','foreign-dash'):
            _,old,new=self.rows[name]
            self.assertEqual('FAIL',new['status'],(name,new))
            self.assertEqual(old['coverage']['gaps'],new['coverage']['gaps'])
            self.assertTrue('wire_body' in new['counts'] or name=='field' and 'wire_text' in new['counts'],(name,new))

    def test_all_masks_preserve_exact_non_target_bytes_and_physical_pin_identity(self):
        source,_,new=self.rows['crlf'];e=new['native_contact_qualification'];self.assertEqual('QUALIFIED',e['status'])
        original=source.read_bytes();base=original.decode();work=Path(e['workdir'])
        for export in e['exports']:
            changed=base
            for a,b,replacement in sorted(export['source_edits'],reverse=True):changed=changed[:a]+replacement+changed[b:]
            actual=(work/export['label']/'source/control.kicad_sch').read_bytes()
            self.assertEqual(changed.encode(),actual)
            if export['label'].startswith('pin-cap-'):
                tree=parse(actual.decode());initial=parse(base)
                pins=lambda t:[(str(first(p,'number')[1]),first(p,'at'),first(p,'name')) for sub in all_nodes(first(first(t,'lib_symbols'),'symbol'),'symbol') for p in all_nodes(sub,'pin')]
                self.assertEqual(pins(initial),pins(tree))

    def test_existing_gap_cannot_turn_a_measured_rejection_into_missing(self):
        for name in ('gap-only','warning-only'):
            _,old,new=self.rows[name]
            self.assertEqual(old['status'],new['status'])
            self.assertEqual(old['findings'],new['findings'])
            self.assertEqual(old['coverage']['gaps'],new['coverage']['gaps'])
            self.assertIn('hide measured',new['native_contact_qualification']['reason'])

class WholeWireGlyphTests(unittest.TestCase):
    def test_visible_literal_hide_outside_the_corridor_still_blocks_release(self):
        cli=find_cli()
        if not cli:self.skipTest('KiCad CLI unavailable')
        base=Path('/tmp/codex-work/asg-circle-tests');base.mkdir(exist_ok=True,parents=True)
        with tempfile.TemporaryDirectory(dir=base) as tmp:
            folder=Path(tmp);tree=native_fixture('far-field');source=folder/'control.kicad_sch';source.write_text(dump(tree)+'\n')
            (folder/'control.kicad_pro').write_text('{"meta":{"version":1}}')
            old=check_scene(read_scene(tree));new=refine_wire_contacts(source,old,cli=cli,workdir=folder/'proof')
            self.assertIn('wire_body',new['counts'],new)
            from schematic_layout.native_geometry import SVG,ink_gap
            native=SVG((folder/'proof/baseline/svg/control.svg').read_text())
            keys={k:n for k,n in native.primitives.items() if 'stroked-text' in native.objects[k]['classes']}
            a,b=read_scene(tree).wires[0]
            self.assertLess(ink_gap([[list(a),list(b),.1524]],native.segments(keys,glyph=True)),0)

class TerminalApertureTests(unittest.TestCase):
    def test_actual_wide_wire_and_minpen_tiny_inner_circle_keep_old_findings(self):
        cli=find_cli()
        if not cli:self.skipTest('KiCad CLI unavailable')
        base=Path('/tmp/codex-work/asg-circle-tests');base.mkdir(exist_ok=True,parents=True)
        for case in ('wide-wire','tiny-ring'):
            with tempfile.TemporaryDirectory(dir=base) as tmp:
                folder=Path(tmp);tree=native_fixture(case);source=folder/'control.kicad_sch';source.write_text(dump(tree)+'\n')
                (folder/'control.kicad_pro').write_text('{"meta":{"version":1}}')
                old=check_scene(read_scene(tree));new=refine_wire_contacts(source,old,cli=cli,workdir=folder/'proof')
                self.assertEqual(old['findings'],new['findings'],(case,new))
                self.assertEqual(old['coverage']['gaps'],new['coverage']['gaps'])
                self.assertEqual('FAIL',new['status'])

if __name__=='__main__':unittest.main()
