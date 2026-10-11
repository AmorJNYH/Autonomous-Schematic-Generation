"""Board-level intent check: drawn net names must match the intent net of the same pins."""

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from schematic_layout.native import compare_netlist

PINS = [["R1.1", "R2.1"], ["R1.2", "R2.2"]]
SHEETS = ["/", "/03_control/", "/Debugger/", "/Headers/"]


def intent(*names):
    return {
        "components": [{"ref": r, "lib_id": "Device:R"} for r in ("R1", "R2")],
        "nets": [{"name": n, "pins": p} for n, p in zip(names, PINS)],
    }


def xml(*names):
    sheets = "".join(f'<sheet number="{i}" name="{s}"/>' for i, s in enumerate(SHEETS, 1))
    nets = "".join(
        f'<net code="{i}" name="{name}">'
        + "".join(f'<node ref="{p.split(".")[0]}" pin="{p.split(".")[1]}"/>' for p in pins)
        + "</net>"
        for i, (name, pins) in enumerate(zip(names, PINS), 1)
    )
    comps = "".join(
        f'<comp ref="{r}"><libsource lib="Device" part="R"/></comp>' for r in ("R1", "R2")
    )
    return (f"<export><design>{sheets}</design><components>{comps}</components>"
            f"<nets>{nets}</nets></export>")


class BoardNetNameTest(unittest.TestCase):
    def check(self, wanted, drawn, layout=None):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "netlist.xml"
            p.write_text(xml(*drawn))
            return compare_netlist(p, intent(*wanted), layout)

    def mismatches(self, result):
        return sorted(e["expected"] for e in result["errors"] if e["kind"] == "net_name_mismatch")

    def test_sheet_path_prefix_and_automatic_names_pass(self):
        r = self.check(["BTN_F", "CLK"], ["/03_control/BTN_F", "Net-(R1-Pad2)"])
        self.assertEqual(r["status"], "PASS", r["errors"])

    def test_automatic_names_whose_pin_names_contain_a_slash_pass(self):
        for drawn in (["Net-(U7-SDO/SAO)", "/03_control/Net-(U2-I/O1)"],
                      ["unconnected-(U2-I/O1-Pad1)", "Net-(MICRO_SD1-CD/DAT3/CS)"]):
            with self.subTest(drawn=drawn):
                r = self.check(["ACC_SA0", "TP_IO"], drawn)
                self.assertEqual(r["status"], "PASS", r["errors"])

    def test_intent_names_with_slashes_match_exactly(self):
        r = self.check(["ESP0/STAT", "/Debugger/BOOT"], ["ESP0/STAT", "/Debugger/BOOT"])
        self.assertEqual(r["status"], "PASS", r["errors"])

    def test_swapped_name_labels_fail_although_partitions_match(self):
        r = self.check(["BTN_F", "CLK"], ["/03_control/CLK", "/03_control/BTN_F"])
        self.assertEqual(self.mismatches(r), ["BTN_F", "CLK"])

    def test_same_leaf_swapped_between_sheets_fails(self):
        r = self.check(["/Debugger/RX", "/Headers/RX"], ["/Headers/RX", "/Debugger/RX"])
        self.assertEqual(self.mismatches(r), ["/Debugger/RX", "/Headers/RX"])

    def test_a_rooted_intent_name_does_not_accept_a_global_label(self):
        r = self.check(["/X", "Y"], ["X", "Y"])
        self.assertEqual(self.mismatches(r), ["/X"])

    def test_page_level_layout_check_does_not_also_run_the_board_check(self):
        r = self.check(["BTN_F", "CLK"], ["/03_control/CLK", "/03_control/BTN_F"], layout={"nets": {}})
        self.assertEqual(self.mismatches(r), [])


if __name__ == "__main__":
    unittest.main()
