---
name: autonomous-schematic-generation
description: >-
  Autonomous-Schematic-Generation (ASG): starting from requirement documents,
  draw readable, electrically correct, natively verified KiCad schematics.
  Requirements → function trace → System_block and pages → exact-MPN pin maps,
  peripheral contracts and calculations → board electrical intent → page scripts
  with pin-geometry drawing recipes and outline rules O1-O8 → one-shot native
  gates (ERC, pin-by-pin netlist against intent, hierarchy, symbol integrity,
  readability, geometry) → render review → one generated design report and a
  small fixed delivery folder. Also redraws existing KiCad projects without
  electrical change, applies authorized electrical revisions, works through
  review comments and extracts PDF reference designs. Self-checks only; owns
  design feasibility, selection, calculations and functional closure. Use for .kicad_sch
  generation or redraw, 原理图自动生成、从需求画原理图、画原理图、重画原理图、原理图排版.
---

# Autonomous-Schematic-Generation (ASG)

## 目的与边界

ASG 从需求文档出发，让 Agent 在 KiCad 中画出**可读、电气正确、经 KiCad 验证**的原理图。

- **电气正确**：电路来自已确认的需求和确切 MPN 的数据手册，用一份独立写出的整板设计要求表表达；
  KiCad 网表必须与设计要求表逐脚一致。
- **可读**：结构由 Agent 按纲要 O1–O8 决定，坐标由 `recipes.Sheet` 按真实引脚几何推出。
- **经 KiCad 验证**：以 KiCad 导出的 ERC、XML 网表和 PDF 为准；JSON、脚本成功或 solver 的 `solved` 都不算证据。

ASG 负责需求到电路的方案可行性、选型依据、设计计算和功能实现，不能把未做完的设计留给别人。
新设计和电气改版同时遵循
[设计待办记录](references/design-closure.md)，区分工程可完成、真实外部依赖和后续环节验证。
电气改版按其中的收敛迭代执行；审计列出的可执行设计动作须继续完成，不能把缺口清单当成结束条件。

以下验收与独立复核不由 ASG 负责：

| 事项 | 交给 |
| --- | --- |
| 独立的电气审查和定稿结论 | 由审查方给出；ASG 只做自检，并处理收到的审查意见 |
| PCB封装库、焊盘/孔/钢网、布局布线、DFM与散热实现 | 《结构与PCB设计要求》交接文档 |
| 生产放行、PCB、SI/PI、EMC | 后续环节 |

## 选择工作流

| 任务 | 做法 |
| --- | --- |
| 从需求做新设计 | 主流程第 0–8 步 |
| 给已有工程新增模块或页面 | 第 0 步只读相关需求，第 2–8 步；改动已有网络时按“电气改版” |
| 重画已有工程，电气不变 | [existing-project-redraw.md](references/existing-project-redraw.md) 锁定基线，再走第 4–8 步 |
| 已授权、保持连线与图面的 Value 参数修改 | [value-patch.md](references/value-patch.md) 生成 KiCad 验证的草稿图，再更新设计要求表/脚本与计算，走第 6–8 步 |
| 授权的电气改版 | 先读 [electrical-redesign.md](references/electrical-redesign.md) 和 [change-preflight.md](references/change-preflight.md)，再走主流程 |
| 收到审查意见后继续设计 | 按 [处理审查意见](references/review-comments.md) 逐条登记处理方式，再按电气改版处理需要改图的项；每条意见写本版做了什么，补设计的待办写 `progress`，没改电路的叫“补计算/补文档”不叫“改图” |
| 从 PDF 参考设计提取电路 | [pdf-schematic-extraction.md](references/pdf-schematic-extraction.md)；提取结果只作线索，仍按第 2 步核对手册 |
| 模块化数据、SKiDL/circuit-synth 导入、锁定基线 | [circuit-ir.md](references/circuit-ir.md)。人读的页面仍按第 5 步用 recipes 画 |
| 用户要求 CopperPilot 协助 | [copperpilot-reference-workflow.md](references/copperpilot-reference-workflow.md) |

## 主流程

### 0. 读需求

按 [requirements-to-intent.md](references/requirements-to-intent.md) 第 1–2 节建立需求清单和
功能追溯表。只用已确认的需求，缺口记为待办。每项映射具体功能路径、器件/固件责任和验收；
不能批量挂整板位号代替追溯。只问证据和工程判断不能解决的产品取舍，分两档：
会改变架构或拓扑的缺口（输入电压范围、输出档位/功率、接口、隔离等级、保护目标等）在第 0–1 步
一次性集中问用户，得到答复再继续，不先画一版再问；不改变架构的缺口（参数细节、优化取舍）按写明的
假设继续设计，记成 `requirement` 待办，随交付一起问。

### 1. 架构与分页

第 1 页必须是 `System_block`，画出真实的系统架构、电源与信号流向、板与隔离边界、接口和各页编号；
只有页面索引不算。框图的每条流向线都要在线旁写出它代表的电源轨或信号（RECT、BULK、FB/FAULT 光耦……），
两端都落在页块、箭头或另一条线上；隔离边界是一条写着“隔离”的直线，一次侧页块在一边、二次侧在另一边，
不穿过任何页块。`verify_schematic.py` 的 `system_block` 检查核对这些，悬空线和无名箭头算 FAIL。
按功能、隔离/电压域和可读面积分页；几个很小的功能块合成一页，不单独占一张 A3。
见 [reference-driven-board-design.md](references/reference-driven-board-design.md)。

### 2. 选型、外围电路要求与计算

- 每个核心器件对应确切 MPN/封装的物理引脚表、典型应用、必需外围和装配状态，记录实际阅读的手册页码。
  分立器件的**符号含义**也按确切料号选：TVS 单向/双向、MOS N/P 沟道、NPN/PNP，脚名按手册（单向二极管用 K/A）。
  KiCad `Device:D_TVS` 只表示双向 TVS，不能用于单向器件。
  见 [symbol-and-peripheral-contracts.md](references/symbol-and-peripheral-contracts.md)。
- 数值计算按 [calculation-preflight.md](references/calculation-preflight.md) 写明保证条件；上电/热插拔、关断/掉电、
  全温角点和引脚应力四类按 [requirements-to-intent.md](references/requirements-to-intent.md) 第 4 节清单逐项核。
- 按 [worst-case-bounds.md](references/worst-case-bounds.md) 推导真正的上下界：非线性量检查区间端点、内部驻点和约束边界，
  保留变量依赖；重放同一算式只验证算术。源表条件须匹配实际电压、温度、电流及测试条件，
  仅在厂家明确许可的范围内使用其插值；工程估计和未知轴不能升为保证。
- **计算门槛按设计用途**：计算的目的是把值选对、留出裕量，让图一次出对。手册保证条件覆盖不到时，
  写明假设、余量和没算进去的项，结论记为有条件成立（`conditional`），不阻塞出图；只有算出不满足（`failed`）
  才是必须先解决的设计缺口。按最坏情况逐条证明属于独立审查，不在 ASG 内重复。
- 每条计算给出位号（`refs`）和算出的值对门槛（`checks`），结论由数字决定；保护/检测/钳位阈值两侧都算
  （不误动作 + 保护有效），稳压管/TVS/基准源都要有计算。`conditional` 要写明缺的是哪项保证（`missing_guarantee`），
  `partial` 要写明漏了什么；没有缺失保证的核对就是 `supported`，不拿“有条件”当免责。见 [设计待办记录](references/design-closure.md)。
- 器件热可行性（功耗→结温）属于选型，在本步算；散热实现才交 PCB。见 requirements-to-intent.md 第 4 节。
- 外围电路要求中的每个数值上/下界也须逐项核原表：确切变体、版本、页/表/参数行、单位、MIN/TYP/MAX 列、脚注及测试条件。
  不能只核计算输入；TYP 或所需限值列的空白/破折号不能写成保证的 `≤`/`≥`，依赖它的负载/时序结论继续保留未知。
- 核实决定架构的确切型号/固件能力；未证实的依赖保持条件状态，并评估替代实现。损耗预算列出主要遗漏项及有依据的边界，不能用子总和证明达标。
- 原理图阶段 `footprint` 可以留空。必须核实所选订货变体、实际物理脚号（含EP/Kelvin）及电气/热额定适用条件；PCB封装库制作、焊盘尺寸、孔径、钢网、courtyard、布线与DFM交给PCB阶段，不能作为原理图定稿门槛。既有封装候选仅作为未确认的后续环节输入，不用填充率证明电气选型完成。
- **资料规则**：新下载的器件数据手册存入工程，同时复制到
  `~/Documents/知识库/HardwareWiki/raw/Datasheet/<分类>/<子类>/`，文件名为 `Vendor - PartNumber.pdf`
  （厂商简称按 `raw/Datasheet/VENDORS.yaml`，分类按 `raw/Datasheet/元器件体系/器件统一分类大表.md`，
  无分类放 `ZZ_其他` 并报告）。raw/ 中已有相同哈希或型号时跳过。只复制原文件，不改工程路径，
  也不触发知识库入库。参考设计和评估板手册放 `raw/Designexample/<拓扑>/<板名>/`，
  文件名为 `Vendor - BoardName - Title.pdf`；应用笔记和标准不放 Datasheet 目录。

### 3. 整板设计要求表

写一份整板 `electrical-intent.json`：器件、网络 `{name: [ref.pin]}`、`no_connect`，以及每个器件的页面
`fields.Circuit`。格式和规则见 [requirements-to-intent.md](references/requirements-to-intent.md) 第 5 节。
每个物理引脚要么接入网络，要么有依据地标 NC。设计要求表从需求和手册写出，不从草稿图回抄。
用 `net_roles` 区分 power/return/signal，至少覆盖 rails 与阈值/反馈等易混淆网络；声明 signal 后 recipes 禁止给它放电源符号。

### 4. 页面方案

为每页写一张简短的方案表，内容包括：读者任务（跟随能量流、看懂反馈、追一个受保护接口……）、
功能块及每块的位号、主路径、rails、出页网络及目的功能/页码、标签边界。先保证一条功能路径易读，再决定拆页或加大纸张。
方案表随交付保存为 `record/page-plan.json`（每页 `file`、`reader_tasks`、`blocks`），本页每个器件都要属于一个功能块；
看图检查按它逐条追路径。见 [human-readable-routing.md](references/human-readable-routing.md) 第 1 节。
纸张在画完后定：内容能放进 A4 就用 A4；一页只剩零散小块时并页，不把小电路摊在 A3 上。

- 按拓扑选结构（Buck、LDO、隔离反激、滤波、MCU 各不相同），见
  [schematic-drawing-standards.md](references/schematic-drawing-standards.md) 第 2 节。不得为别的拓扑编造 SW 节点或电感级。
- 按纲要 O1–O8 决定页面流向、锚点、器件归属、画法、出线、标签、间距和修复顺序，见
  [drawing-recipes.md](references/drawing-recipes.md)。

### 5. 写图页脚本

```python
from schematic_layout.pages import page_intents
from schematic_layout.recipes import Sheet, DOWN, RIGHT, UP, LEFT, add
from schematic_layout.sexpr import dump

RAILS = {"GND": "power:GND", "+3V3": "power:+3V3"}
for n, (key, page) in enumerate(page_intents(board, rails=RAILS).items(), 1):
    s = Sheet(page["intent"], rails=page["rails"], external=page["external"],
              power_ref_start=n * 100 + 1)
    s.place("U201", (101.6, 76.2), pin="3", facing={"3": LEFT})   # 锚点：按引脚朝向定姿
    ...                                                             # series / shunt / bank / divider / label
    root, report = s.build(key)            # 先用 draft=True 出图调试，交付不能是 draft
```

- 先看 `s.plan` 给出的器件角色和网络标签角色。只给锚点写坐标，其余器件用与角色相符的画法从引脚推出。
  有意偏离纲要时用 `s.justify(对象, 理由)` 记录。把方案表的功能块传给 `Sheet(..., blocks={块名: [位号]})`：
  同一块内的器件之间不许用局部连接标签代替导线（HR-01），审计会列出只连一块的标签。
- 间距只为通过检查而加大，通过后缩回：gap、stub、pitch、lead 和电源符号/标签引线超过 12 格（约 15 mm）
  会进结构审计，要么缩小，要么 `justify(对象, 理由, conflict=避让的器件/引脚/text:字段)` 写明避让了什么；
  一页超过 3 处间距豁免本身就是审计不通过，改为折行或重新锚定。不得用加大间距把一页摊满。
- 先列真实 planned 局部网名及其字号。在相应 series 段或 own-pin stub 放置前，显式用
  `max(原gap, s.name_run_steps(原net, font=原字号))` 预留直段，之后仍调用原 `s.name`。
  多段链逐段按真实网络预算；不得全局加gap、缩字、改名或用标签绕过连线。预算不证明无遮挡或 KiCad 字体覆盖。
- `build()` 遇到硬缺陷会直接报错。`report["structure"]` 必须为 PASS，`report["readability"]["gate"]` 必须为 PASS。
  失败时按 O8 改结构（方向、间隙、顺序 → 锚点 → 拆行）后重建，不得手调坐标打补丁。
  `report["readability"]` 还给出 `cell_coverage`（有东西的 25.4 mm 格占比）、`part_groups`（只靠标签/电源符号相连的器件组）
  和 `fits_paper`：覆盖率低、组数多于方案表的功能块、内容能放进更小的纸张，都说明这页要并块、缩间距或换纸。
- 图页脚本随交付版本一起保存；下一版只重生成有变化的页面。

### 6. 组装与一键验证

多页工程由工程脚本组装根图（层次图框、`System_block`），ASG 不自动写多页层次。之后运行：

```bash
python3 <skill>/scripts/verify_schematic.py <root.kicad_sch> --intent electrical-intent.json \
  --out <新的空目录> [--expected-pages N] [--symbol-exceptions F] [--readability-waivers F] \
  [--reference-contract F] [--design-closure D --artifact-root R] \
  [--baseline-xml B --change-contract C --preflight P]
```

它一次完成：KiCad ERC / XML 网表 / PDF 导出，网表分区与器件身份逐脚对比设计要求表（图上画出的网名须等于设计要求表里同一组引脚的网名，
只允许页路径前缀；KiCad 自动网名不比），层次与 PDF 页数，根图的系统框图检查（`system_block`：流向线有名字、两端有着落、隔离边界不穿块、每个页块有线到达），
符号引脚完整性，分立器件符号含义与手册/型号后缀是否一致（`discrete_semantics`），可读性自动检查（零异网交叉、零三折以上两端连线、
内容放得进更小纸张的页算 FAIL），以及每个有效页面的几何检查，汇总到 `summary.json`。
只有全部自动检查为 PASS 时结果才是 `AUTOMATED_PASS`。

- 新设计提供 `--design-closure`，核对需求实现、外部依赖、计算覆盖和证据是否最新；格式与边界见 [设计待办记录](references/design-closure.md)。未提供时明确为 NOT_CHECKED，不能据此声明全流程完成。
- 新设计要求 ERC 零违规。重画工程时保留基线和最终两份原始 ERC，逐条确认没有新增违规，并披露继承的问题。
- ERC 摘要按原始报告的 UUID/object 对应实际层次实例、引脚及 KiCad 网络，再归因到 rail；
  不凭位号或网名文字猜问题对象。无法对应时保留原违规与待核边界，见 [project-verification.md](references/project-verification.md#erc-summary-object-binding)。
- 几何检查只覆盖本次 KiCad 导出中已合格的对象，范围与未支持对象见 [native-geometry.md](references/native-geometry.md)；
  外部 JSON 回执不能授权放行。`geometry` 为 INSUFFICIENT 时保留缺口并在 KiCad 渲染图上核对，有限 PASS 不等于整案通过。
  库里隐藏的引脚号/脚名不计；可见但无法原生核对的引脚文字列在 `geometry.render_review_items`，
  不算缺口，第 7 步看图检查必须逐页覆盖这些对象并在 visual-review.json 里写明。
- 图面检查只有三种结果：PASS、FAIL（画图问题，如外框间距不足 1.27 mm、导线交叉不打点、注释压线）、
  INSUFFICIENT（检查器覆盖不到的对象）。FAIL 由 ASG 改图关闭，不交给人复核；可读性或几何 FAIL 时
  `pack_design.py` 拒绝打包。只有 INSUFFICIENT 缺口留给看图检查核对。
- 板级 `Net-(...)` 式网名须有来源证据，仅有 XML 时保持 INSUFFICIENT，见
  [project-verification.md](references/project-verification.md#automatic-looking-names-need-source-evidence)；
  编码斜杠层次字段只用 [schematic-drawing-standards.md](references/schematic-drawing-standards.md) 的有限回退，不推广。
- 失败时修改相应页面脚本，在新的运行目录重新生成并验证。不得为了降低计数而加 PWR_FLAG、加排除项或改引脚类型。
- 受控的自动结构资格有两类，都在设计要求表中逐网声明、用 `Sheet.power_flag()` 每网放一个 PWR_FLAG，由 `external_supply` 自动检查核对：
  只由连接器引入、板上没有电源输出脚驱动的电源或地（`external_supply`）；经一颗串联电阻、电感、磁珠或保险丝
  从已有驱动的电源派生的电源脚供电网，例如 RC 滤波的模拟电源（`filtered_supply`，逐条列入设计报告）。声明格式与核对内容见
  [requirements-to-intent.md](references/requirements-to-intent.md) 第 5 节“连接器角色与外部供电”。
- 整流、变压器或分立稳压电路没有 KiCad `power_out` 时，不冒充连接器供电，也不修改器件脚型。
  先复核实际能量来源、返回路径、极性、启动和故障状态，再使用 [分立供电复核](references/reviewed-circuit-supply.md)
  的 `reviewed_circuit_supply`。该类是证据对应的人工供电语义结论；自动检查只核证据是否最新和 KiCad 拓扑，
  不自动证明电压、电流、效率或保护成立。未完成复核时保留 ERC，不凭降低计数批准标记。
- `symbol_integrity` 的 `unnamed_pins` 只作诊断（KiCad 运放、单门逻辑等符号的输入/输出脚按库惯例不写名字）。
  列出的每个器件（不限核心器件）都要在外围电路核对记录里按数据手册名字逐脚对应，并在设计报告中列出这些脚；
  否则按脚名核对时会对不上。

### 7. 看图检查

打开导出的 PDF，逐页按 `page-plan.json` 的读者任务追一遍：主路径、每个支持网络到对应引脚和正确回路、
重复通道、每个回路域和隔离跨越。每页记录的路径条数不少于读者任务数；“看过所有页”“与上一版像素一致”都不算证据。
`geometry.render_review_items` 里的引脚文字逐器件处置：每条处置点名该器件并写出在图上看到了什么
（脚号在引脚外侧、脚名未被导线压住……），同一句话不能套用到不同器件；`render_design_report.py` 会检查这两点。
状态写 待返工（REWORK_REQUIRED）、待看图检查（REVIEW_PENDING）或 已看图检查（REVIEWED）。
用户否决会重新打开看图检查。见 [human-readable-routing.md](references/human-readable-routing.md) 第 4 节。

### 8. 交付

- 按 [execution-evidence.md](references/execution-evidence.md) 写 `delivery-evidence.json`，报告前运行
  `scripts/check_delivery_freshness.py`；任何导出后的修改都会使旧结果作废。
- 还有可独立完成的设计项就继续，不以列出缺口代替完成。`pack_design.py --input previous=` 会对比上一版：
  设计阶段待办变多或有依据的需求变少，必须在 notes.json 的 `regression_reason` 写明原因。
- 交付目录只有下面四样，由 [交付与设计报告](references/delivery-report.md) 规定，`pack_design.py` 检查：

```
<交付目录>/
  设计报告.md     唯一给人看的文件：render_design_report.py 生成，agent 只通过 notes.json 补白话
  原理图/         KiCad 工程（根图、各页、项目符号库与封装库）、schematic.pdf、netlist.xml、BOM.csv
  设计资料/       跨版本有效、每版更新的设计文档（方案与选型依据、PCB与结构要求、磁件设计单等）
  record/         设计要求表、页面方案表、待办处理情况、自检结果、看图检查、审查意见处理、本版用到的计算、
                  图页脚本、manifest.json（需求、原厂资料、前一版设计按路径+SHA-256 登记，不复制）
```

```bash
python3 <skill>/scripts/render_design_report.py <交付目录> [--notes notes.json] [--title 标题]
python3 <skill>/scripts/pack_design.py <交付目录> --input requirements=<需求目录> \
  --input datasheets=<资料目录> [--input previous=<前一版交付目录>]
```

报告如实写出各项自检的 PASS/FAIL/INSUFFICIENT 及数量（含零）。历史版本快照、日志、仿真中间文件、
审查方的结果都不放进交付目录。

## 在任务流程中运行

由外部流程派发任务时，读 [任务输入输出格式](references/workflow-handoff.md)。
以 `task.json` 的需求、版本、前版设计和审查意见为输入；架构生成、查资料、计算与改图仍由 ASG 完成。
交付仍按第 8 步的目录；用流程提供的 `pack-result` 生成 `result.json`。独立使用本技能不依赖外部流程。

## 硬性规则

- 设计要求表独立于几何：位号、值、MPN、引脚编号、装配状态和网络归属不因摆放改变；不为布图方便改符号的引脚映射。
- 不手写辅助器件坐标；不把可读页面交给 MST/A* 自动路由；不用标签掩盖失败的连线。
- 标签角色：全局标签只用于出页网络；电源轨和回路用 Value 等于网络名的电源符号；隔离的回路不能用通用 GND。
- DNP 器件保留连线和焊盘，它不等于 IC 的 NC 引脚。
- 不得静默拍平已有层次工程；草稿图生成在新目录，确认基线未变后才写回原工程。
- `AUTOMATED_PASS` 只代表脚本自动检查通过；数据手册审查和看图检查另行完成。如实报告缺口。
- 给人看的文字一律用中文：`design-closure.json` 的假设、没算进去的项、核对项名称、待办、实现说明和 notes 都会原样进报告；
  器件型号、单位和缩写（PFC、OVP）可以保留。计算脚本里写的说明也按此写。`render_design_report.py` 发现英文句子会报问题。

## 参考文件

| 何时读 | 文件 |
| --- | --- |
| 新设计/电气改版的设计待办记录、依赖与计算结论审计 | [design-closure.md](references/design-closure.md) |
| 收到审查意见：逐条处理、采用建议改法、收敛判断 | [review-comments.md](references/review-comments.md) |
| 交付目录、设计报告、打包检查 | [delivery-report.md](references/delivery-report.md) |
| 从需求写设计要求表 | [requirements-to-intent.md](references/requirements-to-intent.md) |
| 架构页、参考设计外围、学习工程师图面 | [reference-driven-board-design.md](references/reference-driven-board-design.md) |
| 选符号、引脚表、外围电路要求 | [symbol-and-peripheral-contracts.md](references/symbol-and-peripheral-contracts.md) |
| 计算条件记录 | [calculation-preflight.md](references/calculation-preflight.md) |
| 非线性极值、条件匹配与插值边界 | [worst-case-bounds.md](references/worst-case-bounds.md) |
| 纲要 O1–O8 与 recipes API | [drawing-recipes.md](references/drawing-recipes.md) |
| 阅读路径、HR-01–HR-11、看图检查 | [human-readable-routing.md](references/human-readable-routing.md) |
| 拓扑结构、标签策略、验证自动检查 | [schematic-drawing-standards.md](references/schematic-drawing-standards.md) |
| 重画已有工程 | [existing-project-redraw.md](references/existing-project-redraw.md) |
| 电气改版与预检 | [electrical-redesign.md](references/electrical-redesign.md)、[change-preflight.md](references/change-preflight.md)、[project-verification.md](references/project-verification.md) |
| 对照工程师模板 | [engineer-template-comparison.md](references/engineer-template-comparison.md) |
| 交付证据与是否最新 | [execution-evidence.md](references/execution-evidence.md) |
| Circuit IR、低层生成器 | [circuit-ir.md](references/circuit-ir.md)、[schematic-generation.md](references/schematic-generation.md) |

运行不需要上游完整仓库、新的 MCP 服务、Bun 或网络连接。
