"""Task 2.2 (outline approved by user 2026-10-27): key and special parts are checked against the derating column of the
project's level; a stress over the derated value but within the rating is conditional with a derating item or the
user's acceptance, one over the rating fails; the level is a requirement and says where it was decided."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_design_closure import audit, load_derating, sha256

RULES, _ = load_derating()
MOS_RULES = sorted(rid for rid, r in RULES.items() if r['type'] == '硅 MOSFET')


def setUpModule():
    global _env
    _env = mock.patch.dict('os.environ', {'HARDWARE_WIKI': str(Path(tempfile.gettempdir()) / 'asg-no-library')})
    _env.start()


def tearDownModule():
    _env.stop()


class DeratingAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.intent = self.root / 'intent.json'
        self.intent.write_text(json.dumps({'components': [
            {'ref': 'Q1', 'lib_id': 'Transistor_FET:Q_NMOS_GDS', 'value': 'NMOS', 'mpn': 'X650N'},
            {'ref': 'C1', 'lib_id': 'Device:C', 'value': '100n'}]}))
        (self.root / 'design.txt').write_text('evidence\n')
        self.record = {
            'schema_version': 1, 'coverage': 'complete', 'intent_sha256': sha256(self.intent),
            'parameter_version': 3, 'derating_version': 1,
            'derating': {'level': 'III', 'source': 'req:R-DER',
                         'parts': {'Q1': {'types': ['硅 MOSFET'],
                                          'not_applicable': {r: '本例只核漏源电压' for r in MOS_RULES if r != 'MOS-VDS-S'}}}},
            'evidence': [{'id': 'E1', 'path': 'design.txt', 'sha256': sha256(self.root / 'design.txt'), 'locator': 'l1'}],
            'requirements': [
                {'id': 'R1', 'status': 'design_supported', 'refs': ['Q1'], 'evidence': ['E1'], 'implementation': '反激主开关',
                 'depends_on': []},
                {'id': 'R-DER', 'status': 'design_supported', 'refs': [], 'evidence': ['E1'], 'implementation': '降额 III 级',
                 'depends_on': [], 'no_check_reason': '降额等级本身不对应电路'}],
            'work_items': [],
            'calculations': [{
                'id': 'C-VDS', 'requirements': ['R1'], 'evidence': ['E1'], 'refs': ['Q1'], 'coverage': 'bounded',
                'conclusion': 'supported', 'rests_on': None, 'omitted_terms': [],
                'parameters': [{'name': 'Vin', 'value': 373, 'unit': 'V', 'basis': 'requirement', 'source': 'req:R1'}],
                'checks': [{'name': '漏源电压', 'value': 560, 'operator': '<=', 'limit': 585, 'unit': 'V',
                            'derating_rule': 'MOS-VDS-S', 'ref': 'Q1', 'rating': 650,
                            'rating_source': 'datasheet:Datasheet/09_MOSFET/X - X650N.pdf#p2',
                            'limit_basis': 'standard', 'limit_source': 'standard:derating-rules#MOS-VDS-S'}]}]}

    def run_audit(self):
        return audit(self.record, self.intent, self.root)

    def codes(self):
        return {e['code'] for e in self.run_audit()['errors']}

    @property
    def check(self):
        return self.record['calculations'][0]['checks'][0]

    def deviate(self, value=600):
        self.check['value'] = value

    def item(self, **fields):
        row = {'id': 'W-DER', 'stage': 'design', 'requirements': ['R1'], 'evidence': [], 'derating': ['C-VDS'],
               'owner': 'ASG', 'action': '换 700 V 管或加钳位', 'consequence_class': 'margin', 'occurrence': 'normal'}
        row.update(fields)
        self.record['work_items'].append(row)
        self.record['requirements'][0]['depends_on'] = ['W-DER']
        return row

    def test_a_check_within_the_derated_limit_passes(self):
        result = self.run_audit()
        self.assertEqual('PASS', result['status'], result['errors'])
        self.assertEqual({'level': 'III', 'source': 'req:R-DER', 'deviations': []}, result['derating'])

    def test_the_level_is_a_requirement_or_a_deferred_clarification(self):
        self.record['derating']['level'] = 'IV'
        self.assertIn('derating_level_missing', self.codes())
        self.record['derating'].update(level='III', source='user:2026-10-27')
        self.assertIn('derating_level_without_source', self.codes())
        self.record['derating']['source'] = 'clarification:CL-DER'
        self.assertIn('derating_level_without_source', self.codes())   # no such clarification, so not deferred

    def test_the_limit_is_the_rules_value_at_the_level(self):
        self.check['limit'] = 600
        self.assertIn('derating_limit_mismatch', self.codes())
        self.record['derating']['level'] = 'II'           # II: 80% of 650 V
        self.check['limit'] = 520
        self.check['value'] = 500
        self.assertNotIn('derating_limit_mismatch', self.codes())
        del self.check['rating']
        self.assertIn('derating_rating_missing', self.codes())

    def test_the_rule_exists_fits_the_part_and_is_cited_as_the_spec(self):
        self.check['derating_rule'] = 'MOS-VDS-X'
        self.assertIn('derating_rule_unknown', self.codes())
        self.check['derating_rule'] = 'CAP-MLCC-CHIP-V'
        self.check['limit_source'] = 'standard:derating-rules#CAP-MLCC-CHIP-V'
        self.assertIn('derating_rule_kind', self.codes())
        self.check.update(derating_rule='MOS-VDS-S', limit_source='standard:T/CPSS 1013 表4')
        self.assertIn('derating_limit_source', self.codes())
        self.check['limit_source'] = 'standard:derating-rules#MOS-VDS-S'
        self.check['rating_source'] = '规格书'
        self.assertIn('derating_rating_without_source', self.codes())

    def test_over_the_derated_value_within_the_rating_needs_an_item(self):
        self.deviate()
        self.assertIn('derating_without_item', self.codes())
        self.assertEqual('supported', self.run_audit()['calculation_basis']['C-VDS']['conclusion'])

    def test_an_open_derating_item_leaves_the_calculation_conditional(self):
        self.deviate()
        self.item(status='open')
        self.assertIn('conclusion_not_derived', self.codes())
        self.record['calculations'][0].update(conclusion='conditional', rests_on='derating')
        self.record['requirements'][0]['status'] = 'conditional'
        result = self.run_audit()
        self.assertEqual([], result['errors'])
        self.assertEqual('INCOMPLETE', result['status'])
        self.assertEqual(['降额 漏源电压', '待办 W-DER'], result['calculation_basis']['C-VDS']['reasons'])
        self.assertEqual(['W-DER'], result['derating']['deviations'][0]['items'])

    def test_the_users_acceptance_closes_the_deviation(self):
        self.deviate()
        row = self.item(status='closed', evidence=['E1'])
        self.assertIn('derating_without_item', self.codes())        # closed without acceptance
        row['accepted'] = 'user:2026-10-27'
        result = self.run_audit()
        self.assertEqual('PASS', result['status'], result['errors'])
        self.assertEqual(['W-DER'], result['derating']['deviations'][0]['accepted'])

    def test_over_the_rating_fails(self):
        self.deviate(700)
        self.item(status='open')
        self.assertEqual('failed', self.run_audit()['calculation_basis']['C-VDS']['conclusion'])

    def test_key_parts_declare_their_types_and_cover_every_rule(self):
        parts = self.record['derating']['parts']
        del parts['Q1']['not_applicable']['MOS-TJ']
        self.assertIn('derating_not_covered', self.codes())
        parts['Q1']['types'] = ['MOSFET']
        self.assertIn('derating_type_unknown', self.codes())
        del parts['Q1']
        self.assertIn('derating_part_undeclared', self.codes())

    def test_a_common_part_is_not_checked_one_by_one(self):
        errors = [e['item'] for e in self.run_audit()['errors']]
        self.assertFalse(any(e.startswith('C1') for e in errors), errors)

    def test_derating_needs_a_layered_record(self):
        self.record['parameter_version'] = 1
        self.assertIn('schema', self.codes())


if __name__ == '__main__':
    unittest.main()
