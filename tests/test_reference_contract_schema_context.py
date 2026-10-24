"""Public API schema diagnostics identify structure without exposing values."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from schematic_layout.reference_contract import verify_reference


class ReferenceContractSchemaContextTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        for path in (ROOT / "tests/fixtures/reference_contract").iterdir():
            shutil.copy2(path, self.base / path.name)
        self.net = self.base / "netlist.xml"
        self.contract = json.loads((self.base / "contract.json").read_text())

    def error(self, contract):
        with self.assertRaises(ValueError) as caught:
            verify_reference(self.net, contract, self.base)
        return str(caught.exception)

    @staticmethod
    def locate(contract, tokens):
        obj = contract
        for token in tokens:
            obj = obj[token]
        return obj

    def test_missing_extra_and_nonobject_at_each_schema_boundary(self):
        cases = [
            ((), "schema_version"), (("scope",), "feature_ids"),
            (("sources", "demo"), "sha256"),
            (("pin_maps", "U1"), "source"),
            (("pin_maps", "U1", "identity"), "mpn"),
            (("pin_maps", "U1", "pins", "1"), "types"),
            (("checks", 0), "locator"), (("checks", 0, "expected"), "dnp"),
            (("features", 0), "boundary"),
            (("features", 0, "stages", 0), "role"),
        ]
        sentinel = "FIELD_VALUE_MUST_NOT_APPEAR"
        for tokens, missing in cases:
            path = "contract" + "".join("/" + str(t) for t in tokens)
            for mutation in ("missing", "extra", "nonobject"):
                with self.subTest(path=path, mutation=mutation):
                    contract = copy.deepcopy(self.contract)
                    obj = self.locate(contract, tokens)
                    if mutation == "missing":
                        del obj[missing]
                        expected = path + "/" + missing
                    elif mutation == "extra":
                        obj["unexpected"] = sentinel
                        expected = path + "/unexpected"
                    else:
                        if tokens:
                            self.locate(contract, tokens[:-1])[tokens[-1]] = sentinel
                        else:
                            contract = sentinel
                        expected = path
                    message = self.error(contract)
                    self.assertIn(expected, message)
                    self.assertNotIn(sentinel, message)

    def test_missing_id_and_unknown_kind_retain_check_index(self):
        for field in ("id", "kind"):
            contract = copy.deepcopy(self.contract)
            del contract["checks"][1][field]
            self.assertIn("contract/checks/1/" + field, self.error(contract))
        contract = copy.deepcopy(self.contract)
        contract["checks"][1]["kind"] = "SECRET_UNSUPPORTED_KIND"
        message = self.error(contract)
        self.assertIn("contract/checks/1/kind", message)
        self.assertNotIn("SECRET_UNSUPPORTED_KIND", message)

    def test_multiple_objects_and_nonzero_stage_do_not_reuse_context(self):
        contract = copy.deepcopy(self.contract)
        contract["sources"]["second"] = copy.deepcopy(contract["sources"]["demo"])
        del contract["sources"]["second"]["sha256"]
        self.assertIn("contract/sources/second/sha256", self.error(contract))
        contract = copy.deepcopy(self.contract)
        contract["pin_maps"]["U2"] = copy.deepcopy(contract["pin_maps"]["U1"])
        del contract["pin_maps"]["U2"]["pins"]["2"]["names"]
        self.assertIn("contract/pin_maps/U2/pins/2/names", self.error(contract))
        contract = copy.deepcopy(self.contract)
        feature = copy.deepcopy(contract["features"][0])
        feature["id"] = "second"
        del feature["stages"][1]["role"]
        contract["features"].append(feature)
        self.assertIn("contract/features/1/stages/1/role", self.error(contract))

    def test_identifier_tokens_are_escaped_without_losing_location(self):
        contract = copy.deepcopy(self.contract)
        contract["sources"]["a/~"] = contract["sources"].pop("demo")
        del contract["sources"]["a/~"]["sha256"]
        self.assertIn("contract/sources/a~1~0/sha256", self.error(contract))
        contract = copy.deepcopy(self.contract)
        contract["pin_maps"]["U/~"] = contract["pin_maps"].pop("U1")
        pins = contract["pin_maps"]["U/~"]["pins"]
        pins["p/~"] = pins.pop("1")
        del pins["p/~"]["types"]
        self.assertIn("contract/pin_maps/U~1~0/pins/p~1~0/types", self.error(contract))

    def test_multiple_missing_and_extra_fields_are_stably_sorted(self):
        messages = []
        for order in (("zeta", "alpha"), ("alpha", "zeta")):
            contract = copy.deepcopy(self.contract)
            del contract["scope"]["feature_ids"]
            del contract["scope"]["core_refs"]
            for key in order:
                contract["scope"][key] = "UNPRINTED_SECRET"
            messages.append(self.error(contract))
        self.assertEqual(messages[0], messages[1])
        self.assertIn("missing ['contract/scope/feature_ids']", messages[0])     # core_refs is optional
        self.assertIn("extra ['contract/scope/alpha', 'contract/scope/zeta']", messages[0])
        self.assertNotIn("UNPRINTED_SECRET", messages[0])

    def test_non_json_extra_key_still_raises_valueerror(self):
        self.contract["scope"][42] = "UNPRINTED_SECRET"
        message = self.error(self.contract)
        self.assertIn("contract/scope", message)
        self.assertNotIn("UNPRINTED_SECRET", message)

    def test_cli_preserves_fail_and_precise_nested_error(self):
        for tokens, field in ((("pin_maps", "U1", "pins", "1"), "types"),
                              (("features", 0, "stages", 1), "role")):
            with self.subTest(tokens=tokens):
                contract = copy.deepcopy(self.contract)
                del self.locate(contract, tokens)[field]
                path = self.base / "invalid.json"
                path.write_text(json.dumps(contract))
                out = self.base / (field + ".json")
                proc = subprocess.run([sys.executable, str(ROOT / "scripts/verify_reference_contract.py"),
                                       str(self.net), str(path), "--out", str(out)], capture_output=True)
                self.assertNotEqual(proc.returncode, 0)
                report = json.loads(out.read_text())
                self.assertEqual(report["status"], "FAIL")
                expected = "contract/" + "/".join(map(str, tokens)) + "/" + field
                self.assertIn(expected, report["error"])

    def test_series_support_bypass_is_rejected_by_existing_distinct_check(self):
        tree = ET.parse(self.net)
        root = tree.getroot()
        component = ET.SubElement(root.find("components"), "comp", ref="R1")
        ET.SubElement(component, "value").text = "10k"
        ET.SubElement(component, "footprint").text = "Demo:R"
        ET.SubElement(component, "libsource", lib="Device", part="R")
        nets = root.find("nets")
        upstream = nets.find("net[@name='IN']")
        load = upstream.find("node[@ref='J1']")
        upstream.remove(load)
        ET.SubElement(upstream, "node", ref="R1", pin="1", pintype="passive")
        downstream = ET.SubElement(nets, "net", code="5", name="SERIES_LOAD")
        downstream.append(load)
        ET.SubElement(downstream, "node", ref="R1", pin="2", pintype="passive")
        tree.write(self.net)
        common = {"source": "demo", "locator": "Synthetic series support test only"}
        self.contract["checks"].extend([
            dict(common, id="series-part", kind="component", ref="R1",
                 expected={"value": "10k", "footprint": "Demo:R", "lib_id": "Device:R", "dnp": False}),
            dict(common, id="series-in", kind="same_net", pins=["U1.1", "R1.1"]),
            dict(common, id="series-out", kind="same_net", pins=["R1.2", "J1.1"]),
            dict(common, id="series-distinct", kind="distinct_nets", pins=["R1.1", "R1.2"]),
        ])
        self.assertEqual(verify_reference(self.net, self.contract, self.base)["status"], "PASS")
        upstream.extend(list(downstream))
        nets.remove(downstream)
        tree.write(self.net)
        report = verify_reference(self.net, self.contract, self.base)
        self.assertEqual(report["checks"]["series-in"]["status"], "PASS")
        self.assertEqual(report["checks"]["series-out"]["status"], "PASS")
        self.assertEqual(report["checks"]["series-distinct"]["status"], "FAIL")
        self.assertEqual(report["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
