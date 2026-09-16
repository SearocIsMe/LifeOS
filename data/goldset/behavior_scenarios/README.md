# 行为场景集（ADR-0003 双路径编制区）

规范与配额：[phases/phase-0/03_核心事实集与行为场景编写规范.md](../../../phases/phase-0/03_核心事实集与行为场景编写规范.md) §4；
来源与签署口径：[ADR-0003](../../../phases/phase-0/adr/ADR-0003_评测材料来源与签署流程修订.md)（2026-09-15 采纳）。

- `behavior_scenarios_template.yaml`：格式示例（2 条，非正式集）；
- `behavior_scenarios_v0.1.yaml`：**已注册冻结（v0.1.0，2026-09-15）**：P2 路径（AI 起草 + 来源留痕 + 独立审核 + 具名负责人签署 author=Jiang Haipeng / reviewer=Searoc）→ 30 个全过 validator → 注册。**冻结后不可原地修改；任何修订 = 新版本号 + 重新签署注册。**

```bash
python3 -m lifeos.cli goldset validate --kind behavior_scenario --file data/goldset/behavior_scenarios/behavior_scenarios_v0.1.yaml
python3 -m lifeos.cli goldset register --kind behavior_scenario --file data/goldset/behavior_scenarios/behavior_scenarios_v0.1.yaml --version 0.1.0 --out phases/phase-0/reports/goldset_behavior_scenarios_v0.1.0.manifest.json
```
