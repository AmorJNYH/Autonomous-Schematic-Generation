"""One generated report plus a small fixed folder; numbers come only from the records."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from audit_design_closure import audit, sha256
from render_design_report import render, REPORT
from pack_design import pack

JARGON = ('合同', '冻结', '门禁', '原生', '闭环', '移交', 'SR', 'schematic-review', 'design_supported', 'handoff')


class Delivery:
    """Synthetic delivery folder in the fixed layout."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'v1'
        self.record = self.root / 'record'
        for d in ('原理图', '设计资料', 'record/evidence'):
            (self.root / d).mkdir(parents=True)
        for name in ('board.kicad_pro', 'board.kicad_sch', 'schematic.pdf', 'netlist.xml', 'BOM.csv'):
            (self.root / '原理图' / name).write_text('x')
        (self.root / '设计资料' / '方案与选型依据.md').write_text('# basis')
        (self.record / 'evidence' / 'design.md').write_text('regulator design basis')
        self.write('electrical-intent.json', {'components': [{'ref': 'U1'}, {'ref': 'R1'}]})
        self.closure = {
            'schema_version': 1, 'coverage': 'complete', 'claim': 'candidate',
            'intent_sha256': sha256(self.record / 'electrical-intent.json'),
            'evidence': [{'id': 'E1', 'path': 'record/evidence/design.md',
                          'sha256': sha256(self.record / 'evidence' / 'design.md'), 'locator': 'section 1'}],
            'requirements': [{'id': 'R-OUT', 'status': 'conditional', 'refs': ['U1'], 'evidence': ['E1'],
                              'implementation': 'U1 output path', 'depends_on': ['W-FW', 'W-CALC', 'W-TEST']}],
            'work_items': [
                {'id': 'W-CALC', 'stage': 'design', 'status': 'open', 'severity': 'P2', 'requirements': ['R-OUT'],
                 'evidence': [], 'owner': '设计', 'action': '补算输出电容纹波电流'},
                {'id': 'W-FW', 'stage': 'external', 'status': 'open', 'severity': 'P0', 'requirements': ['R-OUT'],
                 'evidence': [], 'owner': '固件供应方', 'action': '取得过压保护配置表', 'fallback': '评估独立硬件过压关断'},
                {'id': 'W-TEST', 'stage': 'validation', 'status': 'handoff', 'requirements': ['R-OUT'],
                 'evidence': ['E1'], 'owner': '样机验证', 'action': '满载温升测试'}],
            'calculations': [{'id': 'C1', 'requirements': ['R-OUT'], 'evidence': ['E1'], 'refs': ['U1'],
                              'coverage': 'partial', 'conclusion': 'conditional', 'omitted_terms': ['ripple'],
                              'checks': [{'name': '输出纹波', 'value': 18, 'operator': '<=', 'limit': 30, 'unit': 'mV'}]}]}
        self.write('design-closure.json', self.closure)
        self.write('design-closure-audit.json', audit(self.closure, self.record / 'electrical-intent.json', self.root))
        self.write('summary.json', {'status': 'INCOMPLETE', 'sheets': ['a', 'b'], 'gates': {
            'erc': {'status': 'PASS', 'violations': 0}, 'intent_netlist': {'status': 'PASS', 'errors': 0},
            'geometry': {'status': 'INSUFFICIENT'}, 'design_closure': {'status': 'INCOMPLETE'}}})
        self.write('visual-review.json', {'status': 'REVIEWED', 'pages': [
            {'page': 1, 'file': 'board.kicad_sch', 'paths': ['VIN to VOUT'], 'problems': []}]})
        self.write('page-plan.json', {'schema_version': 1, 'pages': [
            {'file': 'board.kicad_sch', 'reader_tasks': ['跟随 VIN 到 VOUT 的能量流'], 'blocks': {'稳压': ['U1', 'R1']}}]})
        self.write('delivery-evidence.json', {'schema_version': 1})

    def write(self, name, value):
        (self.record / name).write_text(json.dumps(value, ensure_ascii=False))

    def report(self, notes=None):
        return render(self.root, notes)


class DesignReportTests(unittest.TestCase):
    def setUp(self):
        self.d = Delivery()
        self.addCleanup(self.d.tmp.cleanup)

    def test_conclusion_counts_and_what_is_missing(self):
        text, problems = self.d.report()
        self.assertEqual(problems, [])
        lines = [l for l in text.splitlines() if l.strip()]
        self.assertEqual(lines[1], '## 结论')
        self.assertEqual(lines[2], '- **规模**：器件 2 个，图纸 2 页。')
        self.assertEqual(lines[3], '- **自动检查**：共 3 项。通过（PASS） 2 项，没通过（FAIL） 0 项，资料不足（INSUFFICIENT） 1 项。')
        self.assertIn('- **需求**：共 1 条。有设计依据 0 条，有条件成立 1 条，还没有设计 0 条。', text)
        self.assertIn('- **设计是否完成**：还没完成。还差：', text)
        self.assertIn('1 项自动检查资料不足或没做：图面几何（重叠、穿线）', text)
        self.assertIn('2 件待办没做完（设计没做完 1 件，缺外部资料 1 件）', text)

    def test_one_todo_list_ordered_by_consequence(self):
        text, _ = self.d.report({'items': {'W-FW': '固件过压保护配置还没拿到。'}})
        section = text.split('## 待办')[1].split('\n## ')[0]
        self.assertLess(section.index('W-FW（P0：可能损坏器件或危及安全）'), section.index('W-CALC（P2'))
        self.assertIn('- **拿不到时的替代做法**：评估独立硬件过压关断', section)
        self.assertIn('固件过压保护配置还没拿到。', section)
        self.assertNotIn('W-TEST', section)

    def ask_user(self):
        c = self.d.closure
        c['work_items'].append({'id': 'W-STBY', 'stage': 'requirement', 'status': 'open', 'severity': 'P3',
                                'requirements': ['R-OUT'], 'evidence': [], 'owner': '产品负责人',
                                'action': '确定待机功耗上限', 'assumption': '按待机 ≤0.1W 设计'})
        c['requirements'][0]['depends_on'].append('W-STBY')
        self.d.write('design-closure.json', c)
        self.d.write('design-closure-audit.json',
                     audit(c, self.d.record / 'electrical-intent.json', self.d.root))

    def test_requirement_questions_called_out_and_listed_first(self):
        self.ask_user()
        text, problems = self.d.report()
        self.assertEqual(problems, [])
        conclusion = text.split('## 结论')[1].split('\n## ')[0]
        self.assertIn('- **请你定的需求**：1 件（W-STBY）。本版先按写明的假设设计', conclusion)
        self.assertIn('3 件待办没做完（等用户定需求 1 件，设计没做完 1 件，缺外部资料 1 件）', conclusion)
        self.assertIn('等你定的需求排最前', conclusion)
        section = text.split('## 待办')[1].split('\n## ')[0]
        self.assertLess(section.index('W-STBY（P3'), section.index('W-FW（P0'))
        self.assertIn('- **类型**：等用户定需求', section)
        self.assertIn('- **本版按什么假设设计**：按待机 ≤0.1W 设计', section)
        self.assertIn('| 待办：等用户定需求（未关闭） | 1 |', text)

    def test_ask_user_response_must_point_at_requirement_items(self):
        self.ask_user()
        self.d.write('review-responses.json', {'schema_version': 1,
            'sources': [{'id': 'S1', 'path': '/x', 'sha256': '0' * 64}],
            'items': [{'id': 'RC1', 'source': 'S1', 'locator': '1', 'comment': 'c', 'response': 'ASK_USER',
                       'detail': '待机功耗上限要产品定', 'work_items': ['W-STBY']},
                      {'id': 'RC2', 'source': 'S1', 'locator': '2', 'comment': 'c', 'response': 'ASK_USER',
                       'detail': 'd', 'work_items': ['W-CALC']}]})
        _, problems = self.d.report()
        self.assertEqual(problems, ['RC2：待办 W-CALC 的阶段与处理方式“请用户定需求”不符'])

    def test_conditional_calculations_listed_with_assumptions(self):
        text, _ = self.d.report()
        section = text.split('## 有条件成立的计算')[1].split('## ')[0]
        self.assertIn('| C1 | R-OUT | 输出纹波：18 ≤ 30 mV | ripple |', section)
        self.assertIn('不阻塞出图', section)

    def test_english_prose_in_records_is_a_problem(self):
        self.d.closure['calculations'][0]['assumptions'] = [
            'Transformer temperature, fringing and leakage require construction verification.']
        self.d.write('design-closure.json', self.d.closure)
        self.d.write('design-closure-audit.json', audit(self.d.closure, self.d.record / 'electrical-intent.json', self.d.root))
        _, problems = self.d.report()
        self.assertTrue(any('要改成中文' in p and 'C1' in p for p in problems), problems)

    def test_chinese_prose_with_part_numbers_and_acronyms_is_fine(self):
        from render_design_report import english_sentence
        self.assertFalse(english_sentence('NCP1343的FAULT脚经BZT52H-B68检测辅助绕组过压，PFC关断后VCC由HV维持'))
        self.assertFalse(english_sentence('Kelvin回路按TDK ETD39 p2-4核对'))
        self.assertTrue(english_sentence('Only NCP1343 remains on VCC after auxiliary dies'))

    def test_failed_drawing_gate_is_a_problem(self):
        self.d.write('summary.json', {'status': 'FAIL', 'sheets': ['a', 'b'], 'gates': {
            'erc': {'status': 'PASS', 'violations': 0}, 'geometry': {'status': 'FAIL'}}})
        text, problems = self.d.report()
        self.assertTrue(any('图面几何' in p and '改图' in p for p in problems), problems)
        self.assertIn('没通过（FAIL） 1 项', text)
        self.assertNotIn('REVIEW', text)

    def test_geometry_detail_counts_gaps_and_render_review_items(self):
        self.d.write('summary.json', {'status': 'INCOMPLETE', 'sheets': ['a', 'b'], 'gates': {
            'erc': {'status': 'PASS', 'violations': 0},
            'geometry': {'status': 'PASS', 'render_review_items': {'a': ['x', 'y']}}}})
        text, _ = self.d.report()
        self.assertIn('2 个引脚文字交看图检查', text)

    def test_page_plan_is_required_and_checked(self):
        (self.d.record / 'page-plan.json').unlink()
        _, problems = self.d.report()
        self.assertIn('缺少 record/page-plan.json', problems)
        self.d.write('page-plan.json', {'schema_version': 1, 'pages': [
            {'file': 'board.kicad_sch', 'reader_tasks': ['任务一', '任务二'], 'blocks': {'a': ['U1', 'R9'], 'b': ['U1']}},
            {'file': 'other.kicad_sch', 'reader_tasks': [], 'blocks': {}}]})
        _, problems = self.d.report()
        self.assertIn('board.kicad_sch：功能块“a”里的 R9 不在设计要求表里', problems)
        self.assertIn('board.kicad_sch：U1 同时在功能块“a”和“b”里', problems)
        self.assertIn('board.kicad_sch：读者任务 2 条，看图检查只追了 1 条路径', problems)
        self.assertIn('other.kicad_sch：要写明读者任务（reader_tasks）', problems)
        self.assertIn('other.kicad_sch：要按功能块列出器件（blocks）', problems)

    def test_parts_on_a_page_must_belong_to_a_block(self):
        self.d.write('electrical-intent.json', {'components': [
            {'ref': 'U1', 'fields': {'Circuit': 'board'}}, {'ref': 'R1', 'fields': {'Circuit': 'board'}},
            {'ref': 'C1', 'fields': {'Circuit': 'board'}}]})
        _, problems = self.d.report()
        self.assertIn('board.kicad_sch：这些器件不属于任何功能块：C1', problems)

    def test_render_review_items_are_dispositioned_per_symbol(self):
        (self.d.root / '原理图' / 'board.kicad_sch').write_text(
            '(kicad_sch (version 20250114) (generator "t") (uuid "r") (paper "A4") (lib_symbols)\n'
            '(symbol (lib_id "Device:R") (at 0 0 0) (uuid "aaa") (property "Reference" "R1" (at 0 0 0)))\n'
            '(symbol (lib_id "Device:R") (at 0 10 0) (uuid "bbb") (property "Reference" "U1" (at 0 0 0))))\n')
        same = '已在本页原生PDF核对可见引脚号/脚名，无遮挡。'
        self.d.write('visual-review.json', {'status': 'REVIEWED', 'pages': [
            {'page': 1, 'file': 'board.kicad_sch', 'paths': ['VIN to VOUT'], 'problems': [], 'render_review_items': [
                {'item': 'pin-number:aaa: physical pin numbers need native render review', 'disposition': same},
                {'item': 'pin-name:bbb:1: nonunique/noncausal text removal', 'disposition': same},
                {'item': 'pin-name:ccc:1: x', 'disposition': 'C9 看过'}]}]})
        _, problems = self.d.report()
        self.assertIn('board.kicad_sch：R1 的引脚文字处置要写明在图上看到了什么，并点名 R1', problems)
        self.assertIn('board.kicad_sch：条目“pin-name:ccc:1: x”的符号在图里找不到', problems)
        self.d.write('visual-review.json', {'status': 'REVIEWED', 'pages': [
            {'page': 1, 'file': 'board.kicad_sch', 'paths': ['VIN to VOUT'], 'problems': [], 'render_review_items': [
                {'item': 'pin-number:aaa: physical pin numbers need native render review', 'disposition': 'R1 脚号 1、2 可见，在引脚外侧'},
                {'item': 'pin-name:bbb:1: nonunique/noncausal text removal', 'disposition': 'U1 脚名 VIN 在体内，未被导线压住'}]}]})
        _, problems = self.d.report()
        self.assertEqual([], problems)
        self.d.write('visual-review.json', {'status': 'REVIEWED', 'pages': [
            {'page': 1, 'file': 'board.kicad_sch', 'paths': ['VIN to VOUT'], 'problems': [], 'render_review_items': [
                {'item': 'pin-number:aaa: x', 'disposition': 'R1 与 U1 的脚号均可见'},
                {'item': 'pin-name:bbb:1: x', 'disposition': 'R1 与 U1 的脚号均可见'}]}]})
        _, problems = self.d.report()
        self.assertIn('board.kicad_sch：同一句处置用在了 R1、U1：要逐个器件写看到了什么', problems)

    def test_handoffs_listed_apart(self):
        text, _ = self.d.report()
        self.assertIn('| 样机验证 | 样机或试验验证 | 满载温升测试 |', text.split('## 交给后续环节的要求')[1])

    def test_plain_words_only(self):
        text, _ = self.d.report()
        for word in JARGON:
            self.assertNotIn(word, text, word)

    def test_review_responses_are_checked_and_listed(self):
        self.d.write('review-responses.json', {'schema_version': 1,
            'sources': [{'id': 'S1', 'path': '/x/审查报告.md', 'sha256': '0' * 64, 'from': '审查方 v0'}],
            'items': [{'id': 'RC1', 'source': 'S1', 'locator': '待办 1', 'comment': '过压保护配置没依据',
                       'response': 'OBTAIN_DATA', 'detail': '向固件供应方要配置表', 'work_items': ['W-FW']},
                      {'id': 'RC2', 'source': 'S1', 'locator': '待办 2', 'comment': '缺满载温升',
                       'response': 'DECLINE', 'detail': '只能样机测'}]})
        text, problems = self.d.report()
        self.assertIn('RC2：处理方式为“不采纳”时必须填 evidence', problems)
        self.assertIn('- **收到的审查意见**：2 条。补资料 1 条，不采纳 1 条。', text)
        self.assertIn('| RC1 | 过压保护配置没依据 | 补资料 | 向固件供应方要配置表 |', text)
        self.assertIn('设计记录本身有问题', text.splitlines()[2])

    def test_response_stage_must_match_work_item(self):
        self.d.write('review-responses.json', {'schema_version': 1,
            'sources': [{'id': 'S1', 'path': '/x', 'sha256': '0' * 64}],
            'items': [{'id': 'RC1', 'source': 'S1', 'locator': '1', 'comment': 'c', 'response': 'HANDOFF',
                       'detail': 'd', 'work_items': ['W-CALC']}]})
        _, problems = self.d.report()
        self.assertIn('RC1：待办 W-CALC 的阶段与处理方式“交给后续环节”不符', problems)


class PackDesignTests(unittest.TestCase):
    def setUp(self):
        self.d = Delivery()
        self.addCleanup(self.d.tmp.cleanup)
        text, _ = self.d.report()
        (self.d.root / REPORT).write_text(text)
        self.inputs = Path(self.d.tmp.name) / 'req'
        self.inputs.mkdir()
        (self.inputs / 'spec.md').write_text('spec')

    def run_pack(self):
        return pack(self.d.root, {'requirements': str(self.inputs)})

    def test_failed_drawing_gate_cannot_be_packed(self):
        self.d.write('summary.json', {'status': 'FAIL', 'sheets': ['a', 'b'], 'gates': {
            'erc': {'status': 'PASS', 'violations': 0}, 'geometry': {'status': 'FAIL'}}})
        text, _ = self.d.report()
        (self.d.root / REPORT).write_text(text)
        errors, _ = self.run_pack()
        self.assertTrue(any('图面几何' in e for e in errors), errors)

    def test_clean_delivery_packs_with_manifest(self):
        errors, manifest = self.run_pack()
        self.assertEqual(errors, [])
        self.assertEqual(manifest['inputs']['requirements']['kind'], 'directory')
        self.assertIn('原理图/schematic.pdf', manifest['packed'])
        self.assertTrue((self.d.record / 'manifest.json').is_file())

    def test_extra_files_history_and_logs_fail(self):
        (self.d.root / 'README.md').write_text('x')
        (self.d.record / 'baseline-v05').mkdir()
        (self.d.record / 'run.log').write_text('x')
        errors, _ = self.run_pack()
        self.assertTrue(any('README.md' in e for e in errors))
        self.assertTrue(any('record/baseline-v05/' in e for e in errors))
        self.assertTrue(any('run.log' in e for e in errors))

    def test_cited_evidence_must_be_inside(self):
        (self.d.record / 'evidence' / 'design.md').unlink()
        errors, _ = self.run_pack()
        self.assertTrue(any('evidence_missing_or_outside_root' in e for e in errors), errors)

    def test_requirement_evidence_may_stay_in_declared_input(self):
        spec = self.inputs / 'spec.md'
        self.d.closure['evidence'].append({'id': 'E2', 'path': 'requirements/spec.md', 'sha256': sha256(spec),
                                           'locator': 'REQ-1'})
        self.d.closure['requirements'][0]['evidence'].append('E2')
        self.d.write('design-closure.json', self.d.closure)
        errors, manifest = self.run_pack()
        self.assertEqual(errors, [])
        self.assertNotIn('requirements/spec.md', manifest['packed'])
        spec.write_text('changed')
        errors, _ = self.run_pack()
        self.assertTrue(any('stale_evidence E2' in e for e in errors), errors)

    def test_design_documents_must_name_parts_the_design_has(self):
        docs = self.d.root / '设计资料'
        (docs / '装配配置.json').write_text(json.dumps({'assemblies': [{'fit': ['U1', 'U9'], 'dnp': []}]}))
        (docs / 'BOM约束.csv').write_text('ref,value,mpn,note\nR1,10k,,ok\nC7,1u,,removed part\n', encoding='utf-8')
        errors, _ = self.run_pack()
        self.assertTrue(any('装配配置.json: fit U9 is not in the design' in e for e in errors), errors)
        self.assertTrue(any('BOM约束.csv line 3: C7 is not in the design' in e for e in errors), errors)
        self.assertFalse(any(' U1 ' in e or ' R1 ' in e for e in errors), errors)

    def test_design_document_mpn_and_value_must_match(self):
        self.d.write('electrical-intent.json', {'components': [{'ref': 'U1', 'mpn': 'TPS7A4001DGNR', 'value': 'TPS7A4001DGNR'},
                                                               {'ref': 'R1', 'value': '10k'}]})
        self.d.closure['intent_sha256'] = sha256(self.d.record / 'electrical-intent.json')
        self.d.write('design-closure.json', self.d.closure)
        (self.d.root / '设计资料' / 'BOM约束.csv').write_text('位号,value,mpn\nU1,TPS7A4001DGNR,TPS7A16DGNR\nR1,10k,\n', encoding='utf-8')
        errors, _ = self.run_pack()
        self.assertTrue(any("U1 mpn is 'TPS7A16DGNR', the design has 'TPS7A4001DGNR'" in e for e in errors), errors)
        self.assertFalse(any('R1' in e for e in errors), errors)

    def test_missing_schematic_outputs_fail(self):
        (self.d.root / '原理图' / 'BOM.csv').unlink()
        errors, _ = self.run_pack()
        self.assertIn('原理图/BOM.csv is missing', errors)


if __name__ == '__main__':
    unittest.main()
