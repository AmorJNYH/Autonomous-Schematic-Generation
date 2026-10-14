# 从需求到设计闭环

适用于需求驱动的新设计和电气改版。原样重画不需要重新做已冻结的电气设计。
ASG 对其方案、选型、参数和功能实现负责；SR 独立复核这些工作，不代替 ASG 完成它们。

## 先做设计，再记录结论

1. **需求与架构**：每项当前需求对应可检查的功能路径、实现器件/固件和验收方法。引用历史电路时逐项说明适用条件；同一产品的两版应比较全流程结果，需求变化作为差异解释，不把比较缩成同网表重画。用户已选拓扑不重复投票，仍比较内部实现的成本、损耗、面积和供货证据。
2. **器件可行性**：系列宣传或物理引脚存在，不证明确切型号/固件具备所需状态、配置和启动行为。先验证架构依赖的能力，再展开外围。拿不到资料时评估独立硬件或有证据的替代方案，并继续不受影响的计算和电路；不要仅把设计工作搬到“厂家待提供”。核心/安规相关器件要确切料号与证据；通用料可先给可采购的容差、耐压、功率、温度等边界；定制磁件要受控结构/端子、材料与制造指标。不能把所有空 MPN 一律判错，也不能称其为已完成可下单 BOM。
3. **计算闭环**：损耗/能效预算须列出所有适用的主要项，无法精算的项给有来源的上下界及剩余预算。部分损耗的效率上界只能排除明显不可行方案，不能证明达标。磁件先选候选磁芯/材料/窗口并计算绕组、气隙、磁通和损耗，供应商公差及样机验证另列；不能把自由选择的工程输入无限留待供应商。保护要追触发、供电、执行、保持和恢复整条路径及容差/掉电角点，不止静态分压值。不能为补齐表格编造缺失参数或保证值。
4. **状态和可追溯性**：逐个追启动、正常工作、限流、过温、传感器故障、输出过压、掉电及恢复中适用的状态。写清触发源→判定→执行→供电/保持→恢复，映射实际位号/网络与固件责任。批量给每个需求挂上整板位号不构成功能追溯。
5. **工作分类**：`design` 是还能用现有证据完成的方案/计算/选型/连线；`external` 是确实需厂商或其他输入的能力/保证；`validation` 才是已给出设计依据和试验入口的实物/认证验证。只有最后一种可正常交接。工程假设尚未成立时不因“以后实测”而关闭设计项。

## 电气角色与图面

在独立意图中可声明 `net_roles: {"VCC": "power", "RTN": "return", "LIMIT": "signal"}`。
新设计至少给 rails 和易混淆的阈值/反馈/检测网络明确角色。比较阈值、参考电压检测点和反馈量一般属于 signal；真正给器件供电的基准轨按用途确定，不用名字猜测。
`page_intents` 保留逐页角色，`Sheet` 和显式 `power()` 均拒绝给已声明 signal 的网络放电源符号。旧意图无此字段时兼容运行，表示尚无此项语义保护，不能声称已检查。

分页按完整读者任务决定，不按器件类型机械拆页，也不设每页最少器件数。保护检测→锁定→关断能同页清楚表达时优先同页；确有隔离/拥挤理由拆分时给跨页信号标目的功能和页码。扩大纸张前检查主路径折返、锚点距离、局部扇出；减少页数也不能靠缩字。System_block 将真实层次页与功能、供电、反馈/故障箭头对应，避免重复画一套无法直接对应层次的装饰方框。矩形引脚图适合芯片，但 MOS/比较器等应保留正确功能图形或单元表达，不能牺牲真实 pin map。

目检记录实际追踪路径和未解决问题。零交叉、零碰撞仅是几何门禁，不能代替上述判断。需求/元件增加时同时比较绝对阅读体验与可对照的相同功能页，不把总线长或纸张面积单独当成质量分数。

## 可执行的结论审计

`design-closure.json` 是设计审查记录的索引，不复制计算预检的数值模型。

```json
{
  "schema_version": 1,
  "intent_sha256": "<electrical-intent.json 的 SHA256>",
  "coverage": "complete",
  "claim": "candidate",
  "evidence": [
    {"id": "E1", "path": "design-basis.md", "sha256": "<SHA256>", "locator": "第2节，R1功能路径和计算"}
  ],
  "requirements": [
    {"id": "R1", "status": "conditional", "implementation": "U1 输出路径；固件故障态尚待证实",
     "refs": ["U1"], "evidence": ["E1"], "depends_on": ["W1"]}
  ],
  "work_items": [
    {"id": "W1", "stage": "external", "status": "open", "requirements": ["R1"], "evidence": ["E1"],
     "owner": "厂商", "action": "取得确切固件故障态依据", "fallback": "评估独立关断实现及其供电保持"}
  ],
  "calculations": [
    {"id": "C1", "requirements": ["R1"], "evidence": ["E1"], "coverage": "partial",
     "conclusion": "conditional", "omitted_terms": ["故障期间辅助供电保持"]}
  ]
}
```

- `coverage`：全部适用需求/设计工作均已审查才填 `complete`；抽查或历史回放填 `partial`。这不是工具自动证明的完整性。
- `claim`：`candidate` / `design_closed`。需求状态 `design_supported` / `conditional` / `open`；`implementation` 描述功能而非只列料号。
- `work_items`：状态 `open` / `closed` / `handoff`；只有 `validation` 允许 `handoff`。未关闭项需 owner/action，external 还需 fallback 评估（可以有证据地说明尚无可行替代）。closed 与 validation handoff 均需证据。
- 计算：`coverage` 为 `bounded` / `partial`；`conclusion` 为 `supported` / `conditional` / `failed`。有遗漏项不能填 bounded 或 supported。无适用计算时提供 `no_calculations_reason`，不能用空列表绕过。
- 所有证据 path 相对于 `--artifact-root`，不得逃逸该目录；必须有哈希和页码/章节/行号定位。需求源、数据手册和计算结论都纳入相应证据。`refs` 必须存在于意图中；纯使用/验证条件可为空但须说明实现/交接。

```bash
python3 <skill>/scripts/audit_design_closure.py design-closure.json \
  --intent electrical-intent.json --artifact-root . --out design-closure-audit.json
# 与原生门禁一起跑：
python3 <skill>/scripts/verify_schematic.py root.kicad_sch --intent electrical-intent.json \
  --design-closure design-closure.json --artifact-root . --out <新的空目录>
```

审计拒绝过期证据、无效位号/依赖、未关闭依赖却声称已实现、部分计算却声称支持结论等矛盾。
`INCOMPLETE` 表示如实记录的未完成设计；`FAIL` 表示记录/结论有矛盾或输入无效；`PASS` 只表示所声明范围内的证据和依赖闭合，**不证明公式正确、需求无遗漏、固件真实支持、ERC/目检通过或 SR 放行**。人工必须检查证据正文与分类是否成立。新设计交付使用该记录；旧重画流程可不提供，汇总明确显示 NOT_CHECKED。

## 交付状态

分别报告：图纸是否已生成、ASG 设计工作是否闭合、原生门禁、渲染目检、独立 SR、下游验证。
闭环审计 PASS 不能覆盖 ERC FAIL 或目检待返工；AUTOMATED_PASS 不能替代设计结论。
仍有可独立完成的设计项时继续完成，而不以“缺口已列出”作为工作结束。
