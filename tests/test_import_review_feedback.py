import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from import_review_feedback import import_feedback, main


def row(cid, result, **kw):
    return dict(id=cid, review_result=result, **kw)


def records():
    results = {'checks': [
        row('PWR-E01.U1', 'FAIL', finding_id='F1'),
        row('DEV-C01.R5', 'INSUFFICIENT', gap_cause='DESIGN_OPEN'),
        row('DEV-C05.U7', 'INSUFFICIENT', gap_cause='EXTERNAL_DATA', input_requests={'Vz at 0.2 mA': {}}),
        row('REQ-D01.VIN', 'INSUFFICIENT', gap_cause='REQUIREMENT_OPEN'),
        row('PRO-C01.OVP', 'INSUFFICIENT', gap_cause='REVIEW_INCOMPLETE'),
        row('REQ-D01.EMC', 'NA', na_reason='OUTSIDE_SCHEMATIC_STAGE', handoff={'required': True}),
        row('DEV-C01.R6', 'NA', na_reason='Not fitted'),
        row('DEV-C01.R7', 'PASS'),
        row('REQ-H02.OLD1', 'FAIL'),
    ]}
    option = {'status': 'PROPOSED', 'summary': 'Supply from output via Schottky', 'preference': 'DESIGN_FIRST'}
    gate = {'valid': True, 'release': 'NO_GO',
            'categorized_summary': {'unique_findings': 1, 'unique_work_items': 3},
            'workflow': {'work_items': [{'id': 'W1', 'check_ids': ['DEV-C05.U7'], 'design_option': option},
                                        {'id': 'W2', 'check_ids': ['PWR-E01.U1', 'DEV-C01.R5']}]}}
    return results, gate


class ImportReviewFeedbackTests(unittest.TestCase):
    def test_each_sr_record_has_one_fixed_route(self):
        out = import_feedback(*records())
        self.assertEqual(out['status'], 'PASS', out['errors'])
        got = {a['check_id']: (a['action'], a['closure_stage'], a['open_item_kind']) for a in out['actions']}
        self.assertEqual(got, {
            'PWR-E01.U1': ('REDESIGN', 'design', 'DESIGN'),
            'DEV-C01.R5': ('DESIGN', 'design', 'DESIGN'),
            'DEV-C05.U7': ('OBTAIN_EVIDENCE', 'external', 'EVIDENCE'),
            'REQ-D01.VIN': ('ASK_REQUIREMENT_OWNER', None, 'REQUIREMENT'),
            'PRO-C01.OVP': ('WAIT_FOR_SR', None, 'REVIEW'),
            'REQ-D01.EMC': ('HANDOFF', 'validation', 'DOWNSTREAM')})

    def test_requests_options_and_metrics_are_carried_not_rejudged(self):
        out = import_feedback(*records())
        ext = next(a for a in out['actions'] if a['check_id'] == 'DEV-C05.U7')
        self.assertIn('Vz at 0.2 mA', ext['input_requests'])
        self.assertEqual(ext['sr_design_options'][0]['preference'], 'DESIGN_FIRST')
        self.assertEqual(ext['sr_work_items'], ['W1'])
        self.assertEqual(out['metrics'], {'unique_findings': 1, 'unique_work_items': 3,
                                          'design_actions': 2, 'evidence_actions': 1})

    def test_invalid_gate_or_unclassified_gap_is_returned_to_sr(self):
        results, gate = records(); gate['valid'] = False
        self.assertEqual(import_feedback(results, gate)['status'], 'FAIL')
        for cause in (None, 'DOWNSTREAM_VERIFICATION'):
            results, gate = records()
            results['checks'][1]['gap_cause'] = cause
            out = import_feedback(results, gate)
            self.assertEqual(out['status'], 'FAIL')
            self.assertTrue(any('DEV-C01.R5' in e for e in out['errors']))

    def test_cli_writes_hash_bound_output(self):
        results, gate = records()
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / 'r.json').write_text(json.dumps(results)); (d / 'g.json').write_text(json.dumps(gate))
            self.assertEqual(main([str(d / 'r.json'), str(d / 'g.json'), '--out', str(d / 'o.json')]), 0)
            out = json.loads((d / 'o.json').read_text())
            self.assertEqual(len(out['sources']['results_sha256']), 64)


if __name__ == '__main__':
    unittest.main()
