"""Key and special parts carry an MPN, a datasheet and a kind declaration; common parts carry their ratings; a cited
datasheet is the part's own (R7: 21 parts unnamed; P3 aligned with schematic-review, user 2026-10-26)."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from schematic_layout import part_classes as pc

BXW = 'Datasheet/20_电容器/铝电解电容/Rubycon - BXW.pdf'
SR = Path.home() / '.agents' / 'skills' / 'schematic-review' / 'scripts'
PAGE = 'SMBJ series 600 W surface mount transient voltage suppressor. Unidirectional TVS, peak pulse power 600 W, ' * 2


def part(ref, lib, value='', mpn='', datasheet='', **fields):
    return {'ref': ref, 'lib_id': lib, 'value': value, 'mpn': mpn, 'datasheet': datasheet, 'fields': fields}


def declared(ref, lib, kind, quote, value='', mpn='X', datasheet='SMBJ24A.pdf', **fields):
    return part(ref, lib, value, mpn, datasheet, Kind=kind, KindSource='datasheet:SMBJ24A.pdf#p1', KindQuote=quote, **fields)


PD_NETS = {'L_IN': ['J101.1', 'F101.1'], 'L_F': ['F101.2', 'TH101.1'], 'L_NTC': ['TH101.2', 'RV101.1'],
           'VBUS': ['J701.1', 'TH701.1'], 'VBUS_P': ['TH701.2', 'Q701.1'], 'NTC_SENSE': ['TH601.1', 'U601.3'],
           'SGND': ['TH601.2', 'K1.1']}
PD = {'nets': PD_NETS, 'net_roles': {'VBUS': 'power', 'VBUS_P': 'power', 'SGND': 'return', 'NTC_SENSE': 'signal'},
      'high_voltage_nets': ['L_IN', 'L_F', 'L_NTC']}


class ClassTests(unittest.TestCase):
    def test_level_follows_kind_and_position(self):
        ctx = pc.context(PD)
        cases = {
            'key': [part('U201', 'PD100:NCP1623'), part('Q701', 'PD100:NTMFS5C604NL'), part('T301', 'PD100:Transformer'),
                    part('D712', 'PD100:D_TVS_Uni'), part('BR101', 'PD100:GBU4M'), part('D405', 'Device:D', 'BZT52H-B18'),
                    part('L201', 'Device:L', DesignSheet='设计资料/L201.md')],
            'special': [part('F101', 'Device:Fuse'), part('RV101', 'Device:Varistor'), part('CX101', 'Device:C'),
                        part('C305', 'Device:C', '1n/Y1/400Vac'), part('J101', 'Connector_Generic:Conn_01x02'),
                        part('TH101', 'Device:Thermistor_NTC'), part('TH701', 'Device:Thermistor_NTC')],
            'common': [part('D302', 'Device:D_Schottky'), part('D101', 'Device:LED'), part('C201', 'Device:C_Polarized'),
                       part('L401', 'Device:L'), part('L101', 'PD100:CMC'), part('J701', 'Connector:USB_C_Receptacle_USB2.0_16P'),
                       part('TH601', 'Device:Thermistor_NTC'), part('K1', 'Relay:G5V-1'), part('R303', 'Device:R'),
                       part('C101', 'Device:C'), part('TP601', 'Connector:TestPoint'), part('Y1', 'Device:Crystal'),
                       part('BT1', 'Device:Battery_Cell')]}
        for level, parts in cases.items():
            for p in parts:
                self.assertEqual(level, pc.part_class(p, ctx), p['ref'])

    def test_without_high_voltage_nets_connectors_relays_and_ntcs_are_special(self):
        ctx = pc.context({'nets': PD_NETS})
        for p in (part('J701', 'Connector:USB_C_Receptacle_USB2.0_16P'), part('K1', 'Relay:G5V-1'),
                  part('TH601', 'Device:Thermistor_NTC')):
            self.assertEqual('special', pc.part_class(p, ctx), p['ref'])

    def test_kind_from_symbol_and_part_number_before_the_prefix(self):
        # Scan of 20 public KiCad projects: MPN-named project symbols and unlisted kinds.
        cases = {'mosfet': [part('AH2', 'Device:Q_NMOS_SGD'), part('Q3', 'Transistor_FET:2N7002')],
                 'bjt': [part('T5', 'tesla_smps-rescue:Q_NPN_EBC')], 'transformer': [part('Tr1', 'tesla_smps-rescue:Transformer')],
                 'ic': [part('REF1', 'Reference_Voltage:TL431LP'), part('A1', 'MCU_Module:Arduino_Nano_v3.x'),
                        part('Module1', 'CM5IO:ComputeModule5-CM5'), part('U4', 'Interface_USB:CP2102N-A01-GQFN28')],
                 'tvs': [part('D1', 'Power_Protection:PRTR5V0U2X'), part('D29', 'Diode:SMF54A')],
                 'diode': [part('D21', 'Diode:1N4148WT'), part('D33', 'MotorBuck:WS2812B')],
                 'crystal': [part('Y1', 'Device:Crystal_GND24'), part('X1', 'Oscillator:TXC-7C')],
                 'fuse': [part('F1', 'Device:Polyfuse')], 'ferrite': [part('FB2', 'Device:FerriteBead')],
                 'inductor': [part('FL1', 'tesla_smps-rescue:F_CHOKE')], 'connector': [part('J10', 'HR911105A:HR911105A')],
                 'relay': [part('K20', 'Relay:FINDER-40.41')], 'battery': [part('BT1', 'Device:Battery_Cell')],
                 'varistor': [part('RV2', 'Device:Varistor')], 'ntc': [part('R9', 'Device:Thermistor_NTC')],
                 'capacitor': [part('C4', 'Device:CP_Small')], 'resistor': [part('RV3', 'Device:R_Potentiometer_Trim')],
                 'switch': [part('SW1', 'Switch:SW_Push'), part('K32', 'keyboard_parts:KEYSW')],
                 'jumper': [part('JP1', 'Jumper:SolderJumper_2_Open')], 'testpoint': [part('TP3', 'otter:test-pad-1')],
                 'mechanical': [part('H1', 'Mechanical:MountingHole_Pad'), part('FID1', 'Mechanical:Fiducial')],
                 None: [part('BZ1', 'Device:Buzzer'), part('AE1', 'otter:KH-5220-A56_U.FL')]}
        for kind, parts in cases.items():
            for p in parts:
                self.assertEqual(kind, pc.kind_of(p)[0], p['ref'])
        self.assertIsNone(pc.part_class(part('BZ1', 'Device:Buzzer')))

    def test_a_declaration_against_the_symbol_is_a_problem(self):
        self.assertIn('不一致', pc.kind_of(part('D1', 'Device:D_TVS', Kind='diode'))[1])
        self.assertEqual(('tvs', None), pc.kind_of(part('D1', 'Device:D', Kind='tvs')))
        self.assertIn('不是器件类型', pc.kind_of(part('D1', 'Device:D', Kind='suppressor'))[1])

    @unittest.skipUnless((SR / 'device_kinds.py').is_file(), 'schematic-review not installed')
    def test_kind_vocabulary_matches_schematic_review(self):
        sys.path.insert(0, str(SR))
        try:
            import device_kinds
        finally:
            sys.path.remove(str(SR))
        sr = set(device_kinds.KINDS) - {'unknown'}
        self.assertEqual(sr, set(pc.KINDS) - {'mechanical'})
        for name, kind in device_kinds.KINDS.items():
            if name in pc.KINDS:
                self.assertLessEqual(set(kind.cues), set(pc.KINDS[name].cues), name)


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        (self.root / 'SMBJ24A.pdf').write_bytes(b'%PDF smbj')
        (self.root / 'T301设计单.md').write_text('ETD39 N87 56:7:21')
        for target, value in (('library_present', True), ('check', {'status': 'PASS', 'reason': '', 'unshown': []}),
                              ('page_text', PAGE)):
            patcher = mock.patch.object(pc, target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self.dir.cleanup)

    def intent(self):
        return {'nets': PD_NETS, 'high_voltage_nets': ['L_IN'], 'components': [
            part('C201', 'Device:C_Polarized', '120u'),
            part('D712', 'PD100:D_TVS_Uni', 'SMBJ24A', mpn='SMBJ24A-E3/52', datasheet='SMBJ24A.pdf'),
            part('CX101', 'Device:C', '220n/X2/310Vac'),
            part('T301', 'PD100:Transformer', '300uH 56:7:21', mpn='R7-ETD39', DesignSheet='T301设计单.md'),
            part('L201', 'Device:L', '300uH'),
            part('D302', 'Device:D_Schottky', 'BAT54'),
            part('R303', 'Device:R', '0R30', Specification='2W'),
            part('BZ1', 'Device:Buzzer', 'Buzzer'),
            declared('D706', 'PD100:D_TVS_Uni', 'tvs', 'Unidirectional TVS', 'SMBJ24A')]}

    def refs(self, lines):
        return [line.split('（')[0].split(' ')[-1] for line in lines]

    def test_new_design_lists_every_incomplete_part_as_a_problem(self):
        problems, inherited = pc.audit_identity(self.intent(), [self.root])
        self.assertEqual([], inherited)
        self.assertEqual(['C201', 'D712', 'CX101', 'L201', 'BZ1'], self.refs(problems))
        self.assertIn('常规件 C201（120u）缺耐压', problems[0])
        self.assertIn('关键器件 D712（SMBJ24A）缺类型声明', problems[1])
        self.assertIn('特殊器件 CX101（220n/X2/310Vac）缺料号（mpn）、数据手册（datasheet）、类型声明', problems[2])
        self.assertIn('缺额定电流', problems[3])
        self.assertIn('器件类型（认不出，写 fields.Kind', problems[4])

    def test_the_quote_names_the_kind_and_is_on_the_cited_page(self):
        for quote, said in (('Schottky barrier rectifier', '没有说出 tvs'), ('Bidirectional TVS 400 W', '不在 SMBJ24A.pdf 第 1 页')):
            intent = {'nets': {}, 'components': [declared('D706', 'PD100:D_TVS_Uni', 'tvs', quote)]}
            self.assertIn(said, pc.audit_identity(intent, [self.root])[0][0])

    def test_the_declaration_cites_the_parts_own_datasheet(self):
        comp = declared('D706', 'PD100:D_TVS_Uni', 'tvs', 'Unidirectional TVS')
        comp['fields']['KindSource'] = 'datasheet:Datasheet/23_分立半导体/TVS/Littelfuse - SMAJ.pdf#p1'
        self.assertIn('不是同一份', pc.audit_identity({'components': [comp]}, [self.root])[0][0])

    def test_a_datasheet_that_is_nowhere_is_not_a_datasheet(self):
        intent = {'components': [declared('D706', 'PD100:D_TVS_Uni', 'tvs', 'Unidirectional TVS', datasheet='gone.pdf')]}
        self.assertIn('不在交付目录或知识库里', pc.audit_identity(intent, [self.root])[0][0])

    def test_revision_blocks_only_parts_it_adds_or_changes(self):
        touched = pc.touched_refs({'add_components': {'D712': {}}, 'component_changes': {'C201': {}}})
        problems, inherited = pc.audit_identity(self.intent(), [self.root], touched)
        self.assertEqual(['C201', 'D712'], self.refs(problems))
        self.assertEqual(['CX101', 'L201', 'BZ1'], self.refs(inherited))


class CitationTests(unittest.TestCase):
    def setUp(self):
        self.intent = {'components': [
            part('C201', 'Device:C_Polarized', mpn='450BXW120MEFR18X40', datasheet='/x/原厂资料/Rubycon-BXW.pdf'),
            part('C503', 'Device:C_Polarized', mpn='35PZJ330M10X9', datasheet='/x/原厂资料/Rubycon-PZJ.pdf'),
            part('C208', 'Device:C_Polarized', '100u/450V', datasheet='/x/原厂资料/Rubycon-BXW.pdf'),
            part('T301', 'PD100:Transformer', mpn='R7-ETD39', DesignSheet='设计资料/T301.md'),
            part('C206', 'Device:C', '10u/25V')]}

    def closure(self, params=(), gaps=()):
        return {'calculations': [{'id': 'C-LIFE', 'parameters': list(params)}],
                'work_items': [{'id': 'W-INPUT', 'missing': list(gaps)}]}

    def problems(self, **kw):
        return pc.audit_citations(self.intent, self.closure(**kw), [])

    def test_same_datasheet_under_another_file_name_binds(self):
        self.assertEqual([], self.problems(params=[{'name': '寿命', 'ref': 'C201', 'source': 'datasheet:%s#p1' % BXW}],
                                           gaps=[{'source': 'datasheet:%s#p1' % BXW, 'refs': ['C201']}]))

    def test_a_gap_that_cites_a_datasheet_names_its_parts(self):
        # R7 W-INPUT cited BXW and S3J without saying which parts; C201/C208 carried no datasheet.
        self.assertEqual(['待办 W-INPUT 的第 1 项资料缺口 引用了手册 %s，要写明它说的是哪个位号' % BXW],
                         self.problems(gaps=[{'source': 'datasheet:%s#p1' % BXW}]))

    def test_a_cited_datasheet_must_be_the_parts_own(self):
        found = self.problems(params=[{'name': '寿命', 'ref': 'C503', 'source': 'datasheet:%s#p1' % BXW}])
        self.assertEqual(1, len(found))
        self.assertIn('与设计网表里 C503 的 datasheet', found[0])

    def test_a_common_part_cited_for_a_datasheet_value_becomes_special(self):
        found = self.problems(params=[{'name': '有效电容', 'ref': 'C206', 'source': 'datasheet:Datasheet/20_电容器/X - GRM.pdf#p3'}])
        self.assertIn('C206 没有写 datasheet', found[0])
        # A lifetime calculated from the BXW series formula binds C208 to that series: it needs the exact MPN.
        found = self.problems(params=[{'name': '寿命', 'ref': 'C208', 'source': 'datasheet:%s#p1' % BXW}])
        self.assertIn('C208 因此是特殊器件，设计网表里要写它的 mpn', found[0])

    def test_standards_and_design_sheets_are_not_bound(self):
        self.assertEqual([], self.problems(
            params=[{'name': 'Bsat', 'ref': 'T301', 'source': 'datasheet:Datasheet/21_电感器与磁件/铁氧体磁芯/TDK - N87.pdf#p2'}],
            gaps=[{'source': 'datasheet:Standard/GB 4943.1 - 2022.pdf#p40'}]))


if __name__ == '__main__':
    unittest.main()
