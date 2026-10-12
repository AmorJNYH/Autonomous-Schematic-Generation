"""Supplies derived from a driven rail through one declared series passive (e.g. RC-filtered AVCC)."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from schematic_layout.external_supply import filtered_declarations, judge  # noqa: E402
from schematic_layout.pages import page_intents  # noqa: E402

INTENT = {
    "components": [{"ref": "U1", "lib_id": "Amp:AMP"}, {"ref": "R1", "lib_id": "Device:R"},
                   {"ref": "R2", "lib_id": "Device:R"}, {"ref": "C1", "lib_id": "Device:C"}],
    "nets": [{"name": "PVCC", "pins": ["U1.1", "R1.1"]}, {"name": "AVCC", "pins": ["R1.2", "U1.2", "C1.1", "R2.1"]},
             {"name": "AVCC2", "pins": ["R2.2", "U1.3"]}, {"name": "GND", "pins": ["C1.2", "U1.4"]}],
    "filtered_supply": [{"net": "AVCC", "from": "PVCC", "via": "R1", "reason": "RC filter for the analog supply pin"}],
}
PARTS = {"R1": ("Device", "R"), "R2": ("Device", "R"), "C1": ("Device", "C"), "U1": ("Amp", "AMP")}


def xml(nets, parts=PARTS):
    comps = "".join(f'<comp ref="{r}"><libsource lib="{l}" part="{p}"/></comp>' for r, (l, p) in parts.items())
    libparts = "".join(f'<libpart lib="{l}" part="{p}"><pins><pin num="1" type="passive"/><pin num="2" type="passive"/></pins></libpart>'
                       for l, p in sorted(set(parts.values())) if p != "AMP")
    body = "".join(f'<net code="{i}" name="{name}">'
                   + "".join(f'<node ref="{r}" pin="{p}" pintype="{t}"/>' for r, p, t in nodes)
                   + "</net>" for i, (name, nodes) in enumerate(nets.items(), 1))
    return f"<export><components>{comps}</components><libparts>{libparts}</libparts><nets>{body}</nets></export>"


def nets(avcc_flag=True, pvcc_driven=True, avcc_driven=False, avcc2_flag=False):
    return {
        "PVCC": [("U1", "1", "power_in"), ("R1", "1", "passive")] + ([("U9", "1", "power_out")] if pvcc_driven else []),
        "/amp/AVCC": [("R1", "2", "passive"), ("U1", "2", "power_in"), ("C1", "1", "passive"), ("R2", "1", "passive")]
                     + ([("FLGX1", "1", "power_out")] if avcc_flag else []) + ([("U8", "1", "power_out")] if avcc_driven else []),
        "/amp/AVCC2": [("R2", "2", "passive"), ("U1", "3", "power_in")] + ([("FLGX2", "1", "power_out")] if avcc2_flag else []),
        "GND": [("C1", "2", "passive"), ("U1", "4", "power_in")],
    }


class FilteredSupplyTests(unittest.TestCase):
    def run_judge(self, n, intent=INTENT, aliases=None, parts=PARTS):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "n.xml"
            path.write_text(xml(n, parts), encoding="utf-8")
            return judge(path, intent, aliases if aliases is not None else {"FLGX1": "#FLG1"})

    def kinds(self, r):
        return {e["kind"] for e in r["errors"]}

    def test_flag_on_declared_filtered_net_passes(self):
        r = self.run_judge(nets())
        self.assertEqual(r["status"], "PASS", r)

    def test_without_declaration_the_flag_is_undeclared(self):
        r = self.run_judge(nets(), intent={k: v for k, v in INTENT.items() if k != "filtered_supply"})
        self.assertIn("undeclared_pwr_flag", self.kinds(r))

    def test_capacitor_is_not_a_series_supply_path(self):
        intent = dict(INTENT, filtered_supply=[dict(INTENT["filtered_supply"][0], via="C1", **{"from": "GND"})])
        r = self.run_judge(nets(), intent=intent)
        self.assertIn("filtered_via", self.kinds(r))

    def test_source_must_be_driven(self):
        r = self.run_judge(nets(pvcc_driven=False))
        self.assertIn("filtered_source_not_driven", self.kinds(r))

    def test_missing_flag_and_driven_target_fail(self):
        self.assertIn("missing_pwr_flag", self.kinds(self.run_judge(nets(avcc_flag=False), aliases={})))
        self.assertIn("net_has_power_source", self.kinds(self.run_judge(nets(avcc_driven=True))))

    def test_chain_of_filtered_supplies_is_qualified_from_the_driven_root(self):
        intent = dict(INTENT, filtered_supply=INTENT["filtered_supply"] + [
            {"net": "AVCC2", "from": "AVCC", "via": "R2", "reason": "second filter stage"}])
        r = self.run_judge(nets(avcc2_flag=True), intent=intent, aliases={"FLGX1": "#FLG1", "FLGX2": "#FLG2"})
        self.assertEqual(r["status"], "PASS", r)

    def test_declaration_must_match_intent(self):
        bad = dict(INTENT, filtered_supply=[dict(INTENT["filtered_supply"][0], via="R2")])
        self.assertEqual(filtered_declarations(bad)[1][0]["kind"], "filtered_via_not_in_intent")
        with self.assertRaises(ValueError):
            filtered_declarations(dict(INTENT, filtered_supply=[{"net": "AVCC", "via": "R1", "reason": "x"}]))

    def test_page_intent_keeps_declaration_on_the_series_part_page(self):
        board = {"components": [{"ref": "U1", "fields": {"Circuit": "amp"}}, {"ref": "R1", "fields": {"Circuit": "power"}},
                                {"ref": "R2", "fields": {"Circuit": "amp"}}, {"ref": "C1", "fields": {"Circuit": "amp"}}],
                 "nets": INTENT["nets"], "filtered_supply": INTENT["filtered_supply"]}
        pages = page_intents(board, rails=("PVCC", "GND"))
        self.assertEqual(pages["power"]["intent"]["filtered_supply"], INTENT["filtered_supply"])
        self.assertNotIn("filtered_supply", pages["amp"]["intent"])


if __name__ == "__main__":
    unittest.main()
