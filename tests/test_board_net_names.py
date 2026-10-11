"""Board-level intent check: drawn net names must match the intent net of the same pins."""

from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from schematic_layout.native import compare_netlist

INTENT = {
    "components": [
        {"ref": "R1", "lib_id": "Device:R"},
        {"ref": "R2", "lib_id": "Device:R"},
    ],
    "nets": [
        {"name": "BTN_F", "pins": ["R1.1", "R2.1"]},
        {"name": "CLK", "pins": ["R1.2", "R2.2"]},
    ],
}


def xml(names):
    nets = "".join(
        f'<net code="{i}" name="{name}">'
        + "".join(f'<node ref="{p.split(".")[0]}" pin="{p.split(".")[1]}"/>' for p in pins)
        + "</net>"
        for i, (name, pins) in enumerate(names, 1)
    )
    comps = "".join(
        f'<comp ref="{r}"><libsource lib="Device" part="R"/></comp>' for r in ("R1", "R2")
    )
    return f"<export><components>{comps}</components><nets>{nets}</nets></export>"


class BoardNetNameTest(unittest.TestCase):
    def check(self, names):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "netlist.xml"
            p.write_text(xml(names))
            return compare_netlist(p, INTENT)

    def test_matching_hierarchical_and_auto_names_pass(self):
        r = self.check([("/03_control/BTN_F", ["R1.1", "R2.1"]), ("Net-(R1-Pad2)", ["R1.2", "R2.2"])])
        self.assertEqual(r["status"], "PASS", r["errors"])

    def test_swapped_name_labels_fail_although_partitions_match(self):
        r = self.check([("/03_control/CLK", ["R1.1", "R2.1"]), ("/03_control/BTN_F", ["R1.2", "R2.2"])])
        self.assertEqual(r["status"], "FAIL")
        self.assertEqual(
            sorted(e["expected"] for e in r["errors"] if e["kind"] == "net_name_mismatch"),
            ["BTN_F", "CLK"],
        )


if __name__ == "__main__":
    unittest.main()
