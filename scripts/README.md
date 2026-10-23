# ASG scripts — developer reference

## Deterministic generation and geometry

`build_circuit.py` compiles Circuit IR v2, resolves named pins/physical units,
automatically places and packs functional blocks, retries with bounded spacing,
and supports baseline diffs plus locked-block regeneration. See
[`circuit-ir.md`](../references/circuit-ir.md). `import_circuit_synth.py` imports
audited upstream JSON; `schematic_layout.importers.skidl_to_ir` reads an already
built SKiDL Circuit. Neither executes an input Python file.

`generate_schematic.py` consumes separate electrical intent and layout JSON,
writes a new single-sheet project, and runs native ERC/XML/PDF verification.
`check_schematic_geometry.py` inspects a serialized native schematic read-only.
Both use `schematic_layout/` (standard-library runtime).

Readable pages are drawn with `schematic_layout.recipes.Sheet`
([`drawing-recipes.md`](../references/drawing-recipes.md));
`schematic_layout.pages.page_intents()` splits one board intent into page
intents with their external nets and rails, and `schematic_layout.root.Root`
assembles the built pages under a hierarchical root with the System_block
cover. `verify_schematic.py` runs every
automated drawing gate on a saved root sheet (ERC, intent partitions and
identity, hierarchy/PDF, symbol integrity, readability, per-sheet geometry,
optional reference and change contracts) and writes `summary.json`. See
[`schematic-generation.md`](../references/schematic-generation.md) for schema,
commands, supported objects, limitations and `AUTOMATED_PASS` semantics.

Native tests compare exact pin partitions. Tests are in `tests/`; optional
upstream source probes do not require installing the complete MCP server.
