"""Real runner rejection must leave prior experiment bytes untouched."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'evals'))
from run_binding import capture,open_run,validate_run
from bench_common import native,assembly_flag

class RunBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name);self.cache=self.base/'cache';self.cache.mkdir()
        self.source=self.cache/'empty';self.source.mkdir()
        self.prepared={'benchmark_revision':2,'incremental_input_fingerprint':'old','circuits':[
            {'round':'control','cache':str(self.source),'inputs':{},'functional_native':'NOT_RUN','not_run_reason':'Explicit self-authored control without functional CAD'}]}
        self.write_cache();self.out=self.base/'out'
    def write_cache(self):
        (self.cache/'prepared.json').write_text(json.dumps(self.prepared))
    def argv(self,revision=2,types=('M-PIN-SWAP',),repo=REPO):
        return [sys.executable,'-B',str(repo/'evals/mutation_bench/run.py'),'--cache',str(self.cache),'--out',str(self.out),'--revision',str(revision),'--types',*types]
    def run_runner(self,argv):
        return subprocess.run(argv,capture_output=True,text=True)
    def first(self):
        p=self.run_runner(self.argv());self.assertEqual(0,p.returncode,p.stderr)
        return {str(p.relative_to(self.out)):p.read_bytes() for p in self.out.rglob('*') if p.is_file()}
    def unchanged_rejection(self,argv,before):
        p=self.run_runner(argv);self.assertNotEqual(0,p.returncode,p.stdout)
        self.assertIn('binding',p.stderr.lower())
        self.assertEqual(before,{str(p.relative_to(self.out)):p.read_bytes() for p in self.out.rglob('*') if p.is_file()})
    def test_exact_resume_keeps_initial_binding_and_one_row(self):
        self.first();binding=(self.out/'run-binding.json').read_bytes()
        p=self.run_runner(self.argv()+['--resume']);self.assertEqual(0,p.returncode,p.stderr)
        self.assertEqual(binding,(self.out/'run-binding.json').read_bytes())
        self.assertEqual(1,len(json.loads((self.out/'matrix.json').read_text())))
        self.assertTrue(json.loads((self.out/'summary.json').read_text())['run_binding']['verified'])
    def test_cross_revision_rejected_before_any_output_write(self):
        before=self.first();self.prepared['benchmark_revision']=3;self.prepared['incremental_input_fingerprint']='new';self.write_cache()
        self.unchanged_rejection(self.argv(3)+['--resume'],before)
    def test_same_revision_changed_fingerprint_rejected(self):
        before=self.first();self.prepared['incremental_input_fingerprint']='new';self.write_cache()
        self.unchanged_rejection(self.argv()+['--resume'],before)
    def test_changed_actual_cache_payload_rejected(self):
        before=self.first();(self.source/'changed.txt').write_text('new actual input')
        self.unchanged_rejection(self.argv()+['--resume'],before)
    def test_changed_types_rejected(self):
        before=self.first();self.unchanged_rejection(self.argv(types=('M-VALUE',))+['--resume'],before)
    def test_legacy_unbound_output_cannot_be_relabelled(self):
        self.out.mkdir();(self.out/'matrix.json').write_text('[{"old":true}]')
        before={'matrix.json':(self.out/'matrix.json').read_bytes()}
        self.unchanged_rejection(self.argv()+['--resume'],before)
    def test_bound_run_cannot_be_recomputed_in_place(self):
        before=self.first()
        argv=[sys.executable,'-B',str(REPO/'evals/mutation_bench/recompute.py'),'--run',str(self.out)]
        p=self.run_runner(argv);self.assertNotEqual(0,p.returncode,p.stdout)
        self.assertEqual(before,{str(p.relative_to(self.out)):p.read_bytes() for p in self.out.rglob('*') if p.is_file()})
    def test_same_head_dirty_source_and_changed_head_rejected(self):
        clone=self.base/'private-control-repo';shutil.copytree(REPO,clone,ignore=shutil.ignore_patterns('.git','__pycache__'))
        def git(*args):subprocess.run(['git','-C',str(clone),*args],check=True,capture_output=True)
        git('init','-q');git('add','--','.');git('-c','user.name=Benchmark Control','-c','user.email=benchmark-control@example.invalid','commit','-qm','Synthetic source control')
        p=self.run_runner(self.argv(repo=clone));self.assertEqual(0,p.returncode,p.stderr)
        before={str(p.relative_to(self.out)):p.read_bytes() for p in self.out.rglob('*') if p.is_file()}
        target=clone/'evals/bench_common.py';original=target.read_bytes();target.write_bytes(original+b'\n# Actual same-HEAD source control\n')
        self.unchanged_rejection(self.argv(repo=clone)+['--resume'],before);target.write_bytes(original)
        git('-c','user.name=Benchmark Control','-c','user.email=benchmark-control@example.invalid','commit','--allow-empty','-qm','Different HEAD with same source bytes')
        self.unchanged_rejection(self.argv(repo=clone)+['--resume'],before)
    def test_end_validation_rejects_source_or_input_drift(self):
        binding=capture(REPO,self.cache,2,['M-PIN-SWAP'],'mutation');open_run(self.out,binding)
        (self.source/'new').write_text('drift')
        with self.assertRaises(ValueError):validate_run(self.out,REPO,self.cache,2,['M-PIN-SWAP'],'mutation')
    def test_binding_cannot_be_rewritten_during_execution_to_accept_drift(self):
        initial=open_run(self.out,capture(REPO,self.cache,2,['M-PIN-SWAP'],'mutation'))
        (self.source/'new').write_text('changed actual input')
        (self.out/'run-binding.json').write_text(json.dumps(capture(REPO,self.cache,2,['M-PIN-SWAP'],'mutation')))
        with self.assertRaises(ValueError):validate_run(self.out,REPO,self.cache,2,['M-PIN-SWAP'],'mutation',initial)
    def test_dnp_property_is_component_identity_even_when_partitions_unchanged(self):
        before=self.base/'before.xml';after=self.base/'after.xml'
        template='<export><components><comp ref="R4"><value>1k</value>{}</comp></components><nets><net name="A"><node ref="R4" pin="1"/></net></nets></export>'
        before.write_text(template.format(''));after.write_text(template.format('<property name="dnp"/>'))
        a,b=native(before),native(after);self.assertEqual(a['partitions'],b['partitions'])
        self.assertNotEqual(a['components'],b['components']);self.assertFalse(a['components']['R4']['dnp']);self.assertTrue(b['components']['R4']['dnp'])
    def test_actual_marker_flag_schema_and_conflicts(self):
        import xml.etree.ElementTree as ET
        for name in ['dnp','exclude_from_bom','exclude_from_board']:
            with self.subTest(name=name):
                self.assertFalse(assembly_flag(ET.fromstring('<comp/>'),name))
                self.assertTrue(assembly_flag(ET.fromstring(f'<comp><property name="{name}"/></comp>'),name))
                with self.assertRaises(ValueError):assembly_flag(ET.fromstring(f'<comp><property name="{name}"/><{name}>false</{name}></comp>'),name)

if __name__=='__main__':unittest.main()
