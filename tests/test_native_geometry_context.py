"""Finite same-job native controls: unique source causality, never visual guesses."""
import json
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from schematic_layout.scratch import scratch_base
from schematic_layout.native import find_cli
from schematic_layout.native_geometry_context import prepare_geometry_context,load_page_context,page_context_from_job,sha,spans
from schematic_layout.sexpr import form as f,Atom as A,dump,parse,first,all_nodes
from schematic_layout.scene import read_scene
from schematic_layout.qa import check_scene

def uid(name): return str(uuid.uuid5(uuid.NAMESPACE_URL,'ASG-own-native-geometry/'+name))
def effects(angle=0): return f('effects',f('font',f('size',1.27,1.27)))
def fixture(kind):
    root=f('kicad_sch',f('version',20250114),f('generator','eeschema'),f('uuid',uid('root')),f('paper','A4'),f('lib_symbols'))
    x,y=(2.54,50.8) if kind=='offpage' else (50.8,50.8)
    name='${NAME}' if kind=='variable' else 'DUP'
    sh=f('sheet',f('at',x,y),f('size',76.2,38.1),f('stroke',f('width',0),f('type',A('default'))),f('fill',f('color',0,0,0,0)),f('uuid',uid('sheet')),
         f('property','Sheetname',name,f('at',x,y-2.54,0),effects()),
         f('property','Sheetfile','child.kicad_sch',f('at',x,y+40.64,0),effects()),
         f('instances',f('project','native',f('path','/'+uid('root'),f('page','2')))))
    if kind=='pins': sh.append(f('pin','PORT',A('input'),f('at',x,y+19.05,180),effects(),f('uuid',uid('pin'))))
    root.append(sh)
    root.append(f('text','DUP',f('at',x+38.1,y+19.05,0),effects(),f('uuid',uid('caption'))))
    if kind=='wire':
        for px in (x-10.16,x+10.16):
            root.append(f('label','N',f('at',px,y+19.05,0),effects(),f('uuid',uid(str(px)))))
        root.append(f('wire',f('pts',f('xy',x-10.16,y+19.05),f('xy',x+10.16,y+19.05)),f('stroke',f('width',0),f('type',A('default'))),f('uuid',uid('wire'))))
    if kind=='overlay': root.append(f('text','OVERLAY',f('at',x,y+40.64,0),effects(),f('uuid',uid('foreign-text'))))
    if kind=='identical': root.append(f('rectangle',f('start',x,y),f('end',x+76.2,y+38.1),f('stroke',f('width',.254),f('type',A('default'))),f('fill',f('type',A('none'))),f('uuid',uid('foreign-outline'))))
    if kind=='unknown-stroke': first(sh,'stroke').append(f('color',0,0,0,0))
    if kind=='extra-display': sh.append(f('dnp',A('yes')))
    if kind in ('cjk','rotate90','rotate180','bold','filledfont'):
        prop=all_nodes(sh,'property')[0]
        if kind=='cjk': prop[2]='重复 字段'
        if kind.startswith('rotate'): first(prop,'at')[3]=float(kind[6:])
        if kind=='bold': first(first(prop,'effects'),'font').append(A('bold'))
        if kind=='filledfont': first(first(prop,'effects'),'font').append(f('face','Arial'))
    root.append(f('sheet_instances',f('path','/',f('page','1'))))
    child=f('kicad_sch',f('version',20250114),f('generator','eeschema'),f('uuid',uid('child')),f('paper','A4'),f('lib_symbols'))
    return root,child

class SpanTests(unittest.TestCase):
    def test_exact_span_preserves_non_target_bytes_unicode_and_comments(self):
        src='(x ; comment\n (property "字段" "DUP" (effects (font (size 1 1)))))\n'
        ranges=spans(src);start,end=ranges[(1,3)]
        self.assertEqual('(effects (font (size 1 1)))',src[start:end])
        changed=src[:start]+src[start:end-1]+' (hide yes))'+src[end:]
        self.assertEqual(src[:start],changed[:start]);self.assertEqual('\n',changed[-1])

class NativeContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cli=find_cli()
        if not cls.cli: raise unittest.SkipTest('KiCad native tool missing')
        tempbase=scratch_base()/'native-geometry-tests';tempbase.mkdir(parents=True,exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(prefix='asg-native-geometry-',dir=tempbase);cls.base=Path(cls.temp.name);cls.rows={}
        for kind in ('clear','wire','overlay','offpage','pins','variable'):
            folder=cls.base/kind;folder.mkdir();a,b=fixture(kind)
            (folder/'native.kicad_sch').write_text(dump(a)+'\n');(folder/'child.kicad_sch').write_text(dump(b)+'\n')
            (folder/'native.kicad_pro').write_text(json.dumps({'meta':{'filename':'native.kicad_pro','version':1},'text_variables':{'NAME':'NativeVariable'}}))
            before={p.name:sha(p) for p in folder.iterdir() if p.is_file()}
            ctx=prepare_geometry_context(folder/'native.kicad_sch',None,cls.cli,folder/'context')
            after={p.name:sha(p) for p in folder.iterdir() if p.is_file()}
            if before!=after: raise AssertionError('native tool modified original source')
            page=page_context_from_job(ctx,folder/'native.kicad_sch') if ctx['status']=='PASS' else {'gaps':ctx['gaps']}
            report=check_scene(read_scene(parse((folder/'native.kicad_sch').read_text()),page),reserved=[])
            cls.rows[kind]=(ctx,report)
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def test_clear_caption_same_literal_inside_frame_qualified(self):
        ctx,report=self.rows['clear'];self.assertEqual('PASS',report['status'],report)
        self.assertEqual(2,report['coverage']['native_sheet_fields'])
    def test_true_foreign_wire_crossing_caught(self):
        self.assertIn('wire_sheet_frame',self.rows['wire'][1]['counts'])
    def test_real_sheet_field_overlay_caught(self):
        self.assertIn('native_sheet_text_overlap',self.rows['overlay'][1]['counts'])
    def test_native_extents_off_page_caught(self):
        self.assertIn('off_page',self.rows['offpage'][1]['counts'])
    def test_outline_or_variable_unknown_not_pass(self):
        for kind in ('pins','variable'):
            self.assertEqual('INSUFFICIENT',self.rows[kind][1]['status'])
            self.assertIn('Unsupported sheet object: sheet',self.rows[kind][1]['coverage']['gaps'])
    def test_sidecar_sha_and_original_input_drift_rejected(self):
        folder=self.base/'clear';p=folder/'context/context.json'
        with self.assertRaises(ValueError):load_page_context(p,folder/'native.kicad_sch','wrong')
        child=folder/'child.kicad_sch';old=child.read_bytes();child.write_bytes(old+b'\n')
        with self.assertRaises(ValueError):page_context_from_job(self.rows['clear'][0],folder/'native.kicad_sch')
        child.write_bytes(old)
    def test_bound_native_svg_tamper_rejected(self):
        folder=self.base/'clear';p=folder/'context/context.json';svg=next((folder/'context/baseline/svg').glob('*.svg'));old=svg.read_bytes();svg.write_bytes(old+b'\n')
        with self.assertRaises(ValueError):page_context_from_job(self.rows['clear'][0],folder/'native.kicad_sch')
        svg.write_bytes(old)
    def test_recomputed_sidecar_sha_does_not_authorize_fake_derived_ink(self):
        folder=self.base/'clear';p=folder/'context/context.json';old=p.read_bytes();data=json.loads(old)
        data['pages']['native.kicad_sch']['texts'][0]['box'][0]-=50
        p.write_text(json.dumps(data))
        with self.assertRaises(ValueError):load_page_context(p,folder/'native.kicad_sch',sha(p))
        p.write_bytes(old)
    def test_self_declared_pass_without_native_witnesses_rejected(self):
        folder=self.base/'clear';p=folder/'fake.json';p.write_text(json.dumps({'schema':'native-geometry-context-v1','status':'PASS','root':str(folder/'native.kicad_sch')}))
        with self.assertRaises(ValueError):load_page_context(p,folder/'native.kicad_sch',sha(p))
    def test_live_job_derived_lists_and_gaps_cannot_be_modified(self):
        ctx=self.rows['clear'][0];page=ctx['pages']['native.kicad_sch'];original=page['texts'];page['texts']=[]
        with self.assertRaises(ValueError):page_context_from_job(ctx,self.base/'clear/native.kicad_sch')
        page['texts']=original

if __name__=='__main__': unittest.main()
