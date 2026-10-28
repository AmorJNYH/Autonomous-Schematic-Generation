"""Task 2.2, judged by stress-spec.md (user 2026-10-27): a check that names a derating rule uses the rule's value at the
project's level; a stress over the derated value but within the rating passes with a stress risk and an improvement, one
over the rating fails; only the stresses written are checked, and a stress against a rating that names no rule is a hint;
the level is a requirement and says where it was decided."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_design_closure import audit, sha256


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
            'derating': {'level': 'III', 'source': 'req:R-DER'},
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

    def test_a_check_within_the_derated_limit_passes(self):
        result = self.run_audit()
        self.assertEqual('PASS', result['status'], result['errors'])
        self.assertEqual({'level': 'III', 'source': 'req:R-DER', 'stress_risks': [], 'hints': []}, result['derating'])

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

    def test_over_the_derated_value_within_the_rating_is_a_stress_risk(self):
        self.deviate()
        self.assertIn('stress_risk_without_improvement', self.codes())
        self.check['improvement'] = '换 700 V 管或加钳位'
        result = self.run_audit()
        self.assertEqual('PASS', result['status'], result['errors'])
        self.assertEqual({'conclusion': 'supported', 'rests_on': None, 'reasons': []}, result['calculation_basis']['C-VDS'])
        risk = result['derating']['stress_risks'][0]
        self.assertEqual(('Q1', 'MOS-VDS-S', 600, 585, 650, '换 700 V 管或加钳位'),
                         (risk['ref'], risk['rule'], risk['value'], risk['limit'], risk['rating'], risk['improvement']))

    def test_over_the_rating_fails(self):
        self.deviate(700)
        self.check['improvement'] = '换 800 V 管'
        self.assertEqual('failed', self.run_audit()['calculation_basis']['C-VDS']['conclusion'])
        self.assertEqual([], self.run_audit()['derating']['stress_risks'])

    def test_only_the_stresses_written_are_checked(self):
        # A key part with one stress written is not asked for every rule of its type.
        self.assertEqual([], self.run_audit()['errors'])
        self.record['derating']['parts'] = {}      # an old declaration is ignored, not required
        self.assertEqual([], self.run_audit()['errors'])

    def test_a_stress_against_a_rating_without_a_rule_is_a_hint(self):
        for k in ('derating_rule', 'limit_basis', 'limit_source'):
            del self.check[k]
        self.check.update(limit_basis='guaranteed', limit_source='datasheet:Datasheet/09_MOSFET/X - X650N.pdf#p2', limit=650)
        result = self.run_audit()
        self.assertNotIn('derating_rule_available', {e['code'] for e in result['errors']})
        self.assertEqual(1, len(result['derating']['hints']))
        self.assertTrue(result['derating']['hints'][0].startswith('derating_rule_available C-VDS:漏源电压'))

    def test_a_common_part_is_not_checked_one_by_one(self):
        errors = [e['item'] for e in self.run_audit()['errors']]
        self.assertFalse(any(e.startswith('C1') for e in errors), errors)

    def test_derating_needs_a_layered_record(self):
        self.record['parameter_version'] = 1
        self.assertIn('schema', self.codes())


if __name__ == '__main__':
    unittest.main()
