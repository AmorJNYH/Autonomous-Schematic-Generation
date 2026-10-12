"""Revision-3 native name attribution and frozen-input safety."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO/'evals'), str(REPO/'evals/mutation_bench'), str(REPO/'scripts')]
from native_probe import probe_delta, attributable_name_errors
from incremental_delivery import safe_relative, fingerprint, replay_frozen, require_cache_revision
from compare_calibration_runs import compare
spec = importlib.util.spec_from_file_location('mutation_runner_revision3', REPO/'evals/mutation_bench/run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def xml(names=('A','B'), groups=(('R1.1',),('R1.2',))):
    return '<export><components/><nets>' + ''.join(
        f'<net name="{name}">' + ''.join(f'<node ref="{p.rsplit(".",1)[0]}" pin="{p.rsplit(".",1)[1]}"/>' for p in pins) + '</net>'
        for name,pins in zip(names,groups)) + '</nets></export>'


class Revision3Tests(unittest.TestCase):
    def delta(self, before, after, identities=({},{})):
        with tempfile.TemporaryDirectory() as directory:
            a,b=Path(directory)/'a.xml',Path(directory)/'b.xml'
            a.write_text(before);b.write_text(after)
            return probe_delta(a,b,*identities,{'nets':[{'name':'A','pins':['R1.1']},{'name':'B','pins':['R1.2']}]})

    def record(self, delta):
        return {'probe_kind':delta['probe_kind'],'native_delta':delta,'probe_valid':True,
                'new_errors':{},'caught_by':[]}

    def classify(self, record, gate='intent_netlist'):
        runner.classify({'gates':{gate:{'status':'PASS'}}},{},
                        {'gates':{gate:{'status':'FAIL'}}},{},{'type':'M-PIN-SWAP'},record)

    def test_native_rename_without_partition_change_is_name_only(self):
        delta=self.delta(xml(),xml(('B','A')))
        self.assertEqual('NAME_ONLY',delta['probe_kind'])
        self.assertFalse(delta['partitions_changed'])
        self.assertTrue(delta['net_names_changed'])
        self.assertEqual(['R1.1'],delta['name_targets'][0]['pins'])

    def test_native_no_op_is_not_name_only(self):
        self.assertEqual('NATIVE_NO_OP',self.delta(xml(),xml())['probe_kind'])

    def test_legacy_board_intent_dict_uses_existing_normalization(self):
        with tempfile.TemporaryDirectory() as directory:
            a,b=Path(directory)/'a.xml',Path(directory)/'b.xml';a.write_text(xml());b.write_text(xml(('B','A')))
            result=probe_delta(a,b,{},{},{'nets':{'A':['R1.1'],'B':['R1.2']},'components':[]})
            self.assertEqual('A',result['name_targets'][0]['expected'])

    def test_topology_and_identity_remain_separate(self):
        self.assertEqual('TOPOLOGY',self.delta(xml(),xml(groups=(('R1.1','R1.2'),())))['probe_kind'])
        self.assertEqual('IDENTITY',self.delta(xml(),xml(),({'R1':'1k'},{'R1':'9k'}))['probe_kind'])

    def test_target_name_error_catches_inherited_fail(self):
        delta=self.delta(xml(),xml(('B','A')));record=self.record(delta)
        error={'path':'/errors','entry':{'kind':'net_name_mismatch','expected':'A','actual':['B']}}
        record['new_errors']={'intent_netlist':[error]}
        runner.classify({'gates':{'intent_netlist':{'status':'FAIL'}}},{},
                        {'gates':{'intent_netlist':{'status':'FAIL'}}},{},{'type':'M-PIN-SWAP'},record)
        self.assertEqual('CAUGHT',record['status'])
        self.assertEqual(['intent_netlist'],record['caught_by'])

    def test_unrelated_fail_and_pass_to_fail_do_not_catch_name_only(self):
        for gate,error in (('erc',{'kind':'net_name_mismatch','expected':'A','actual':['B']}),
                           ('intent_netlist',{'kind':'net_name_mismatch','expected':'OTHER','actual':['B']}),
                           ('intent_netlist',{'kind':'pin_partition_mismatch','expected':'A','actual':['B']}),
                           ('intent_netlist',{'kind':'net_name_mismatch','expected':'A','actual':['A']})):
            with self.subTest(gate=gate,error=error):
                record=self.record(self.delta(xml(),xml(('B','A'))))
                record['new_errors']={gate:[{'path':'/errors','entry':error}]}
                self.classify(record,gate)
                self.assertEqual('MISSED',record['status'])

    def test_missing_native_is_not_run(self):
        record={'probe_kind':'NOT_RUN'}
        self.classify(record)
        self.assertEqual('NOT_RUN',record['status'])

    def test_missing_functional_cad_never_calls_verifier(self):
        entry={'id':'b2-r02-v1','functional_native':'NOT_RUN','not_run_reason':'No functional CAD','files':{}}
        def forbidden(*args): raise AssertionError('Missing functional CAD must not be verified as board')
        result=replay_frozen([entry],Path('/tmp/codex-work/unused'),forbidden,forbidden)[entry['id']]
        self.assertEqual('NOT_RUN',result['comparison_status'])
        self.assertIsNone(result['frozen_native_comparison'])

    def test_fingerprint_binds_actual_payload_and_functional_scope(self):
        source={'id':'one','files':{'a':'123'},'functional_native':'AVAILABLE'}
        changed=copy.deepcopy(source);changed['files']['a']='456'
        self.assertNotEqual(fingerprint([source]),fingerprint([changed]))
        changed=copy.deepcopy(source);changed['functional_native']='NOT_RUN'
        self.assertNotEqual(fingerprint([source]),fingerprint([changed]))

    def test_safe_relative_rejects_archive_escape(self):
        for name in ('../secret','/abs','a/../../secret'):
            with self.subTest(name=name),self.assertRaises(ValueError):safe_relative(name)

    def test_cache_revision_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory,'prepared.json').write_text(json.dumps({'benchmark_revision':3}))
            with self.assertRaises(ValueError):require_cache_revision(directory,2)
            require_cache_revision(directory,3)

    def test_missing_functional_runner_resume_retains_single_not_run_row(self):
        with tempfile.TemporaryDirectory() as directory:
            cache=Path(directory)/'cache';cache.mkdir();source=cache/'missing-functional';source.mkdir()
            (cache/'prepared.json').write_text(json.dumps({'benchmark_revision':3,'circuits':[
                {'round':'b2-r02-v1','cache':str(source),'inputs':{},'functional_native':'NOT_RUN','not_run_reason':'No functional CAD'}]}))
            out=Path(directory)/'out'
            argv=[sys.executable,'-B',str(REPO/'evals/mutation_bench/run.py'),'--cache',str(cache),'--out',str(out),
                  '--revision','3','--types','M-PIN-SWAP']
            for resume in ([],['--resume']):
                run=subprocess.run(argv+resume,capture_output=True,text=True)
                self.assertEqual(0,run.returncode,run.stderr)
            rows=json.loads((out/'matrix.json').read_text());base=json.loads((out/'baseline.json').read_text())
            self.assertEqual(1,len(rows));self.assertEqual('NOT_RUN',rows[0]['status']);self.assertEqual(1,len(base))

    def test_cross_revision_and_fingerprint_comparisons_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            before,after=Path(directory)/'before',Path(directory)/'after'
            def write(root,suite,name,data):
                target=root/suite/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(data))
            for root in (before,after):
                common={'asg_commit':'fixed','execution_provenance_verified':True}
                write(root,'overstrict','summary.json',{**common,'benchmark_inputs_hash':'same',
                    'G1':{'reported':0},'G2':{},'report_execution_verified':True,'source_cache_hash_verified':True})
                write(root,'overstrict','matrix.json',[])
                write(root,'mutation','summary.json',{**common,'benchmark_revision':3,'incremental_input_fingerprint':'same'})
                write(root,'mutation','baseline.json',[{'round':'01','inputs':{'input':'hash'}}])
                write(root,'mutation','matrix.json',[{'round':'01','type':'M-VALUE','status':'MISSED','plan':{}}])
                write(root,'delivery','summary.json',{**common,'benchmark_revision':3,'incremental_input_fingerprint':'same',
                    'runs':[{'id':'helper','original_helper_sha256':'hash'}], 'rounds':{
                        '01':{'frozen_native_comparison':{'frozen_sha256':'hash','component_identity_equal':True,'physical_partition_equal':True}},
                        'b2-r02-v1':{'frozen_native_comparison':None,'functional_native':'NOT_RUN','comparison_status':'NOT_RUN','source_fingerprint':'hash'}}})
            for root in (before,after):
                for suite in ('overstrict','mutation','delivery'):
                    binding=root/suite/'run-binding.json'
                    binding.write_text(json.dumps({'schema_version':1,'HEAD':'fixed','suite':suite,'revision':2 if suite=='overstrict' else 3,'input_fingerprint':None if suite=='overstrict' else 'same','source_bytes':{'selfauthored':'fixture'},'cache_bytes':{'selfauthored':'fixture'}}))
                    summary=root/suite/'summary.json';data=json.loads(summary.read_text())
                    data['run_binding']={'verified':True,'initial_receipt_verified':True,'path':str(binding),'sha256':hashlib.sha256(binding.read_bytes()).hexdigest()}
                    summary.write_text(json.dumps(data))
            self.assertEqual('AUTOMATIC_GUARDS_PASS',compare(before,after,'fixed','fixed')['status'])
            path=after/'mutation/summary.json';data=json.loads(path.read_text());data['incremental_input_fingerprint']='changed';path.write_text(json.dumps(data))
            self.assertIn('INCREMENTAL_INPUT_FINGERPRINT_CHANGED_OR_MISSING:mutation',compare(before,after,'fixed','fixed')['errors'])
            data['benchmark_revision']=2;path.write_text(json.dumps(data))
            self.assertIn('BENCHMARK_REVISION_CHANGED:mutation',compare(before,after,'fixed','fixed')['errors'])


if __name__=='__main__':unittest.main()
