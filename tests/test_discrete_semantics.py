"""Discrete symbol meaning must match the exact part, not only its pin numbers."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from schematic_layout import discrete_semantics as ds
from schematic_layout.discrete_semantics import audit_discrete_semantics, mpn_meaning

SYMBOLS = {
    'Device:D_TVS': ('Bidirectional transient-voltage-suppression diode', ('A1', 'A2')),
    'Device:D_Zener': ('Zener diode', ('K', 'A')),
    'Test:TVS_Uni': ('', ('K', 'A')),
    'Device:Q_PMOS': ('P-MOSFET transistor, gate/source/drain', ('G', 'S', 'D')),
    'Device:Q_NMOS': ('N-MOSFET transistor, gate/source/drain', ('G', 'S', 'D')),
    'Device:Q_NPN': ('NPN transistor, base/emitter/collector', ('B', 'E', 'C')),
}


def cache(lib_ids):
    out = []
    for lib in lib_ids:
        desc, pins = SYMBOLS[lib]
        body = ' '.join('(pin passive line (at 0 0 0) (length 2.54) (name "%s") (number "%d"))' % (p, i + 1)
                        for i, p in enumerate(pins))
        out.append('(symbol "%s" (property "Description" "%s") (symbol "x_1_1" %s))' % (lib, desc, body))
    return '(kicad_sch (version 20250114) (lib_symbols %s))' % ' '.join(out)


class DiscreteSemanticsTests(unittest.TestCase):
    def run_case(self, parts, text=None):
        """parts: [(ref, lib_id, mpn)]; text: datasheet first-pages text for every part."""
        with tempfile.TemporaryDirectory() as tmp:
            sheet = Path(tmp) / 'page.kicad_sch'
            sheet.write_text(cache({lib for _, lib, _ in parts}))
            pdf = Path(tmp) / 'part.pdf'
            pdf.write_text('stub')
            intent = {'components': [{'ref': r, 'lib_id': lib, 'mpn': mpn, 'datasheet': str(pdf) if text else ''}
                                     for r, lib, mpn in parts]}
            with mock.patch.object(ds, 'datasheet_text', return_value=text):
                return audit_discrete_semantics([sheet], intent, [tmp])

    def test_bidirectional_symbol_for_unidirectional_datasheet_fails(self):
        r = self.run_case([('D702', 'Device:D_TVS', 'PESD5V0L1UA')],
                          'Low capacitance unidirectional ESD protection diode. Unidirectional ESD protection of one line')
        self.assertEqual('FAIL', r['status'])
        self.assertEqual('symbol_semantics_mismatch', r['errors'][0]['code'])
        self.assertIn('bidirectional', r['errors'][0]['detail'])

    def test_unidirectional_ka_symbol_passes(self):
        r = self.run_case([('D702', 'Test:TVS_Uni', 'PESD5V0L1UA')], 'Low capacitance unidirectional ESD protection diode')
        self.assertEqual('PASS', r['status'], r)

    def test_tvs_mpn_suffix_decides_family_datasheets(self):
        self.assertEqual('unidirectional', mpn_meaning('SMBJ24A-E3/52'))
        self.assertEqual('bidirectional', mpn_meaning('SMBJ24CA-E3/52'))
        self.assertEqual('unidirectional', mpn_meaning('P6KE33A'))
        self.assertIsNone(mpn_meaning('PESD5V0L1UA'))
        family_sheet = 'Available in unidirectional and bidirectional. VBR (bidirectional) 6.4 V to 231 V'
        self.assertEqual('FAIL', self.run_case([('D706', 'Device:D_TVS', 'SMBJ24A-E3/52')], family_sheet)['status'])
        self.assertEqual('PASS', self.run_case([('D706', 'Device:D_TVS', 'SMBJ24CA-E3/52')], family_sheet)['status'])
        self.assertEqual('FAIL', self.run_case([('D706', 'Device:D_Zener', 'SMBJ24CA')], family_sheet)['status'])

    def test_mosfet_channel_mismatch_fails(self):
        r = self.run_case([('Q701', 'Device:Q_PMOS', 'NTMFS5C604NL')], 'Power MOSFET 60 V, single N-Channel. N-Channel')
        self.assertEqual('FAIL', r['status'])
        self.assertEqual('PASS', self.run_case([('Q701', 'Device:Q_NMOS', 'NTMFS5C604NL')], 'single N-Channel')['status'])

    def test_complement_named_in_passing_still_decides(self):
        text = 'NPN switching transistor. NPN general purpose. NPN. PNP complement: MMBT3906'
        self.assertEqual('PASS', self.run_case([('Q302', 'Device:Q_NPN', 'MMBT3904')], text)['status'])

    def test_ambiguous_datasheet_is_unresolved_not_pass(self):
        r = self.run_case([('Q1', 'Device:Q_NMOS', 'DUAL')], 'N-channel and P-channel pair. N-channel. P-channel')
        self.assertEqual('INSUFFICIENT', r['status'])
        self.assertEqual('Q1', r['unresolved'][0]['ref'])

    def test_no_polarity_evidence_is_not_applicable(self):
        r = self.run_case([('D303', 'Device:D_Zener', 'BZT52H-C5V1')], 'Single Zener diodes in a SOD123F package')
        self.assertEqual('NOT_APPLICABLE', r['status'])
        r = self.run_case([('D1', 'Device:D_TVS', '')])
        self.assertEqual('NOT_APPLICABLE', r['status'])


if __name__ == '__main__':
    unittest.main()
