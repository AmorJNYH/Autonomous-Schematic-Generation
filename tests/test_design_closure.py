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

# Citations here name no real PDF; without a library they are NOT_CHECKED and leave these checks alone
# (test_citations covers the citation check itself). The CLI subprocesses inherit the setting.
_env = None


def setUpModule():
    global _env
    from unittest import mock
    _env = mock.patch.dict('os.environ', {'HARDWARE_WIKI': str(Path(tempfile.gettempdir()) / 'asg-no-library')})
    _env.start()


def tearDownModule():
    _env.stop()


class DesignClosureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.intent = self.root / 'intent.json'
        self.intent.write_text(json.dumps({'components': [{'ref': 'U1'}]}))
        self.source = self.root / 'design.txt'
        self.source.write_text('Requirement and design evidence for a synthetic regulator.\n')
        self.record = {'schema_version': 1, 'coverage': 'complete',
            'intent_sha256': sha256(self.intent),
            'evidence': [{'id': 'E1', 'path': 'design.txt', 'sha256': sha256(self.source), 'locator': 'line 1'}],
            'requirements': [{'id': 'R1', 'status': 'design_supported', 'refs': ['U1'], 'evidence': ['E1'],
                              'implementation': 'Regulator output path; rated operating envelope in E1', 'depends_on': ['W1']}],
            'work_items': [{'id': 'W1', 'stage': 'design', 'status': 'closed', 'requirements': ['R1'], 'evidence': ['E1']}],
            'calculations': [{'id': 'C1', 'requirements': ['R1'], 'evidence': ['E1'], 'refs': ['U1'],
                              'coverage': 'bounded', 'conclusion': 'supported', 'omitted_terms': [],
                              'checks': [{'name': 'output ripple', 'value': 18, 'operator': '<=', 'limit': 30, 'unit': 'mV'}]}]}

    def run_audit(self):
        return audit(self.record, self.intent, self.root)

    def codes(self):
        return {e['code'] for e in self.run_audit()['errors']}

    def external(self):
        self.record['work_items'][0].update(stage='external', status='open', owner='vendor', consequence_class='function', occurrence='normal',
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
        self.record['calculations'][0].update(conclusion='conditional', missing_guarantee='loss model at full load')
        self.record['requirements'][0]['status'] = 'conditional'
        self.assertEqual('INCOMPLETE', self.run_audit()['status'])

    def test_conditional_calculation_with_written_assumptions_does_not_block(self):
        self.record['calculations'][0].update(coverage='partial', conclusion='conditional',
                                              omitted_terms=['line regulation has only a typical value'],
                                              missing_guarantee='line regulation over temperature')
        result = self.run_audit()
        self.assertEqual('PASS', result['status'], result)
        self.record['calculations'][0].update(coverage='bounded', omitted_terms=[], assumptions=['typical Vth used'])
        self.assertEqual('PASS', self.run_audit()['status'])

    def test_conditional_names_the_missing_guarantee_and_partial_names_omissions(self):
        self.record['calculations'][0].update(coverage='partial', conclusion='conditional', assumptions=['typ Vf'])
        codes = self.codes()
        self.assertIn('conditional_without_missing_guarantee', codes)
        self.assertIn('partial_without_omitted_terms', codes)
        self.record['calculations'][0].update(omitted_terms=['ESR drift'], missing_guarantee='Vf at -10 °C')
        self.assertEqual('PASS', self.run_audit()['status'], self.run_audit())

    def test_conditional_calculation_must_state_its_assumptions(self):
        self.record['calculations'][0].update(conclusion='conditional')
        self.assertIn('conditional_without_assumptions', self.codes())

    def test_failed_calculation_blocks_and_cannot_support_requirement(self):
        self.record['calculations'][0]['conclusion'] = 'failed'
        self.record['calculations'][0]['checks'][0]['value'] = 45
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
        del self.record['work_items'][0]['occurrence']
        result = self.run_audit()
        self.assertEqual('FAIL', result['status'])
        self.assertIn({'code': 'missing_consequence', 'item': 'W1'}, result['errors'])

    def test_level_follows_from_consequence_and_occurrence(self):
        self.external()
        item = self.record['work_items'][0]
        for consequence, occurrence, level in (('safety', 'fault', 'P0'), ('damage', 'condition', 'P0'),
                                               ('damage', 'fault', 'P1'), ('function', 'normal', 'P1'),
                                               ('function', 'fault', 'P2'), ('margin', 'condition', 'P2'),
                                               ('margin', 'fault', 'P3'), ('optimization', 'normal', 'P3')):
            item.update(consequence_class=consequence, occurrence=occurrence)
            self.assertEqual({'W1': level}, self.run_audit()['severities'], (consequence, occurrence))
        item.update(consequence_class='margin', occurrence='normal', severity='P0')   # a hand-written level that disagrees
        self.assertIn({'code': 'severity_contradicts_rule', 'item': 'W1: P0, rule gives P2'}, self.run_audit()['errors'])
        item['severity'] = 'P2'
        self.assertNotIn('severity_contradicts_rule', {e['code'] for e in self.run_audit()['errors']})

    def test_requirement_gap_must_state_current_assumption(self):
        self.record['requirements'][0]['status'] = 'conditional'
        self.record['work_items'][0].update(stage='requirement', status='open', owner='用户', consequence_class='margin', occurrence='normal',
                                            action='确定待机功耗上限')
        result = self.run_audit()
        self.assertEqual('FAIL', result['status'])
        self.assertIn({'code': 'missing_assumption', 'item': 'W1'}, result['errors'])
        self.record['work_items'][0]['assumption'] = '按待机 ≤0.1W 设计'
        result = self.run_audit()
        self.assertEqual('INCOMPLETE', result['status'])
        self.assertIn({'code': 'open_requirement', 'item': 'W1'}, result['pending'])

    def test_requirement_gap_cannot_be_handed_off(self):
        self.record['work_items'][0].update(stage='requirement', status='handoff', owner='用户',
                                            action='确定待机功耗上限', assumption='按待机 ≤0.1W 设计')
        self.assertIn('unfinished_design_handoff', self.codes())

    def test_convergence_keeps_independent_design_executable(self):
        self.record['convergence_version'] = 1
        self.record['work_items'][0].update(status='open', blocked_by=[], owner='engineering', consequence_class='margin', occurrence='normal',
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

    def test_cli_resolves_evidence_in_declared_inputs(self):
        library = Path(self.tmp.name + '-library')
        library.mkdir()
        self.addCleanup(lambda: [f.unlink() for f in library.iterdir()] and library.rmdir())
        self.source.rename(library / 'design.txt')
        record, out = self.root / 'record.json', self.root / 'result.json'
        record.write_text(json.dumps(self.record))
        cli = [sys.executable, '-B', str(Path(__file__).resolve().parents[1] / 'scripts/audit_design_closure.py'),
               str(record), '--intent', str(self.intent), '--artifact-root', str(self.root), '--out', str(out)]
        subprocess.run(cli, capture_output=True)
        self.assertEqual('FAIL', json.loads(out.read_text())['status'])
        subprocess.run(cli + ['--input', 'datasheets=%s' % library], capture_output=True)
        self.assertEqual('PASS', json.loads(out.read_text())['status'])


if __name__ == '__main__':
    unittest.main()


class CalculationChecksTests(unittest.TestCase):
    """Conclusions follow from computed margins; thresholds need both sides."""
    setUp = DesignClosureTests.setUp
    run_audit = DesignClosureTests.run_audit
    codes = DesignClosureTests.codes

    def zener_board(self):
        self.intent.write_text(json.dumps({'components': [{'ref': 'U1'}, {'ref': 'D1', 'lib_id': 'Device:D_Zener'}]}))
        self.record['intent_sha256'] = sha256(self.intent)

    def test_calculation_needs_checks_and_refs(self):
        del self.record['calculations'][0]['checks']
        self.record['calculations'][0]['refs'] = []
        self.assertTrue({'missing_checks', 'missing_refs'} <= self.codes())

    def test_failed_check_cannot_be_called_conditional(self):
        self.record['calculations'][0].update(coverage='partial', conclusion='conditional', assumptions=['typ Vf'])
        self.record['calculations'][0]['checks'][0]['value'] = 45
        self.assertIn('conclusion_contradicts_checks', self.codes())

    def test_passing_checks_cannot_be_called_failed(self):
        self.record['calculations'][0]['conclusion'] = 'failed'
        self.assertIn('conclusion_contradicts_checks', self.codes())

    def test_malformed_check_is_schema_error(self):
        self.record['calculations'][0]['checks'][0]['operator'] = 'about'
        self.assertIn('schema', self.codes())

    def test_threshold_part_without_calculation_is_rejected(self):
        self.zener_board()
        self.assertIn('threshold_part_uncalculated', self.codes())
        self.record['calculations'][0]['refs'].append('D1')
        self.assertNotIn('threshold_part_uncalculated', self.codes())

    def test_threshold_part_found_by_series_prefix_or_declared_role(self):
        for part in ({'lib_id': 'Device:D', 'value': 'BZX84C5V1'}, {'lib_id': 'Device:D', 'value': 'D', 'mpn': 'SMBJ15A'},
                     {'lib_id': 'Reference_Voltage:XYZ', 'value': 'XYZ', 'fields': {'ComponentRole': 'threshold'}}):
            with self.subTest(part=part):
                self.intent.write_text(json.dumps({'components': [{'ref': 'U1'}, {'ref': 'D1', **part}]}))
                self.record['intent_sha256'] = sha256(self.intent)
                self.assertIn('threshold_part_uncalculated', self.codes())
        self.intent.write_text(json.dumps({'components': [{'ref': 'U1'}, {'ref': 'D1', 'lib_id': 'Device:D', 'value': '1N4148'}]}))
        self.record['intent_sha256'] = sha256(self.intent)
        self.assertNotIn('threshold_part_uncalculated', self.codes())

    def test_threshold_window_needs_both_sides(self):
        self.zener_board()
        calc = self.record['calculations'][0]
        calc.update(kind='threshold', refs=['U1', 'D1'], checks=[
            {'name': 'aux at 21 V output incl. leakage peak vs Vz min + Vfault min', 'side': 'no_false_trip',
             'value': 66.0, 'operator': '<', 'limit': 69.4, 'unit': 'V'}])
        self.assertIn('threshold_window_incomplete', self.codes())
        calc['checks'].append({'name': 'output at max trip vs output capacitor rating', 'side': 'protection',
                               'value': 25.0, 'operator': '<=', 'limit': 35.0, 'unit': 'V'})
        self.assertEqual('PASS', self.run_audit()['status'], self.run_audit())

    def test_threshold_false_trip_margin_failure_must_be_failed(self):
        self.zener_board()
        calc = self.record['calculations'][0]
        calc.update(kind='threshold', refs=['D1'], coverage='partial', conclusion='conditional',
                    assumptions=['leakage peak 10 %'], checks=[
            {'name': 'no false trip', 'side': 'no_false_trip', 'value': 71.0, 'operator': '<', 'limit': 69.4, 'unit': 'V'},
            {'name': 'protects', 'side': 'protection', 'value': 25.0, 'operator': '<=', 'limit': 35.0, 'unit': 'V'}])
        self.assertIn('conclusion_contradicts_checks', self.codes())


class ParameterSourceTests(unittest.TestCase):
    """Every number a calculation uses names where it came from; an unspecified pin mode needs its alternatives ruled out."""
    setUp = DesignClosureTests.setUp
    run_audit = DesignClosureTests.run_audit
    codes = DesignClosureTests.codes
    SHEET = 'datasheet:Datasheet/PD/Richtek - RT7209.pdf#p12'

    def opto_board(self):
        # The R5 case: a PD controller GPIO sinks an optocoupler LED; the datasheet gives no sink current or VOL.
        self.intent.write_text(json.dumps({'components': [{'ref': 'U1'}, {'ref': 'U601'}, {'ref': 'R407'}]}))
        self.record.update(parameter_version=1, intent_sha256=sha256(self.intent))
        self.record['work_items'].append({'id': 'W-OPTO', 'stage': 'external', 'status': 'open', 'requirements': ['R1'],
                                          'evidence': [], 'consequence_class': 'function', 'occurrence': 'normal', 'owner': '原厂', 'action': '取得 GPIO 灌电流保证',
                                          'fallback': '见 OP-GPIO1'})
        self.record['requirements'][0].update(status='conditional', depends_on=['W1', 'W-OPTO'])
        self.record['calculations'][0].update(refs=['U601', 'R407'], coverage='partial', conclusion='conditional',
                                              omitted_terms=['寿命 CTR'], missing_guarantee='GPIO1 灌电流时的 VOL', parameters=[
            {'name': 'R407', 'ref': 'R407', 'value': 470, 'unit': 'ohm', 'basis': 'design_choice'},
            {'name': 'CTR 寿命保持', 'value': 0.5, 'unit': '1', 'basis': 'model', 'reason': '设计折减'},
            {'name': 'VOL', 'ref': 'U601', 'value': 0.4, 'unit': 'V', 'basis': 'unspecified',
             'source': self.SHEET, 'locator': 'GPIO1 一节只有开路电压与偏置电流档', 'operating_point': 'OP-GPIO1'}])
        self.record['operating_points'] = [{
            'id': 'OP-GPIO1', 'refs': ['U601'], 'pins': ['GPIO1'], 'mode': '开漏灌电流驱动光耦 LED', 'specified': False,
            'source': self.SHEET, 'locator': 'GPIO1 特性表无灌电流/VOL', 'work_item': 'W-OPTO',
            'alternatives': [{'approach': '小信号 MOS 缓冲', 'specified': True, 'feasible': False, 'reason': '占位'}]}]
        return self.record['calculations'][0], self.record['operating_points'][0]

    def test_parameters_are_checked_only_with_parameter_version(self):
        self.assertEqual('NOT_CHECKED', self.run_audit()['parameters'])
        self.record['parameter_version'] = 1
        self.assertIn('missing_parameters', self.codes())

    def test_device_parameter_needs_a_datasheet_page(self):
        calc, _ = self.opto_board()
        calc['parameters'][2].update(basis='guaranteed', source='RT7209 datasheet')   # the invented VOL<=0.4 V
        self.assertIn('parameter_without_datasheet_location', self.codes())
        calc['parameters'][2].update(source=self.SHEET, locator='')
        self.assertIn('parameter_without_datasheet_location', self.codes())

    def test_model_and_derived_parameters_say_why(self):
        calc, _ = self.opto_board()
        del calc['parameters'][1]['reason']
        calc['parameters'].append({'name': 'IF', 'value': 1e-3, 'unit': 'A', 'basis': 'derived', 'source': 'calc:C9'})
        self.assertTrue({'model_parameter_without_reason', 'derived_parameter_without_basis'} <= self.codes())

    def test_unspecified_parameter_ties_to_an_unspecified_operating_point(self):
        calc, point = self.opto_board()
        self.assertEqual(['OP-GPIO1'], self.run_audit()['unspecified_operations'])
        self.assertNotIn('unspecified_parameter_without_operating_point', self.codes())
        point['specified'] = True
        self.assertIn('unspecified_parameter_without_operating_point', self.codes())

    def test_unguaranteed_parameter_cannot_support_a_conclusion(self):
        calc, _ = self.opto_board()
        calc.update(coverage='bounded', conclusion='supported', omitted_terms=[])
        self.assertIn('supported_with_unguaranteed_parameter', self.codes())

    def test_feasible_specified_alternative_refuses_the_unspecified_mode(self):
        _, point = self.opto_board()
        self.assertNotIn('unspecified_operation_with_specified_alternative', self.codes())
        self.assertEqual('INCOMPLETE', self.run_audit()['status'])
        point['alternatives'][0]['feasible'] = True
        result = self.run_audit()
        self.assertEqual('FAIL', result['status'])
        self.assertIn('unspecified_operation_with_specified_alternative', {e['code'] for e in result['errors']})

    def test_kept_unspecified_mode_needs_alternatives_and_a_vendor_item(self):
        _, point = self.opto_board()
        point.update(alternatives=[], work_item='W1')
        self.assertTrue({'unspecified_operation_without_alternatives', 'unspecified_operation_without_vendor_item'}
                        <= self.codes())

    def test_operating_point_cites_where_the_datasheet_was_read(self):
        _, point = self.opto_board()
        point['source'] = 'RT7209 p12'
        self.assertIn('operating_point_source', self.codes())


class DataGapTests(unittest.TestCase):
    """An open external item says what the datasheet gives, what is missing, what to ask and a fallback of its own."""
    setUp = DesignClosureTests.setUp
    run_audit = DesignClosureTests.run_audit
    codes = DesignClosureTests.codes
    external = DesignClosureTests.external
    SHEET = 'datasheet:Datasheet/PD/Richtek - RT7209.pdf#p18'

    def gap_board(self):
        # The R6 case: USBP is specified only unloaded, so the blocking MOS turn-off path is unknown.
        self.record['gap_version'] = 1
        self.record['requirements'][0].update(status='conditional')
        self.record['calculations'][0].update(coverage='partial', conclusion='conditional', omitted_terms=['开关轨迹'],
                                              missing_guarantee='USBP 带载驱动能力与关断时延')
        item = self.record['work_items'][0]
        item.update(stage='external', status='open', consequence_class='function', occurrence='normal', owner='Richtek 应用支持',
                    action='按关断时延积分 Q701 的 VDS-ID-t 并核 SOA',
                    missing=[{'source': self.SHEET, 'given': 'VOH_USBP 只在 RL=10MΩ 下规定', 'needed': '带 120nC 栅荷时的开通与关断时间'}],
                    why_external='电荷泵驱动和故障时序在芯片内部与固件里', calculations=['C1'],
                    consequence='Q701 超出 SOA 后 D-S 短路，端口无法断开', questions=['从检测到故障到 USBP 下拉的最大时延'],
                    fallback='栅极加由短路检测触发的快放电')
        return item

    def test_gaps_are_checked_only_with_gap_version(self):
        self.external()
        self.assertEqual('NOT_CHECKED', self.run_audit()['gaps'])
        self.record['gap_version'] = 1
        self.assertIn('gap_missing_fields', self.codes())

    def test_complete_gap_record_has_no_gap_errors(self):
        self.gap_board()
        result = self.run_audit()
        self.assertEqual('CHECKED', result['gaps'])
        self.assertEqual([], [e for e in result['errors'] if e['code'].startswith('gap_')])

    def test_each_gap_field_is_required(self):
        item = self.gap_board()
        for field in ('missing', 'why_external', 'calculations', 'consequence', 'questions'):
            saved = item.pop(field)
            self.assertIn({'code': 'gap_missing_fields', 'item': 'W1:' + field}, self.run_audit()['errors'])
            item[field] = saved

    def test_gap_without_dependent_calculation_says_why(self):
        item = self.gap_board()
        item['calculations'] = []
        self.assertIn('gap_missing_fields', self.codes())
        item['no_calculation_reason'] = '只确认固件上电默认行为，没有数值计算依赖它'
        self.assertNotIn('gap_missing_fields', self.codes())

    def test_gap_cites_where_it_was_found(self):
        item = self.gap_board()
        item['missing'][0]['source'] = 'RT7209 手册 p18'
        self.assertIn('gap_bad_source', self.codes())

    def test_gap_links_to_existing_conditional_calculations(self):
        item = self.gap_board()
        item['calculations'] = ['C9']
        self.assertIn('gap_unlinked_calculation', self.codes())
        item['calculations'] = ['C1']
        self.record['calculations'][0].update(coverage='bounded', conclusion='supported', omitted_terms=[])
        self.assertIn('gap_unlinked_calculation', self.codes())

    def test_owner_is_required_but_its_wording_is_not_judged(self):
        item = self.gap_board()
        item['owner'] = '电路设计与原厂应用支持'
        self.assertNotIn('gap_vague_owner', self.codes())
        item['owner'] = ''
        self.assertIn('missing_owner', self.codes())

    def test_shared_boilerplate_fallback_is_rejected(self):
        item = self.gap_board()
        twin = copy.deepcopy(item)
        twin['id'] = 'W2'
        self.record['work_items'].append(twin)
        self.assertIn({'code': 'gap_generic_fallback', 'item': 'W1、W2'}, self.run_audit()['errors'])
        twin['fallback'] = '换带短路保护的负载开关'
        self.assertNotIn('gap_generic_fallback', self.codes())

