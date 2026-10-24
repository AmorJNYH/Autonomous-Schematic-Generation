# 从需求到设计完成

适用于需求驱动的新设计和电气改版。原样重画不需要重新做已设计定型的电气设计。
ASG 对其方案、选型、参数和功能实现负责；审查方只提意见，不代替 ASG 完成这些工作。

## 先做设计，再记录结论

1. **需求与架构**：每项当前需求对应可检查的功能路径、实现器件/固件和验收方法。引用历史电路时逐项说明适用条件；同一产品的两版应比较全流程结果，需求变化作为差异解释，不把比较缩成同网表重画。用户已选拓扑不重复投票，仍比较内部实现的成本、损耗、面积和供货证据。
2. **器件可行性**：系列宣传或物理引脚存在，不证明确切型号/固件具备所需状态、配置和启动行为。先验证架构依赖的能力，再展开外围。拿不到资料时评估独立硬件或有证据的替代方案，并继续不受影响的计算和电路；不要仅把设计工作搬到“厂家待提供”。核心/安规相关器件要确切料号与证据；通用料可先给可采购的容差、耐压、功率、温度等边界；定制磁件要受控结构/端子、材料与制造指标。不能把所有空 MPN 一律判错，也不能称其为已完成可下单 BOM。
3. **计算要完整**：损耗/能效预算须列出所有适用的主要项，无法精算的项给有来源的上下界及剩余预算。部分损耗的效率上界只能排除明显不可行方案，不能证明达标。磁件先选候选磁芯/材料/窗口并计算绕组、气隙、磁通和损耗，供应商公差及样机验证另列；不能把自由选择的工程输入无限留待供应商。保护要追触发、供电、执行、保持和恢复整条路径及容差/掉电角点，不止静态分压值。不能为补齐表格编造缺失参数或保证值。
4. **状态和可追溯性**：逐个追启动、正常工作、限流、过温、传感器故障、输出过压、掉电及恢复中适用的状态。写清触发源→判定→执行→供电/保持→恢复，映射实际位号/网络与固件责任。批量给每个需求挂上整板位号不构成功能追溯。
5. **工作分类**：`design` 是还能用现有证据完成的方案/计算/选型/连线；`external` 是确实需厂商或其他输入的能力/保证；`validation` 才是已给出设计依据和试验入口的实物/认证验证。`pcb` 仅指封装库、布局实现、DFM；它与 `validation` 可交给后续环节。工程假设尚未成立时不因“以后实测”而关闭设计项。审查意见的处理方式与这些阶段的对应见 [处理审查意见](review-comments.md#1-逐条登记)。

## 从审查缺口回到电路

把同一物理问题原因合并，但将可独立执行的动作拆开。例如“偏置设计、固件能力、闭壳热测”不是一个等待厂家任务。
优先处理决定可行性的预算和状态边界；在生成下一版之前，先完成足以改变方案选择的计算。

- 对损耗/裕量不足，计算主导项和剩余预算，比较保持用户要求的具体替代实现。先核决定性的启动、额定、驱动和供电条件，再为候选画外围。被排除的候选记录真正不适用的条件，继续评估可行方向。
- 区分设计自由度、原厂保证条件和后续环节测量。可选阻值、匝数、保持容量、隔离路径和通用料额定由工程先确定；不能只给“待选型”。已知应力可用有来源的保守额定包络关闭，不为每个普通器件索取无关的全温实测。
- 动态保护用电荷/能量、最大传播时间、控制电源谷值和执行元件限值建立可复算边界；不足时更换供电或执行路径。缺厂家软件状态时评估可独立实现的硬件，但不把替代方案的副作用留空。
- 本版写明实际做了什么：改了什么、哪条边界改善、代价是什么、哪些检查受影响，不和上一版比较。仅重跑旧模型、重复标INSUFFICIENT或增加报告不能算设计进展。
- **待办每版重新确认。** 本版交付的待办只列这次设计过程中确认仍需做的事项。上一版的待办不能原样搬过来：
  每一条都按本版的电路、计算和资料重新核过，仍然成立才写进来，并按本版的认识重写内容。编号不要求跨版本一致。
- 还有当前可执行设计动作时继续工作。只有实际依赖尚未取得且替代路径已评估，才报告该分支受阻；同时完成其余分支。PCB阶段才产生的实测可列为后续环节的要求，但决定拓扑、保护有效性、额定和安全间距的设计不得推迟到PCB。
- **先分类，再动图。** 收到审查意见后先按 [处理审查意见](review-comments.md) 逐条登记处理方式：
  电路错误和没做完的设计是设计工作；缺资料的按意见写明的范围补资料；只能靠样机/试验得到的
  能效、EMC、热、寿命、实际寄生写进交给后续环节的要求，不改图。
  补证或计算时发现保守参数下算不过、路径缺失或额定越限，才是需要改图的设计缺口。
- **不用加电路去关闭证据缺口。** “缺全温最大值”“缺实测波形”“只有典型值”不是电路缺陷：先用物理上限（供电轨、钳位、
  限流）或有依据的保守界限定界。不能为了让某条检查有保证值而增加隔离器、锁存、监控、独立辅助电源等新电路，
  除非用保守界限计算证明现电路确实不满足。
  **例外：工作方式本身不在手册规定范围内。** 缺一个保证值，是手册规定了这种用法、只是没给某个参数；
  而手册根本没有对应章节的用法（例如控制器 GPIO 只规定了开路电压和偏置电流档，却拿来灌电流驱动光耦）是设计缺陷，
  不是证据缺口。改用规定范围内的做法（外加小信号管缓冲、规定的电流源档位、参考电路接法）属于设计修正，
  按 SKILL.md 第 2 步“优先手册规定的工作方式”处理，记录在 `operating_points`。
- **改图前写明代价。** 新增或替换电路前（包括采用审查意见附带的改法），在设计记录里写：预计解决哪些意见、
  新增多少器件和需要新审的状态/规则、新器件自身带来哪些新的证据需求；是否采用按设计判断并写明理由。
  新器件带来的待办按正常设计工作处理，不能以此为理由保留手册未规定的工作方式。

新设计/电气改版在现有设计待办记录增加`convergence_version: 1`；有前置工作时才写`blocked_by`（仅填真实前置工作ID，不含泛泛风险），缺省视为没有。
外部未关闭项增加`fallback_work: [可执行替代设计ID]`；若无可行替代，可省略或写空列表，并以`fallback_evidence: [证据ID]`记录已完成的评估。
外部任务与替代设计不是互相阻塞的循环：替代方案能用公开资料推进，就不应依赖正在替代的那份厂家资料。

`audit_design_closure.py`在原有结论之外返回`convergence`：`CONTINUE_DESIGN`列当前可执行动作，
`WAITING_DEPENDENCIES`列实际前置项，`NO_OPEN_DESIGN_ACTIONS`只表示声明的动作已耗尽，绝不等于电气通过。
未知ID、循环依赖和未评估的外部替代会报错；旧记录明确显示`NOT_ASSESSED`。工作依赖分类本身仍须人工复核，不能通过填虚假前置项制造停工理由。

## 电气角色与图面

在独立设计要求表中可声明 `net_roles: {"VCC": "power", "RTN": "return", "LIMIT": "signal"}`。
新设计至少给 rails 和易混淆的阈值/反馈/检测网络明确角色。比较阈值、参考电压检测点和反馈量一般属于 signal；真正给器件供电的基准轨按用途确定，不用名字猜测。
`page_intents` 保留逐页角色，`Sheet` 和显式 `power()` 均拒绝给已声明 signal 的网络放电源符号。旧设计要求表无此字段时兼容运行，表示尚无此项语义保护，不能声称已检查。

分页按完整读者任务决定，不按器件类型机械拆页，也不设每页最少器件数。保护检测→锁定→关断能同页清楚表达时优先同页；确有隔离/拥挤理由拆分时给跨页信号标目的功能和页码。扩大纸张前检查主路径折返、锚点距离、局部扇出；减少页数也不能靠缩字。System_block 将真实层次页与功能、供电、反馈/故障箭头对应，避免重复画一套无法直接对应层次的装饰方框。矩形引脚图适合芯片，但 MOS/比较器等应保留正确功能图形或单元表达，不能牺牲真实 pin map。

图面审阅记录实际追踪路径和未解决问题。零交叉、零碰撞仅是几何自动检查，不能代替上述判断。需求/元件增加时同时比较绝对阅读体验与可对照的相同功能页，不把总线长或纸张面积单独当成质量分数。

## 可执行的结论审计

`design-closure.json` 是设计审查记录的索引，不复制计算预检的数值模型。

```json
{
  "schema_version": 1, "parameter_version": 2,
  "intent_sha256": "<electrical-intent.json 的 SHA256>",
  "coverage": "complete",
  "evidence": [
    {"id": "E1", "path": "design-basis.md", "sha256": "<SHA256>", "locator": "第2节，R1功能路径和计算"}
  ],
  "requirements": [
    {"id": "R1", "status": "conditional", "implementation": "U1 输出路径；固件故障态尚待证实",
     "refs": ["U1"], "evidence": ["E1"], "depends_on": ["W1"]}
  ],
  "work_items": [
    {"id": "W1", "stage": "external", "status": "open", "requirements": ["R1"], "evidence": ["E1"],
     "consequence_class": "function", "occurrence": "fault", "owner": "厂商", "action": "取得确切固件故障态依据", "fallback": "评估独立关断实现及其供电保持"},
    {"id": "W2", "stage": "design", "status": "open", "requirements": ["R1"], "evidence": [],
     "consequence_class": "function", "occurrence": "fault", "owner": "ASG", "action": "补算故障期间辅助供电保持"}
  ],
  "calculations": [
    {"id": "C1", "requirements": ["R1"], "evidence": ["E1"], "refs": ["D403", "R408", "U402"],
     "kind": "threshold", "coverage": "partial", "conclusion": "conditional", "rests_on": "vendor_data",
     "assumptions": ["辅助绕组漏感尖峰按稳态值的10%计"],
     "omitted_terms": [{"term": "故障期间辅助供电保持", "kind": "not_calculated", "work_item": "W2"}],
     "parameters": [
       {"name": "Vz", "ref": "D403", "value": 30, "unit": "V", "basis": "typical",
        "source": "datasheet:Datasheet/.../Nexperia - BZT52H.pdf#p3", "locator": "表 7，IZ=5mA；200µA 下没有给"},
       {"name": "漏感尖峰比", "value": 0.1, "unit": "1", "basis": "model", "reason": "按稳态值的 10% 计"}],
     "checks": [
       {"name": "21V输出时AUX_DC峰值 对 动作下限(Vz最小+FAULT门限最小)", "side": "no_false_trip",
        "value": 67.6, "operator": "<", "limit": 69.5, "unit": "V"},
       {"name": "动作上限折算的输出电压 对 输出电容额定", "side": "protection",
        "value": 25.1, "operator": "<=", "limit": 35, "unit": "V"}]}
  ]
}
```

- `coverage`：全部适用需求/设计工作均已审查才填 `complete`；抽查或历史回放填 `partial`。这不是工具自动证明的完整性。
- 需求状态 `design_supported` / `conditional` / `open`；`implementation` 描述功能而非只列料号。
- `work_items`：阶段 `requirement`（等用户定需求）/ `design` / `external` / `validation` / `pcb`；状态 `open` / `closed` / `handoff`；`validation` 与 `pcb` 允许 `handoff`。未关闭项需 owner/action；`open` 项还需 `consequence_class`（不做的后果：`safety` 安全 / `damage` 器件损坏 / `function` 功能失效 / `margin` 性能余量 / `optimization` 优化）和 `occurrence`（何时出现：`normal` 正常工作 / `condition` 特定工况 / `fault` 仅故障时），等级由审计按规则推出，不手填：安全 P0；器件损坏 P0，仅故障时 P1；功能失效 P1，仅故障时 P2；性能余量 P2，仅故障时 P3；优化 P3。报告按等级排序；写了 `severity` 而与规则不符记 `severity_contradicts_rule`；external 的资料缺口按下面的 `gap_version 1` 写；requirement 还需 `assumption` 写明本版按什么假设设计，只用于不改变架构的需求缺口（改变架构的先问用户再设计，见 requirements-to-intent.md 第 1 节）。closed 与 handoff 均需证据。`pcb` 须声明 `scope` 为 `footprint_library` / `layout_implementation` / `dfm`，并用非空 `electrical_preconditions` 指向已关闭的 design 工作；这些前提须有选定变体、物理脚号及相关电气边界证据，不能用“已建封装”自证。该分类仍需人工检查，脚本不理解正文电气内容。
- 计算：`coverage` 为 `bounded` / `partial`；`conclusion` 为 `supported` / `conditional` / `failed`。无适用计算时提供 `no_calculations_reason`，不能用空列表绕过。
  - **结论由记录推出**（`parameter_version: 2`）：审计按下表推出结论，写的 `conclusion`/`rests_on` 与推出的不一致记
    `conclusion_not_derived`。报告按三档计数，分“依赖厂家资料的计算”“依赖工程估计的计算”两节列出每条依赖的参数或项。

    | 记录里有 | `conclusion` | `rests_on` | 报告用语 |
    |---|---|---|---|
    | 任一 `checks` 不满足 | `failed` | — | 不满足 |
    | `typical`/`unspecified` 参数，或计算 id 出现在未关闭 external 待办的 `calculations` 里 | `conditional` | `vendor_data` | 依赖厂家资料 |
    | 否则，有 `model` 参数或 `not_calculated` 的遗漏项 | `conditional` | `estimate` | 依赖工程估计 |
    | 都没有 | `supported` | — | 设计成立 |

  - `omitted_terms`：每项 `{term, kind, work_item}`。`not_calculated`（影响检查结果却没算）指向一件未关闭的 `design` 待办，
    有它时 `coverage` 是 `partial`，否则是 `bounded`（写错记 `coverage_not_derived`）；`verify_by_test`（只能靠样件或试验确认）
    指向一件 `validation` 阶段的 `handoff` 待办，不影响结论和 `coverage`。指错记 `not_calculated_without_design_item` /
    `verify_by_test_without_validation_handoff`。`missing_guarantee` 不再必填，缺的保证由审计从参数里列出。
  - 需求：挂着不是设计成立的计算时，不能记 `design_supported`（`requirement_status_not_derived`）。
  - `parameter_version: 1` 的旧记录照旧审计（下面两段），报告写明“结论没有按依据分层”。
  - `refs`：这条计算决定了哪些位号的取值，非空，且都在设计要求表里。
  - `checks`：非空列表，每项是一个算出来的值和它必须满足的门槛 `{name, value, operator(<=,<,>=,>), limit, unit}`。
    **结论由数字决定**：任一项不满足，`conclusion` 只能是 `failed`；全部满足才可以是 `conditional`/`supported`。
    不能在脚本里给所有计算统一写 `conditional`，也不能只写公式和假设不给门槛——没有门槛的计算什么也没证明。
  - **阈值窗口**：保护、检测、钳位类计算填 `"kind": "threshold"`，`checks` 必须两侧都有：
    `side: "no_false_trip"`（正常工作最高点，含纹波、漏感尖峰、温漂和容差，低于动作下限）和
    `side: "protection"`（动作上限仍低于被保护对象的耐受值或需求的保护点）。只算一侧会漏掉误动作或保护无效。
  - 设计要求表里的稳压管、TVS、基准源都必须出现在某条计算的 `refs` 里：按 lib_id（含 Zener/TVS/TL431/LM4040/Ref 等）、
    value 或 mpn 的系列前缀（1N47、BZX、SMBJ、PESD、TLV431、LM385 等）识别，通用符号画的其他阈值器件在 `fields.ComponentRole` 写 `threshold`；
    否则审计报 `threshold_part_uncalculated`。设计资料里写的阈值（如“对应30V包络”）必须与这条计算的数字一致。
  旧记录（`parameter_version: 1`）：门槛按设计用途：`conditional` 必须用 `omitted_terms` 或 `assumptions`（字符串列表）写明假设，并在 `missing_guarantee` 里写明缺的是哪一项保证（哪个器件、哪个参数、哪个条件手册或需求没给）；写明后不阻塞设计完成，需求也可以据此记为 `design_supported`；报告把它们列在“有条件成立的计算”一节，交独立审查严格核对。只有 `failed` 计入未完成，且不能支撑 `design_supported` 的需求。
  `coverage: partial` 必须有非空 `omitted_terms`：说不出漏了什么就不是 partial。`conditional` 不是免责词：1.33 A < 3 A 这种没有缺失保证的核对要写 `bounded`/`supported`，审计报 `conditional_without_missing_guarantee` 和 `partial_without_omitted_terms`。
- **参数来源**（新交付写 `"parameter_version": 2`；两版都没有时报告提出问题、`pack_design.py` 拒绝打包）：
  每条计算加非空 `parameters`，每项 `{name, value, unit, basis, ref, source, locator}`。`basis` 取：
  - `guaranteed`：手册保证的 MIN/MAX；`typical`：手册典型值。两者都要 `ref`（位号）和 `source`
    `datasheet:<库内路径>#p<页>` 加 `locator`（表名/参数符号/条件）。
  - 手册引用的核对（`schematic_layout/citations.py`，参数、工作点、缺口里的 `datasheet:` 都核）：文件不在知识库
    （`HARDWARE_WIKI/raw`）或声明的资料里、页码超出文档页数，记 `citation_wrong`，审计 FAIL。`guaranteed`/`typical`
    的数值在所引页的文字里找不到（含 SI 前缀换算、百分数、尾随 0、Unicode 负号）时列入报告“引用待人工核对”，不拦。
    `locator` 文字不核。找不到知识库或没有 poppler（`pdfinfo`/`pdftotext`）时记为“没核对”并写明原因。
  - `derived`：由其他值推出，写 `derivation`，`source` 是手册页或 `calc:<计算 id>`。
  - `design_choice`：本设计选定的值（电阻阻值、容差档、匝数），写 `ref`。
  - `model`：工程假设或折减（CTR 保持系数、效率包络等），写 `reason`。
  - `requirement`（版本 2）：来自需求的输入（额定功率、最低输入电压），`source` 写 `req:<需求编号>`，编号须在 `requirements` 里。
  - `constant`（版本 2）：物理常数（铜电阻率），写 `reason`。
  - `unspecified`：手册没给的器件参数。`source`/`locator` 写查过的位置，`operating_point` 指向一条 `specified: false` 的工作点；
    `value` 可留空。含 `typical` 或 `unspecified` 的计算不能是 `supported`。
- **工作点**（`operating_points`，与 `parameter_version` 一起检查）：`{id, refs, pins, mode, specified, source, locator}`。
  `specified: true` 时 `source`/`locator` 指向手册规定这种用法的位置；`specified: false` 时指向查过但没有规定的位置，
  还要 `alternatives`（每项 `{approach, specified, feasible, reason}`）和 `work_item`（external 厂家确认待办）。
  有 `specified` 且 `feasible` 的替代做法时，审计报 `unspecified_operation_with_specified_alternative`（FAIL）。
  保留下来的未规定工作点列在报告“手册未规定的工作点”一节。
  ```json
  {"id": "OP-GPIO1", "refs": ["U601"], "pins": ["GPIO1"], "mode": "开漏灌电流驱动光耦 LED", "specified": false,
   "source": "datasheet:Datasheet/.../Richtek - RT7209.pdf#p12", "locator": "GPIO1 一节只有开路电压与偏置电流档",
   "work_item": "W-OPTO",
   "alternatives": [{"approach": "小信号 MOS 缓冲", "specified": true, "feasible": false, "reason": "……"}]}
  ```
- **资料缺口**（`"gap_version": 1`，新交付必填；有未关闭的 external 待办而没有它时报告提出问题、`pack_design.py` 拒绝打包）：
  每件未关闭的 external 待办写：
  - `missing`：非空列表，每项 `{source, given, needed}`。`source` 是发现缺口的位置：`datasheet:<库内路径>#p<页>`、
    `review:<审查目录>/<待办编号>` 或 `user:<日期>`；`given` 写手册给了什么（含测试条件），`needed` 写设计还需要什么。
  - `why_external`：为什么只能由这个负责方给，例如行为在芯片内部或固件里，外部推不出来。
  - `calculations`：依赖这项资料的计算 id，非空，且都是 `conditional`；报告在待办下列出这些计算依赖的参数（版本 1 为 `missing_guarantee`），
    并在“依赖厂家资料的计算”表（版本 1 为“有条件成立的计算”）里反查对应待办。确实没有计算依赖它（固件行为确认、安规资格这类）时写空列表，
    并用 `no_calculation_reason` 说明为什么，不为凑字段挂不相关的计算。
  - `consequence`：资料与假设不符时具体会出什么问题，不能只写后果等级。
  - `questions`：能直接发给负责方的问题，每条独立成句；报告按 `owner` 汇总到“要向外部要的资料”一节。
  - `owner`：写到具体公司或角色（“Richtek 应用支持”），问题清单按它汇总。
  - `fallback`：本项自己的替代做法和代价，或本项为什么没有替代；两件以上待办的 `fallback` 文字相同，审计报 `gap_generic_fallback`。
  - `action`：资料到手后怎么关闭这项（重算哪条计算、核对什么）。
  其他报错：缺字段 `gap_missing_fields`，位置格式不对 `gap_bad_source`，计算不存在或不是 conditional `gap_unlinked_calculation`。
  审计只查格式；问题问得对不对、替代做法能不能用，仍要人看。
  ```json
  {"id": "W-PORT-SOA", "stage": "external", "status": "open", "consequence_class": "damage", "occurrence": "fault", "owner": "Richtek 应用支持",
   "missing": [{"source": "datasheet:Datasheet/.../Richtek - RT7209.pdf#p18", "given": "VOH_USBP=VO+8.5–12V，只在 RL=10MΩ 下规定",
                "needed": "带 120nC 栅荷时的电荷泵电流、开通与关断时间"}],
   "why_external": "电荷泵驱动能力、故障到下拉的时延和重试时序在芯片内部与固件里",
   "calculations": ["PORT-GATE"], "consequence": "Q701 短路关断或重试时超出 SOA，D-S 短路后端口无法断开",
   "questions": ["从检测到故障到 USBP 开始下拉的最大时延", "短路重试每次开通的持续时间、间隔与次数上限"],
   "fallback": "栅极加由短路检测触发的快放电，增加 3 个器件",
   "action": "按最小 ESR 与最大输出电容积分 Q701 的 VDS-ID-t，对照 SOA 与瞬态热阻核结温"}
  ```
- 待办的 `progress`：design 阶段未关闭的待办写本版做到哪（算了什么、定了什么、还差什么），不能等于 `action`；审查回复 `DESIGN` 引用的待办没有它就不算处理。
- 所有证据 path 相对于 `--artifact-root`，不得逃逸该目录；必须有哈希和页码/章节/行号定位。需求源、数据手册和计算结论都纳入相应证据。`refs` 必须存在于设计要求表中；纯使用/验证条件可为空但须说明实现/交接。

```bash
python3 <skill>/scripts/audit_design_closure.py design-closure.json \
  --intent electrical-intent.json --artifact-root . --out design-closure-audit.json
# 与 KiCad 自动检查一起跑：
python3 <skill>/scripts/verify_schematic.py root.kicad_sch --intent electrical-intent.json \
  --design-closure design-closure.json --artifact-root . --out <新的空目录>
```

审计拒绝过期证据、无效位号/依赖、未关闭依赖却声称已实现、部分计算却声称支持结论等矛盾。
`INCOMPLETE` 表示如实记录的未完成设计；`FAIL` 表示记录/结论有矛盾或输入无效；`PASS` 只表示所声明范围内的证据和依赖闭合，**不证明公式正确、需求无遗漏、固件真实支持、ERC/图面审阅通过或审查通过**。人工必须检查证据正文与分类是否成立。新设计交付使用该记录；旧重画流程可不提供，汇总明确显示 NOT_CHECKED。

## 交付状态

分别报告：图纸是否已生成、ASG 设计工作是否闭合、KiCad 自动检查、图面审阅、审查意见处理、后续环节验证。设计报告由 `render_design_report.py` 按这些记录生成。
待办记录审核 PASS 不能覆盖 ERC FAIL 或图面审阅待返工；AUTOMATED_PASS 不能替代设计结论。
仍有可独立完成的设计项时继续完成，而不以“缺口已列出”作为工作结束。

## 原理图设计定型与技术转交PCB

原理图设计定型检查需求功能、确切变体与物理脚号、启动与保护状态、参数极值、电气选型、KiCad 验证结果。封装库缺失和DFM未做本身不阻断此阶段。引脚未知、额定不足、供电未建立或保护逻辑未闭合仍属于原理图问题，不能改名为PCB待办。封装热条件影响电气额定时，当前阶段建立设计边界，后续环节验证铜面积、散热与实际温升；不得使用未满足散热条件的最大额定直接放行。

报告分别列出原理图待办、真实外部依赖、PCB实现转交和实测转交。交给PCB工作只改变工作归属，不自动关闭相关电气缺陷，也不代表生产放行。
