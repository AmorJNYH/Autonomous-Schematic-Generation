"""Signals remain signals through splitting and explicit power drawing calls."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from schematic_layout.pages import page_intents
from schematic_layout.recipes import Sheet, RIGHT


class NetRolesTests(unittest.TestCase):
    def setUp(self):
        self.board = {'components': [
            {'ref': 'R1', 'lib_id': 'Device:R', 'value': '10k', 'fields': {'Circuit': 'sense'}},
            {'ref': 'R2', 'lib_id': 'Device:R', 'value': '20k', 'fields': {'Circuit': 'compare'}}],
            'nets': {'THRESHOLD': ['R1.1', 'R2.1'], 'RETURN': ['R1.2'], 'BIAS': ['R2.2']}, 'no_connect': [],
            'net_roles': {'THRESHOLD': 'signal', 'RETURN': 'return', 'BIAS': 'power'}}

    def test_rejects_threshold_in_rails_before_page_split(self):
        with self.assertRaisesRegex(ValueError, 'Signal nets cannot use power symbols'):
            page_intents(self.board, rails={'THRESHOLD': 'power:+2V5'})

    def test_preserves_page_roles_and_cross_page_signal(self):
        page = page_intents(self.board, rails={'RETURN': 'power:GND', 'BIAS': 'power:+5V'})['sense']
        self.assertEqual({'THRESHOLD': 'signal', 'RETURN': 'return'}, page['intent']['net_roles'])
        self.assertEqual(['THRESHOLD'], page['external'])
        Sheet(page['intent'], rails=page['rails'], external=page['external'])

    def test_direct_sheet_and_explicit_power_call_cannot_bypass_role(self):
        page = page_intents(self.board)['sense']['intent']
        with self.assertRaisesRegex(ValueError, 'Signal nets cannot'):
            Sheet(page, rails={'THRESHOLD': 'power:+2V5'})
        sheet = Sheet(page, rails={})
        sheet.place('R1', (50.8, 50.8))
        with self.assertRaisesRegex(ValueError, 'Signal nets cannot'):
            sheet.power('R1.1', symbol='power:+2V5')

    def test_valid_supply_and_legacy_intent_remain_supported(self):
        page = page_intents(self.board, rails={'BIAS': 'power:+5V'})['compare']
        Sheet(page['intent'], rails=page['rails'])
        legacy = copy.deepcopy(self.board)
        del legacy['net_roles']
        self.assertEqual(2, len(page_intents(legacy, rails={'THRESHOLD': 'power:+2V5'})))

    def test_does_not_infer_role_from_name(self):
        board = copy.deepcopy(self.board)
        board['nets']['+3V3'] = board['nets'].pop('THRESHOLD')
        board['net_roles']['+3V3'] = board['net_roles'].pop('THRESHOLD')
        with self.assertRaisesRegex(ValueError, 'Signal nets cannot'):
            page_intents(board, rails={'+3V3': 'power:+3V3'})

    def test_typo_and_unknown_net_rejected(self):
        for roles in ({'THRESHOLD': 'threshold'}, {'NOT_A_NET': 'signal'}):
            self.board['net_roles'] = roles
            with self.assertRaisesRegex(ValueError, 'Invalid net_roles'):
                page_intents(self.board)


if __name__ == '__main__':
    unittest.main()
