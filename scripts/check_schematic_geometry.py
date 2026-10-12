#!/usr/bin/env python3
"""Read-only KiCad geometry gate. Unsupported objects remain INSUFFICIENT."""

import argparse
import hashlib
import json
from pathlib import Path
from schematic_layout.sexpr import parse
from schematic_layout.scene import read_scene
from schematic_layout.qa import check_scene
from schematic_layout.generate import pin_net_map
from schematic_layout.geometry import Box
from schematic_layout.pages import normalize
from schematic_layout.native_geometry_context import load_page_context
from schematic_layout.native_circle_contacts import refine_wire_contacts


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("schematic", type=Path)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--intent", type=Path)
    ap.add_argument("--layout", type=Path)
    ap.add_argument("--grid-mm", type=float, default=1.27)
    ap.add_argument("--native-context", type=Path, help="Fresh full-project geometry sidecar")
    ap.add_argument("--native-context-sha256", help="Same-job sidecar receipt SHA")
    args = ap.parse_args()
    layout = json.loads(args.layout.read_text()) if args.layout else {}
    pin_nets = None
    if args.intent:
        try:
            pin_nets = pin_net_map(normalize(json.loads(args.intent.read_text())))
        except (ValueError, TypeError, KeyError) as exc:
            ap.error(f"Invalid --intent: {exc}; use nets {{name: [ref.pin]}} or [{{name, pins}}]")
    native_context = None
    context_gap = None
    if args.native_context:
        try:
            native_context = load_page_context(args.native_context, args.schematic, args.native_context_sha256)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            context_gap = "Native geometry context unavailable: " + str(exc)
    source_bytes = args.schematic.read_bytes()
    scene = read_scene(parse(source_bytes.decode('utf-8')), native_context)
    if context_gap:
        scene.gaps.append(context_gap)
    report = check_scene(
        scene,
        grid=layout.get("grid_mm", args.grid_mm),
        reserved=[Box(*b) for b in layout["reserved"]]
        if "reserved" in layout
        else None,
        pin_nets=pin_nets,
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
