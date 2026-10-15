# 读取 SR 审查结果

收到 schematic-review（SR）结果后、改图之前读本页。分类以 SR 原生记录为准：
ASG 不重新判定 SR 结论，也不按自己的理解重新分类“证据不足”。

## 1. 先生成动作清单

```bash
python3 <skill>/scripts/import_review_feedback.py review-results.json review-gate.json \
  --out review-feedback.json
```

- 两个文件来自同一次 SR 运行。gate 的 `valid` 不为 true，或有 INSUFFICIENT 缺 `gap_cause`、
  使用已取消的 `DOWNSTREAM_VERIFICATION` 时，结果为 FAIL：退回 SR 修正记录，ASG 不据此动图。
- REQ-H02 历史处置行不进入本轮动作。PASS 与普通 NA 不产生动作。
- 输出绑定两份输入的 SHA256；改图后的设计记录引用这份 `review-feedback.json`。

## 2. 固定对应关系

| SR 记录 | ASG 动作 | design-closure `stage` | 控制器 open_items `kind` | 是否改图 |
|---|---|---|---|---|
| FAIL | `REDESIGN`：按 finding 的 remediation 改 | `design` | DESIGN | 是 |
| INSUFFICIENT + DESIGN_OPEN | `DESIGN`：完成选型/计算/配置，到真实取舍点再请用户决定 | `design` | DESIGN | 计算证明需要时 |
| INSUFFICIENT + EXTERNAL_DATA | `OBTAIN_EVIDENCE`：按 `input_requests` 的取得方法补证，并评估替代实现 | `external` | EVIDENCE | 否（见第 3 节） |
| INSUFFICIENT + REQUIREMENT_OPEN | `ASK_REQUIREMENT_OWNER`：交需求责任方，任务状态 `NEEDS_INPUT` | 不建工作项 | REQUIREMENT | 否 |
| INSUFFICIENT + REVIEW_INCOMPLETE | `WAIT_FOR_SR`：SR 自己未审完，ASG 不处理 | 不建工作项 | REVIEW | 否 |
| INSUFFICIENT + USER_DEFERRED | `NONE`：用户已暂缓 | 不建工作项 | 不列 | 否 |
| NA + `na_reason: OUTSIDE_SCHEMATIC_STAGE` | `HANDOFF`：把 SR handoff 的约束和验证方法写入 `downstream_constraints` | `validation`（状态 `handoff`） | DOWNSTREAM | 否 |

- `EXTERNAL_DATA` 的 `input_requests` 已写明缺什么、所需范围、取得方法和关闭条件，直接作为 external 工作项的
  action 和关闭依据，不重写成更宽的“索取完整资料”。工程内已有资料能回答的，读算后交回 SR。
- `HANDOFF` 项是产品仍需验证的要求，不是不适用；ASG 不为它加电路、不建 design 工作项。
- PCB 封装、布局、DFM 是 ASG 自己的 `pcb` 交接，与 SR 阶段 NA 不混用。

## 3. SR 的电路改进建议

SR 可能在任务上附 `design_option: PROPOSED`。它是候选方案，不是改图指令：

1. **直接采用**：对应 FAIL；或 `preference: DESIGN_FIRST`（SR 判断原厂不会给出所需保证）。
2. **先补证**：`EVIDENCE_FIRST`，或 `EITHER` 且第 2 节的补证路径能在本轮完成。补证失败后再按第 1 条处理。
3. 不论哪种，改图前都按 [设计闭环](design-closure.md#收敛迭代从审查缺口回到电路) 做收敛估算：
   写出预计关闭的 SR 检查、新增器件和新的证据需求。新增缺口多于关闭的不采用，记录理由交回 SR。

“不用加电路去关闭证据缺口”仍然成立：SR 的建议只有在第 1 条成立、且收敛估算净关闭时才构成改图理由。

## 4. 收敛指标

每轮记录 `review-feedback.json` 的 `metrics`：`unique_findings`、`unique_work_items`（SR 唯一根因数）、
`design_actions`、`evidence_actions`，以及本轮 ASG 意图中的器件数。用这些数字判断是否收敛，不另行人工计数：

- 一轮之后 `unique_findings + unique_work_items` 不降，而器件数上升，即为发散，停下来重审方案；
- 连续两轮发散，向用户报告并给出删减/合并的简化方案。
