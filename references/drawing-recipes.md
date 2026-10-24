# Drawing recipes (readable sheets from pin geometry)

Use for every sheet a person will read, new or redrawn. The agent writes a short
page script that states **structure**; `schematic_layout.recipes.Sheet` derives
the geometry from the real library pins and writes explicit wires. This is the
construction layer behind [human-readable-routing.md](human-readable-routing.md).

Readable wiring is a placement problem. When a pin faces away from the net it
joins, every router has to loop back. On a 100 W charger the hand-placed v0.2.2
pages had 29 different-net crossings and 237 bends. The same circuit, redrawn by
placing support parts from their pins with explicit spines, had 0 crossings and
82 bends.

## Workflow

1. Write the presentation plan (reading path, blocks, rails, labels) per
   human-readable-routing.md section 1. For a board, get each page's intent and
   external nets from `pages.page_intents(board, rails=...)`.
2. `sheet = Sheet(intent, rails={...}, external=[...])` and read `sheet.plan`:
   the proposed role of every part and the label role of every net.
3. Write the page script following the outline rules below: place anchors,
   then draw every other part with the recipe its role allows. Keep coordinates
   only for anchors and deliberate Z legs. Record each intended deviation with
   `sheet.justify(part_or_net, reason)` where it is made.
   List the actual planned local names and fonts before placing their runs.
   For the relevant series leg or own-pin stub, explicitly reserve
   `max(existing_gap, sheet.name_run_steps(net, font))`, then call `name` with
   that same raw logical name and font. Budget each net separately in a chain;
   do not enlarge all gaps or change the naming policy.
4. `root, report = sheet.build(name)`, then write `dump(root)`. Build raises on
   any hard defect (see below); fix the structure, not the symptom.
5. `report["structure"]` must be PASS: every finding is either fixed or a
   recorded deviation with its reason.
6. Run `scripts/verify_schematic.py <root.kicad_sch> --intent <intent.json>
   --out <fresh dir>`: native ERC, intent partitions and identity, hierarchy/PDF,
   symbol integrity, the mandatory readability gate and geometry on every
   active sheet, in one pass. At board level every drawn (non-automatic) net
   name must equal the intent name of the same pin set, allowing only a sheet
   path prefix. `compare_netlist(xml, intent, report["layout"])` instead checks
   a single page's label and rail names against its layout policy.
7. Render natively and trace each declared reading task.

## Outline rules (how to decide the structure)

These rules are the 绘图纲要 inside the ASG 纲要 of SKILL.md: any change to
them needs a draft approved by a person first (SKILL.md, 纲要的修改).

The agent owns the topology decisions; these rules make them repeatable. Apply
them in order. A later rule refines an earlier one and never reverses it; only
O8 changes an earlier decision, in the order it states.

| # | Decision | Rule |
| --- | --- | --- |
| O1 | Page flow | Pick the page's reading task first. A **path page** (power stage, filter, protected interface) runs its main energy/signal path left to right along one row, from the input interface to the output interface; a second path gets its own row below, rows ordered by their position in the system. When the main path is wider than the drawing area, fold it into the next row at a node that is already a bank, rail or test point; a fold continues the same path. A **controller page** (MCU, PD/protocol controller, PHY) centres the controller; each pin group's support circuit sits on that pin group's side, and external interfaces sit on the page edge facing their connector or sheet. |
| O2 | Anchors | Anchors are parts with three or more pins and connectors (`sheet.plan` proposes them). Place anchors first, upright where possible; rotate or mirror (`place(..., facing=...)`) only so inputs face upstream and outputs downstream. Anchors that form one function, such as a controller with its FETs or a driver with its bridge, share one block; otherwise one block per anchor, in path order. |
| O3 | Ownership | A two-pin part belongs to the anchor whose pin net it touches. If several anchors share that net, it belongs to the pin that gives it its function (a pull-up to the open-drain output it pulls, a bypass to the supply pin it decouples, a gate resistor to its gate), else to the first anchor in path order. A part between two anchors, or in a passive chain with no anchor pin, belongs to the path segment it lies on and is drawn in path order. Never draw a support part inside another anchor's block. |
| O4 | Recipe by role | Use the proposed role from `sheet.plan`: `series` on the path axis; `shunt` off its node toward its rail (returns down, positive supplies up, a negative rail below its return); `bank` for parallel parts on the same nets, as one bank with one return; `divider` stacked with the tap sideways to the sense pin; `lane_*` as identical series+shunt lanes with the same arrangement; `decoupling` as a shunt or bank at its anchor's supply pin. |
| O5 | Pin exits | Start each branch from the pin along its outward direction (`stub`, or a recipe started at the pin). A support branch that must reach a pin on the far side of its anchor goes over or under the anchor block, never through another branch; if that is impossible, move the part to that pin's side. |
| O6 | Rails and labels | Rails and returns are power symbols from the declared `rails`; global labels only on `external` nets; small names on the plan's `name` nets; a local join label only with a boundary reason. |
| O7 | Spacing | Recipe gaps are at least two grid steps and at most `MAX_SPACING_STEPS` (12, about 15 mm) unless the script records why; the same cap applies to stubs, explicit bank pitches and leads, and rail/label leads. Widen a gap before moving parts by hand, then shrink it back once the build passes. A net that carries a small name needs one straight run longer than the name plus two grid steps. A vertical part with a long value needs that text width free on one side. Blocks are separated by more space than parts inside a block; a page is not padded to fill its paper. |
| O8 | Repair order | On a build error or failing gate, first change the recipe direction, gap or order; then the anchor position or orientation; then fold the path or split the block into rows (O1). Never add a label to hide a failed wire. After the page passes, read `report["readability"]`: shrink gaps that the audit lists, and if `fits_paper` is smaller than the sheet, move to that paper or bring the page's remaining blocks onto it. |

What is checked automatically:

| Rule | Checked by | Not checked (trace in the render) |
| --- | --- | --- |
| O4 | structure audit: recipe against role, banks drawn as one bank, identical lanes | whether the role itself suits the circuit |
| O6 | structure audit: global labels exactly on external nets, rails only as their power symbols, selected names present, no unselected local label without a reason; with `blocks`, a local join label whose wired parts all belong to one block | label wording |
| O7 | `build()` hard rejections: body clearance, text collisions, wires through bodies; structure audit: gaps, stubs, pitches, leads beyond `MAX_SPACING_STEPS` without a reason; readability gate: a sheet whose content fits a smaller paper | block-versus-part spacing, whether a low `cell_coverage` page should be merged |
| O1, O2, O3, O5 | readability gate catches some consequences (crossings, U-turns) | path order, block membership, ownership, branch side |

A structure audit PASS therefore covers O4 and O6 only. Review the other rules
on the rendered page before calling the page readable.

## API

| Call | Draws |
| --- | --- |
| `Sheet(intent, rails, external, paper, dirs, power_ref_start, blocks)` | One sheet. `rails` maps nets to `power:` symbols, `external` lists nets leaving the sheet; both enable `plan` and the audit. `power_ref_start` keeps `#PWR` references unique across pages. `blocks` is the page plan's `{block: [refs]}`; with it the audit rejects a local join label that only joins parts of one block (HR-01). |
| `plan` | `{"parts": {ref: {role, why, ...}}, "nets": {net: "power" \| "global" \| "name" \| None}}`. A net is a return when `intent["net_roles"]` says so; only undeclared rails fall back to the power symbol's direction. A resistor is a `Device:R*` part or one whose `fields.ComponentRole` is `resistor`. |
| `justify(part_or_net, reason, conflict)` | Records an intended deviation; the audit lists it with the reason. A spacing deviation also needs `conflict`: the part, pin or `text:<field>` the extra room avoids. |
| `place(ref, at, rotation, mirror, pin, facing, order)` | An anchor: controller, connector, magnetic, bridge. `facing={pin: direction}` picks rotation/mirror from the required pin exits (`order=(a, b, axis)` keeps pin a before b); with `pin`, `at` is that pin's tip. |
| `orient(ref, facing, order)` | The (rotation, mirror) that `facing` would choose; raises when no orientation gives those exits. |
| `put(ref, pin, at, toward)` | Part with `pin` on `at`, extending along `toward` (pin faces back). Parts with more than two pins stay upright. |
| `stub(pin, n)` | Pin exit along its own direction; returns the end point. |
| `series(start, [refs], toward, gap, net)` | Series chain on one axis in circuit order; the pin on the current net faces the start. Returns far-pin points. |
| `shunt(node, ref, toward, gap, rail)` | Two-pin branch off a node; far pin gets its declared rail symbol (`rail=False`: the far pin is returned). |
| `bank(start, refs, toward, hang, pitch, gap, rail, common, depth, lead)` | Parallel parts off a spine at a measured pitch; with `common` one straight return line and one symbol (`rail=False`: the common line is a signal net, e.g. N_EMI under L_EMI, or a gate line beside a drive line). `depth` fixes the common line's distance; `lead=0` puts the first part at `start` (inline with a pin). `hang=RIGHT` with `toward=DOWN` gives the classic side-by-side parallel pair. Returns the spine end. |
| `divider(top, upper, lower, toward, gap, rail)` | Stacked divider; returns the tap point on the midpoint wire. |
| `connect(a, b, first, x, y)` | L (`first` h/v) or Z (middle leg at `x` or `y`) between pins/points. |
| `wire(*pins_or_points, net)` | Explicit orthogonal polyline; every pin must be on `net`. |
| `power(target, symbol, net, length)` | Rail/return symbol whose Value is the net name (declared symbol by default); a perpendicular pin is left sideways far enough to clear the part body. |
| `label(target, kind, length, outward, net, reason)` | Global label where the net leaves the sheet, or a local join with `reason`. Extends along the pin direction or `outward`: left, right, up or down. |
| `name_run_steps(net, font=1.0)` | Read-only necessary straight-run budget: the existing local `label_geometry` width for this declared raw logical net/font plus two grid steps, rounded up to grid steps. No placement or label is added. |
| `name(net, at, font=1.0)` | Small local name on the net's own wire, mid-segment and clear of pins and dots: above a horizontal wire, else beside a vertical one. Only on a connected piece that has no label or rail symbol of that net yet; when every piece already shows the name, `build()` skips it (`report["names_skipped_already_labelled"]`), and an explicit `at` on such a piece is an error. |
| `select_local_names(intent, external, rails)` | Default selection: page-local nets touching a part with three or more pins. |
| `text(text, at, font)` | Block title or note. |

Every recipe records a gap, stub, pitch, lead or lead length beyond
`MAX_SPACING_STEPS` in `sheet.spacing`; the audit lists each as a `spacing`
finding unless `justify(ref_or_pin, reason)` says why the run needs the room,
and more than `MAX_SPACING_DEVIATIONS`
(3) justified spacing deviations on one page is itself a finding: fold or
re-anchor the page (O8). A measured bank pitch (`pitch_for`) is never a finding. The readability metrics in the report add
`paper`, `content_size_mm`, `fits_paper`, `oversized_paper` (a gate reason),
`occupancy`, `cell_coverage` (share of 25.4 mm cells holding any object),
`part_groups`/`part_group_refs` (parts joined only through labels or rail
symbols count as separate groups) and `longest_segment_mm`.

`build(name, draft=False)` returns the native root and a report. With `draft=True`
name and field failures are listed in `draft_failures` instead of raised, so a
page can be rendered while it is being fixed; a draft is never delivered. Fields
that fit on no side (bridges, parts wired on all four sides) take a clear body
corner. Content stays 5 mm inside the page edge and out of the title block: `build()` raises on a wire that
leaves that area, enters the title block or crosses a body, using the geometry gate's own check (`qa.wire_findings`). The report holds every recipe decision, crossing
locations, label and rail sets, readability metrics with the gate, the
structure audit, and a `layout` whose net policies `compare_netlist` uses to
check label and rail names.

`name_run_steps` validates a declared logical net and a finite positive numeric
font; it does not decode names, shorten them, resolve variables or pick a font.
The grid is 1.27 mm; the local-name font defaults to 1.0 mm, independently of
Reference/Value field defaults. Explicit reservation before placement can avoid
a later insufficient-length rejection, but sufficient length is only a space
budget. Parts, text, foreign wires, junctions, page boundaries and native glyph
coverage still need the unchanged strict build and native verification. The
query gives no new qualification for encoded/markup/CJK/variable text, external
fonts or mirrored glyphs. Keep their existing source and coverage boundaries.

For a declared local net `node`, one series leg may be planned as:

```python
font = 1.0
gap = max(existing_gap, sheet.name_run_steps(node, font))
sheet.series(start_pin, [support_ref], toward, gap=gap)
sheet.name(node, font=font)
```

`start_pin` must actually be on `node`; every later leg in a multi-part chain
can have a different net and needs its own budget. The same query can explicitly
budget `stub(pin, max(existing_length, ...))` before wiring that own-pin exit.
It does not move existing anchors or promise that an entire first build passes.

For a multi-page project keep one board intent (see
[requirements-to-intent.md](requirements-to-intent.md)) and split it with
`schematic_layout.pages.page_intents(board, rails=...)`: each page gets its own
components, the page-local part of every net, its NC pins and its `external`
nets (nets with pins on another page that are not rails). Build each page with
its own `power_ref_start`. For a redraw, restore the baseline identity (symbol
properties, UUIDs, pin UUIDs, instance paths, page UUID, title block) before
writing. Assemble the root with `schematic_layout.root.Root`:

```python
from schematic_layout.root import Root

r = Root("PD100_R5", date="2026-10-23", rev="R5")          # paper defaults to A4
r.page("02_Input", input_root, (25.4, 50.8), note="交流 / EMI / 整流")
r.page("03_PFC", pfc_root, (119.38, 50.8))
...                                                         # the other pages
r.flow("RECT", "02_Input", "03_PFC")                        # same row: straight, arrow at 03_PFC
r.flow("FB/FAULT", "07_PD", "05_Bias", kind="signal", via=[(345.44, 223.52), (157.48, 223.52)])
r.isolation(x=302.26)                                       # straight line labelled 隔离
r.write(out_dir, libraries={"PD100": "PD100.kicad_sym"})
```

`page` takes the root returned by `Sheet.build` (or a `.kicad_sch` path) and
numbers pages in the order added, from 2. A flow without `via` needs the two
blocks to share a row or column band; `via` points give an orthogonal route
whose first and last legs leave and enter the blocks straight. The flow name
sits beside its longest leg; `label_at` moves it. `write` rewrites every child
symbol's instance path to the root project, writes the cover, pages,
`.kicad_pro` and `sym-lib-table` into a fresh directory, and raises when a
cover text sits on a line or the System_block audit fails. Then run
`scripts/verify_schematic.py` on the root with the board intent. The charger redraw (`design/v0.2.5-recipes/scripts/redraw.py` in that
project) is a worked example of nine hierarchical pages drawn this way.

Native label styles (render-verified on KiCad 10.0.6): global labels extend
left at 0/`right`, right at 180/`left`, up at 90/`left`, down at 270/`right`;
local labels use 0/`left bottom`, 180/`right bottom`, 90/`left bottom`,
270/`right bottom`, and KiCad draws their text readable (above a horizontal
wire, left of a vertical one).

## Hard rejections in `build()`

- Unplaced parts; off-grid or coincident terminals (from `make_root`).
- Diagonal wires; a wire over another net's terminal; different nets touching
  or overlapping (a clean perpendicular crossing is allowed but reported).
- A wire through a part body (a pin's own outward exit is not a traversal), closer
  than 5 mm to the page edge or entering the title block: the same `qa.wire_findings`
  check the geometry gate runs on the written wires.
- An unwired pin; a net drawn in separate pieces unless every piece carries its
  label or rail symbol.
- A rail symbol, label or name that collides; no clear Reference/Value position.

Typical fixes: lengthen a `gap` or stub, change a recipe direction, move or
reorient an anchor, split a crowded block into rows, reverse a chain's order.

A rail-placement rejection keeps its net/anchor prefix and adds `diagnostic=`
JSON for the first failing `body` or `Value` envelope. It identifies actual
foreign-wire segments, obstacle references/pins/annotation or reserved-region
indices, earlier rail requests and page edges. These are construction locators
and conservative envelope checks, not native object UUIDs, ink measurements or
electrical-short findings. Use them with O8; they neither move a rail nor waive
the original rejection. A coordinate alone does not establish a pin owner.

Two pins 7.62 mm apart cannot both hang a shunt down: fold one branch up or make
the lower pin's run shorter than the upper one's. Never replace a failed wire
with a label unless the plan declares that boundary.

## Worked example

`tests/fixtures/drawing/recipe_board.py` draws a 12 V to 5 V buck, a 3.3 V LDO
with indicator, and two USB ESD lanes on A4 (22 parts, 0 crossings, 11 bends):

```python
s = Sheet(INTENT, rails={'GND': 'power:GND', '+5V': 'power:+5V', '+3V3': 'power:+3V3'},
          external=['MCU_DP', 'MCU_DN', 'USB_VBUS'])
s.place('J1', (20.32, 50.8)); s.power('J1.2')
s.series('J1.1', ['F1', 'D1'], RIGHT, gap=3)            # input chain
vin = s.bank('D1.1', ['C1', 'C2'], RIGHT)               # input bank, one return
s.put('U1', '1', add(vin, RIGHT, 12), RIGHT); s.wire(vin, 'U1.1')
sw = s.stub('U1.2', 3); s.shunt(sw, 'D2', DOWN)          # catch diode at SW
out = s.bank(s.series(sw, ['L1'], RIGHT, gap=6)[-1], ['C3', 'C4'], RIGHT)
rail = s.wire(out, add(out, RIGHT, 3)); s.power(rail)   # declared +5V symbol
r1 = s.series(rail, ['R1'], RIGHT, gap=3)[-1]            # upper divider leg
tap = s.wire(r1, add(r1, RIGHT, 2)); s.shunt(tap, 'R2', DOWN)
fb = s.stub('U1.4', 2); s.connect(fb, tap, y=fb[1] - 10.16)   # FB over the top
```

`draw(bad=True)` is the negative example: the same netlist with the feedback
wire dropped through the +5 V spine and the LED reversed into a U-turn. The gate
names the crossing (`+5V`/`FB`) and the tortuous connection (`D3.2`, `R3.2`);
the structure audit names D3, placed by hand although its role is a shunt.

## Keep the generator with the delivery

Store the page scripts (intent derivation, recipe redraw, assembly) inside every delivered
revision directory, next to the native project. The next electrical revision regenerates only
its changed pages from the previous revision's intent plus these scripts; a delivery without its
generator forces hand edits of readable pages, which this workflow forbids. Directory clean-ups
must not delete a revision's generator while a later revision still derives from it.

## Limits

- The agent chooses structure; nothing here recognizes a topology.
- Single-unit symbols only. A functional pin-grouped presentation symbol needs
  its own verified physical pin map (see symbol-and-peripheral-contracts.md).
- One `Sheet` per page. For a hierarchical project, copy each symbol's project
  instance path and UUID from the baseline page, as a redraw must preserve them.
- `check_scene` accepts a pin's own straight outward exit through graphics
  that reach past its tip (LED arrows, magnetics arcs, thermistor marks); any
  other wire through the body box is still reported.
- Text widths are estimates; native render review remains mandatory.
