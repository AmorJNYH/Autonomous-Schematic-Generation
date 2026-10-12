"""Source-qualified name checks; deliberately no regex source inference."""
from pathlib import Path
import sys
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'tests')]
from schematic_layout.native import compare_netlist, find_cli
from schematic_layout.net_name_origin import audit_name_origins
from test_board_net_names import xml, intent, PINS

class OriginTests(unittest.TestCase):
    def check(self, origins=None, drawn='Net-(U7-SDO/SAO)', expected='CLOCK'):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'native.xml';p.write_text(xml(drawn,'Y'))
            return compare_netlist(p,intent(expected,'Y'),name_origins=origins)
    def test_unknown_is_insufficient(self):
        r=self.check();self.assertEqual(r['status'],'INSUFFICIENT')
        self.assertEqual(r['coverage_gaps'][0]['pins'],PINS[0])
    def test_explicit_fake_automatic_name_fails(self):
        for n in ('Net-(U7-SDO/SAO)','unconnected-(U7-I/O1-Pad1)','X/Net-(anything)tail'):
            r=self.check({frozenset(PINS[0]):'EXPLICIT'},n)
            self.assertEqual(r['status'],'FAIL');self.assertEqual(r['errors'][0]['kind'],'net_name_mismatch')
    def test_proven_automatic_slash_passes(self):
        self.assertEqual(self.check({frozenset(PINS[0]):'AUTOMATIC'})['status'],'PASS')
    def test_exact_name_needs_no_origin(self):
        self.assertEqual(self.check(expected='Net-(U7-SDO/SAO)')['status'],'PASS')
    def test_nonautomatic_wrong_name_still_fails(self):
        self.assertEqual(self.check(drawn='WRONG')['status'],'FAIL')
    def test_origin_bound_to_partition(self):
        self.assertEqual(self.check({frozenset(PINS[1]):'AUTOMATIC'})['status'],'INSUFFICIENT')
    def test_missing_hierarchy_never_exports(self):
        with tempfile.TemporaryDirectory() as d, patch('schematic_layout.net_name_origin.subprocess.run') as run:
            d=Path(d);x=d/'native.xml';x.write_text(xml('X','Y'))
            r=audit_name_origins(d/'missing.kicad_sch',x,'cli',d/'out')
            self.assertEqual(r['status'],'INSUFFICIENT');run.assert_not_called()
@unittest.skipUnless(find_cli(), 'Native KiCad unavailable')
class NativeOriginTests(unittest.TestCase):
    def test_full_same_source_native_controls(self):
        with tempfile.TemporaryDirectory() as d:
            run = subprocess.run([sys.executable, '-B', str(ROOT / 'tests/fixtures/drawing/net_name_origin_controls.py'),
                                  '--output', d], capture_output=True, text=True, timeout=120)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            rows = json.loads((Path(d) / 'native-controls.json').read_text())
            self.assertEqual(len(rows), 11)
            for row in rows:
                with self.subTest(case=row['tag']):
                    self.assertEqual(row['command']['returncode'], 0)
                    if row['tag'] in ('global-manual','local-manual','hierarchical','multiinstance','power-manual','hidden-power-manual'):
                        self.assertEqual(row['audit']['status'], 'MEASURED')
                        self.assertEqual(row['result']['status'], 'FAIL')
                        self.assertTrue(any(e['kind']=='net_name_mismatch' for e in row['result']['errors']))
                    elif row['tag']=='automatic-slash':
                        self.assertEqual(row['audit']['status'], 'MEASURED')
                        self.assertEqual(row['result']['status'], 'PASS')
                    else:
                        self.assertEqual(row['audit']['status'], 'INSUFFICIENT')
                        self.assertTrue(row['audit']['gaps'])

if __name__=='__main__':unittest.main()
