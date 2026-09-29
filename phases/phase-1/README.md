# 阶段 1：最小数据打通平台 + 跨模型连续性验证

> 状态：工程实施完成（2026-09-29）。前置条件已满足：阶段 0 全部工程动作与人工收尾完成，Gate 0 复跑 verdict=PASS（[`reports/gate0_report.json`](../phase-0/reports/gate0_report.json)），双人签署与独立保留集均已关闭。Gate 1 七项指标 mock 出数 verdict=PASS（[`reports/gate1_report.json`](reports/gate1_report.json)，judge=field-compare-v0，真臂另出）。

## 本阶段定位（路线图 §3）

- **唯一研究目标**：H1 最小实验——同一 Life Instance、相同结构化状态，Provider A → Provider B，核心事实召回能否 ≥90%；
- **同时是「平台在最小数据上端到端跑通」的阶段**：状态→记忆→规划→审批→渲染→写回全链路；
- **验证对象**：自动化断言（对照冻结 gold set）+ 团队内人审；结论对内有效，不构成用户感知证据。

## 关键决策（2026-09-29，ADR-0005 待写）

**H1 双 Provider 均取本地 vLLM 端点**（架构负责人确认）：

- 路线图原文为「Provider A（云端）→ Provider B（本地）」，但云端 Secret 已弃用删除；
- 当前环境三个本地端点：Qwen3.6-35B-A3B-FP8（常态）、Qwen3.8-Flash-Next-FP8（按需）、GLM-5.3-Flash（按需）；
- H1 绑定：Provider A = Qwen3.6-35B，Provider B = GLM-5.3-Flash（均为集群内 vLLM，确定性路由 + 本地权重固定，零云成本）；
- 此偏差以 ADR 记录，属实验设计的等价替换（云端 API 与本地 vLLM 同为 OpenAI 兼容协议）。

## 文档索引

| 文档 | 内容 |
|---|---|
| [`01_详细设计.md`](01_详细设计.md) | S1–S4 各模块设计：Life Kernel（惰性衰减）、Relationship Engine、Context Assembly、Model Gateway、Eval Harness |
| [`02_工程设计执行方案.md`](02_工程设计执行方案.md) | 验收 case 定义、Gate 1 七项指标的测量脚本设计、执行顺序 |

## Gate 1 判据（规格书 §10，共七项）

L2 重放 100% ｜ 核心事实召回 ≥90% ｜ 称呼关系一致 ≥95% ｜ 记忆错误 ≤5% ｜ 跨模型行为意图一致 ≥80% ｜ 高危 Policy 违规 0 ｜ 证据链完整 100%。

## 目录约定

沿用阶段 0 惯例：`01_`/`02_` 编号文档、`adr/` 记录决策、`reports/` 存放评估输出；代码增量落在 [`src/lifeos/`](../../src/lifeos/)（kernel、gateway、assembly、eval 各子包），测试落在 [`tests/`](../../tests/)。
