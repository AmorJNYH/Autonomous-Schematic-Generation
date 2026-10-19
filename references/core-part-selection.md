# 核心器件选型

本文规定 ASG 怎样为每个**核心器件角色**找候选、比较并记录结论。核心器件指决定架构或固件/配置依赖的器件：
控制器与协议 IC（PFC、反激、SR、PD、MCU）、功率开关、磁件、隔离与反馈器件；两脚通用件（电阻、电容、普通二极管）按计算直接定值，
不走本流程。选型在第 1 步定架构之后、第 2 步核手册之前做：先定型号，再按 [symbol-and-peripheral-contracts.md](symbol-and-peripheral-contracts.md) 核对它的手册。

## 1. 器件库在哪里

器件资料不在本技能内，在本机知识库 `~/Documents/知识库/HardwareWiki`（环境变量 `HARDWARE_WIKI` 可改）：

| 位置 | 内容 | 怎么找 |
|---|---|---|
| `raw/Datasheet/<一级类>/<二级类>/Vendor - PartNumber.pdf` | 器件手册，约四千份；`catalog.json` 索引了厂商、型号、分类、标签和前几页正文 | `scripts/find_parts.py --category "<二级类>" 关键词…`、`--mpn 型号`；`--text` 连正文一起搜（正文多为英文，关键词用英文） |
| `raw/Designexample/<拓扑>/<板名>/` | 参考设计、评估板手册 | `find_parts.py --designs 关键词…`，结果按板文件夹归并 |
| `raw/Applicationnote/` | 应用笔记 | `find_parts.py --notes 关键词…` |
| `raw/Datasheet/元器件体系/器件统一分类大表.md` | 分类规则与各厂商产品线 | 决定一个新手册放哪个目录 |
| `wiki/entities/` | 已整理的器件/概念条目 | 直接按文件名打开 |

每类器件是干什么的、选它看什么参数，见 [part-roles.md](part-roles.md)；选型从那张表的"按功能找类"开始，
先定二级类，再在类里检索候选。没入索引的 PDF 检索结果标 `未入索引`，可以用，但要自己读文件名核对型号。

## 2. 候选从哪里来（按优先级）

1. 用户指定或用户的优选料表：有就以它为准，其余候选只用来证明它可行或说明为什么不行。
2. 上一版已审查的设计沿用的型号：不换，除非审查意见或新需求要求换。
3. 同拓扑参考设计的核心器件：`find_parts.py --designs <拓扑/功率/接口>`，打开板手册的 BOM，把它用的控制器、开关、磁件抄成候选，记下板名。
4. 库内同类手册：按 part-roles.md 定二级类，`find_parts.py --category "<二级类>"` 列出全部，
   用决定性参数先筛掉明显不合的，剩下的打开手册首页核。
5. 库里没有合适的类或候选不足两个时才外部检索（Digikey/JLCPCB MCP 工具或网页），下载的手册按 SKILL.md 第 2 步资料规则存入库里，
   然后它就成了第 4 条的候选。记录里写明这一步做过。

## 3. 怎么比较

每个角色先写**决定性条件**：从需求表抽出的、能直接淘汰候选的量（输入电压范围、功率等级、协议版本、隔离等级、
开关频率、封装热阻上限、固件/配置工具依赖、成本或可得性目标）。不写泛泛的"性能好"。
比较时逐条对照手册首页/特性表，用页码记录；只在淘汰或决定时才深读。

淘汰顺序：

1. 电气不满足决定性条件（电压、功率、协议、隔离）。
2. 依赖拿不到：需要 NDA、专有配置工具、未公开固件，而需求没有给出获得途径。
3. 资料不足：库里只有简介没有完整手册，且外部也拿不到——不能选。
4. 封装/热/可得性/成本：按需求的目标；需求没给目标时记"未评估"，不编数字。
5. 剩下多个都能用时，优先参考设计已验证的组合（减少外围设计风险），其次库里资料最全的。

至少两个候选才算比较过；只有一个时写 `single_candidate_reason`（用户指定、沿用上一版、该类库里只有一份且外部检索也没找到……）。

## 4. 记录：`record/selection.json`

```json
{
  "schema_version": 1,
  "library_root": "~/Documents/知识库/HardwareWiki",
  "roles": [
    {
      "role": "PFC 控制器",
      "refs": ["U201"],
      "requirements": ["R-IN-01", "R-EFF-02"],
      "decisive": ["输入 90–264 VAC", "100 W 级 CrM/DCM 多模", "待机功耗 ≤ 75 mW", "外部 MOS 驱动"],
      "sources": ["designexample:raw/Designexample/USB-PD/NCP1343PD100WGEVB", "catalog:08_电源管理/AC-DC 转换器"],
      "candidates": [
        {"mpn": "NCP1623", "vendor": "onsemi", "status": "selected",
         "datasheet": "raw/Datasheet/08_电源管理/AC-DC 转换器/onsemi - NCP1623.pdf",
         "reason": "参考设计验证的组合；多模 CrM/DCM 满足轻载效率；p.1 特性、p.6 表 3 待机功耗", "pages": "1, 6"},
        {"mpn": "L4984D", "vendor": "ST", "status": "rejected",
         "datasheet": "raw/Datasheet/08_电源管理/AC-DC 转换器/ST - L4984D.pdf",
         "reason": "固定 CrM，轻载效率不满足 R-EFF-02；p.1", "pages": "1"}
      ]
    }
  ]
}
```

字段要求（`render_design_report.py` 检查，不满足算记录问题，`pack_design.py` 拒绝打包）：

- 每个角色有 `role`、非空 `refs`、非空 `decisive`、非空 `sources`、`candidates`。
- 候选 ≥ 2，否则要有 `single_candidate_reason`；`status` 只能是 `selected`/`rejected`/`alternate`，恰好一个 `selected`。
- 每个候选有 `mpn`、`reason`、`datasheet`；`datasheet` 是相对 `library_root` 的路径，文件必须存在（也可以是交付目录内 `设计资料/` 下的文件）。
- `selected` 的每个位号都在设计要求表里，且该器件的 `value` 含选定型号。
- 设计要求表里每个 U/Q/T 开头的器件都属于某个角色；一个角色可以覆盖多个位号（例如两只并联 MOS）。

报告的"核心器件选型"一节由这份记录生成：角色、选定型号、候选数和一句理由。理由用中文，型号和单位可以保留。
