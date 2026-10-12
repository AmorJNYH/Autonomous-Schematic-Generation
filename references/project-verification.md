# Verify multi-page delivery and intentional electrical changes

Both tools are read-only, emit JSON and exit nonzero for `FAIL` or `INSUFFICIENT`.
They neither generate a hierarchy nor certify hardware.
Choose a fresh `--out` path for every run. Existing files, symlinks and hardlink
aliases are rejected before processing, and reports are created exclusively.
This also protects malformed input files from being overwritten by error reports.

For pin-to-body artwork, physical pin/type/source evidence and peripheral/stage
contracts, also run the tools in
[symbol-and-peripheral-contracts.md](symbol-and-peripheral-contracts.md).
The hierarchy and change checks below do not replace those independent gates.

## Hierarchy and complete PDF

```sh
python3 scripts/audit_project.py candidate/board.kicad_sch \
  --pdf candidate/board-complete.pdf --expected-pages 12 \
  --baseline baseline/board.kicad_sch --out output/project-audit.json
```

Use the actual expected count, or omit `--expected-pages`; 12 is an example.
Optional Poppler `pdfinfo` reads the real PDF page count. Missing requested PDF
coverage is `INSUFFICIENT`. Count equality does not prove page content/order:
export the current root through KiCad, bind its hash, and review the PDF.

The root directory is the delivery boundary. The tool follows `Sheetfile`,
resolves `${KIPRJMOD}`, counts every instance (including reused child files),
reports missing files/cycles and records file hashes. Nonportable paths and
unresolved variables fail. Missing project annotation is a coverage gap; use
`--project NAME` if the root filename differs from the annotation project name.
Nonconsecutive page identifiers are legal; duplicate identifiers are reported.

Reference/unit pairs use the selected instance context. Shared cached library
IDs must agree; multi-unit references must share a complete consistent pin
definition. Signatures cover unit/style, number/name/type/shape/hidden state
independently of artwork. Unresolved symbol inheritance is insufficient. This
also checks active unit pins and agreement with the instance annotation. It
does not resolve `sym-lib-table`, check footprint pads or assess graphic layout.

With `--baseline`, file/instance/reference and pin-signature changes are reported.
This delta is descriptive, not approval of removals or arbitrary changes. Bind
the expected page list and protected files to the authorized scope.

## Electrical-change contract

Export both root netlists as `kicadxml`, then run:

```sh
python3 scripts/verify_design_change.py baseline.xml candidate.xml \
  change.json --out output/design-change.json
```

A complete minimal contract for a resistor value change:

```json
{
  "schema_version": 1,
  "component_changes": {
    "R1": {"value": {"before": "1k", "after": "2k"}}
  }
}
```

Only that identity change is permitted; all physical partitions and other
component properties must remain unchanged. Set `baseline_sha256` to the frozen
XML hash for stored/reused contracts. Reports bind both actual XML hashes.

| Optional field | Meaning |
| --- | --- |
| `remove_components` | Unique list of baseline references; affected nets also need explicit replacement. |
| `add_components` | New reference → `{ "identity": ..., "pins": ["1", "2"] }`; list all physical pin numbers. A reference also listed in `remove_components` is a replacement (symbol/package swap with renumbered or additional pins): its old pins are dropped and every new pin must appear in `replace_partitions`. |
| `component_changes` | Existing reference → identity field → exact `before` / `after`; verify the baseline precondition. |
| `replace_partitions` | List of `{ "before": [["J1.1", "R1.1"]], "after": [["J1.1"], ["R1.1"]] }`; each inner list is a complete physical net. Empty outer lists mean no nets, not empty nets. |
| `named_nets` | Required exact candidate names → complete pin sets; declare interfaces whose names matter downstream. |
| `same_net` | Lists of at least two known physical pins that must share a net. |
| `distinct_net` | Lists of pins that must all be on separate nets; this does not prove galvanic isolation. |

An identity has exactly `value`, `footprint`, `datasheet`, `lib_id`, `dnp` and
`fields`. Text values are strings, `dnp` is Boolean, `fields` is a string map.
Example: `{ "value": "10k", "footprint": "", "datasheet": "", "lib_id":
"Device:R", "dnp": true, "fields": {} }`. Blank fixture fields do not qualify
a real BOM. Review presentation-driven library-ID changes explicitly.

Every replaced `before` partition must exist once. The final expected graph must
retain every remaining baseline pin and all declared new pins exactly once.
Unknown, duplicate, missing and invented pins fail. `#` references are virtual
and excluded consistently; physical NC singleton nets remain significant. Local
net names may change without changing partitions; use `named_nets` for important
names. `verify_schematic.py` still requires drawn names to match the intent, so
update the intent names in the same revision. Expected partitions must come from independent intent, not the candidate.

Native exported pins are not independent datasheet evidence. This tool does not
check package mapping, unexported hidden pins, assembled DNP operation or analog
performance. Keep source tables, footprint/population and performance checks.

```sh
python3 -m unittest discover -s tests -p 'test_project_audit.py' -v
python3 -m unittest discover -s tests -p 'test_design_change.py' -v
```


## Electrical redesign preflight

For electrical revisions also run the [change preflight](change-preflight.md) before
writing the candidate and at final delivery. Include its status and unresolved
assumptions alongside native/ERC/readability results. Artifact freshness alone does
not detect a freshly generated stale note; facts bindings check declared current values.

## ERC summary object binding

Keep the original native ERC report and bind each summarized violation through
its actual UUID/object to the current source hierarchy instance, pin and native
net before attributing it to a rail. References, display names and coordinates
are useful locators, but their text alone does not establish the affected object
or rail; reused sheets and renamed nets can make such guesses wrong. Include the
source/report hashes and object locator used for the attribution in the review
evidence. If an object cannot be resolved, retain the original violation and
state the unresolved attribution rather than inventing a rail diagnosis or
quieting it. This is a review instruction, not a new required schema field or a
change to ERC thresholds, power flags or existing gates.

### Automatic-looking names need source evidence

For board verification, XML alone cannot distinguish a hand-written `Net-(...)`
(or `unconnected-(...)`) label from a KiCad generated name. `verify_schematic.py`
and the native board verifier use a same-source native naming counterfactual
when such a name differs from the intent: re-export the unchanged hierarchy,
then consistently rename scalar labels, sheet interfaces, power names and hidden
power-pin names in a diagnostic copy. Both exports must retain the complete
physical partitions and component identity, including UUID sheet paths. A
copy-location `Sheetfile` property is excluded from identity comparison; ordinary
component fields are retained. No source design is edited.

A changed native name carrying the unique diagnostic marker proves an explicit
name on that partition. A proven automatic name may differ from the intent,
including when its pin name contains `/`. The origin audit leaves bus, encoded/variable interface names,
inherited or missing embedded symbol definitions and unbound source/XML
unqualified; this does not qualify the separate encoding contract. The public
XML-only `compare_netlist` API returns `INSUFFICIENT` for a differing automatic-
looking name without source evidence. Page layout checks retain their existing
scope. Inspect `net-name-origin.json` and its source hashes and native commands;
a passing partition comparison alone does not establish name provenance.
# Finite hierarchy geometry

The runner's fresh hierarchy SVG channel can qualify supported no-sheet-pin
rectangular frames and complete shown sheet fields, and capture finite uniquely
bound pin-name ink. Unknown rendering/instance/number/outline profiles retain
coverage gaps; this does not make an incomplete page PASS. See
[native geometry scope](native-geometry.md) for exact binding, reject rules and
the audit-only serialized sidecar boundary. Ordinary in-memory build defaults
are unchanged.
