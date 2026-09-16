# 核心事实集（ADR-0003 双路径编制区）

规范与流程：[phases/phase-0/03_核心事实集与行为场景编写规范.md](../../../phases/phase-0/03_核心事实集与行为场景编写规范.md)；
来源与签署口径：[ADR-0003](../../../phases/phase-0/adr/ADR-0003_评测材料来源与签署流程修订.md)（2026-09-15 采纳：P1 人工编写+双人互审 ／ P2 AI 起草+来源记录+独立审核+具名负责人审定）。

## 文件说明

| 文件 | 性质 |
|---|---|
| `core_facts_template.yaml` | **格式示例**（仅 3 条，展示字段写法，不得并入正式集，不计入 50 条） |
| `core_facts_v0.1.yaml` | **已注册冻结（v0.1.0，2026-09-15）**：ADR-0003 P2 路径——AI 起草（来源与逐条 notes 留痕，provenance 块在文件头）→ 独立质疑式审核（评审报告）→ 具名负责人逐条审定签署（author=Jiang Haipeng / reviewer=Searoc）→ 50 条全过 validator → 注册。**冻结后不可原地修改；任何修订 = 新版本号 + 重新签署注册。** |

## 操作流程

1. 两位编写人各按类别配额写约 25 条（配额表见 03 文档 §3.3）；
2. 交叉互审 → 仲裁 → 填 `review` 签署块；
3. 校验：
   ```bash
   python3 -m lifeos.cli goldset validate --kind core_facts --file data/goldset/core_facts/core_facts_v0.1.yaml
   ```
4. 注册冻结：
   ```bash
   python3 -m lifeos.cli goldset register --kind core_facts --file data/goldset/core_facts/core_facts_v0.1.yaml --version 0.1.0 --out phases/phase-0/reports/goldset_core_facts_v0.1.0.manifest.json
   ```

> 测试与示例代码引用的 `tests/fixtures/` 下材料是**工程 fixture**（演示管线用），与 gold set 无关，不得混用。
