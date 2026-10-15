"""Design claims must not outrun the evidence or their dependencies."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_design_closure import audit, sha256


class DesignClosureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.intent = self.root / 'intent.json'
        self.intent.write_text(json.dumps({'components': [{'ref': 'U1'}]}))
        self.source = self.root / 'design.txt'
        self.source.write_text('Requirement and design evidence for a synthetic regulator.\n')
        self.record = {'schema_version': 1, 'coverage': 'complete', 'claim': 'candidate',
            'intent_sha256': sha256(self.intent),
            'evidence': [{'id': 'E1', 'path': 'design.txt', 'sha256': sha256(self.source), 'locator': 'line 1'}],
            'requirements': [{'id': 'R1', 'status': 'design_supported', 'refs': ['U1'], 'evidence': ['E1'],
                              'implementation': 'Regulator output path; rated operating envelope in E1', 'depends_on': ['W1']}],
            'work_items': [{'id': 'W1', 'stage': 'design', 'status': 'closed', 'requirements': ['R1'], 'evidence': ['E1']}],
            'calculations': [{'id': 'C1', 'requirements': ['R1'], 'evidence': ['E1'],
                              'coverage': 'bounded', 'conclusion': 'supported', 'omitted_terms': []}]}

    def run_audit(self):
        return audit(self.record, self.intent, self.root)

    def codes(self):
        return {e['code'] for e in self.run_audit()['errors']}

    def external(self):
        self.record['work_items'][0].update(stage='external', status='open', owner='vendor', severity='P1',
            action='Obtain exact firmware feature evidence', fallback='Compare independent hardware implementation')

    def test_complete_design_record_passes_but_does_not_claim_native_or_sr(self):
        result = self.run_audit()
        self.assertEqual('PASS', result['status'])
        self.assertIn('not physics', result['scope'])

    def test_open_firmware_dependency_prevents_supported_requirement(self):
        self.external()
        self.assertIn('unsupported_requirement_claim', self.codes())

    def test_honest_conditional_design_is_incomplete_not_false_failure(self):
        self.external()
        self.record['requirements'][0]['status'] = 'conditional'
        self.assertEqual('INCOMPLETE', self.run_audit()['status'])
        self.record['claim'] = 'design_closed'
        self.assertIn('false_design_closure', self.codes())

    def test_affected_requirement_must_link_back_to_dependency(self):
        self.record['requirements'][0]['depends_on'] = []
        self.assertIn('unlinked_dependency', self.codes())

    def test_downstream_handoff_does_not_hide_unfinished_design(self):
        self.record['work_items'][0].update(status='handoff', owner='lab', action='Measure corner temperature')
        self.assertIn('unfinished_design_handoff', self.codes())
        self.record['work_items'][0]['stage'] = 'validation'
        self.assertEqual('PASS', self.run_audit()['status'])
        self.assertEqual(['W1'], self.run_audit()['downstream_handoffs'])

    def test_omitted_loss_terms_cannot_prove_budget(self):
        self.record['calculations'][0].update(coverage='partial', omitted_terms=['core loss', 'clamp loss'])
        self.assertIn('partial_calculation_claimed_supported', self.codes())
        self.record['calculations'][0]['conclusion'] = 'conditional'
        self.record['requirements'][0]['status'] = 'conditional'
        self.assertEqual('INCOMPLETE', self.run_audit()['status'])

    def test_conditional_calculation_with_written_assumptions_does_not_block(self):
        self.record['calculations'][0].update(coverage='partial', conclusion='conditional',
                                              omitted_terms=['line regulation has only a typical value'])
        result = self.run_audit()
        self.assertEqual('PASS', result['status'], result)
        self.record['calculations'][0].update(coverage='bounded', omitted_terms=[], assumptions=['typical Vth used'])
        self.assertEqual('PASS', self.run_audit()['status'])

    def test_conditional_calculation_must_state_its_assumptions(self):
        self.record['calculations'][0].update(conclusion='conditional')
        self.assertIn('conditional_without_assumptions', self.codes())

    def test_failed_calculation_blocks_and_cannot_support_requirement(self):
        self.record['calculations'][0]['conclusion'] = 'failed'
        self.assertIn('unsupported_calculation_dependency', self.codes())
        self.record['requirements'][0]['status'] = 'conditional'
        result = self.run_audit()
        self.assertEqual('INCOMPLETE', result['status'])
        self.assertIn({'code': 'calculation_failed', 'item': 'C1'}, result['pending'])

    def test_omissions_cannot_be_marked_bounded(self):
        self.record['calculations'][0]['omitted_terms'] = ['bias loss']
        self.assertIn('contradictory_coverage', self.codes())

    def test_stale_intent_and_source_are_rejected(self):
        self.intent.write_text(json.dumps({'components': [{'ref': 'U1'}, {'ref': 'U2'}]}))
        self.source.write_text('Changed without re-review')
        self.assertTrue({'stale_intent', 'stale_evidence'} <= self.codes())

    def test_missing_source_and_unknown_references_are_rejected(self):
        self.source.unlink()
        self.record['requirements'][0]['refs'] = ['U999']
        self.record['requirements'][0]['depends_on'] = ['W999']
        self.assertTrue({'evidence_missing_or_outside_root', 'unknown_refs', 'unknown_depends_on'} <= self.codes())

    def test_source_path_escape_and_duplicate_ids_rejected(self):
        self.record['evidence'][0]['path'] = '../outside'
        self.record['requirements'].append(copy.deepcopy(self.record['requirements'][0]))
        self.assertTrue({'evidence_missing_or_outside_root', 'duplicate_id'} <= self.codes())

    def test_partial_review_cannot_pass_and_no_calculations_needs_reason(self):
        self.record.update(coverage='partial', calculations=[])
        result = self.run_audit()
        self.assertEqual('INCOMPLETE', result['status'])
        self.assertTrue({'partial_review', 'calculation_scope_missing'} <= {x['code'] for x in result['pending']})

    def test_open_work_needs_a_consequence_level(self):
        self.external()
        del self.record['work_items'][0]['severity']
        result = self.run_audit()
        self.assertEqual('FAIL', result['status'])
        self.assertIn({'code': 'missing_severity', 'item': 'W1'}, result['errors'])

    def test_convergence_keeps_independent_design_executable(self):
        self.record['convergence_version'] = 1
        self.record['work_items'][0].update(status='open', blocked_by=[], owner='engineering', severity='P2',
                                            action='Calculate remaining regulator bounds')
        self.record['requirements'][0]['status'] = 'conditional'
        result = self.run_audit()
        self.assertEqual('INCOMPLETE', result['status'])
        self.assertEqual(['W1'], result['convergence']['ready_design_actions'])
        self.assertEqual('CONTINUE_DESIGN', result['convergence']['status'])

    def test_convergence_rejects_malformed_external_fallback(self):
        self.external()
        self.record['convergence_version'] = 1
        self.record['requirements'][0]['status'] = 'conditional'
        self.record['work_items'][0].update(blocked_by=[], fallback_work=[], fallback_evidence=[{}])
        self.assertIn('convergence_unassessed_fallback', self.codes())

    def pcb_handoff(self):
        self.record['work_items'].append(dict(id='PCB1', stage='pcb', status='handoff',
            scope='footprint_library', electrical_preconditions=['W1'],
            requirements=['R1'], evidence=['E1'], owner='PCB engineer',
            action='Create and verify pads against the selected package drawing'))
        self.record['requirements'][0]['depends_on'].append('PCB1')

    def test_footprint_library_handoff_preserves_schematic_closure(self):
        self.pcb_handoff()
        result = self.run_audit()
        self.assertEqual('PASS', result['status'])
        self.assertEqual(['PCB1'], result['pcb_handoffs'])

    def test_pcb_handoff_cannot_hide_open_electrical_selection(self):
        self.pcb_handoff()
        self.record['work_items'][0].update(status='open', owner='designer', action='Confirm pin map and ratings')
        self.assertIn('pcb_electrical_precondition', self.codes())

    def test_startup_cannot_be_reclassified_as_pcb_implementation(self):
        self.pcb_handoff()
        self.record['work_items'][-1]['scope'] = 'supply_startup'
        self.assertIn('pcb_scope', self.codes())

    def test_pcb_prerequisite_must_be_explicit_electrical_work(self):
        self.pcb_handoff()
        self.record['work_items'][-1]['electrical_preconditions'] = ['UNKNOWN']
        self.assertIn('unknown_electrical_preconditions', self.codes())
        self.record['work_items'][-1]['electrical_preconditions'] = []
        self.assertIn('missing_electrical_preconditions', self.codes())

    def test_cli_malformed_record_fails_with_report(self):
        record = self.root / 'record.json'
        record.write_text('{bad json')
        out = self.root / 'result.json'
        p = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve().parents[1] / 'scripts/audit_design_closure.py'),
            str(record), '--intent', str(self.intent), '--artifact-root', str(self.root), '--out', str(out)], capture_output=True)
        self.assertEqual(1, p.returncode)
        self.assertEqual('FAIL', json.loads(out.read_text())['status'])


if __name__ == '__main__':
    unittest.main()
