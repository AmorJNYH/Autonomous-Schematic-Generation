"""Supplies derived from a driven rail through one declared series passive (e.g. RC-filtered AVCC)."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from schematic_layout.external_supply import filtered_declarations, judge  # noqa: E402
from schematic_layout.pages import page_intents  # noqa: E402

INTENT = {
    "components": [{"ref": "U1", "lib_id": "Amp:AMP"}, {"ref": "R1", "lib_id": "Device:R", "value": "10"},
                   {"ref": "R2", "lib_id": "Device:R", "value": "100k"}, {"ref": "C1", "lib_id": "Device:C"},
                   {"ref": "D1", "lib_id": "Device:D"}],
    "nets": [{"name": "PVCC", "pins": ["U1.1", "R1.1"]}, {"name": "AVCC", "pins": ["R1.2", "U1.2", "C1.1", "R2.1"]},
             {"name": "AVCC2", "pins": ["R2.2", "U1.3"]}, {"name": "GND", "pins": ["C1.2", "U1.4"]}],
    "filtered_supply": [{"net": "AVCC", "from": "PVCC", "via": "R1", "reason": "RC filter for the analog supply pin"}],
}
PARTS = {"R1": ("Device", "R", "10"), "R2": ("Device", "R", "100k"), "C1": ("Device", "C", ""),
         "D1": ("Device", "D", ""), "U1": ("Amp", "AMP", "")}
SHEETS = ["/", "/amp/", "/x/"]


def xml(nets, parts=PARTS, dnp=()):
    comps = "".join(f'<comp ref="{r}"><value>{v}</value><libsource lib="{l}" part="{p}"/>'
                    + ('<property name="dnp"/>' if r in dnp else "") + "</comp>" for r, (l, p, v) in parts.items())
    libparts = "".join(f'<libpart lib="{l}" part="{p}"><pins><pin num="1" type="passive"/><pin num="2" type="passive"/></pins></libpart>'
                       for l, p in sorted({(l, p) for l, p, _ in parts.values()}) if p != "AMP")
    body = "".join(f'<net code="{i}" name="{name}">'
                   + "".join(f'<node ref="{r}" pin="{p}" pintype="{t}"/>' for r, p, t in nodes)
                   + "</net>" for i, (name, nodes) in enumerate(nets.items(), 1))
    design = "".join(f'<sheet number="{i}" name="{s}"/>' for i, s in enumerate(SHEETS, 1))
    return f"<export><design>{design}</design><components>{comps}</components><libparts>{libparts}</libparts><nets>{body}</nets></export>"


def nets(avcc_flag=True, pvcc_driven=True, avcc_driven=False, avcc2_flag=False):
    return {
        "PVCC": [("U1", "1", "power_in"), ("R1", "1", "passive")] + ([("U9", "1", "power_out")] if pvcc_driven else []),
        "/amp/AVCC": [("R1", "2", "passive"), ("U1", "2", "power_in"), ("C1", "1", "passive"), ("R2", "1", "passive")]
                     + ([("FLGX1", "1", "power_out")] if avcc_flag else []) + ([("U8", "1", "power_out")] if avcc_driven else []),
        "/amp/AVCC2": [("R2", "2", "passive"), ("U1", "3", "power_in")] + ([("FLGX2", "1", "power_out")] if avcc2_flag else []),
        "GND": [("C1", "2", "passive"), ("U1", "4", "power_in")],
    }


def renamed(old, new, **changes):
    """INTENT with one net renamed (declaration follows the rename)."""
    intent = copy.deepcopy(INTENT)
    for n in intent["nets"]:
        if n["name"] == old:
            n["name"] = new
    d = intent["filtered_supply"][0]
    for k in ("net", "from"):
        if d[k] == old:
            d[k] = new
    d.update(changes)
    return intent


def declared(**changes):
    return dict(INTENT, filtered_supply=[dict(INTENT["filtered_supply"][0], **changes)])


class FilteredSupplyTests(unittest.TestCase):
    def run_judge(self, n, intent=INTENT, aliases=None, parts=PARTS, dnp=()):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "n.xml"
            path.write_text(xml(n, parts, dnp), encoding="utf-8")
            return judge(path, intent, aliases if aliases is not None else {"FLGX1": "#FLG1"})

    def kinds(self, r):
        return {e["kind"] for e in r["errors"]}

    def test_flag_on_declared_filtered_net_passes(self):
        r = self.run_judge(nets())
        self.assertEqual(r["status"], "PASS", r)

    def test_without_declaration_the_flag_is_undeclared(self):
        r = self.run_judge(nets(), intent={k: v for k, v in INTENT.items() if k != "filtered_supply"})
        self.assertIn("undeclared_pwr_flag", self.kinds(r))

    def test_via_must_be_a_declared_series_part_with_matching_identity(self):
        self.assertIn("filtered_via", self.kinds(self.run_judge(nets(), intent=declared(via="C1", **{"from": "GND"}))))
        diode = copy.deepcopy(INTENT); diode["components"][1]["lib_id"] = "Device:D"
        self.assertIn("filtered_via", self.kinds(self.run_judge(nets(), intent=diode,
                                                               parts=dict(PARTS, R1=("Device", "D", "10")))))
        mpn = copy.deepcopy(INTENT); mpn["components"][1].update(lib_id="Vishay:CRCW060310R0FKEA",
                                                                 fields={"ComponentRole": "series_resistor"})
        self.assertEqual(self.run_judge(nets(), intent=mpn, parts=dict(PARTS, R1=("Vishay", "CRCW060310R0FKEA", "10")))["status"], "PASS")
        self.assertIn("filtered_via", self.kinds(self.run_judge(nets(), parts=dict(PARTS, R1=("Device", "R", "22")))))
        self.assertIn("filtered_via", self.kinds(self.run_judge(nets(), dnp=("R1",))))

    def test_source_must_be_driven_through_the_actual_far_net(self):
        self.assertIn("filtered_source_not_driven", self.kinds(self.run_judge(nets(pvcc_driven=False))))
        n = nets(pvcc_driven=False)
        n["/x/PVCC"] = n.pop("PVCC")                      # undriven far net on another sheet
        n["PVCC"] = [("U9", "1", "power_out"), ("U7", "1", "power_in")]  # unrelated driven net, same leaf
        r = self.run_judge(n)
        self.assertEqual(r["status"], "FAIL")
        self.assertIn("filtered_source_not_driven", self.kinds(r))

    def test_rooted_source_name_and_shorted_or_third_net_via(self):
        n = nets(); n["/x/PVCC"] = n.pop("PVCC")
        r = self.run_judge(n, intent=renamed("PVCC", "/x/PVCC"))
        self.assertEqual(r["status"], "PASS", r)
        shorted = nets(); shorted["/amp/AVCC"].append(("R1", "1", "passive")); shorted["PVCC"].remove(("R1", "1", "passive"))
        self.assertIn("filtered_via_not_between_nets", self.kinds(self.run_judge(shorted)))
        third = nets(); third["PVCC"].remove(("R1", "1", "passive")); third["/x/OTHER"] = [("R1", "1", "passive")]
        self.assertIn("filtered_via_not_between_nets", self.kinds(self.run_judge(third)))

    def test_missing_duplicate_flag_and_driven_target_fail(self):
        self.assertIn("missing_pwr_flag", self.kinds(self.run_judge(nets(avcc_flag=False), aliases={})))
        two = nets(); two["/amp/AVCC"].append(("FLGX2", "1", "power_out"))
        self.assertIn("duplicate_pwr_flag", self.kinds(self.run_judge(two, aliases={"FLGX1": "#FLG1", "FLGX2": "#FLG2"})))
        self.assertIn("net_has_power_source", self.kinds(self.run_judge(nets(avcc_driven=True))))

    def test_declared_net_needs_a_power_input_and_returns_stay_returns(self):
        n = nets(); n["/amp/AVCC"] = [(r, p, "passive" if t == "power_in" else t) for r, p, t in n["/amp/AVCC"]]
        self.assertIn("filtered_net_without_power_input", self.kinds(self.run_judge(n)))
        g = nets(); g["/amp/AGND"] = g.pop("/amp/AVCC")
        self.assertIn("filtered_return_from_supply", self.kinds(self.run_judge(g, intent=renamed("AVCC", "AGND"))))

    def test_declared_native_name_must_match(self):
        n = nets(); n["/amp/FOO"] = n.pop("/amp/AVCC")
        self.assertIn("filtered_net_name_mismatch", self.kinds(self.run_judge(n)))

    def test_external_and_filtered_on_one_net_is_ambiguous(self):
        intent = dict(INTENT, components=INTENT["components"] + [{"ref": "J1", "lib_id": "Connector_Generic:Conn_01x02"}],
                      external_supply=[{"net": "AVCC", "pin": "J1.1", "reason": "x"}])
        intent["nets"] = [dict(n, pins=n["pins"] + ["J1.1"]) if n["name"] == "AVCC" else n for n in INTENT["nets"]]
        n = nets(); n["/amp/AVCC"].append(("J1", "1", "passive"))
        self.assertIn("ambiguous_pwr_flag", self.kinds(self.run_judge(n, intent=intent)))

    def test_chain_of_filtered_supplies_is_qualified_from_the_driven_root(self):
        intent = dict(INTENT, filtered_supply=INTENT["filtered_supply"] + [
            {"net": "AVCC2", "from": "AVCC", "via": "R2", "reason": "second filter stage"}])
        r = self.run_judge(nets(avcc2_flag=True), intent=intent, aliases={"FLGX1": "#FLG1", "FLGX2": "#FLG2"})
        self.assertEqual(r["status"], "PASS", r)
        cycle = dict(INTENT, filtered_supply=[{"net": "AVCC", "from": "AVCC2", "via": "R2", "reason": "x"},
                                              {"net": "AVCC2", "from": "AVCC", "via": "R2", "reason": "y"}])
        self.assertEqual(self.run_judge(nets(pvcc_driven=False, avcc2_flag=True), intent=cycle,
                                        aliases={"FLGX1": "#FLG1", "FLGX2": "#FLG2"})["status"], "FAIL")

    def test_declaration_must_match_intent(self):
        self.assertEqual(filtered_declarations(declared(via="R2"))[1][0]["kind"], "filtered_via_not_in_intent")
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
