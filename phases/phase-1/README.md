# 阶段 1：最小数据打通平台 + 跨模型连续性验证

> 状态：工程实施完成（2026-09-29），真臂出数完成（2026-09-29）。前置条件已满足：阶段 0 全部工程动作与人工收尾完成，Gate 0 复跑 verdict=PASS（[`reports/gate0_report.json`](../phase-0/reports/gate0_report.json)），双人签署与独立保留集均已关闭。Gate 1 七项指标 mock 出数 verdict=PASS（[`reports/gate1_report.json`](reports/gate1_report.json)，judge=field-compare-v0）。真臂回放完成：30 case / 28 一致，h1_score=0.933（[`reports/h1_real_arm_report.json`](reports/h1_real_arm_report.json)）。

## 本阶段定位（路线图 §3）

- **唯一研究目标**：H1 最小实验——同一 Life Instance、相同结构化状态，Provider A → Provider B，核心事实召回能否 ≥90%；
- **同时是「平台在最小数据上端到端跑通」的阶段**：状态→记忆→规划→审批→渲染→写回全链路；
- **验证对象**：自动化断言（对照冻结 gold set）+ 团队内人审；结论对内有效，不构成用户感知证据。

## 关键决策（2026-09-29，ADR-0005 已签署）

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

## 验收步骤与执行记录（2026-09-29 详细）

> 全部步骤自动化可复跑；mock 模式在无 GPU/无外网环境可复现。各 case 断言明细见 [`02_工程设计执行方案.md`](02_工程设计执行方案.md) §2–§3，DoD 见 §5。

### 步骤 1：阶段 0 前置闭环检查（迁移验收）

- 命令：`bash scripts/gate0_check.sh`
- 实测：exit 0，`verdict=PASS`，报告覆盖 [`../phase-0/reports/gate0_report.json`](../phase-0/reports/gate0_report.json)（旧本机报告已归档为 [`gate0_report.20260915.local.json`](../phase-0/reports/gate0_report.20260915.local.json)）；GPU 探测见 NVIDIA H200 NVL 143771 MiB，Python 3.10.12
- 判定：✅ 通过（满足 HANDOVER §6 "verdict 必须再次 PASS 才算迁移完成"，实测回填见实测段）

### 步骤 2：全量单元回归（tier A）

- 命令：`PYTHONPATH=src python3 -m pytest tests/ -q`
- 实测：**91 passed, 2 deselected**（含阶段 0 既有用例，无回归）
- DB 断言：`PYTHONPATH=src python3 -m pytest tests/ -m db -q` → 2 skipped（无集群连接时按设计跳过；集群内 runner 运行为 2 passed：迁移/权限断言 + 持久化→回注水化→回放 100%→隔离）
- 判定：✅ 通过

### 步骤 3：S1 内核/关系/管线衰减增量验收

- 运行命令（实测：**30 passed**）：

  ```bash
  cd /local-sc-w3/LifeOS && PYTHONPATH=src python3 -m pytest tests/test_kernel.py tests/test_relationship.py -q
  ```

- 测试：[`tests/test_kernel.py`](../../tests/test_kernel.py)、[`tests/test_relationship.py`](../../tests/test_relationship.py)
- 断言覆盖：衰减纯函数（同输入精确相等）、衰减单调性（向基线收敛不穿越）、物化触发（仅五类调用物化）、关系更新 `clip(r_t + w·p·c − λΔt)`、关系版本化（version 递增不删史）、主观谓词隔离、管线 L2 `state_delta`（先惰性衰减到 now 再加 delta，同事件序列重放一致）
- 实现：[`src/lifeos/kernel/decay.py`](../../src/lifeos/kernel/decay.py)（`DECAY_PARAMS`）、[`src/lifeos/kernel/relationship.py`](../../src/lifeos/kernel/relationship.py)、[`EventPipeline.ingest`](../../src/lifeos/events/pipeline.py) 衰减增量
- 判定：✅ 通过

### 步骤 4：S2 组装/网关验收

- 运行命令（实测：**14 passed**）：

  ```bash
  cd /local-sc-w3/LifeOS && PYTHONPATH=src python3 -m pytest tests/test_assembly.py tests/test_gateway.py -q
  ```

- 测试：[`tests/test_assembly.py`](../../tests/test_assembly.py)、[`tests/test_gateway.py`](../../tests/test_gateway.py)
- 断言覆盖：Assembly 纯函数（逐字符相等）、prompt_hash 稳定（任一字段变化 hash 变化）、模板版本化（未注册抛错）、Gateway mock 确定性回显、逐笔 provenance（ModelInvocation 落库）、switch 系统 L0 断言（快照逐字段相等）、extract 契约（fail-closed 无副作用）
- 实现：[`src/lifeos/assembly/`](../../src/lifeos/assembly/)、[`src/lifeos/gateway/`](../../src/lifeos/gateway/)
- 判定：✅ 通过

### 步骤 5：S3 规划器验收

- 运行命令（实测：**11 passed**）：

  ```bash
  cd /local-sc-w3/LifeOS && PYTHONPATH=src python3 -m pytest tests/test_planner.py -q
  ```

- 测试：[`tests/test_planner.py`](../../tests/test_planner.py)（11 用例）
- 断言覆盖：6 意图枚举（恰为 6 个无越界）、打分封闭（同状态同分）、reason 证据链（含全部候选得分分解）、Policy 独占衔接（proposed → approved/rejected 仅由 Policy 转出）、comfort 触发（security < 0.4 时排名第一）、stay_quiet 基线（无强信号时排名第一）
- 实现：[`src/lifeos/planner/engine.py`](../../src/lifeos/planner/engine.py)
- 判定：✅ 通过

### 步骤 6：S4 评测闭环 + Gate 1 mock 出数

- 运行命令（实测：**11 passed**）：

  ```bash
  cd /local-sc-w3/LifeOS && PYTHONPATH=src python3 -m pytest tests/test_h1_harness.py -q
  ```

- 测试：[`tests/test_h1_harness.py`](../../tests/test_h1_harness.py)
- 出数命令（对照冻结 gold set，mock provider，离线可复跑）：

  ```bash
  PYTHONPATH=src python3 -c "
  import yaml
  from lifeos.evalharness.gate1 import run_gate1
  cf = yaml.safe_load(open('data/goldset/core_facts/core_facts_v0.1.yaml', encoding='utf-8'))
  bs = yaml.safe_load(open('data/goldset/behavior_scenarios/behavior_scenarios_v0.1.yaml', encoding='utf-8'))
  report = run_gate1(facts=cf['items'], scenarios=bs['items'])
  print(report.verdict)
  "
  ```

- 实测结果（judge=field-compare-v0，mock_mode=true，fact_recall 逐条 50/50）：

  | 指标 | 实测值 | 阈值 | 判定 |
  |---|---|---|---|
  | replay_consistency | 1.0 | =1.0 | ✅ |
  | fact_recall | 1.0 | ≥0.9 | ✅ |
  | salutation_consistency | 1.0 | ≥0.95 | ✅ |
  | memory_error_rate | 0.0 | ≤0.05 | ✅ |
  | intent_consistency | 1.0 | ≥0.8 | ✅ |
  | policy_violations | 0.0 | =0 | ✅ |
  | evidence_chain | 1.0 | =1.0 | ✅ |

- 产出：[`reports/gate1_report.json`](reports/gate1_report.json)（verdict=PASS）
- 判定：✅ 通过（七项全过 → 不阻塞阶段 2；按 [`01_详细设计.md`](01_详细设计.md) 判定规则）

### 步骤 7：文档与签署闭环

- [`02_工程设计执行方案.md`](02_工程设计执行方案.md) §5 DoD 五项全部勾选；
- ADR-0005 签署：Accepted（Jiang Haipeng，2026-09-29），落 [`adr/ADR-0005_阶段1环境适配与参数基线.md`](adr/ADR-0005_阶段1环境适配与参数基线.md)
- 判定：✅ 通过

### 真臂出数（已闭环，2026-09-29）

- 按 ADR-0005 D3/D4：以真实 vLLM 端点（Provider A = Qwen3.6-35B-A3B-FP8 → Provider B = GLM-5.3-Flash）回放 30 条行为场景探针（同 prompt_hash 双臂对称调用），结果：
  - **h1_score = 0.933**（28/30 一致，达标线 ≥80%），解析失败 0；
  - 2 例差异：BS-016 仅 `slot_key` 不同（intent_type 一致）、BS-022 语义差异（stay_quiet vs comfort，真实分歧）；
  - 引导解码：`response_format: json_schema`（[`INTENT_SCHEMA`](../../src/lifeos/gateway/provider.py)，enum 形状强制，双臂对称启用），prompt_hash 不变；
  - 产出：[`reports/h1_real_arm_report.json`](reports/h1_real_arm_report.json)（`judge: field-compare-v0` + 端点/base_url 实测元数据）；
  - 诚实性：分数为确定性字段比较判官的工程信号，不得作为产品结论引用（规格 §5.2 / ADR-0005 D2）；
  - 回归：改动后全量 `pytest` 91 passed（含阶段 0 既有用例无回归）。
  - 判定：✅ 闭环

## 目录约定

沿用阶段 0 惯例：`01_`/`02_` 编号文档、`adr/` 记录决策、`reports/` 存放评估输出；代码增量落在 [`src/lifeos/`](../../src/lifeos/)（kernel、gateway、assembly、evalharness、planner 各子包），测试落在 [`tests/`](../../tests/)。
