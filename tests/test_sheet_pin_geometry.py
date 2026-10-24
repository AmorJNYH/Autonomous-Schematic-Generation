"""Synthetic native sheet terminal contacts; the sheet outline stays unqualified."""
import os, sys, unittest
from pathlib import Path
ROOT = Path(os.environ.get('ASG_ROOT', Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT/'scripts'))
from schematic_layout.sexpr import form as f
from schematic_layout.scene import read_scene
from schematic_layout.qa import check_scene


def schematic(pin=None, end=(50.8, 50.8), label=None):
    sheet = f('sheet', f('at',50.8,40.64),f('size',25.4,25.4))
    if pin is not None:
        sheet.append(pin)
    root = f('kicad_sch',f('paper','A4'),sheet,
             f('wire',f('pts',f('xy',40.64,50.8),f('xy',*end))),
             f('label','SOURCE',f('at',40.64,50.8,0),
               f('effects',f('font',f('size',1.27,1.27)))))
    if label:
        root.append(label)
    return root


def terminal(point=(50.8,50.8), angle=180):
    return f('pin','PORT','input',f('at',*point,angle),
             f('effects',f('font',f('size',1.27,1.27))))


class SheetPinGeometryTests(unittest.TestCase):
    def report(self, root):
        return check_scene(read_scene(root))
    def test_outline_gap_is_retained_after_valid_terminal_contact(self):
        report=self.report(schematic(terminal()))
        self.assertEqual('INSUFFICIENT',report['status'])
        self.assertIn('Unsupported sheet object: sheet',report['coverage']['gaps'])
        self.assertEqual(1,report['coverage']['sheet_pins'])


if __name__=='__main__':
    unittest.main()
