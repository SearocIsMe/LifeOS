# 真臂出数预案：四基线真模型对比（vLLM 端点确认 checklist）

> 预案日期：2026-09-30。骨架已就绪（[`real.py`](../../src/lifeos/baselines/real.py) client + [`assembly.py`](../../src/lifeos/baselines/assembly.py) 四臂组装，202 tests）；真臂出数待本 checklist 逐项确认后执行（不抢跑）。
> 公平对照纪律（spec §4.4）：四臂共用**同一生成模型 + 同一渲染模板骨架 + 同一 Policy 审批**，差异仅在「身份上下文组装」层；材料一律从各臂**完整输出管线**取样，不允许手工拼接。

## 1. vLLM 端点确认 checklist（逐项实测后勾选）

| # | 检查项 | 命令 | 通过判据 | 状态 |
|---|---|---|---|---|
| 1.1 | `llm-dev` 命名空间 vLLM Pod 就绪 | `kubectl -n llm-dev get pods` | 候选 1（Qwen3.6-35B-A3B-FP8）`Running 1/1` | ✅ 确认 |
| 1.2 | NodePort 30803 可达 | `curl -s http://192.168.10.203:30803/v1/models` | 返回模型清单含 Qwen3.6-35B | ✅ 确认（**bug 已修**：端点开启 Bearer 鉴权，key 在 `llm-dev/vllm-secret`，client 走 `LIFEOS_GEN_API_KEY` env 注入；无 key → `{"error":"Unauthorized"}`） |
| 1.3 | port-forward 建立并冒烟 | `PYTHON="$PWD/.venv/bin/python" bash scripts/gate0_check.sh --with-db`（自动 port-forward）+ curl `/v1/chat/completions` | HTTP 200 + choices 非空 | ✅ 确认（**bug 已修**：model id 实际为官方前缀 `Qwen/Qwen3.6-35B-A3B-FP8`，短名 404；client 新增 `resolve_model()` 从 `/v1/models` 自动发现并缓存） |
| 1.4 | 统一生成模型版本锁定 | `/v1/models` 响应比对报告记录 | model_version 与报告一致（spec §9.5） | ✅ 确认（实际 id `Qwen/Qwen3.6-35B-A3B-FP8` 已在 comparison_real 记录） |
| 1.5 | 双臂端点（可选，场景三） | 30804（GLM-5.3-Flash）同上 | 同 1.2/1.3 | ✅ 确认（同 secret/鉴权口径） |

> **真臂冒烟（2026-09-30）**：`run_baselines_real.py --mode real --base-url http://192.168.10.203:30803/v1 --limit 2` **PASS（exit 0）**——4 臂 × 2 probes 全部 VLLMChatClient 真实生成（LifeOS 臂延迟 5.5s/请求，policy=approve，usage 落档 prompt=265/completion=1120 tokens）。真臂数据可用性确认；全量 30 场景出数待执行。

> **T5 已交付（2026-09-30）**：跑分协议 runner [`scripts/demo/run_baselines_real.py`](../../scripts/demo/run_baselines_real.py) 落档——mock 模式 30 冻结场景 × 4 臂 PASS（exit 0，分报告 + `comparison_real.json`），`--mode real` 无 `--base-url` fail-closed exit 1（不抢跑），CI 覆盖 4 用例全绿。下表步骤 2.2/2.3/2.5 已由 runner 实现，真臂执行时直接 `--mode real --base-url <...>`。

## 2. 出数步骤（checklist 全过后执行）

| 步骤 | 动作 | 落点 |
|---|---|---|
| 2.1 | 30 个冻结场景中的重逢/换模型片段注入（材料池与呈现顺序已在预注册文档冻结） | `data/goldset/behavior_scenarios/behavior_scenarios_v0.1.yaml` |
| 2.2 | 四臂组装层逐臂生成 system_prompt（[`assembly.py`](../../src/lifeos/baselines/assembly.py) 纯函数，prompt_hash 留痕） | 差异仅在组装层 |
| 2.3 | 统一 client 出数（[`real.py`](../../src/lifeos/baselines/real.py) `VLLMChatClient`，temperature=0 + seed pin） | 逐笔 `ModelInvocation` provenance |
| 2.4 | Policy 审批流跑同 prompt（拒绝正确率 = 主系统门槛） | `policy/engine.py` |
| 2.5 | 分报告 + `comparison_real.json`（主系统门槛 + 优于最佳基线点估计） | `reports/baselines/` |
| 2.6 | 中文能力基线：Baseline A 无状态问答准确率（spec §4.3 语言控制） | comparison_real 附表 |

## 3. 判定纪律

- 主系统门槛不过 → 整改一轮（2～4 周，重跑同一冻结场景集）；
- 优于最佳基线的**配对差值 CI** 留待盲测 n≥50（本出数只产点估计）；
- 逐笔 `ModelInvocation` 落 tokens/latency/cost/purpose/model_version（成本可计算，spec §3.4）。

## 4. 签署

- 预案编写：AI GLM 5.3 flash（2026-09-30）
- checklist 确认与出数执行：并回填第 1 节 [x]
