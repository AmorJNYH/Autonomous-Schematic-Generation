# 交付目录与设计报告

每一版交付都是同一个固定形状的小目录。给人看的只有 `设计报告.md`，其余是原理图本身和可复核的记录。

## 目录

| 位置 | 放什么 | 不放什么 |
|---|---|---|
| `设计报告.md` | `render_design_report.py` 生成 | 手写的 README、说明、HTML |
| `原理图/` | `.kicad_pro`、根图与各页 `.kicad_sch`、项目符号库/封装库及库表、`schematic.pdf`、`netlist.xml`、`BOM.csv` | 草稿图、旧版图 |
| `设计资料/` | 跨版本有效、每版更新的设计文档，名字固定：如 `方案与选型依据.md`、`器件选型与用法依据.md`、`PCB与结构要求.md`、`磁件设计单.md` | 按版本号命名的说明（`v12…`、`v16…`），把仍有效的内容并入固定文档 |
| `record/` | 见下表 | 日志、历史快照、审查方的结果文件 |

`record/` 内容：

| 文件 | 说明 |
|---|---|
| `electrical-intent.json` | 设计要求表（每个器件、网络应该怎样） |
| `design-closure.json` | 需求、待办、计算的处理情况；证据路径相对交付目录，所引证据必须在本目录内；需求、原厂资料可留在 `--input` 登记的位置（按文件名找到并核对 SHA-256） |
| `design-closure-audit.json` | `audit_design_closure.py` 的输出（`verify_schematic.py` 输出目录里的 `design-closure.json`，改名放入） |
| `summary.json` | `verify_schematic.py` 的自动检查结果，原样复制 |
| `visual-review.json` | 看图检查：`{"status": "REVIEWED/REVIEW_PENDING/REWORK_REQUIRED", "pages": [{"page", "paths", "problems"}]}` |
| `delivery-evidence.json` | 导出后有没有再改过的核对记录 |
| `review-responses.json` | 收到审查意见时必有，格式见 [处理审查意见](review-comments.md) |
| `design-change.json` 等 | 改版时的改动核对与动手前检查 |
| `calculations/` | 本版设计还在依赖的计算（不管是哪一版算的），作废的不带 |
| `scripts/` | 图页脚本，下一版只重生成有变化的页面 |
| `evidence/` | 设计结论引用的截图、手册摘页等 |
| `manifest.json` | `pack_design.py` 写：需求、原厂资料、前一版设计的路径和 SHA-256，本目录每个文件的 SHA-256 |

单个文件超过 10 MB 说明带了不该带的东西：仿真原始波形、整份手册、历史台账。只留结论引用的部分，
其余留在工作目录，或用 `--input` 按路径登记。

## 设计报告

`render_design_report.py <交付目录> [--notes notes.json] [--title 标题]` 从 `record/` 生成，顺序固定：

1. **结论**：器件数、页数；自动检查各项结果的数量；看图检查；需求状态；收到的审查意见及处理方式的数量；
   设计是否完成，没完成时逐条列出还差什么。
2. **这版改了什么**：器件数变化，加上 notes 的 `changes`。
3. **审查意见怎么处理的**：逐条列出意见、处理方式、说明。
4. **待办**：`design-closure.json` 里未关闭的待办，按 `severity` 从重到轻排，写明类型、要做什么、找谁、
   拿不到时的替代做法。
5. **交给后续环节的要求**：状态为 handoff 的 validation / pcb 待办，按负责方列表。
6. **自动检查明细**、**设计资料**链接、**关键设计依据**（notes 的 `highlights`，最多 8 条）、**数字一览**、**详细记录**。

报告里的数字和状态都来自记录，不手改报告；要改内容就改记录后重新生成。agent 只通过 notes.json 补白话：

```json
{"summary": "1–3 句：这一版的状态和最要紧的一件事",
 "changes": "这版改了什么、为什么，一段话",
 "items": {"W1": "这件待办用白话说是什么问题"},
 "highlights": ["已经核对清楚、值得一提的设计结论（最多 8 条）"]}
```

写给硬件工程师看：用“定稿”“待办”“交给后续环节”这类说法，不写内部代号和英文状态码；
`action`、`owner`、`fallback` 也按这个要求写，因为它们原样出现在报告里。

## 打包检查

```bash
python3 <skill>/scripts/pack_design.py <交付目录> --input requirements=<需求目录> \
  --input datasheets=<原厂资料目录> [--input previous=<前一版交付目录>]
```

检查失败就修正后重跑，直到 PASS：顶层只能有上面四样；`原理图/` 和 `record/` 的必需文件齐全；
`record/` 只有允许的子目录；没有日志和超大文件；`design-closure.json` 在交付目录内重新审核不出错；
报告用到的记录没有问题。通过后写 `record/manifest.json`。
