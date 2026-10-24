#!/usr/bin/env python3
"""Read-only KiCad geometry gate. Unsupported objects remain INSUFFICIENT."""

import argparse
import hashlib
import json
from pathlib import Path
from schematic_layout.sexpr import parse
from schematic_layout.scene import read_scene
from schematic_layout.qa import check_scene
from schematic_layout.geometry import Box
from schematic_layout.native_circle_contacts import refine_wire_contacts


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("schematic", type=Path)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--layout", type=Path)
    args = ap.parse_args()
    layout = json.loads(args.layout.read_text()) if args.layout else {}
    source_bytes = args.schematic.read_bytes()
    scene = read_scene(parse(source_bytes.decode('utf-8')))
    report = check_scene(
        scene,
        reserved=[Box(*b) for b in layout["reserved"]]
        if "reserved" in layout
        else None,
    )
    report = refine_wire_contacts(args.schematic, report,
                                  expected_source_sha256=hashlib.sha256(source_bytes).hexdigest())
    result = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(result)
    else:
        print(result, end="")
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
