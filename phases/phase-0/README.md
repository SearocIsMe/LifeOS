# 阶段 0：契约与可重放骨架（Phase 0）

> 对应《LifeOS_研发路线图_v0.9.1》§2「阶段 0：契约与可重放骨架」。
> 周期 3 周 ｜ 2 人 ｜ 1～2 人月 ｜ 出口 = Gate 0。

## 本阶段回答的问题

- **做什么**：Schema（15 实体）+ 三级事件协议（L0/L1/L2）+ `deterministic_commit` + Policy 最小骨架（2 条红线）+ 回放取证 + 50 条核心事实集 / 30 个行为场景落库注册。
- **为什么先做它**：它是唯一「做对做错立刻知道」的阶段——回放一致率要么 100% 要么不是；全部后续工作都建立在这份契约上（路线图 §1.0）。
- **验证对象**：自动化断言（CI）+ 开发团队双人互审；结论只对工程团队内部有效（路线图 §1.1）。

## Gate 0 判据（规格书 §10，未通过只改契约层，不做 UI/Demo）

1. 示例事件全链路 round-trip（L0→L1→L2→状态写）；
2. 相同 L2 重放 100% 一致；
3. LLM 输出不能直写权威表；
4. Policy 拒绝后无状态副作用。

## 文档索引

| 文档 | 内容 | 读者 |
|---|---|---|
| [01_详细设计.md](01_详细设计.md) | 阶段 0 全部契约与模块的详细设计（15 实体、事件协议、`deterministic_commit`、Policy、隔离、事务、回放、gold set 落库） | 全体成员 |
| [02_工程设计执行方案.md](02_工程设计执行方案.md) | 按周/天的任务分解与执行步骤；10 个验收 case（AC-01～AC-10）的精确定义与验证命令；Gate 0 报告流程 | 工程执行者 |
| [03_核心事实集与行为场景编写规范.md](03_核心事实集与行为场景编写规范.md) | 「50 条核心事实必须人工编写」的原因、要求、规格定义、双人互审流程与校验器清单；§1.4/1.5 论证「为什么恰好是 50/30」（数字来源与可挑战路径）；§7 业界 persona 材料赛道对位（PersonaChat/CharacterEval/PersonaGym 等） | 事实/场景编写人与审校人 |
| [adr/ADR-0001_阶段0边界参数确认.md](adr/ADR-0001_阶段0边界参数确认.md) | Day 1 必须落档的边界参数记录 | 决策层 |
| [adr/ADR-0002_Gate0环境检查记录.md](adr/ADR-0002_Gate0环境检查记录.md) | GPU/模型候选/Provider key/基础设施实测记录（**须实测填写，禁止虚构**；2026-09-16 起随 ADR-0004 在新集群重测） | 工程负责人 |
| [adr/ADR-0003_评测材料来源与签署流程修订.md](adr/ADR-0003_评测材料来源与签署流程修订.md) | 材料来源双路径（P1 人工编写 / P2 AI 起草+具名负责人审定）与签署口径 | 全体成员 |
| [adr/ADR-0004_部署环境迁移至K8s集群.md](adr/ADR-0004_部署环境迁移至K8s集群.md) | 部署环境迁移决策：`lifeos-dev` 命名空间；`dtc-w1`(3×H200) 推理；`aisi-w7` 数据库；compose 降级为备选 | 决策层/工程 |
| [HANDOVER_迁移K8s集群交接.md](HANDOVER_迁移K8s集群交接.md) | **迁移交接文档**：背景/状态快照/代码触点/验证顺序/K8s 清单草稿/纪律红线（新环境接手者从 §5 开始） | 接手执行者 |

## 目录约定

```
phases/
  phase-0/            ← 本阶段（设计 + ADR + 报告）
    reports/          ← Gate 0 验收报告等产物（由验证命令生成）
  phase-1/            ← 阶段 1 启动时创建
  phase-2/            ← 阶段 2 启动时创建
  phase-3/            ← 阶段 3 启动时创建
```

代码骨架在仓库根目录（`src/lifeos/`、`alembic/`、`tests/`、`scripts/`、`data/goldset/`、`docker-compose.yml`）——阶段 0 的工程定位就是「初始化这个仓库」。

## 快速开始（验证工具）

```bash
# 纯本地（无需数据库）：跑全部纯函数级验收
python3 -m pytest tests -q -m "not db"
python3 -m lifeos.cli verify all

# 需要数据库：启动 PostgreSQL + pgvector 后
docker compose up -d postgres
python3 -m pytest tests -q -m db

# 一键 Gate 0 自检（生成报告）
bash scripts/gate0_check.sh            # 不含 DB 层
bash scripts/gate0_check.sh --with-db  # 含 DB 层（需 Docker）
```

## 当前状态（诚实记录，随进度更新）

- [x] 阶段 0 详细设计文档（01/02/03 + ADR-0001/0002/0003）
- [x] 工程骨架代码（15 实体 Schema、事件管线、`deterministic_commit`、Policy 最小骨架、回放取证、gold set 校验器/注册、CLI、27 项自动化测试）
- [x] 材料编制（**ADR-0003 P2 路径**，2026-09-15）：AI 起草候选池（draft.1→draft.2，来源与逐条 notes 完整留痕）→ 独立质疑式审核（《[LifeOS_Phase0_评审与80条候选材料](LifeOS_Phase0_评审与80条候选材料.md)》）→ 结构校验全过（配额/唯一性/中文占比零错误零警告）→ **具名负责人逐条审定签署**（author=Jiang Haipeng ／ reviewer=Searoc，2026-09-15）→ 阶段化 `data/goldset/core_facts/core_facts_v0.1.yaml` 与 `data/goldset/behavior_scenarios/behavior_scenarios_v0.1.yaml`
- [x] AC-09 注册冻结（2026-09-15）：`core_facts` v0.1.0（50 条，content_hash `506c9f4c…`）与 `behavior_scenario` v0.1.0（30 个，content_hash `e4bef442…`）已写入 `GoldSetRegistry`；manifest 见 `reports/goldset_core_facts_v0.1.0.manifest.json`、`reports/goldset_behavior_scenarios_v0.1.0.manifest.json`
- [x] 工程验证（2026-09-15）：tier A 25/25 PASS；PostgreSQL 16+pgvector 容器、alembic 0001 迁移、tier B 2/2 PASS；Gate 0 四条判据全 pass；`reports/gate0_report.json` verdict=**PASS**（13:52Z）
- [x] **环境迁移执行（ADR-0004，2026-09-16 完成）**：`lifeos-dev` namespace 建立；postgres（`aisi-w7`，huawei-sc 100Gi）与 ai-stack（`dtc-w1`，gpu.shared）就绪；tier A 25/25 + tier B 2/2 全绿；新环境 `reports/gate0_report.json` **verdict=PASS**（2026-09-16T03:15Z，旧报告归档 `gate0_report.20260915.local.json`）；全程记录见 [reports/migration_20260916_k8s.md](reports/migration_20260916_k8s.md)
- [x] ADR-0002 全字段在新环境重测（2026-09-16~21，实测回填见该 ADR 追记）：K8s v1.28.15、`dtc-w1` 3×H200 NVL（驱动 570.148.08/CUDA 12.8）、`aisi-w7` 规格、huawei-sc、postgres 限额、本地模型候选（Qwen3.6-35B-A3B-FP8 ✅已部署并冒烟通过；Qwen3.8-Flash-Next-FP8 待新节点 4×H200；Qwen2.5 系按负责人决策移出）、Provider key 以 Secret 配置（`lifeos-provider-a-siliconflow`/`-a-zhipu`/`-b-qwen36`）。**遗留**：两家云端计费告警配置；Qwen3.8 等 4×H200 新节点
- [x] **Gate 0 报告双人签署（2026-09-21）**：架构负责人 Jiang Haipeng + 非编写成员 Searoc 复核签署新环境 `reports/gate0_report.json`（verdict=PASS，签署记录在该文件 signatures 字段。**注意**：`gate0 report` 重跑会重新生成此文件并清掉 signatures——重跑后须把签署字段重新追加，或先备份 `gate0_report_signatures` 段）
- [x] P2 收尾（ADR-0003，2026-09-21）：独立保留集 v0.1.0 圈定并签署——`data/goldset/holdout/holdout_v0.1.yaml`（事实 12 条 + 场景 6 个，7 类/5 情境全覆盖，确定性抽样规则可复核，id 引用不改动冻结材料）；校验 `python3 scripts/holdout_check.py`（author=AI GLM 5.3 flash / reviewer=Jiang Haipeng）

> 运行环境（2026-09-16 起）：K8s 集群（ADR-0004）。宿主机 aisi-w4 一键自检：
> `PYTHON="$PWD/.venv/bin/python" bash scripts/gate0_check.sh --with-db`（自动 kubectl apply/wait + port-forward，密码取自 Secret）
> Pod 内验证：`kubectl -n lifeos-dev exec lifeos-ai-stack-0 -- bash -lc "cd /data/LifeOS && .venv/bin/python -m pytest tests -q -m db"`
> 本地推理端点（Provider B，2026-09-21 起全本地化、零云成本）：Qwen3.6-35B-A3B-FP8 @ `llm-dev/vllm-qwen36-35b-a3b-fp8:8000`（NodePort 30803）与 Qwen3.8-Flash-Next-FP8 @ `llm-dev/vllm-qwen38-flash-next-2gpus:8000`（NodePort 30806，2×H200），两者冒烟均通过；连接信息在 Secret `lifeos-provider-b-qwen36` / `-qwen38`；云端 Provider 已弃用（Secret 保留作应急兜底）
> 材料注册后已冻结：任何修订 = 新版本号 + 重新走签署与注册（不可原地改 `v0.1.0`）。

> 运行环境（2026-09-16 起）：K8s 集群（ADR-0004）。宿主机 aisi-w4 一键自检：
> `PYTHON="$PWD/.venv/bin/python" bash scripts/gate0_check.sh --with-db`（自动 kubectl apply/wait + port-forward，密码取自 Secret）
> Pod 内验证：`kubectl -n lifeos-dev exec lifeos-ai-stack-0 -- bash -lc "cd /data/LifeOS && .venv/bin/python -m pytest tests -q -m db"`
> 本地推理端点（Provider B）：Qwen3.6-35B-A3B-FP8 @ `llm-dev/vllm-qwen36-35b-a3b-fp8:8000`（NodePort 30803），连接信息在 Secret `lifeos-provider-b-qwen36`，2026-09-21 冒烟通过
