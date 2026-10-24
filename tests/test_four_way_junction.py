"""Sheet.build rejects four wires and pins at one point, as KiCad's four_way_junction does (R6 redraw: four on 03/05/07)."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from schematic_layout.pages import page_intents
from schematic_layout.recipes import DOWN, RIGHT, Sheet, add


def part(ref, lib):
    return {'ref': ref, 'lib_id': lib, 'value': ref, 'footprint': '', 'fields': {'Circuit': 'p'}}


INTENT = {'schema_version': 1,
          'components': [part('J1', 'Connector_Generic:Conn_01x02'), part('R1', 'Device:R'), part('R2', 'Device:R')],
          'nets': {'VIN': ['J1.1', 'R1.1', 'R2.1'], 'GND': ['J1.2', 'R1.2', 'R2.2']}, 'no_connect': [],
          'external_supply': [{'net': 'VIN', 'pin': 'J1.1', 'reason': 'test'}, {'net': 'GND', 'pin': 'J1.2', 'reason': 'test'}]}


class FourWayJunctionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from schematic_layout.generate import Libraries, library_dirs
        try:
            Libraries(library_dirs()).load('Device:R')
        except ValueError:
            raise unittest.SkipTest('KiCad symbol libraries are not installed')

    def sheet(self, flag_on_node):
        page = page_intents(INTENT, rails={'GND': 'power:GND'})['p']
        s = Sheet(page['intent'], rails=page['rails'], external=page['external'])
        s.place('J1', (50.8, 76.2), mirror='y')
        a = s.stub('J1.1', 4)
        s.series(a, ['R1'], RIGHT, gap=6)
        s.shunt(a, 'R2', DOWN, gap=6)                    # a: J1 stub, R1 and R2 meet - a T
        s.power_flag(a if flag_on_node else add(a, (-1, 0), 2))
        s.power('R1.2')
        s.power(s.stub('J1.2', 2))
        return s

    def test_a_rail_symbol_on_a_tee_makes_four(self):
        with self.assertRaisesRegex(ValueError, 'Four or more wires and pins meet'):
            self.sheet(True).build('p', draft=True)

    def test_the_same_symbol_on_the_stub_is_two_tees(self):
        try:
            self.sheet(False).build('p', draft=True)
        except ValueError as error:
            self.assertNotIn('Four or more', str(error))


if __name__ == '__main__':
    unittest.main()
