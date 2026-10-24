#!/usr/bin/env python3
"""Audit one delivered native hierarchy; optionally compare an older root."""
import argparse
import json
from pathlib import Path
from schematic_layout.project_audit import audit_project, compare_projects


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("root")
    p.add_argument("--pdf", help="Current complete PDF, not a selected-page extract")
    p.add_argument("--project", help="Native project annotation name; defaults to root filename stem")
    p.add_argument("--expected-pages", type=int)
    p.add_argument("--netlist", type=Path, help="Native XML for independent export inventory diagnostics")
    p.add_argument("--baseline", help="Older root schematic, used for a descriptive file/instance delta")
    p.add_argument("--out", required=True)
    args = p.parse_args()
    out = Path(args.out)
    if out.exists() or out.is_symlink():
        p.error("Report output already exists; choose a fresh path")
    try:
        result = audit_project(args.root, args.pdf, args.project, args.expected_pages, netlist=args.netlist)
        if args.baseline:
            baseline = audit_project(args.baseline, project=args.project)
            result["baseline_status"] = baseline["status"]
            result["delta"] = compare_projects(baseline, result)
            if baseline["status"] != "PASS":
                result["baseline_issues"] = {k: baseline[k] for k in ["errors", "coverage_gaps"]}
    except (ValueError, OSError, KeyError, IndexError, TypeError) as exc:
        result = {"status": "FAIL", "error": str(exc)}
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ["status", "page_count", "component_count"] if k in result}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
