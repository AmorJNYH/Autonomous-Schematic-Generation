---
name: autonomous-schematic-generation
description: >-
  Autonomous-Schematic-Generation (ASG): starting from requirement documents,
  draw readable, electrically correct, natively verified KiCad schematics.
  Requirements → function trace → System_block and pages → exact-MPN pin maps,
  peripheral contracts and calculations → board electrical intent → page scripts
  with pin-geometry drawing recipes and outline rules O1-O8 → one-shot native
  gates (ERC, pin-by-pin netlist against intent, hierarchy, symbol integrity,
  readability, geometry) → render review → handoff to schematic-review. Also
  redraws existing KiCad projects without electrical change, applies authorized
  electrical revisions and extracts PDF reference designs. Self-checks only;
  owns design feasibility, selection, calculations and functional closure;
  independent electrical review belongs to schematic-review. Use for .kicad_sch
  generation or redraw, 原理图自动生成、从需求画原理图、画原理图、重画原理图、原理图排版.
---

# Autonomous-Schematic-Generation (ASG)

## 目的与边界

ASG 从需求文档出发，让 Agent 在 KiCad 中画出**可读、电气正确、经原生验证**的原理图。

- **电气正确**：电路来自已确认的需求和确切 MPN 的数据手册，用一份独立写出的板级电气意图表达；
  原生网表必须与意图逐脚一致。
- **可读**：结构由 Agent 按纲要 O1–O8 决定，坐标由 `recipes.Sheet` 按真实引脚几何推出。
- **经原生验证**：以 KiCad 导出的 ERC、XML 网表和 PDF 为准；JSON、脚本成功或 solver 的 `solved` 都不算证据。

ASG 负责需求到电路的方案可行性、选型依据、设计计算和功能实现；不能把未做完的设计留给 SR。
SR 独立审查这些设计结论。新设计和电气改版同时遵循
[设计闭环](references/design-closure.md)，区分工程可完成、真实外部依赖和下游验证。

以下验收与独立复核不由 ASG 签署：

| 事项 | 交给 |
| --- | --- |
| 严格的电气审查：工况、裕量、应力、保护、需求符合性、冻结结论 | `schematic-review` |
| 封装、散热、布局实现 | 《结构与PCB设计要求》交接文档 |
| EasyEDA 出图 | `easyeda-schematic-draw` |
| 生产准出、PCB、SI/PI、EMC | 下游流程 |

## 选择工作流

| 任务 | 做法 |
| --- | --- |
| 从需求做新设计 | 主流程第 0–8 步 |
| 给已有工程新增模块或页面 | 第 0 步只读相关需求，第 2–8 步；改动已有网络时按“电气改版” |
| 重画已有工程，电气不变 | [existing-project-redraw.md](references/existing-project-redraw.md) 冻结基线，再走第 4–8 步 |
| 已授权、保持连线与图面的 Value 参数修改 | [value-patch.md](references/value-patch.md) 生成原生验证候选，再更新意图/脚本与计算，走第 6–8 步和 SR 复审 |
| 授权的电气改版 | 先读 [electrical-redesign.md](references/electrical-redesign.md) 和 [change-preflight.md](references/change-preflight.md)，再走主流程 |
| 从 PDF 参考设计提取电路 | [pdf-schematic-extraction.md](references/pdf-schematic-extraction.md)；提取结果只作线索，仍按第 2 步核对手册 |
| 模块化数据、SKiDL/circuit-synth 导入、锁定基线 | [circuit-ir.md](references/circuit-ir.md)。人读的页面仍按第 5 步用 recipes 画 |
| 用户要求 CopperPilot 协助 | [copperpilot-reference-workflow.md](references/copperpilot-reference-workflow.md) |

## 主流程

### 0. 读需求

按 [requirements-to-intent.md](references/requirements-to-intent.md) 第 1–2 节建立需求清单和
功能追溯表。只用已确认的需求，缺口标 OPEN。每项映射具体功能路径、器件/固件责任和验收；
不能批量挂整板位号代替追溯。只问证据和工程判断不能解决的产品取舍。

### 1. 架构与分页

第 1 页必须是 `System_block`，画出真实的系统架构、电源与信号流向、板与隔离边界、接口和各页编号；
只有页面索引不算。按功能、隔离/电压域和可读面积分页。
见 [reference-driven-board-design.md](references/reference-driven-board-design.md)。

### 2. 选型、外围合同与计算

- 每个核心器件绑定确切 MPN/封装的物理引脚表、典型应用、必需外围和装配状态，记录实际阅读的手册页码。
  见 [symbol-and-peripheral-contracts.md](references/symbol-and-peripheral-contracts.md)。
- 数值计算按 [calculation-preflight.md](references/calculation-preflight.md) 写明保证条件；上电/热插拔、关断/掉电、
  全温角点和引脚应力四类按 [requirements-to-intent.md](references/requirements-to-intent.md) 第 4 节清单逐项核。
- 按 [worst-case-bounds.md](references/worst-case-bounds.md) 推导真正的上下界：非线性量检查区间端点、内部驻点和约束边界，
  保留变量依赖；重放同一算式只验证算术。源表条件须匹配实际电压、温度、电流及测试条件，
  仅在厂家明确许可的范围内使用其插值；工程估计和未知轴不能升为保证。
- 外围合同中的每个数值上/下界也须逐项核原表：确切变体、版本、页/表/参数行、单位、MIN/TYP/MAX 列、脚注及测试条件。
  不能只核计算输入；TYP 或所需限值列的空白/破折号不能写成保证的 `≤`/`≥`，依赖它的负载/时序结论继续保留未知。
- 核实决定架构的确切型号/固件能力；未证实的依赖保持条件状态，并评估替代实现。损耗预算列出主要遗漏项及有依据的边界，不能用子总和证明达标。
- 原理图阶段 `footprint` 可以留空；散热和机械需求写进交接文档。
- **资料规则**：新下载的器件数据手册存入工程，同时复制到
  `~/Documents/知识库/HardwareWiki/raw/Datasheet/<分类>/<子类>/`，文件名为 `Vendor - PartNumber.pdf`
  （厂商简称按 `raw/Datasheet/VENDORS.yaml`，分类按 `raw/Datasheet/元器件体系/器件统一分类大表.md`，
  无分类放 `ZZ_其他` 并报告）。raw/ 中已有相同哈希或型号时跳过。只复制原文件，不改工程路径，
  也不触发知识库入库。参考设计和评估板手册放 `raw/Designexample/<拓扑>/<板名>/`，
  文件名为 `Vendor - BoardName - Title.pdf`；应用笔记和标准不放 Datasheet 目录。

### 3. 板级电气意图

写一份整板 `electrical-intent.json`：器件、网络 `{name: [ref.pin]}`、`no_connect`，以及每个器件的页面
`fields.Circuit`。格式和规则见 [requirements-to-intent.md](references/requirements-to-intent.md) 第 5 节。
每个物理引脚要么接入网络，要么有依据地标 NC。意图从需求和手册写出，不从候选图回抄。
用 `net_roles` 区分 power/return/signal，至少覆盖 rails 与阈值/反馈等易混淆网络；声明 signal 后 recipes 禁止给它放电源符号。

### 4. 页面方案

为每页写一张简短的方案表，内容包括：读者任务（跟随能量流、看懂反馈、追一个受保护接口……）、
功能块、主路径、rails、出页网络及目的功能/页码、标签边界。先保证一条功能路径易读，再决定拆页或加大纸张。见 [human-readable-routing.md](references/human-readable-routing.md) 第 1 节。

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
  有意偏离纲要时用 `s.justify(对象, 理由)` 记录。
- 先列真实 planned 局部网名及其字号。在相应 series 段或 own-pin stub 放置前，显式用
  `max(原gap, s.name_run_steps(原net, font=原字号))` 预留直段，之后仍调用原 `s.name`。
  多段链逐段按真实网络预算；不得全局加gap、缩字、改名或用标签绕过连线。预算不证明无遮挡或原生字体覆盖。
- `build()` 遇到硬缺陷会直接报错。`report["structure"]` 必须为 PASS，`report["readability"]["gate"]` 必须为 PASS。
  失败时按 O8 改结构（方向、间隙、顺序 → 锚点 → 拆行）后重建，不得手调坐标打补丁。
- 图页脚本随交付版本一起保存；下一版只重生成有变化的页面。

### 6. 组装与一键验证

多页工程由工程脚本组装根图（层次图框、`System_block`），ASG 不自动写多页层次。之后运行：

```bash
python3 <skill>/scripts/verify_schematic.py <root.kicad_sch> --intent electrical-intent.json \
  --out <新的空目录> [--expected-pages N] [--symbol-exceptions F] [--readability-waivers F] \
  [--reference-contract F] [--design-closure D --artifact-root R] \
  [--baseline-xml B --change-contract C --preflight P]
```

它一次完成：KiCad ERC / XML 网表 / PDF 导出，网表分区与器件身份逐脚对比意图（图上画出的网名须等于同一组引脚的意图名，
只允许页路径前缀；KiCad 自动网名不比），层次与 PDF 页数，
符号引脚完整性，可读性门禁，以及每个有效页面的几何检查，汇总到 `summary.json`。
只有全部门禁为 PASS 时结果才是 `AUTOMATED_PASS`。

- 新设计提供 `--design-closure`，核对需求实现、外部依赖、计算覆盖和证据新鲜度；格式与边界见 [设计闭环](references/design-closure.md)。未提供时明确为 NOT_CHECKED，不能据此声明全流程完成。
- 新设计要求 ERC 零违规。重画工程时保留基线和最终两份原始 ERC，逐条确认没有新增违规，并披露继承的问题。
- ERC 摘要按原始报告的 UUID/object 绑定实际层次实例、引脚及原生网络，再归因到 rail；
  不凭位号或网名文字猜问题对象。无法绑定时保留原违规与待核边界，见 [project-verification.md](references/project-verification.md#erc-summary-object-binding)。
- 层次工程的几何检查使用本次原生导出的有限覆盖，支持已合格的图框、完整层次字段和部分脚名字迹；
  具体范围及未支持对象见 [native-geometry.md](references/native-geometry.md)。外部 JSON 回执不能授权放行。
  原生路径只增加有限的绝对圆形直径半圆 `A` 覆盖，逐段保护弧内部和实际笔宽；椭圆、非半圆、填充曲线、曲线字形等仍不足。
  导线与物理引脚身份仍按严格 MLZ 核验；路径可解析不等于页面几何或 ERC 全部通过。
  `geometry` 为 INSUFFICIENT 时（如层次脚轮廓、脚号或字形尚未合格），保留缺口并在原生渲染图上核对；有限图框 PASS 不等于所有字迹或整案通过。
- 失败时修改相应页面脚本，在新的运行目录重新生成并验证。不得为了降低计数而加 PWR_FLAG、加排除项或改引脚类型。
- 受控的自动结构资格有两类，都在意图中逐网声明、用 `Sheet.power_flag()` 每网放一个 PWR_FLAG，由 `external_supply` 门禁核对：
  只由连接器引入、板上没有电源输出脚驱动的电源或地（`external_supply`）；经一颗串联电阻、电感、磁珠或保险丝
  从已有驱动的电源派生的电源脚供电网，例如 RC 滤波的模拟电源（`filtered_supply`，逐条列入交接说明由 SR 复核）。声明格式与核对内容见
  [requirements-to-intent.md](references/requirements-to-intent.md) 第 5 节“连接器角色与外部供电”。
- 整流、变压器或分立稳压电路没有原生 `power_out` 时，不冒充连接器供电，也不修改器件脚型。
  先复核实际能量来源、返回路径、极性、启动和故障状态，再使用 [分立供电复核](references/reviewed-circuit-supply.md)
  的 `reviewed_circuit_supply`。该类是证据绑定的人工供电语义结论；门禁只核证据新鲜度和原生拓扑，
  不自动证明电压、电流、效率或保护成立。未完成复核时保留 ERC，不凭降低计数批准标记。
- `symbol_integrity` 的 `unnamed_pins` 只作诊断（KiCad 运放、单门逻辑等符号的输入/输出脚按库惯例不写名字）。
  列出的每个器件（不限核心器件）都要在参考合同里按数据手册名字逐脚绑定，并在交接说明中列出这些脚；
  否则 schematic-review 的严格解析会因缺脚名失败。

### 7. 渲染目检

打开导出的 PDF，逐页按方案表追一遍读者任务：主路径、每个支持网络到对应引脚和正确回路、
重复通道、每个回路域和隔离跨越。记录追过的路径和发现的问题；“看过所有页”不算证据。
状态写 待返工（REWORK_REQUIRED）、待目检（REVIEW_PENDING）或 已目检（REVIEWED）。
用户否决会重新打开目检。见 [human-readable-routing.md](references/human-readable-routing.md) 第 4 节。

### 8. 交付与交接

- 按 [execution-evidence.md](references/execution-evidence.md) 写 `delivery-evidence.json`，报告前运行
  `scripts/check_delivery_freshness.py`；任何导出后的修改都会使旧结果作废。
- 分别报告图纸生成、设计闭环、原生门禁、目检和独立 SR 状态；还有可独立完成的设计项就继续，不以列出缺口代替完成。
- 交接给 `schematic-review` 的内容：工程文件和哈希、电气意图、需求追溯表、器件合同、计算、OPEN 清单、
  `summary.json` 和目检记录。报告时如实写出 PASS/FAIL/INSUFFICIENT 各项及其数量（含零）。

## 有状态工作流交接

参与 ASG/SR 薄控制器流程时，读 [工作流交接合同 v1](references/workflow-handoff.md)。
以 `task.json` 的需求、版本、前版设计和审查问题为输入；架构生成、取证、计算与改图仍由 ASG 完成。
交付原有设计与证据；用控制器 `pack-result` 自动生成 `result.json`，无需手填 hash 或候选版本。
日常出图与整改沿用当前版本，关键交接检查当前依赖；重要变化和冻结记录里程碑。
控制器只验交接与新鲜度，不替 ASG 自检或 SR 电气审查；独立使用本技能不依赖控制器。

## ASG 自检与 schematic-review 的分工

| ASG 出图时自检 | 交 schematic-review |
| --- | --- |
| 需求功能路径、架构可行性、选型与设计计算；原生 ERC 和意图一致性 | 需求符合性与功能完整性判定 |
| 确切 MPN 引脚表；声明的外围合同（`--reference-contract`） | 工况、裕量、应力、保护和时序的系统审查 |
| 计算预检的条件与门槛 | 全面的最坏情况分析与 FAIL/待核判定 |
| 层次、符号完整性、几何、可读性；渲染目检 | 冻结/放行结论、P0–P3 分级、修改建议 |

## 硬性规则

- 意图独立于几何：位号、值、MPN、引脚编号、装配状态和网络归属不因摆放改变；不为布图方便改符号的引脚映射。
- 不手写辅助器件坐标；不把可读页面交给 MST/A* 自动路由；不用标签掩盖失败的连线。
- 标签角色：全局标签只用于出页网络；电源轨和回路用 Value 等于网络名的电源符号；隔离的回路不能用通用 GND。
- DNP 器件保留连线和焊盘，它不等于 IC 的 NC 引脚。
- 不得静默拍平已有层次工程；候选图生成在新目录，确认基线未变后才写回原工程。
- `AUTOMATED_PASS` 只代表脚本门禁通过；数据手册审查和渲染目检另行完成。如实报告缺口。

## 参考文件

| 何时读 | 文件 |
| --- | --- |
| 新设计/电气改版的设计闭环、依赖与计算结论审计 | [design-closure.md](references/design-closure.md) |
| 从需求写电气意图 | [requirements-to-intent.md](references/requirements-to-intent.md) |
| 架构页、参考设计外围、学习工程师图面 | [reference-driven-board-design.md](references/reference-driven-board-design.md) |
| 选符号、引脚表、外围合同 | [symbol-and-peripheral-contracts.md](references/symbol-and-peripheral-contracts.md) |
| 计算条件合同 | [calculation-preflight.md](references/calculation-preflight.md) |
| 非线性极值、条件匹配与插值边界 | [worst-case-bounds.md](references/worst-case-bounds.md) |
| 纲要 O1–O8 与 recipes API | [drawing-recipes.md](references/drawing-recipes.md) |
| 阅读路径、HR-01–HR-11、目检 | [human-readable-routing.md](references/human-readable-routing.md) |
| 拓扑结构、标签策略、验证门禁 | [schematic-drawing-standards.md](references/schematic-drawing-standards.md) |
| 重画已有工程 | [existing-project-redraw.md](references/existing-project-redraw.md) |
| 电气改版与预检 | [electrical-redesign.md](references/electrical-redesign.md)、[change-preflight.md](references/change-preflight.md)、[project-verification.md](references/project-verification.md) |
| 对照工程师模板 | [engineer-template-comparison.md](references/engineer-template-comparison.md) |
| 交付证据与新鲜度 | [execution-evidence.md](references/execution-evidence.md) |
| Circuit IR、低层生成器 | [circuit-ir.md](references/circuit-ir.md)、[schematic-generation.md](references/schematic-generation.md) |

运行不需要上游完整仓库、新的 MCP 服务、Bun 或网络连接。

For board-level automatic-looking net names, follow the source qualification in
[project-verification.md](references/project-verification.md#automatic-looking-names-need-source-evidence).
A hand-written `Net-(...)` label is not evidence of an automatic name; XML-only
unknown origin stays `INSUFFICIENT`. Do not bypass this with a name-pattern regex.

For encoded-slash hierarchical fields, the narrow readable-orientation fallback
in [schematic-drawing-standards.md](references/schematic-drawing-standards.md)
retains raw width and all coverage gaps. Do not generalize it into decoding,
font qualification, geometry tolerance changes or owner collision exemptions.
