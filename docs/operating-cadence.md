# 运行节奏：每块板子的固定动作

改进计划第 6 阶段。这是 SKILL.md 之外的操作清单，面向运行 ASG 和 SR 的人；每块板子的每一版都按这个顺序走，
不跳步。目的只有一个：让审查和测试发现的每个问题都变成技能或知识库里的一行，并且不把已经画好的板子改坏。

## 一版的七步

| 步 | 谁 | 做什么 | 产物 | 门禁 |
|---|---|---|---|---|
| 1 | ASG | 按 SKILL.md 设计并交付 | 交付目录（含 `record/selection.json`、`record/lessons.json`） | `pack_design.py` PASS |
| 2 | SR | 独立审查，不看 ASG 的结论先看需求和手册 | 审查报告与待办编号 | SR 自己的门禁 |
| 3 | ASG | 逐条登记并归因：`review-responses.json` 每条 `cause`，`lessons.json` 对应事件 | 更新后的记录 | `render_design_report.py` 无归因问题 |
| 4 | 维护者 | 按归因改技能或知识库：`rule_*` 改 `scripts/`，`knowledge_*` 改 `references/` 或知识库，`judgment` 写明为什么拦不住 | 代码或知识文件改动 | 合成测试通过 |
| 5 | 维护者 | 跑回归：`python3 scripts/run_regression.py`；问题数或门禁不得比基线差 | 回归输出 | PASS，或 `--update-baseline` 并在台账说明 |
| 6 | 维护者 | 台账条目（Event/Causes/Changed 三行）并提交；新板子登记进 `tests/regression/boards.json` | git 提交 | `scripts/check_ledger.py` PASS |
| 7 | 测试/生产 | 实物或测试结果回来后，以 `test:<记录>` 为事件再走 3–6 | 同上 | 同上 |

## 每步的检查点

- **第 1 步**：`lessons.json` 至少一条事件；没学到东西的写 `cause: none` 并引用核对过的页码。泛泛的总结会被报告拒绝。
  读过的手册都在知识库里（`pack_design.py` 核对），参考设计放 `raw/Designexample/<拓扑>/<板名>/`。
- **第 3 步**：归因先于修改。同一条意见若上一版已出现过，`cause` 不能再是 `judgment`：上次的改动没拦住，说明归因错了，重新归因。
- **第 4 步**：能用脚本判定的不写成文字；每条新文字规则都要问一次能不能变成门禁或检查项。
- **第 5 步**：回归失败先看是不是误报（新规则在旧板上报出了真问题）。是真问题就更新基线并在台账写明；不是就改规则。
- **第 6 步**：没有事件来源的改动不提交。计划内的阶段性改动，事件写 `user:<日期>` 并注明计划阶段。

## 每版记三个数

写在 `docs/improvement-ledger.md` 对应条目里，趋势见 `docs/improvement-plan.md` "怎么知道计划有效"：

1. 同一条审查意见在下一版再次出现的条数。
2. 归因为 `judgment` 的意见占比。
3. 回归集上的问题数。

## 命令

```bash
python3 scripts/render_design_report.py <交付目录> --notes <交付目录>/record/notes.json --title "<标题>"
python3 scripts/pack_design.py <交付目录> --input requirements=<需求目录> --input datasheets=<资料目录> --input previous=<上一版>
python3 -m unittest discover -s tests
python3 scripts/run_regression.py
python3 scripts/check_ledger.py
```
