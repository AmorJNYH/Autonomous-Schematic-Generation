#!/usr/bin/env python3
"""Audit active hierarchy symbols against body ink and native XML; never edit inputs."""
import argparse
import json
from pathlib import Path
from schematic_layout.symbol_integrity import audit_symbols


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root", type=Path)
    p.add_argument("--netlist", type=Path)
    p.add_argument("--project")
    p.add_argument("--exceptions", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    if args.out.exists() or args.out.is_symlink():
        p.error("Report output already exists; use a fresh path")
    try:
        report = audit_symbols(args.root, args.netlist, args.project,
                               json.loads(args.exceptions.read_text()) if args.exceptions else None)
    except (ValueError, OSError, KeyError, IndexError, TypeError) as exc:
        report = {"status": "FAIL", "error": str(exc)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as f:
        f.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "graphics", "physical_pin_count", "error") if k in report}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
