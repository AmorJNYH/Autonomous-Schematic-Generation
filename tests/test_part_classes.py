"""Core and exact-MPN parts carry an MPN and a datasheet; a cited datasheet is the part's own (R7: 21 parts unnamed)."""
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from schematic_layout import part_classes as pc

BXW = 'Datasheet/20_电容器/铝电解电容/Rubycon - BXW.pdf'


def part(ref, lib, value='', mpn='', datasheet='', **fields):
    return {'ref': ref, 'lib_id': lib, 'value': value, 'mpn': mpn, 'datasheet': datasheet, 'fields': fields}


class ClassTests(unittest.TestCase):
    def test_class_follows_symbol_and_reference(self):
        cases = {
            'core': [part('U201', 'PD100:NCP1623'), part('Q701', 'PD100:NTMFS5C604NL'), part('T301', 'PD100:Transformer')],
            'exact': [part('D302', 'Device:D_Schottky'), part('D101', 'Device:LED'), part('D712', 'PD100:D_TVS_Uni'),
                      part('BR101', 'PD100:GBU4M'), part('F101', 'Device:Fuse'), part('RV101', 'Device:Varistor'),
                      part('TH101', 'Device:Thermistor_NTC'), part('CX101', 'Device:C'), part('CY301', 'Device:C'),
                      part('C201', 'Device:C_Polarized'), part('L401', 'Device:L'), part('L101', 'PD100:CMC'),
                      part('J701', 'Connector:USB_C_Receptacle_USB2.0_16P'), part('J101', 'Connector_Generic:Conn_01x02')],
            'spec': [part('R303', 'Device:R'), part('C101', 'Device:C'), part('C412', 'Device:C_Small'),
                     part('TP601', 'Connector:TestPoint')]}
        for kind, parts in cases.items():
            for p in parts:
                self.assertEqual(kind, pc.part_class(p), p['ref'])

    def test_prefix_or_symbol_family_decides_and_unknown_parts_need_an_mpn(self):
        # Scan of 20 public KiCad projects: 150 of 2774 parts named after their MPN or of an unlisted kind fell to spec.
        cases = {
            'core': [part('AH2', 'Device:Q_NMOS_SGD'), part('Q3', 'motor_parts:BSS816NWH6327'),
                     part('Tr1', 'tesla_smps-rescue:Transformer'), part('REF1', 'Reference_Voltage:TL431LP'),
                     part('A1', 'MCU_Module:Arduino_Nano_v3.x'), part('Module1', 'CM5IO:ComputeModule5-CM5')],
            'exact': [part('D21', 'Diode:1N4148WT'), part('D1', 'Power_Protection:PRTR5V0U2X'), part('D33', 'MotorBuck:WS2812B'),
                      part('CR1', 'TSD05CDYFR:TSD05CDYFR'), part('Y1', 'Device:Crystal_GND24'), part('X1', 'Oscillator:TXC-7C'),
                      part('F1', 'Device:Polyfuse'), part('FB2', 'Device:FerriteBead'), part('FL1', 'tesla_smps-rescue:F_CHOKE'),
                      part('J10', 'HR911105A:HR911105A'), part('K20', 'Relay:FINDER-40.41'), part('BT1', 'Device:Battery_Cell'),
                      part('BZ1', 'Device:Buzzer'), part('AE1', 'otter:KH-5220-A56_U.FL'), part('RV2', 'Device:Varistor'),
                      part('R9', 'Device:Thermistor_NTC'), part('C4', 'Device:CP_Small')],
            'spec': [part('RV3', 'Device:R_Potentiometer_Trim'), part('R2', 'SPIRIT-components:1K-05W-0805-RES_ERJP06J102V'),
                     part('C3', 'SPIRIT-components:USBC_capacitor_GRM033R60J334ME90D'), part('SW1', 'Switch:SW_Push'),
                     part('K32', 'keyboard_parts:KEYSW'), part('JP1', 'Jumper:SolderJumper_2_Open'),
                     part('H1', 'Mechanical:MountingHole_Pad'), part('FID1', 'Mechanical:Fiducial'), part('TP3', 'otter:test-pad-1')]}
        for kind, parts in cases.items():
            for p in parts:
                self.assertEqual(kind, pc.part_class(p), p['ref'])


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        (self.root / 'BXW.pdf').write_bytes(b'%PDF bxw')
        (self.root / 'T301设计单.md').write_text('ETD39 N87 56:7:21')
        patcher = mock.patch.object(pc, 'library_present', return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.dir.cleanup)

    def intent(self):
        # R7: the bulk capacitor lost its MPN and datasheet; the diode kept a family name without a datasheet.
        return {'components': [
            part('C201', 'Device:C_Polarized', '120u/450V'),
            part('D302', 'Device:D_Schottky', 'BAT54', mpn='BAT54'),
            part('C208', 'Device:C_Polarized', '100u/450V', mpn='450BXW100MEFR18X35', datasheet='BXW.pdf'),
            part('T301', 'PD100:Transformer', '300uH 56:7:21', mpn='R7-ETD39', DesignSheet='T301设计单.md'),
            part('L201', 'Device:L', '300uH/7.5A', mpn='R7-PFC-300U'),
            part('R303', 'Device:R', '0R30', 功率='2W'),
            part('C301', 'Device:C', '4n7/630V')]}

    def test_new_design_lists_every_unnamed_part_as_a_problem(self):
        problems, inherited = pc.audit_identity(self.intent(), [self.root])
        self.assertEqual([], inherited)
        self.assertEqual(['C201', 'D302', 'L201'], [p.split('（')[0].split(' ')[-1] for p in problems])
        self.assertIn('缺料号（mpn）、数据手册（datasheet）', problems[0])
        self.assertIn('fields.DesignSheet', problems[2])

    def test_a_datasheet_that_is_nowhere_is_not_a_datasheet(self):
        intent = {'components': [part('D706', 'Device:D_TVS', 'SMBJ24A', mpn='SMBJ24A-E3/52', datasheet='gone.pdf')]}
        self.assertIn('不在交付目录或知识库里', pc.audit_identity(intent, [self.root])[0][0])

    def test_revision_blocks_only_parts_it_adds_or_changes(self):
        touched = pc.touched_refs({'add_components': {'D302': {}}, 'component_changes': {'C201': {}}})
        problems, inherited = pc.audit_identity(self.intent(), [self.root], touched)
        self.assertEqual(['C201', 'D302'], [p.split('（')[0].split(' ')[-1] for p in problems])
        self.assertEqual(['L201'], [p.split('（')[0].split(' ')[-1] for p in inherited])


class CitationTests(unittest.TestCase):
    def setUp(self):
        self.intent = {'components': [
            part('C201', 'Device:C_Polarized', mpn='450BXW120MEFR18X40', datasheet='/x/原厂资料/Rubycon-BXW.pdf'),
            part('C503', 'Device:C_Polarized', mpn='35PZJ330M10X9', datasheet='/x/原厂资料/Rubycon-PZJ.pdf'),
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

    def test_a_spec_part_cited_for_a_datasheet_value_needs_that_datasheet(self):
        found = self.problems(params=[{'name': '有效电容', 'ref': 'C206', 'source': 'datasheet:Datasheet/20_电容器/X - GRM.pdf#p3'}])
        self.assertIn('C206 没有写 datasheet', found[0])

    def test_standards_and_design_sheets_are_not_bound(self):
        self.assertEqual([], self.problems(
            params=[{'name': 'Bsat', 'ref': 'T301', 'source': 'datasheet:Datasheet/21_电感器与磁件/铁氧体磁芯/TDK - N87.pdf#p2'}],
            gaps=[{'source': 'datasheet:Standard/GB 4943.1 - 2022.pdf#p40'}]))


if __name__ == '__main__':
    unittest.main()
