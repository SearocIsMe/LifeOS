# 独立保留集（holdout）v0.1.0

- 文件：`holdout_v0.1.yaml`（**id 引用清单**，不含条目本体——冻结材料内容零改动）
- 基于：`core_facts` v0.1.0（50 条，hash `506c9f4c…`）与 `behavior_scenarios` v0.1.0（30 个，hash `e4bef442…`），`based_on` 中登记冻结 hash，校验脚本比对
- 规模：**事实 12 条（≥10）+ 场景 6 个（≥6）**，fact 7 类全覆盖、scenario 5 种 situation 标签全覆盖、6 个 intent 全覆盖
- 抽样规则：确定性分层抽样（规则全文写在 yaml `selection_rule` 字段，无随机数，任何人可复核复现）

## 纪律（ADR-0003 P2 收尾）

1. 本清单所引条目**不用于**任何调试、调参、提示词迭代、演示或开发验证；
2. 仅用于**最终盲评**（held-out evaluation）；评测实现必须引用本清单 id，并在 `EvaluationRun.metrics_json` 中声明 `holdout=true`；
3. 修订 = 新版本 + 重新签署（不可原地改 `v0.1.0`）；
4. **未签署前本清单不生效**（`review` 块留空，待具名负责人审定签署）。

## 校验

```bash
.venv/bin/python scripts/holdout_check.py   # exit 0 = 通过；未签署时给 WARNING
```

校验内容：id 引用可解析、数量达标、based_on hash 与冻结材料一致、类别/情境覆盖、签署状态（签署状态仅告警，因签署是人工步骤）。

## 签署（待办）

`holdout_v0.1.yaml` 的 `review` 块需具名负责人填写：`author`（起草方已填 AI 协作 → 由负责人审定后填 `reviewer` 或按 P2 惯例 author=Jiang Haipeng / reviewer=Searoc）与 `review_date`。签署后该文件即生效并随仓库提交。
