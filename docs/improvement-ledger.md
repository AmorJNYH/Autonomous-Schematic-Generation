# 此前问题点的改造闭环

Every entry from here on ends with lines the test suite checks
(`scripts/check_ledger.py`): `Event:` the review item, datasheet page, test
record or user correction that caused the change (a cited datasheet must exist
in the library and have the cited page); `Changed:` the files touched.
`Causes:` (how many items fell in each cause class) is an optional note. An
entry that changes the ASG 纲要 or the 绘图纲要 O1–O8 also carries `Approved:
user:<date>` and `Outline:` the hash from `check_ledger.py --outline-hash`.

## 计算结论分三档，由参数依据推出：parameter_version 2 (2026-10-23)

R1–R6 六版 164 条计算全部 `conditional`：`supported` 要求没有任何遗漏项，而每条都能写出“样件实测”一类的项；
`missing_guarantee` 是自由文字，R6 的 PFC-CS 与 `omitted_terms` 逐字相同；98 个 `model` 参数里有 12 个需求输入和 1 个物性常数。
用户按 `docs/proposals/2026-10-23-计算结论分层草案.md` 定为三档。`parameter_version: 2` 时审计用 `calculation_basis()` 推出结论：
有 `typical`/`unspecified` 参数或挂着未关闭的缺资料待办为依赖厂家资料，有 `model` 参数或没算的项为依赖工程估计，
否则设计成立；写的 `conclusion`/`rests_on`/`coverage` 与推出的不一致即 FAIL。遗漏项分 `not_calculated`（指向未关闭的 design 待办）
和 `verify_by_test`（指向 validation 技术转交）；依据加 `requirement`、`constant`；需求挂着不成立的计算不能记 `design_supported`。
报告按三档计数并分两节列出每条依赖的参数。版本 1 照旧审计，报告写明没有分层；R6 不回改。

- Event: user:2026-10-23
- Changed: SKILL.md, references/design-closure.md, references/delivery-report.md, references/terminology.md, scripts/audit_design_closure.py, scripts/render_design_report.py, tests/test_design_closure.py, tests/test_design_report.py, docs/proposals/2026-10-23-计算结论分层草案.md, docs/improvement-ledger.md
- Approved: user:2026-10-23
- Outline: bc996312760f5e9a

## 按步审视的修正：工况角点、停产料号、暂缓意见归因 (2026-10-23)

按步审视 ASG 第 0–8 步对照 R1–R6 记录：R5 验收与从头审查的电气错误全部出在第 2 步，画图一侧没有。
其中三个 P1 不在原有工况清单里：21 V 轻载同步整流最短导通时间（F-SR-TONMIN）、90 Vac 被判为高线（F-PFC-90V）、
反馈光耦单点开路时输出越过电容额定（F-A）。第 2 步与 requirements-to-intent.md 第 4 节的清单加入“工作包络角点”
和“单点故障”两类，“最坏情况属于独立审查”改为只指逐参数的形式化证明，角点和单点故障由 ASG 算；
三条写进对应模式文件的必算项与已知坑。D201 MUR550APFG 在手册订货表里列为 DISCONTINUED（F-D201），技能没有任何地方查：
新增 `schematic_layout/lifecycle.py`，`render_design_report.py` 对设计要求表里有 `mpn` 和 `datasheet` 的每个器件读手册全文，
列在停产/不推荐新设计标题下的料号算记录问题，`lifecycle_reason` 保留时在报告“停产料号”一节列出；R6 的 45 个这类器件里只查出 D201。
R6 把 9 条暂缓的审查意见记为 `cause: none`、“下一轮再归因”，其中有 P1 的 F-SR-TONMIN：`cause: none` 的 `why_none`
写推迟归因的话算记录问题。原生几何通道范围冻结，不再增加对象类型，新缺口交图面审阅。

- Event: review:SR-20261023-R5-从头审查-claude-5802e8c/F-SR-TONMIN, review:SR-20261023-R5-验收-claude-6d74689/F-PFC-90V, review:SR-20261023-R5-验收-claude-6d74689/F-A, review:SR-20261023-R5-验收-claude-6d74689/F-D201, user:2026-10-23
- Changed: SKILL.md, references/requirements-to-intent.md, references/core-part-selection.md, references/review-comments.md, references/native-geometry.md, references/circuit-patterns/synchronous-rectification.md, references/circuit-patterns/pfc-boost.md, references/circuit-patterns/isolated-feedback.md, scripts/schematic_layout/lifecycle.py, scripts/render_design_report.py, tests/test_lifecycle.py, tests/test_design_report.py, docs/improvement-ledger.md
- Approved: user:2026-10-23
- Outline: 3e5d2f9bf2a2a798

## 建图与几何检查共用一条导线判定，页边统一 5 mm (2026-10-23)

`Sheet.build()` 手写了三条导线检查（离开 12 mm 内框、进标题栏、穿器件本体），几何检查又用 5 mm 边距和另一段
穿本体判定各查一遍，标题栏保留区的数在 `qa.py` 与 `generate.py` 各抄一份；同一根线可能建图不过而门禁通过，或反过来。
用户定为统一 5 mm。现在 `qa.wire_findings` 是唯一判定（`FRAME_MARGIN_MM = 5`、`title_block()`），建图对计划中的线段、
门禁对写出的导线各调用一次；建图时电源符号与标签的页内范围、可读性的纸张判断（HR-11）也用同一边距。
R6 八页的纸张判断不变，全部 PASS。

- Event: user:2026-10-23
- Changed: scripts/schematic_layout/qa.py, scripts/schematic_layout/recipes.py, scripts/schematic_layout/generate.py, scripts/schematic_layout/readability.py, references/drawing-recipes.md, references/human-readable-routing.md, tests/test_wire_envelope.py, docs/improvement-ledger.md

## 检查只为电路正确或交代不确定性：合并改动 (2026-10-23)

用户审定 9 个改进点后要求全量审查每一项检查：凡不服务于电路正确、也不交代不确定性的检查删除或改写，
并按 `docs/proposals/2026-10-23-合并改动草案.md` 逐步执行。本次落地：
删除 58 项只核记录形式或互相抵消的检查（网名来源证据、图面锁定、回归集、负责方措辞、无引脚对象的外部角色合同等），
改写 45 项为直接核对电路或写明“没核对”；无引脚对象改由符号的 `ComponentRole`（mechanical/documentation）加
“所有单元无引脚”判定；KiCad 10（20260306）注释格式加入并用 KiCad 10.0.6 实际保存的工程复核；
生成的工程把 `single_global_label`、`four_way_junction` 设为 error，一键验证读取工程 ERC 设置，除
`simulation_model_issue`、`footprint_filter` 外被设为忽略的规则即 FAIL；`deliver.py` 改为白名单状态、缺结果即停、
预检文件不成对 FAIL、新鲜度在打包前；新增手册引用核对（`schematic_layout/citations.py`：文件与页码错 FAIL，
数值找不到列入报告“引用待人工核对”，R6 的 190 条引用全部核对通过）；后果等级由 `consequence_class` × `occurrence`
推出；审查回复加 `recurs_from`，复发的意见不能归 `judgment`；图面审阅核对每个待看图对象都有处置、不得“沿用”；
新增 `references/terminology.md`，报告用语专业化，记录与 notes 里的禁用词和“共/全部 N …”总数由报告核对。
纲要按草案第四节修改（验证、支撑、P6、P7、第 5–8 步与全文术语）；第 8 步台账说明随 `check_ledger.py` 改为 Event/Changed 两行。

- Event: user:2026-10-23
- Changed: SKILL.md, README.md, references/terminology.md, references/design-closure.md, references/delivery-report.md, references/core-part-selection.md, references/review-comments.md, references/symbol-and-peripheral-contracts.md, references/project-verification.md, references/drawing-recipes.md, references/human-readable-routing.md, references/change-preflight.md, references/requirements-to-intent.md, scripts/deliver.py, scripts/audit_design_closure.py, scripts/render_design_report.py, scripts/verify_schematic.py, scripts/verify_design_preflight.py, scripts/check_ledger.py, scripts/pack_design.py, scripts/schematic_layout/citations.py, scripts/schematic_layout/native.py, scripts/schematic_layout/native_hierarchy.py, scripts/schematic_layout/design_change.py, scripts/schematic_layout/project_audit.py, scripts/schematic_layout/symbol_integrity.py, scripts/schematic_layout/reference_contract.py, scripts/schematic_layout/recipes.py, scripts/schematic_layout/readability.py, scripts/schematic_layout/scene.py, scripts/schematic_layout/system_block.py, scripts/schematic_layout/root.py, scripts/schematic_layout/qa.py, scripts/schematic_layout/net_name_origin.py, scripts/run_regression.py, tests/test_citations.py, tests/test_pinless_evidence.py, tests/test_design_report.py, tests/test_design_closure.py, tests/test_deliver.py, docs/improvement-ledger.md
- Approved: user:2026-10-23
- Outline: 1751f50ca861aaf9

## 交付按固定顺序一次跑完：deliver.py (2026-10-23)

R6 从待办记录到打包要手工串十来个命令，出过约 8 次操作错误：新鲜度检查拿错了文件（manifest.json）、
`--reference-contract` 给错文件、预检“有条件通过”时退出码非零把命令链断开、旧预检报告没删导致拒绝覆盖、
重放漏 `--output-root`；`delivery-evidence.json` 每版都要另写脚本生成。技能只有分步命令，没有执行顺序和参数的规范（rule_missing）。
现在 `scripts/deliver.py <交付目录>` 按固定顺序跑：准备、待办审计、生成前预检、出图、一键验证、交付预检、生成报告、
交付证据、证据新鲜度、打包、输入核对；参数记在 `record/deliver.json`，每版沿用；`inputs` 同时传给待办审计
（新增 `--input`）、一键验证和打包；每步状态从它写出的结果读，只有 PASS、DONE、有条件通过、未完成、AUTOMATED_PASS、
FRESH 继续，其余状态、没写出结果或命令出错即停；预检文件只有一个算 FAIL；交付证据按本次运行写出的文件生成。用 R6 副本实跑验证。

- Event: user:2026-10-23
- Causes: rule_missing 1
- Changed: SKILL.md, references/delivery-report.md, docs/operating-cadence.md, scripts/deliver.py, scripts/audit_design_closure.py, scripts/verify_schematic.py, scripts/README.md, tests/test_deliver.py, tests/test_design_closure.py, docs/improvement-ledger.md
- Approved: user:2026-10-23
- Outline: ec7bab061aca9f4d

## 待办只看本版；外部条件不确定时给出选型方案并先问再画 (2026-10-23)

用户审视 R3–R6 后指出：待办编号是否跨版本一致不重要，重要的是内容；每次交付的待办只由本版设计过程中确认仍需做的事项决定，
不需要版本之间的比较和收敛规则。原规则让每版比较未解决数与器件数、`pack_design.py` 在待办变多或有依据的需求变少时
要求 `regression_reason`，R6 也因此把 R5 的待办整体搬过来（judgment：规则把版本比较当成了设计状态）。
选型方面，RT7209B 一颗芯片带出 16 件外部资料待办中的 10 件，选型却不比较外部依赖，也不给用户可选方案（rule_missing）。
现在删除版本间比较（review-comments §3、design-closure 的收敛估算与每轮比较、`pack_design` 的倒退检查、notes 的 `regression_reason`），
保留“改图”点名的位号须与上一版不同这一核对；待办每版重新确认。每个选定候选写 `external_dependencies`；不为空时要有 2–3 个
`options`、一个推荐和理由，以及用户的 `decision`，第 2 步结束时先问再画；报告新增“外部条件不确定的选型”一节。
“上一版已审查的型号不换”改为作为候选之一同等比较。R4 的选型记录没写外部依赖，多一个报告问题（R1–R3 没有选型记录，原本就报缺失），按运行节奏第 5 步更新基线。

- Event: user:2026-10-23
- Causes: judgment 1, rule_missing 1
- Changed: SKILL.md, references/design-closure.md, references/review-comments.md, references/delivery-report.md, references/core-part-selection.md, scripts/pack_design.py, scripts/render_design_report.py, tests/test_design_report.py, tests/regression/baseline.json, docs/improvement-ledger.md
- Approved: user:2026-10-23
- Outline: 01b2862ba30f8cfa

## 不依赖计算的资料缺口写明理由 (2026-10-23)

把 R6 迁到 gap_version 1 时，W-VTR（固件上电行为确认）和 W-ISO（加强绝缘资格）没有任何数值计算依赖它们，
`calculations` 非空的要求只能靠挂不相关的计算来满足（rule_missing）。现在允许空列表加 `no_calculation_reason`，
报告在“影响的计算”写“无”并给出理由。

- Event: user:2026-10-23
- Causes: rule_missing 1
- Changed: references/design-closure.md, scripts/audit_design_closure.py, scripts/render_design_report.py, tests/test_design_closure.py, docs/improvement-ledger.md

## 资料缺口在待办里当场写清，报告按负责方汇总问题 (2026-10-23)

逐条讲解 R6 的外部待办时，用户发现设计时已经知道的资料缺口，报告没有讲清楚：待办只有一句 action，
缺的是哪条规格、为什么只能找原厂、要问什么都不在报告里；14 件 external 待办只用了两句共用的替代做法；
找谁写成“电路设计与原厂应用支持”；缺口细节只在“有条件成立的计算”表里，和待办没有关联。
归因：`missing_guarantee` 只要求写在计算上，external 待办只要求 owner/action/fallback，审计和报告都不要求说明缺口（rule_missing）。
现在 `gap_version: 1` 的未关闭 external 待办要写 missing（手册给了 / 还需要 / 页码）、why_external、calculations、consequence、
questions 和具体的 owner、本项自己的 fallback；审计报缺字段、出处格式、计算不存在或非 conditional、泛称负责方和重复替代做法；
报告逐件列出缺口、影响的计算和问题，新增“要向外部要的资料”一节按负责方汇总，计算表反查对应待办，结论单列缺外部资料一行。
有未关闭 external 待办却没有 `gap_version` 的交付报告提出问题；R1–R4 因此各多一个报告问题，这是真问题，按运行节奏第 5 步更新基线。R6 尚未迁移。

- Event: user:2026-10-23
- Causes: rule_missing 1
- Changed: references/design-closure.md, references/delivery-report.md, scripts/audit_design_closure.py, scripts/render_design_report.py, tests/test_design_closure.py, tests/test_design_report.py, tests/regression/baseline.json, docs/improvement-ledger.md

## 计算参数逐项有来源；优先手册规定的工作方式 (2026-10-23)

R5 的 U601（RT7209BGQW）GPIO1/GPIO3 用开漏灌电流直驱光耦 U403/U202。手册 GPIO 一节只有开路电压和偏置电流档，
没有灌电流、VOL 或导通电阻，参考电路 GPIO 悬空；R4-OPTO 计算却写了"VOL≤0.4V"，W-OPTO 记为 external 后照样交付。
归因：第 2 步已写"空白不能写成保证的 ≤/≥"，但 design-closure 的计算只有 checks 和自由文本假设，审计不查参数来源
（rule_not_enforced）；没有"优先手册规定的工作方式"的规则，"不用加电路去关闭证据缺口"和收敛估算反而把外置缓冲判为不采用
（rule_missing）；模式库"故障/许可信号光耦"把 GPIO 灌电流当默认驱动（knowledge_wrong）。
现在 `parameter_version: 1` 的计算逐项列 `parameters`（basis 与 `datasheet:<路径>#p<页>` 定位），手册没给的标 `unspecified`
并指向 `operating_points`；有可行的规定内替代却保留未规定方式即 FAIL、拒绝打包；缺 `parameter_version` 的交付报告提出问题。
R1–R4 的旧记录因此各多一个报告问题，这是真问题（旧计算确实没有参数来源），按运行节奏第 5 步更新基线。

- Event: review:SR-20261023-R5-从头审查-claude-5802e8c/F-GPIO-SINK, review:SR-20261023-R5-全新独立复审-1fe4df6/W-OPTO, user:2026-10-23
- Causes: rule_not_enforced 1, rule_missing 1, knowledge_wrong 1
- Changed: SKILL.md, references/design-closure.md, references/circuit-patterns/isolated-feedback.md, scripts/audit_design_closure.py, scripts/render_design_report.py, tests/test_design_closure.py, tests/test_design_report.py, tests/regression/baseline.json, docs/improvement-ledger.md
- Approved: user:2026-10-23
- Outline: 2c8f8fa9a4aa0bac

## 根图与 System_block 助手；纲要哈希覆盖主流程 (2026-10-23)

框架复查发现：第 1 步强制 System_block，第 6 步却只写"由工程脚本组装根图"，技能里没有任何组装代码或样例。
100 W PD R4 的 `record/scripts/assemble.py` 手写了层次图框坐标、子页实例路径改写、System_block
箭头逐点坐标与文字对齐特判、`.kicad_pro` 和 `sym-lib-table`，每块新板都要重写一遍，System_block 只能事后审计。
新增 `schematic_layout/root.py`：`Root.page/flow/isolation/write` 由页框推出流向线端点与箭头，
能量流与控制链线宽不同，写盘前拒绝压线文字并跑 System_block 审计；两页小板端到端 `verify_schematic.py`
为 AUTOMATED_PASS（`tests/test_root.py`）。同时纲要写明主流程步骤也须人确认，但哈希原先只覆盖纲要一节和 O1–O8，
现把 SKILL.md「主流程」纳入；硬性规则中与 P1–P7 重复的说法改为引用 P 编号。三项均经用户确认后实施。

- Event: user:2026-10-23
- Causes: rule_missing 2, knowledge_missing 1
- Changed: SKILL.md, README.md, references/drawing-recipes.md, scripts/README.md, scripts/schematic_layout/root.py, scripts/check_ledger.py, tests/test_root.py, docs/improvement-ledger.md
- Approved: user:2026-10-23
- Outline: 5c9fb9e09c709245

## ASG 纲要定为核心标准 (2026-10-23)

用户要求整个架构体现在纲要里，纲要作为 ASG 的核心标准，后续改纲要须先和人确认。
此前"纲要"只指绘图规则 O1–O8，核心原则分散在 SKILL.md 硬性规则、README 设计约定和改进计划三处；
改进闭环第 4 步允许按归因直接改技能，没有任何东西保护纲要。现在 SKILL.md 增加「ASG 纲要（核心标准）」
（架构、P1–P7、修改规则），O1–O8 改称绘图纲要并归入其中；`check_ledger.py` 对两段纲要文字取哈希，
与最新一条带 `Outline:` 的已确认台账条目不一致即 FAIL。草案经用户逐项确认后写入。

- Event: user:2026-10-23
- Causes: rule_missing 1
- Changed: SKILL.md, README.md, references/drawing-recipes.md, docs/operating-cadence.md, docs/improvement-ledger.md, scripts/check_ledger.py, tests/test_ledger.py
- Approved: user:2026-10-23
- Outline: 84c5b3a6360b1107

## Library lookup recognises renamed copies (2026-10-19)

Filing the 100 W PD datasheets showed that `locate_file` only matched a
library copy by the catalog's (stale) SHA-256 or by file name, so 25 files
that were already in the library under another name were reported missing.
It now also hashes library files of the same byte size, and one walk of
`raw/` serves a whole datasheets folder (130 files: 31 s → a few seconds).
On the 100 W PD inputs the unfiled list went 34 → 3 (one part and two
licence documents).

- Event: test:2026-10-19-100W-PD-datasheets-filed (filing session's report), user:2026-10-19
- Causes: rule_not_enforced 1
- Changed: scripts/find_parts.py, scripts/pack_design.py, tests/test_find_parts.py

## Reviewer side of selection and attribution (2026-10-19)

Improvement plan stage 5, done in the schematic-review repository
(`scripts/review_selection.py`, `references/selection-review.md`, its own
`docs/improvement-ledger.md` and `check_ledger.py`). SR now re-judges every
selection role and every attributed comment independently. On this side
review-comments.md says how those verdicts come back: a DISAGREE with an
alternative part is a DESIGN/REDESIGN item, a wrong rejection reason is
knowledge_wrong, a missing decisive condition is knowledge_missing, and a
comment that recurs after a judgment attribution may not be judgment again.
Left open: SR's own regression set over the same deliveries, which needs
reproducible review runs.

- Event: user:2026-10-19 (accepted improvement plan, stage 5)
- Causes: rule_missing 1
- Changed: references/review-comments.md

## Circuit pattern library, first batch (2026-10-19)

Improvement plan stage 4. part-roles.md says what a kind of part does;
nothing said how a function is usually built, which approaches exist and
what each one's known pitfalls are, so every board started from a reference
design's BOM. `references/circuit-patterns/` holds 16 patterns extracted
from 100 W PD R1–R4 (input protection, PFC, QR flyback, ZCD, Y-cap
bridging, bias supply, aux OVP latch, isolated feedback, synchronous
rectification, output storage, current sensing, PD output control, Type-C
protection, NTC sensing, test points, AC indicator); each approach lists
its part classes, required peripherals, calculations, pitfalls that cite
the R4 review items, and sources. `find_parts.py --patterns` searches
them; `page-plan.json` names a pattern approach per functional block (the
report checks it exists, or that lessons.json registers the gap). The
patterns live in the skill because the wiki schema has no such page type.

- Event: review:SR-20261019-R3-改版前独立审查-41f4ad3/W-OPTO, W-MLCC, W-SR, W-PORT-SOA, W-AUX-OVP, W-ZCD, W-CAL and the other R4 items cited in the pattern files; user:2026-10-19 (plan stage 4)
- Causes: knowledge_missing 16
- Changed: references/circuit-patterns.md, references/circuit-patterns, scripts/find_parts.py, scripts/render_design_report.py, tests/test_find_parts.py, tests/test_design_report.py, SKILL.md, references/delivery-report.md, README.md

## Operating cadence (2026-10-19)

Improvement plan stage 6. `docs/operating-cadence.md` fixes the seven
steps of every board version (deliver, independent review, attribute,
change, regress, ledger and commit, feed back test results), the checkpoint
of each step and the three numbers recorded per version.

- Event: user:2026-10-19 (accepted improvement plan, stage 6)
- Causes: rule_missing 0 (process document, no finding)
- Changed: docs/operating-cadence.md, SKILL.md

## Decisive conditions judged by the script (2026-10-19)

Improvement plan stage 3. `selection.json` recorded decisive conditions as
prose, so the report could only check that something was written, not that
the chosen part met it. Conditions are now objects (`param`, `op` in
<=, >=, covers, equals, has, `limit`, `unit`, `requirement`); every
candidate records the value it was read at with the page; selected and
alternate candidates must satisfy every condition, a rejected one must fail
at least one or carry a `reject_kind` (dependency, data, availability, cost,
preference). The report's selection table shows each rejection's basis. The
R4 record was converted: 11 roles, 48 candidates, 6 rejected on preference,
1 on data, the rest on a failed condition.

- Event: user:2026-10-19 (accepted improvement plan, stage 3)
- Causes: rule_not_enforced 1
- Changed: scripts/render_design_report.py, tests/test_design_report.py, references/core-part-selection.md

## Datasheet filing gate (2026-10-19)

Improvement plan stage 2. SKILL.md step 2 has long said every downloaded
datasheet is copied into the HardwareWiki library, and nothing checked it:
R4 declares 130 vendor documents as its datasheets input and the library's
coverage of them was unknown. `pack_design.py` now locates every PDF of the
`datasheets` input in the library (catalog SHA-256, else file name under
`raw/`) and refuses to pack while any is missing, naming them;
`find_parts.py --file <pdf>` answers for one file.

- Event: user:2026-10-19 (accepted improvement plan, stage 2)
- Causes: rule_not_enforced 1
- Changed: scripts/pack_design.py, scripts/find_parts.py, tests/test_find_parts.py, tests/test_design_report.py, SKILL.md, references/delivery-report.md

## Regression skeleton and the feedback channel (2026-10-19)

Improvement plan stages 0 and 1 (`docs/improvement-plan.md`). Until now a
review's findings became skill changes only when someone read the report and
decided what to change, and a rule change was verified only on synthetic
fixtures.

- `scripts/run_regression.py` re-runs the report and packing checks on the
  real deliveries listed in `tests/regression/boards.json` (100 W PD R1–R4;
  missing folders are skipped) and fails when a board's report problems,
  packing errors or gate statuses get worse than `baseline.json`. Nothing in
  a delivery is written.
- `record/lessons.json` is a required delivery record: one event per review
  item, datasheet page, test record or user correction, with a cause class
  and the file the change landed in (rules go to `scripts/`, knowledge to
  `references/` or the library, `judgment` must say why no rule could catch
  it, `none` must cite what was checked). The report lists them under
  本版学到的东西.
- Every review response carries `cause`; a cause other than `none` must have
  a matching event in `lessons.json` with the same class.
- `scripts/check_ledger.py` checks this ledger's newest entry for the three
  lines below; `tests/test_ledger.py` runs it on the real ledger.
- The 23 R4 review items were attributed: 14 rule_not_enforced (calculations
  the skill asked for but never enforced until d86e397's missing_guarantee
  and progress checks), 1 rule_missing (System_block gate, 20c7011), 7
  knowledge_missing (selection decisive conditions and part-roles rows), 1
  judgment (calibration budget).

- Event: review:SR-20261019-R3-改版前独立审查-41f4ad3/W-AC … W-DRAW (23 items, see the R4 delivery's lessons.json), user:2026-10-19
- Causes: rule_not_enforced 14, rule_missing 1, knowledge_missing 7, judgment 1
- Changed: scripts/run_regression.py, scripts/check_ledger.py, scripts/render_design_report.py, tests/regression/boards.json, tests/test_regression.py, tests/test_ledger.py, tests/test_design_report.py, SKILL.md, references/review-comments.md, references/delivery-report.md, README.md

## Core part selection (2026-10-19)

Asked how ASG decides which core parts to use, the honest answer was that it
did not: step 2 verified whatever MPN the architecture step had already
written, and the 100 W PD revisions took every IC from the one reference
design in the knowledge base. The skill also had no picture of what kinds of
parts exist, so it could not even start a search from the function needed.

- `references/part-roles.md` gives that picture: every category and
  subcategory of `HardwareWiki/raw/Datasheet` with what the part does, where
  it sits in a circuit and the parameters that eliminate candidates, plus a
  function → category index to start from. `find_parts.py --roles-coverage`
  keeps it aligned with the library's real subcategories (new subcategory in
  the library = missing row).
- `scripts/find_parts.py` searches the library's `catalog.json` (vendor,
  model, category, facets, optional first pages), lists PDFs not yet indexed
  as 未入索引, and finds reference designs and application notes by path. The
  library stays outside the skill (`HARDWARE_WIKI`, default
  `~/Documents/知识库/HardwareWiki`).
- `references/core-part-selection.md` fixes the candidate sources in order
  (user's parts list, previous reviewed revision, same-topology reference
  designs, library category search, external search last with the datasheet
  filed into the library), the elimination order and the record
  `record/selection.json`. `render_design_report.py` requires it: each role
  needs decisive conditions, sources and at least two candidates (or a
  reason), exactly one selected candidate whose MPN is the part's value in
  the intent, a reason per candidate, a datasheet that exists in the
  library, and every U/Q/T part covered by a role. The report gains a
  核心器件选型 section; `pack_design.py` refuses a delivery without it.

## 100 W PD R4 review follow-up (2026-10-19)

The R4 report passed every drawing gate and still showed the skill letting a
revision stand still. Traced to rules that only checked presence, not content:

- 18 of 23 review responses shared one `detail` sentence and 8 `DESIGN`
  responses pointed at work items whose `action` was the comment itself.
  `check_responses` rejects a `detail` reused across comments, requires an
  open design work item referenced by `DESIGN` to carry `progress` (what this
  version did, not equal to `action`), requires `REDESIGN` changes to name a
  part or page, and adds `CALC_DOC` (补计算/补文档) for document-only work so
  it is no longer called 改图. The report states after the summary how many
  comments were actually redrawn or recalculated.
- Open design work went 0 → 10 and supported requirements 8 → 0 between R3
  and R4 without a word. `pack_design.py --input previous=` compares both
  counts and refuses a regression unless `notes.json` gives
  `regression_reason`; it also checks that a `REDESIGN` response's named
  parts differ from the previous intent.
- All 27 calculations were `partial`/`conditional`, including 1.33 A < 3 A.
  `conditional` now needs `missing_guarantee` (which guarantee is absent) and
  `partial` needs non-empty `omitted_terms`; the report prints values with
  three significant digits instead of 16-digit floats.
- draw_pages.py kept gap=38 and pitch=35 behind 12 `justify` calls.
  `justify` takes `conflict` (part, pin or `text:<field>`) for spacing
  deviations, a reason alone leaves the finding open, and more than three
  justified spacing deviations on a page is a finding.
- `highlights` carried process talk ("第二轮将核销"); process words in
  highlights are a report problem.

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
