"""System_block cover audit: labelled, attached flow lines; a visible boundary; every block reached."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'scripts'))
from schematic_layout.sexpr import Atom, dump, form, parse
from schematic_layout.system_block import audit_system_block

CLI = HERE.parent / 'scripts' / 'audit_system_block.py'


def sheet(name, x, y, w=76.2, h=30.48):
    return form('sheet', form('at', x, y), form('size', w, h), form('uuid', name),
                form('property', 'Sheetname', name, form('at', x, y - 2.54, 0)),
                form('property', 'Sheetfile', name + '.kicad_sch', form('at', x, y + h + 2.54, 0)))


def line(points, width=0.35):
    return form('polyline', form('pts', *[form('xy', x, y) for x, y in points]),
                form('stroke', form('width', width), form('type', Atom('default'))), form('uuid', str(points)))


def arrow(x1, y1, x2, y2):
    d = 2.54 if x2 >= x1 else -2.54
    return [line([(x1, y1), (x2, y2)]), line([(x2 - d, y2 - 1.27), (x2, y2), (x2 - d, y2 + 1.27)])]


def text(s, x, y):
    return form('text', s, form('at', x, y, 0), form('effects', form('font', form('size', 1.27, 1.27))), form('uuid', s))


def root(*items):
    return form('kicad_sch', form('version', 20250114), form('generator', 'test'), form('uuid', 'root'),
                form('paper', 'A3'), form('lib_symbols'), *items)


def good():
    # Input -> PFC -> Flyback | boundary | Secondary; the boundary text names it.
    return root(sheet('02_Input', 25.4, 50.8), sheet('03_PFC', 119.38, 50.8), sheet('04_Flyback', 213.36, 50.8),
                sheet('06_Secondary', 320.04, 50.8),
                *arrow(101.6, 66.04, 119.38, 66.04), text('L/N 整流后 RECT', 110.49, 63.5),
                *arrow(195.58, 66.04, 213.36, 66.04), text('BULK 251–391V', 204.47, 63.5),
                *arrow(289.56, 66.04, 320.04, 66.04), text('T301 二次侧 VRAW', 304.8, 63.5),
                line([(304.8, 30.48), (304.8, 101.6)]), text('隔离边界 4kV', 304.8, 27.94))


class SystemBlockTests(unittest.TestCase):
    def test_good_cover_passes(self):
        r = audit_system_block(good())
        self.assertEqual('PASS', r['status'], r)
        self.assertEqual((4, 3, 3, 1), (r['sheets'], r['flow_lines'], r['arrowheads'], r['boundaries']))

    def test_unlabelled_dangling_and_unreached(self):
        r = audit_system_block(root(
            sheet('02_Input', 25.4, 50.8), sheet('03_PFC', 119.38, 50.8), sheet('07_PD', 213.36, 139.7),
            *arrow(101.6, 66.04, 119.38, 66.04),                       # no text
            line([(157.48, 81.28), (157.48, 120.65)]), text('控制', 160.02, 100.33)))  # ends in the void
        self.assertEqual('FAIL', r['status'])
        self.assertTrue(any(f.startswith('polyline 0:') and 'no text' in f for f in r['findings']), r)
        self.assertTrue(any('[157.48, 120.65]' in f and 'touches no block' in f for f in r['findings']), r)
        self.assertIn('block 07_PD: no flow line reaches it', r['findings'])

    def test_line_through_a_block_and_bent_boundary(self):
        r = audit_system_block(root(
            sheet('03_PFC', 119.38, 50.8), sheet('04_Flyback', 213.36, 50.8), sheet('05_Bias', 119.38, 139.7),
            *arrow(195.58, 66.04, 213.36, 66.04), text('BULK', 204.47, 63.5),
            line([(157.48, 139.7), (157.48, 96.52), (236.22, 96.52), (236.22, 81.28)]), text('驱动 FLY_DRV', 200.0, 93.98),
            line([(298.45, 38.1), (298.45, 101.6), (205.74, 101.6), (205.74, 205.74)]), text('隔离', 300.99, 60.96),
            line([(160.02, 55.88), (160.02, 76.2)]), text('穿块', 162.56, 66.04)))
        self.assertEqual('FAIL', r['status'])
        self.assertTrue(any('isolation boundary bends' in f for f in r['findings']), r)
        self.assertTrue(any('runs through block 03_PFC' in f for f in r['findings']), r)
        self.assertEqual(1, r['boundaries'])

    def test_no_blocks_is_insufficient(self):
        self.assertEqual('INSUFFICIENT', audit_system_block(root())['status'])

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'root.kicad_sch'
            path.write_text(dump(good()) + '\n')
            r = subprocess.run([sys.executable, str(CLI), str(path), '--out', str(Path(tmp) / 'r.json')],
                               capture_output=True, text=True)
            self.assertEqual(0, r.returncode, r.stdout + r.stderr)
            self.assertIn('"PASS"', (Path(tmp) / 'r.json').read_text())
            self.assertEqual('PASS', audit_system_block(parse(path.read_text()))['status'])


if __name__ == '__main__':
    unittest.main()
