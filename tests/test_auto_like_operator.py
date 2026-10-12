"""Opt-in operator scope, original 17 defaults, and actual native NAME_ONLY."""
from pathlib import Path
import sys,copy,json,tempfile,unittest,subprocess,importlib.util,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'evals'),str(ROOT/'evals/mutation_bench'),str(ROOT/'scripts'),str(ROOT/'tests/fixtures/drawing')]
from operators import TYPES
from extra_operators import EXTRA_TYPES,mutate_extra,selected_types,AUTO_LIKE_LITERAL
from bench_common import native
from native_probe import probe_delta
from schematic_layout.sexpr import parse,dump,form,Atom,first,all_nodes
from schematic_layout.native import find_cli,compare_netlist
import recipe_board
spec=importlib.util.spec_from_file_location('auto_like_mutation_runner',ROOT/'evals/mutation_bench/run.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

def fixture(d,name='CLOCK',kind='label',duplicate=False):
    n=form(kind,name,form('at',20,20,0),form('effects',form('font',form('size',1.27,1.27))),form('uuid','unique-label'))
    if kind!='label':n.append(form('shape',Atom('input')))
    tree=form('kicad_sch',form('version',Atom('20250114')),form('uuid','root'),form('paper','A4'),form('lib_symbols'),n)
    if duplicate:tree.append(copy.deepcopy(n))
    (d/'test.kicad_sch').write_text(dump(tree)+'\n')
    (d/'electrical-intent.json').write_text(json.dumps({'components':[],'nets':[{'name':name,'pins':['R1.1']}]}))
    return tree
class AutoLikeOperatorTests(unittest.TestCase):
    def test_default17_and_revision2_unchanged(self):
        self.assertEqual(len(TYPES),17);self.assertNotIn('M-NAME-AUTO-LIKE',TYPES)
        self.assertEqual(selected_types(None,2,TYPES),list(TYPES));self.assertEqual(selected_types(None,3,TYPES),list(TYPES))
    def test_explicit_extra_and_unknown_rejected(self):
        self.assertEqual(selected_types(['M-NAME-AUTO-LIKE'],3,TYPES),['M-NAME-AUTO-LIKE'])
        with self.assertRaisesRegex(ValueError,'requires'):selected_types(['M-NAME-AUTO-LIKE'],2,TYPES)
        with self.assertRaisesRegex(ValueError,'Unknown'):selected_types(['MISSPELLED'],3,TYPES)
    def test_one_literal_change_keeps_uuid_style_bytes_and_intent(self):
        for kind in ('label','global_label','hierarchical_label'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as t:
                d=Path(t);before=fixture(d,kind=kind);raw=(d/'test.kicad_sch').read_bytes();intent=(d/'electrical-intent.json').read_bytes();p=mutate_extra(d,'M-NAME-AUTO-LIKE')
                self.assertEqual(p['status'],'APPLICABLE');before[-1][1]=AUTO_LIKE_LITERAL
                self.assertEqual(parse((d/'test.kicad_sch').read_text()),parse(dump(before)))
                self.assertEqual((d/'test.kicad_sch').read_bytes(),raw.replace(b'"CLOCK"',('"'+AUTO_LIKE_LITERAL+'"').encode(),1))
                self.assertEqual((d/'electrical-intent.json').read_bytes(),intent)
    def test_unsupported_encoding_and_duplicate_out_of_scope(self):
        for name,dup in [('A{slash}B',False),('${VAR}',False),('DATA[0]',False),('CLOCK',True)]:
            with self.subTest(name=name),tempfile.TemporaryDirectory() as t:
                d=Path(t);fixture(d,name=name,duplicate=dup);before=(d/'test.kicad_sch').read_bytes()
                self.assertEqual(mutate_extra(d,'M-NAME-AUTO-LIKE')['status'],'OUT_OF_SCOPE');self.assertEqual((d/'test.kicad_sch').read_bytes(),before)
    def test_no_label_and_linked_hier_interface_out_of_scope(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);tree=fixture(d,kind='hierarchical_label');tree.append(form('sheet',form('property','Sheetfile','child.kicad_sch'),form('uuid','child'),form('pin','CLOCK',Atom('input'),form('at',20,20,0))))
            (d/'test.kicad_sch').write_text(dump(tree));(d/'child.kicad_sch').write_text('(kicad_sch (uuid "childroot") (lib_symbols))')
            self.assertEqual(mutate_extra(d,'M-NAME-AUTO-LIKE')['status'],'OUT_OF_SCOPE')
    def test_generic_fail_and_changed_intent_never_count(self):
        p={'type':'M-NAME-AUTO-LIKE'}
        for valid,kind in [(False,'NAME_ONLY'),(False,'TOPOLOGY')]:
            r={'probe_valid':valid,'probe_kind':kind,'caught_by':['erc'],'new_errors':{},'native_delta':{}}
            runner.classify({}, {}, {'gates':{'erc':{'status':'FAIL'}}},{},p,r);self.assertEqual(r['status'],'INVALID_PROBE');self.assertEqual(r['caught_by'],[])
        r={'probe_valid':True,'probe_kind':'NAME_ONLY','caught_by':[],'new_errors':{'erc':[{'entry':{'kind':'other'}}]},'native_delta':{'name_targets':[]}}
        runner.classify({}, {}, {'gates':{'erc':{'status':'FAIL'},'intent_netlist':{'status':'FAIL'}}},{},p,r);self.assertEqual(r['status'],'MISSED')
    def test_only_new_target_name_error_catches(self):
        delta={'name_targets':[{'expected':'CLOCK','before_names':['CLOCK'],
                                'after_names':[AUTO_LIKE_LITERAL],'pins':['R1.1']}]}
        for entry,wanted in [({'kind':'net_name_mismatch','expected':'CLOCK','actual':[AUTO_LIKE_LITERAL]},'CAUGHT'),
                              ({'kind':'net_name_mismatch','expected':'OTHER','actual':[AUTO_LIKE_LITERAL]},'MISSED')]:
            r={'probe_valid':True,'probe_kind':'NAME_ONLY','caught_by':[],'native_delta':delta,
               'new_errors':{'intent_netlist':[{'entry':entry}]}}
            runner.classify({'gates':{'intent_netlist':{'status':'FAIL'}}},{},
                            {'gates':{'intent_netlist':{'status':'FAIL'}}},{},
                            {'type':'M-NAME-AUTO-LIKE'},r)
            self.assertEqual(r['status'],wanted)
    def test_unknown_cli_has_no_output(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);out=d/'out';r=subprocess.run([sys.executable,'-B',str(ROOT/'evals/mutation_bench/run.py'),'--cache',str(d/'missing-cache'),'--out',str(out),'--types','M-UNKNOWN'],capture_output=True,text=True)
            self.assertNotEqual(r.returncode,0);self.assertIn('Unknown mutation type',r.stderr);self.assertFalse(out.exists())
    @unittest.skipUnless(find_cli(),'Native unavailable')
    def test_actual_native_main_misses_same_partition_manual_auto_name(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);tree,_=recipe_board.draw().build('auto-like-native');src=d/'probe.kicad_sch';src.write_text(dump(tree)+'\n');(d/'electrical-intent.json').write_text(json.dumps(recipe_board.INTENT));cli=find_cli()
            before=d/'before.xml';after=d/'after.xml'
            def export(p):
                run=subprocess.run([cli,'sch','export','netlist','--format','kicadxml','-o',str(p),str(src)],capture_output=True,text=True);self.assertEqual(run.returncode,0,run.stderr)
            export(before);plan=mutate_extra(d,'M-NAME-AUTO-LIKE');self.assertEqual(plan['status'],'APPLICABLE');export(after)
            delta=probe_delta(before,after,native(before)['components'],native(after)['components'],recipe_board.INTENT)
            self.assertEqual(delta['probe_kind'],'NAME_ONLY');self.assertFalse(delta['identity_changed']);self.assertFalse(delta['partitions_changed'])
            old=compare_netlist(before,recipe_board.INTENT);new=compare_netlist(after,recipe_board.INTENT)
            rec={'probe_kind':'NAME_ONLY','probe_valid':True,'native_delta':delta,'caught_by':[],'new_errors':{'intent_netlist':runner.new_entries({'intent_netlist':old},{'intent_netlist':new},'intent_netlist')}}
            runner.classify({'gates':{'intent_netlist':{'status':old['status']}}},{},{'gates':{'intent_netlist':{'status':new['status']}}},{},plan,rec)
            self.assertEqual(rec['status'],'MISSED')
if __name__=='__main__':unittest.main()
