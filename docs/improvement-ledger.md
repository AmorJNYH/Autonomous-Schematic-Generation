# 此前问题点的改造闭环

## 100 W PD R3 drawing review (2026-10-19)

Reading the eight rendered pages of the R3 delivery against the drawing rules,
with every automated gate at PASS:

- All seven circuit pages were A3 with the drawing in 25–38 % of the 25.4 mm
  cells; 02_Input fitted A4 with its frame margin. The page scripts reached
  passing builds by widening gaps (C407 at 38 steps, R404 at 25, stubs of 24–25,
  pitches of 35) and never shrank them, which HR-11 forbids but nothing
  measured. `readability.measure` now reports `paper`, `content_size_mm`,
  `fits_paper`, `occupancy`, `cell_coverage`, `part_groups` and
  `longest_segment_mm`; a sheet whose content fits a smaller paper fails the
  gate (`oversized_paper`, waivable with a reason). Recipes record any gap,
  stub, explicit pitch, lead or rail/label length beyond `MAX_SPACING_STEPS`
  (12) and the structure audit lists them until `justify` names them. O7/O8
  say to shrink back after the build passes and to choose the paper afterwards.
- 03_PFC joined the FB divider to U201 and the drive to the power stage with
  13 local labels justified as "block boundary"; 06_Secondary was three islands
  (SR driver, output bank, shunt) joined only by rail symbols. `Sheet` takes
  the page plan's `blocks={name: [refs]}` and the audit rejects a local join
  label whose wired parts all belong to one block (HR-01); `part_groups`
  shows islands against the declared blocks.
- The System_block page had eight unnamed arrows, a control polyline ending in
  the void and a solid "isolation boundary" that looked like a wire and ended
  twice in the void; 06_Secondary sat on the primary row so the boundary had
  to snake. `schematic_layout.system_block` audits the cover: flow lines need
  a text within 6 mm, both ends on a block/arrowhead/line, a 隔离-labelled
  straight boundary that crosses no block, every block reached. It runs as the
  `system_block` gate in `verify_schematic.py` when the root holds sheets, and
  as `scripts/audit_system_block.py` alone. On R3 it lists 10 findings.
- The visual review dispositioned all 84 pin-text items with one copied
  sentence per page and cited "pixel-identical to the previously reviewed
  PDF" as its basis; the step-4 page plan was never saved. `page-plan.json`
  is now a required record (file, reader tasks, blocks covering every part on
  the page); `render_design_report.py` checks that each page's review traced
  at least one path per reader task and that each `render_review_items`
  disposition names its own symbol and is not reused across symbols.

## Finite native diameter semicircles, 2026-10-13

- A subsequent independent audit found terminal `Z` could append a 4097th
  segment after an exactly 4096-segment arc. All arc-path additions now use
  one bounded append operation, with a final total check. The 4096 budget is
  unchanged. Reject-first controls include the actual SVG consumer, closure,
  preceding ML strokes, later subpaths, repeated Z and token/radius overflow;
  exactly 4096 segments with and without closure remain legal. This closes
  a profile-budget violation; the audit did not establish lost electrical ink.

- A native absolute circular `A` on one page previously aborted full-project
  SVG parsing and prevented every page from obtaining a fresh context. Added
  the bounded, exact-diameter, unrotated half-circle profile documented in
  `references/native-geometry.md`; no reference, model or coordinate special
  cases, no page-failure isolation and no unknown-curve skipping.
- Every arc chord carries stroke+sagitta+serialization+numerical protection,
  shared by native ink consumers and foreign foreground contact checks.
  Physical conductor/pin-cap/pin-leg attribution remains strict MLZ. Full
  primitive equality, hidden text, causal deletions and fresh input/tool/raw
  producer bindings are unchanged.
- Reject-first vectors cover arc interior versus endpoint/bbox shortcuts,
  near tangency and wide paint, both sweeps, foreign dashes, malformed/overflow
  inputs, ellipses, transforms, filled glyphs and finite segment budgets.
  Native fixtures also retain wide-wire/tiny-aperture/glyph protections. A
  supported far native arc does not remove an existing unknown sheet-object
  gap or hide a measured finding behind that gap.
- ERC zero-violation policy is unchanged. Duplicate physical common-output
  facts require a future explicitly evidenced generic rule; same reference or
  same name does not authorize independent power outputs to connect.
- This entry describes scope and regression controls, not benchmark results,
  whole-page PASS, G1 reduction or hardware approval. Those require independent
  same-input measurement and review.

## Symbol and peripheral generation gates, 2026-09-15

- Added actual inner-pin-to-stroke checks, distinct from symbol AABBs and native
  electrical continuity. Stroke width, arc sweep, unit/style, hidden/zero-length
  pins and standard separate bodyless supply units have explicit treatment.
- Added source-bound exact MPN/package and full physical pin name/type contracts,
  direct native peripheral/assembly assertions and declared functional stages.
- Added automatic symbol checks to native generation verification and optional
  `--reference-contract` on both generation entrypoints. Supplying a contract
  makes its assertions a required automated gate; omitted evidence is not verified.
- Reproduced 33 corrected internal-leg/artwork candidates on a private full-board
  before/after regression while retaining two intentional NC-terminal candidates
  for explicit disposition. No private design or manufacturer PDF is packaged.
- Added 35 regression tests for real failure modes and negative mutations; all
  136 current tests passed. Scope adequacy, datasheet interpretation, functional
  performance, footprint dimensions and production release remain separate gates.

## Existing-project electrical changes and delivery, 2026-09-15

- Added a native-XML change-contract verifier: explicit component additions,
  removals and before/after identity/partition changes; retained physical NC
  pins; optional frozen-baseline hash and named/same-net/distinct-net contracts.
- Added a root hierarchy audit: instance-aware page/component counts, portable
  sheet paths, missing/cyclic children, annotation coverage, cached-library and
  multi-unit pin signatures, actual PDF count and descriptive baseline delta.
- Added neutral failure fixtures and native KiCad before/after resistor pin/value
  changes. Tests cover unexpected opens/shorts, DNP drift, pin loss, stale hashes,
  cache conflicts, reused sheets and historical PDF count mismatch.
- Carried forward System_block as the architecture cover, and documented module
  expansion, electrical redesign, canonical cross-page symbols and CopperPilot
  candidate provenance. No private board or vendor reference package is included.
- The tools are read-only verifiers, not an automatic multi-page writer. The
  project-specific geometry extensions are documented as bounded work requiring
  native validation; the stock engine's unsupported objects remain insufficient.
- All earlier generation, redraw and population mechanisms are retained. The
  release evidence is in `release-validation.md`; electrical/production approval
  and external service availability are not implied by these checks.

对应 2026-09-08 调研清单，更新于 2026-09-14。本表说明程序真正执行的规则，
不把流程文字或单一 ERC 结果当成已解决图面问题。

| 编号/原问题 | 落地变化 | 证据与边界 |
| --- | --- | --- |
| G1 临时写坐标和 S 表达式，缺稳定接口 | Circuit IR v2 → pin 编译 → 自动 layout → route → writer → native verification | `build_circuit.py`、输入/编译/每次尝试快照；旧 v1 明确定位接口继续可用 |
| G2 把 Buck 布局套到所有稳压器 | 分开 rc/divider/capacitor_bank/ldo/buck_async/integrated_power/functional | 角色合同拒绝缺失/不支持的角色；电源模板是布局模板，特定 IC 仍须电气与原生回归 |
| G3 控制区只考虑本体间距 | 按 body、pin 出线、Reference/Value 总占用计算行列；扩距重排 | 12 只长 Value 电容；改变字长后占用扩大；纸张不足明确失败 |
| G4 wire_geometry 只有统计，无穿芯检测 | 回读真实缓存符号，线段检查本体/字段/引脚 | 既有穿芯/线穿文字反例 + 生成前避障 + 生成后独立 QA |
| G5 按坐标猜功能组 | 原始电路模块/实例/角色；默认布局按实际连接遍历 | 两组 RC 实例隔离、单页拼排；不是完整电路功能识别或任意拓扑优化器 |
| G6 geometry check 缺统一覆盖与结果 | PASS/FAIL/INSUFFICIENT/REVIEW；对象、坐标、缺口、版本与 hash | 未覆盖的隐藏脚、叠加脚、复杂原生页对象不会伪装成零碰撞 |
| G7 固化可疑的连线规则 | 保留 KiCad 10.0.4 原生直连/未分段 T/旋转镜像实验 | 每次回归重做 native XML；不推广为所有历史版本必然相同 |
| G8 为了排版改变引脚或接口定义 | 编译器锁真实物理引脚；named pin 必须实库解析；符号 hash | 错脚、重名脚、遗漏脚、重复位号、库 hash 漂移全部拒绝 |
| G9 机械套公共地母线/PWR_FLAG | 标签必须在 presentation 显式选择；端口只绑定已声明网络 | 无自动标签降级、无自动补 PWR_FLAG 或改 pin type；复杂电源符号未覆盖则失败 |
| G10 没有固定生成回归包 | 旧 29 项加 IR/自动布局/多单元/属性/锁定/导入回归 | fixtures、原生 XML/ERC/PDF、源码对象探针、最终产物 hash；示例均标为测试夹具 |

四类主要痛点的自动验收：

- **器件堆叠**：分开分配真实总占用；生成后本体/字段相交仍是硬失败。
- **走线穿芯**：引脚朝向约束 + 完整线段避障；路由失败触发有限重排。
- **Value 堆积**：可见字段水平并预留宽度，采购/额定值另存隐藏属性；不截断原值。
- **布局不清楚/标题栏侵入**：按功能模块、方向、标题、留白拼页，预留页框和标题栏。
  自动布局只在硬约束通过后交付候选；可读性仍以最终原生全页与局部目检确认。

架构阶段的当前边界：

| 原建议阶段 | 当前状态 |
| --- | --- |
| 一：坏图必须被拦住 | 已有统一几何门禁与坏图反例；明确报告模型未覆盖对象 |
| 二：单功能块稳定生成 | 已有电路表示、模板、真实空间预算、自动放置/布线/复验；RC、电容阵列、多单元夹具实测；实际 Buck/LDO 等仍按具体器件复验 |
| 三：多块多页 | 模块复用、逻辑层次/端口/标量总线、多块单页已实现；原生多页 sheet/跨页导出、图形总线仍未实现 |
| 四：增量编辑 | 已有带差异与锁定检查的新目录再生成；不宣称支持任意手工工程原位编辑或任意已有分页工程的局部重排 |

对已有的复杂硬件工程，应先回读原生网表和组件身份，再建立经确认的 IR。
资料不足保持 INSUFFICIENT；本次没有把历史 LM5013/RK3576/SSA100 原图当作
已修复或已电气验收的成果，也没有改动它们。

复验入口：`python3 -m unittest discover -s tests -v`，以及
`tests/probe_structured_upstream.py`（可选上游隔离环境）。具体运行结果保存在
本地 `output/ir-integration/`，不把临时路径或测试数据当成正式产品输入。

## Engineer-reference comparison, TPS53355 Rev B (2026-09-10)

- Added explicit local routing groups with exact terminal partition validation,
  original-net labels and per-group fixed rails. Replaced the TPS53355 test's
  temporary-name monkeypatch with a supported low-level API.
- Added measured explicit visible fields, including 90-degree capacitor-bank
  fields, reserved before automatic fields and routing. Pin corridors are now
  also protected when placing labels on wired nets; interior wire label anchors
  are normalized as real split points.
- Added four regressions including native group connectivity/identity, rotated
  fields, invalid groups, immutable IR and collision rejection. Adapted the
  unsplit-T native probe to merge all contiguous segments, including extra
  label split points, before testing the same physical topology.
- Added an engineer-comparison guide and a reproducible compact TPS53355 draft.
  This is an explicit project recipe; automatic packing still does not choose
  this topology, capacitor MPNs/DC-bias guarantees or production constraints.

## Control-pin and peripheral completeness, TPS53355 Rev C (2026-09-11)

- Added explicit pin-provenance and peripheral-function ledgers to the workflow;
  distinguish datasheet-required connections, calculated values, default
  population and engineering options. Reference-image NC/DNP resistors retain
  actual wired pads instead of disappearing into an IC no-connect marker.
- Extended the TPS53355 example from 37 to 47 components (40 fitted, 7 DNP),
  with RF/MODE options, PG/VDD/VREG isolation links and VIN/load bypasses.
  Default RF remains electrically open at nominal 500 kHz; documented RF
  alternatives are held for frequency-dependent redesign and validation.
- Added a recipe-specific population gate: remove DNP, collapse fitted 0-ohm
  links, enforce mutually exclusive controls and compare retained baseline pin
  groups. Eight regressions cover errors that native all-pads ERC cannot detect.
  This is not a universal analog or arbitrary-assembly validator.

## Reference circuits and existing-project redraw (2026-09-14)

- Added datasheet peripheral contracts, explicit local branch ownership and
  negative mutations for a bounded KSZ8081RNA example. Added shared-terminal
  coverage and power-marker geometry regressions; connectivity includes each
  physical pad even where one drawn stem is shared.
- Documented the project-specific multi-page redraw workflow in
  `existing-project-redraw.md`: preserve hierarchy/identity, plan local circuits,
  compare complete native pin partitions and named interfaces, retain raw ERC
  and inspect its semantic delta. Existing electrical findings remain visible.
- Recorded native-grid and actual drawing-frame checks, per-page visual review,
  explicit handling of changed local net names, protected application to the
  original project and verification from the delivered path. Compare decoded
  pixels rather than PNG file hashes for visual equivalence.
- These are reusable checks and drawing procedures derived from project work.
  The project-specific multi-page writer and proprietary engineering sources
  are not distributed. The general generator remains a bounded single-sheet
  backend; this update does not claim arbitrary automatic board layout or
  electrical/production qualification of the examples.

## Readable drawing construction (2026-09-30)

- Root cause from a rejected 100 W charger redraw: blind coordinates and
  page-spanning ground wires, not the router. Added `recipes.Sheet`
  (`drawing-recipes.md`): supporting parts are placed from real pin geometry by
  series/shunt/bank/divider/lane recipes with explicit wires, power symbols named
  by net and fields placed last. Different-net contact, wires through bodies and
  unnamed disconnected pieces are rejected at build time.
- The readability checker is now a mandatory gate with reported locations and
  reasoned per-sheet waivers. HR-07 fixes label roles, including small local
  names on selected nets.
- Regression pair `tests/fixtures/drawing/recipe_board.py`: identical native
  partitions; the bad drawing reproduces the charger's support-net crossing and
  two-terminal U-turn and fails the gate. The fixture is not a qualified design,
  and the builder does not choose a topology's structure.
- Outline rules O1-O8 with `Sheet.plan` (proposed part and net roles from
  connectivity) and a structure audit; deviations need recorded reasons.
  Vertical global/local labels and names, render-verified on KiCad 10.0.6; the
  scene reader accepts the four tested local label styles. QA no longer reports
  a pin's own straight exit through graphics that overhang its tip (11 such
  findings on the charger v0.2.4 pages); foreign wires are still reported.
- Nine-page charger redraw (v0.2.5) with recipes: native identity, partitions and
  ERC by net group unchanged; readability, structure audit and geometry PASS on
  all pages. Added from that work: `bank` lead/depth, draft builds, corner
  fields, frame margin, named-part body clearance messages, coincident pads
  counted once for junctions, rung-vs-lane planning fix, and native global-label
  outlines in the scene reader (v0.2.4 pages: 60 QA errors -> 2).

## Requirements-first drawing focus (2026-10-07)

- SKILL.md now covers only the drawing flow from requirement documents to a
  verified schematic (936 → about 200 lines). Strict review is handed to
  `schematic-review`; the analyzer documentation moved unchanged to
  `references/analysis-toolkit.md`, without the mandatory SPICE/EMC review
  contract (those companion skills and `analyze_emc.py` are not shipped).
- New `references/requirements-to-intent.md`: requirement inventory, function
  trace, board intent format (`fields.Circuit` page key), OPEN items, handoff.
- Outline rules: O1 covers controller pages and folding a long path (the O1/O8
  conflict is removed), O2 groups anchors of one function, O3 resolves parts on
  nets shared by several anchors and anchor-less chains, O4 places negative
  rails; the audit coverage table states that the structure audit covers O4
  and O6 only.
- From the charger v0.4.0 project scripts: `Sheet.place(..., pin=, facing=,
  order=)` and `Sheet.orient()` replace project helpers that used the private
  `_shape`; `schematic_layout.pages.page_intents()` splits a board intent into
  page intents with external nets and page rails; `scripts/verify_schematic.py`
  replaces per-project gate runners. On charger v0.4.0 it reproduces the
  project's own results in about 3 s (intent partitions, hierarchy, symbols,
  readability PASS; the eight inherited `power_pin_not_driven` ERC findings;
  root `System_block` geometry INSUFFICIENT for sheet/polyline objects).


## 100 W PD R1 review follow-up (2026-10-16)

Problems found reviewing the 100 W PD R1 delivery, traced to skill rules:

- D403 aux-OVP zener shipped with prose only ("30 V envelope"); by estimate the circuit
  trips near 24 V output and no calculation covered it. Calculations now carry
  `refs` and numeric `checks`; `kind: "threshold"` needs both a
  `no_false_trip` and a `protection` side; every zener/TVS/reference in the
  intent must be named by a calculation (`threshold_part_uncalculated`).
- All 16 calculations were `conditional` because the project script hardcoded
  it. The conclusion must now agree with the checks
  (`conclusion_contradicts_checks`); a calculation without checks is rejected.
- LDO dissipation (0.73 W, MSOP) was left as "verify": device thermal
  feasibility (power → junction temperature) is now part of selection; only
  heat-sinking implementation goes to PCB.
- Repeated net text (`PFC_DRV PFC_DRV`): `Sheet.name()` no longer places a
  name on a connected piece that already has a label or rail symbol of that net.
- Geometry was INSUFFICIENT on every page with a symbol: pin numbers were
  appended as gaps unconditionally, shared-cache pin names too, and hidden
  `${INTERSHEET_REFS}`/cached `${KICAD9_SYMBOL_DIR}` counted as display
  variables. Library-hidden pin text is ignored; visible unqualified pin text
  is `render_review_items` for the render review. On R1: 5 pages PASS, 2 REVIEW
  (the two dispositioned clearance warnings), 1 INSUFFICIENT (filled arc in the
  USB-C symbol); pin-text items about 520 → 93.
- Calculation assumptions were English: record prose shown in the report must
  be Chinese; `render_design_report.py` reports English sentences as problems.
- D702–D706 (unidirectional PESD5V0L1UA, SMBJ24A) were drawn with KiCad
  `Device:D_TVS`, which is bidirectional only (A1/A2). Connectivity matched the
  intent, so no gate saw it. New `discrete_semantics` gate compares each
  symbol's cached description/pin names with the datasheet's first pages and
  standard TVS MPN suffixes (TVS direction, MOSFET channel, BJT type); on R1
  it fails all five and passes Q302/Q501/Q701.
- The last R2 geometry gap was two filled half discs in KiCad's
  `Connector:USB_C_Receptacle_USB2.0_16P`. Filled paths in the qualified
  circular-A profile are now covered by their bounding box (fill inside the
  boundary hull); curved glyphs and translucent fills stay unsupported.
- R2 geometry stayed REVIEW on two rail symbols within 1.27 mm of IC bodies,
  "dispositioned" in the visual review. That is a drawing defect ASG can
  close itself: `Sheet.build()` now runs the page gate's body_clearance /
  body_overlap check on the built page and fails (draft: records it), and
  SKILL.md forbids handing geometry REVIEW to a human. The report shows
  REVIEW as 没通过：要改图.
- Simplified: the geometry gate has no REVIEW state any more. Its four former
  warnings (body_clearance, graphic_text, graphic_wire/pin, wire_crossing) are
  errors, so a page is PASS, FAIL or INSUFFICIENT; a readability/geometry FAIL
  is a report problem and blocks packing.
