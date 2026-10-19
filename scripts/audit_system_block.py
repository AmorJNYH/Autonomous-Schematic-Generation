#!/usr/bin/env python3
"""Audit a System_block cover page: every flow line labelled and attached to a
block, arrowhead or line; a text-labelled isolation boundary (隔离) that stays
straight and crosses no block; every block reached by a flow line.

Drawing audit only; see references/reference-driven-board-design.md.
"""

import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from schematic_layout.sexpr import parse  # noqa: E402
from schematic_layout.system_block import audit_system_block  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", type=Path, help="root .kicad_sch holding the sheet blocks")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    report = audit_system_block(parse(args.root.read_text(encoding="utf-8")))
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
