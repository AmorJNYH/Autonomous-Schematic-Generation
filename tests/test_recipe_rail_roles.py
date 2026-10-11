"""Narrow rail-role suggestions, preserving recipe guards and other topology."""
import copy
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / 'scripts'), str(HERE / 'fixtures' / 'drawing')]
from recipe_board import EXTERNAL, INTENT, RAILS
from schematic_layout.recipes import ALLOWED, RIGHT, UP, Sheet


def two_pin(ref='R_TEST', lib='Device:R', first_net='SUPPLY_A', second_net='SUPPLY_B', value='22'):
    nets = [{'name': first_net, 'pins': [ref + '.1']}]
    if first_net == second_net:
        nets[0]['pins'].append(ref + '.2')
    else:
        nets.append({'name': second_net, 'pins': [ref + '.2']})
    return {'schema_version': 1, 'design_id': 'synthetic-rail-role',
            'components': [{'ref': ref, 'lib_id': lib, 'value': value, 'footprint': ''}],
            'nets': nets, 'no_connect': []}


class RailRoleTests(unittest.TestCase):
    def test_renamed_positive_and_negative_rail_resistors_suggest_series(self):
        # Negative-voltage symbols in this library also have non-return glyphs.
        # This checks the existing glyph heuristic, not electrical polarity.
        cases = [
            ('R_ALPHA', 'SUPPLY_A', 'SUPPLY_B', 'power:+5V', 'power:+3V3', '22', 'Device:R'),
            ('X42', 'NEG_IN', 'NEG_OUT', 'power:-5V', 'power:-3V3', '1k', 'Device:R_Small'),
            ('R_Z', 'GND', 'RETURN', 'power:+5V', 'power:+3V3', '10', 'Device:R'),
        ]
        for ref, first, second, first_symbol, second_symbol, value, lib in cases:
            with self.subTest(ref=ref, nets=(first, second)):
                sheet = Sheet(two_pin(ref, lib, first, second, value),
                              rails={first: first_symbol, second: second_symbol})
                self.assertFalse(sheet._power_shape(first_symbol)[2])
                self.assertFalse(sheet._power_shape(second_symbol)[2])
                self.assertEqual({'role': 'series', 'why': 'between distinct declared non-return rails'},
                                 sheet.plan['parts'][ref])
                self.assertEqual({first: 'power', second: 'power'}, sheet.plan['nets'])

    def test_same_net_one_return_and_two_returns_keep_old_decoupling(self):
        cases = [
            ('A', 'A', {'A': 'power:+5V'}),
            ('A', 'B', {'A': 'power:+5V', 'B': 'power:GND'}),
            ('A', 'B', {'A': 'power:GND', 'B': 'power:GNDA'}),
            # A supply-looking net name does not override a return glyph.
            ('POSITIVE', 'OTHER', {'POSITIVE': 'power:GND', 'OTHER': 'power:+5V'}),
        ]
        for first, second, rails in cases:
            with self.subTest(nets=(first, second), rails=rails):
                sheet = Sheet(two_pin(first_net=first, second_net=second), rails=rails)
                self.assertEqual({'role': 'decoupling', 'why': 'both pins on rails'},
                                 sheet.plan['parts']['R_TEST'])

    def test_signal_and_undeclared_rail_like_names_keep_old_roles(self):
        for rails, expected in (({}, 'series'), ({'SUPPLY_A': 'power:+5V'}, 'shunt'),
                                ({'SUPPLY_B': 'power:GND'}, 'shunt')):
            with self.subTest(rails=rails):
                sheet = Sheet(two_pin(), rails=rails)
                self.assertEqual(expected, sheet.plan['parts']['R_TEST']['role'])
        with self.assertRaisesRegex(ValueError, 'Unknown rail/external nets'):
            Sheet(two_pin(), rails={'NOT_IN_INTENT': 'power:+5V'})
        with self.assertRaises(ValueError):
            Sheet(two_pin(), rails={'SUPPLY_A': 'UnknownLibrary:UnknownPower', 'SUPPLY_B': 'power:+5V'})

    def test_two_rail_capacitors_and_other_nonresistors_keep_old_role(self):
        for lib in ('Device:C', 'Device:C_Polarized', 'Device:L', 'Device:D'):
            with self.subTest(lib=lib):
                sheet = Sheet(two_pin(lib=lib), rails={'SUPPLY_A': 'power:+5V', 'SUPPLY_B': 'power:+3V3'})
                self.assertEqual({'role': 'decoupling', 'why': 'both pins on rails'},
                                 sheet.plan['parts']['R_TEST'])

    def test_existing_bank_divider_lane_anchor_and_net_roles_snapshot(self):
        sheet = Sheet(copy.deepcopy(INTENT), rails=RAILS, external=EXTERNAL)
        self.assertEqual({
            'J1': 'anchor', 'U1': 'anchor', 'U2': 'anchor', 'J2': 'anchor',
            'C1': 'bank', 'C2': 'bank', 'C3': 'decoupling', 'C4': 'decoupling',
            'R1': 'divider_upper', 'R2': 'divider_lower',
            'R4': 'lane_series', 'R5': 'lane_series', 'D4': 'lane_shunt', 'D5': 'lane_shunt',
            'F1': 'series', 'D1': 'series', 'D2': 'shunt', 'L1': 'shunt',
            'C5': 'decoupling', 'C6': 'decoupling', 'R3': 'shunt', 'D3': 'shunt',
        }, {ref: entry['role'] for ref, entry in sheet.plan['parts'].items()})
        self.assertEqual({
            'VIN_RAW': None, 'VIN_F': None, 'VIN': 'name', 'GND': 'power', 'SW': 'name',
            '+5V': 'power', 'FB': 'name', '+3V3': 'power', 'LED_A': None,
            'MCU_DP': 'global', 'MCU_DN': 'global', 'USB_DP': 'name', 'USB_DN': 'name', 'USB_VBUS': 'global',
        }, sheet.plan['nets'])

    def test_rung_between_candidate_lanes_and_explicit_nc_keep_old_roles(self):
        intent = {'schema_version': 1, 'design_id': 'synthetic-rung', 'components': [
            {'ref': 'J1', 'lib_id': 'Connector_Generic:Conn_01x03', 'value': 'J', 'footprint': ''},
            {'ref': 'C1', 'lib_id': 'Device:C', 'value': '4n7', 'footprint': ''},
            {'ref': 'R1', 'lib_id': 'Device:R', 'value': '100', 'footprint': ''},
            {'ref': 'R2', 'lib_id': 'Device:R', 'value': '100', 'footprint': ''}],
            'nets': [{'name': 'P', 'pins': ['J1.1', 'C1.1', 'R1.2']},
                     {'name': 'N', 'pins': ['J1.2', 'C1.2', 'R2.2']},
                     {'name': 'GND', 'pins': ['J1.3', 'R1.1', 'R2.1']}], 'no_connect': []}
        sheet = Sheet(intent, rails={'GND': 'power:GND'})
        self.assertEqual({'J1': 'anchor', 'C1': 'series', 'R1': 'shunt', 'R2': 'shunt'},
                         {ref: entry['role'] for ref, entry in sheet.plan['parts'].items()})
        intent = two_pin()
        intent['nets'].pop()
        intent['no_connect'] = ['R_TEST.2']
        sheet = Sheet(intent, rails={'SUPPLY_A': 'power:+5V'})
        self.assertEqual('explicit', sheet.plan['parts']['R_TEST']['role'])

    def test_series_recipe_passes_structure_and_shunt_cannot_bypass_it(self):
        rails = {'SUPPLY_A': 'power:+5V', 'SUPPLY_B': 'power:+3V3'}
        for recipe, expected in (('series', 'PASS'), ('shunt', 'FAIL')):
            with self.subTest(recipe=recipe):
                intent = two_pin()
                intent['components'].append({'ref': 'J1', 'lib_id': 'Connector_Generic:Conn_01x02',
                                             'value': 'Synthetic supply domains', 'footprint': ''})
                for index, net in enumerate(intent['nets'], 1):
                    net['pins'].append('J1.' + str(index))
                sheet = Sheet(intent, rails=rails)
                sheet.place('J1', (50.8, 50.8), facing={'1': RIGHT})
                if recipe == 'series':
                    sheet.series('J1.1', ['R_TEST'], RIGHT, gap=4)
                else:
                    sheet.shunt('J1.1', 'R_TEST', UP, gap=4)
                sheet.power('J1.1')
                sheet.power('J1.2')
                self.assertEqual({'series'}, ALLOWED['series'])
                report = sheet._audit([])
                self.assertEqual(expected, report['status'], report)
                recipe_findings = [row for row in report['findings'] if row['rule'] == 'recipe']
                self.assertEqual([] if expected == 'PASS' else ['R_TEST'],
                                 [row['subject'] for row in recipe_findings])


if __name__ == '__main__':
    unittest.main()
