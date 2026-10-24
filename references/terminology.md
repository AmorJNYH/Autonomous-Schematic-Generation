# 术语对照

报告、记录（`design-closure.json`、`review-responses.json` 等）和 `notes.json` 用同一套术语，没有另一层口语说明。
第一张表“不用的词”一列由 `render_design_report.py` 读取：记录或 notes 的文字里出现这些词算记录问题，打包被拒。

## 术语

| 用词 | 含义 | 不用的词 |
|---|---|---|
| 自动检查 | 一键验证里由脚本和 KiCad 完成的检查：ERC、网表逐脚对照、层次、符号、可读性、几何等 | 门禁 |
| 图面审阅 | 按本版 PDF 逐页审阅读图路径和全部待看图对象，写出看到了什么 | 看图检查 |
| 完成、关闭 | 设计完成：需求、计算和待办都已处理；关闭：一条待办有证据地处理完 | 设计闭环 |
| 设计定型 | 设计完成且独立审查通过，可以交后续环节实施 | 定稿 |
| 技术转交 | 状态为 `handoff` 的要求，交 PCB、结构、样机验证等后续环节落实 | 交接、移交 |
| KiCad 导出 | KiCad 自己导出的网表、ERC 报告和 PDF | 原生 |
| 外围电路核对表 | `reference-input.json`：核心器件引脚与手册的对照和外围电路检查（USB PD 协议的“合同”是协议术语，照用） | 契约 |
| 待办 | `design-closure.json` 的 `work_items` 中的一条，任何状态 | |
| 未关闭项 | 状态为 `open` 的待办（`handoff` 计入技术转交，不算未关闭项） | |
| 独立审查 | 由 schematic-review 技能或其他审查方做的审查；ASG 只做自检 | |
| 后果等级 | 由 `consequence_class` 和 `occurrence` 按规则推出的 P0–P3，见 [design-closure.md](design-closure.md) | |
| 引用待人工核对 | 所引手册页的文字里没找到的数值，需对照原页确认 | |
| 白话说明 | 不再使用：notes 与记录按本表同一套术语写 | 白话 |

## 报告固定用语

| 用语 | 对应字段 |
|---|---|
| 责任方 | `owner` |
| 处理措施 | `action`（缺外部资料的待办写作“关闭方式”） |
| 外部依赖原因 | `why_external` |
| 失效后果 | `consequence` |
| 替代方案 | `fallback` |
| 前置项 | `blocked_by` |
| 关联需求 | `requirements` |
| 设计假设 | `assumption` |
| 本版进展 | `progress` |

## 计数

记录与 notes 里写总数时用“共”或“全部”，并与记录一致，否则算记录问题：

| 写法 | 核对对象 |
|---|---|
| 共 N 项计算 | `design-closure.json` 的 `calculations` 条数 |
| 共 N 件未关闭项 | 状态为 `open` 的待办数 |
| 共 N 条需求 | `requirements` 条数 |
| 共 N 条审查意见 | `review-responses.json` 的 `items` 条数 |
| 共 N 个器件 | 设计要求表的 `components` 个数 |
| 共 N 页 | 图纸页数（`summary.json` 的 `sheets`） |

不带“共/全部”的数字是部分计数（“其中 3 条需求有条件成立”），不核对。
