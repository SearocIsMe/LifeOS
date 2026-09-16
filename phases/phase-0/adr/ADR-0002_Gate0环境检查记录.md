# ADR-0002：Gate 0 环境检查记录

- 状态：**部分实测（2026-09-15）；2026-09-16 起部署环境迁移至 K8s 集群（[ADR-0004](ADR-0004_部署环境迁移至K8s集群.md)），旧机实测记录转为历史存档，全部字段须在新环境重测（见文末追记）**
- 日期：2026-09-15（首轮实测）
- 关联：路线图 §2「环境检查项（Gate 0 前置）」；原始数据存档 `phases/phase-0/reports/envcheck.json`、`gate0_report.json`

> **诚实要求**：本 ADR 的每个字段必须**实测后填写**，禁止凭记忆或估计填写。下表已填字段均标注了实测来源与日期；「待填」字段必须由负责人补测（候选模型清单尤其需要查阅官方模型卡，不得由 AI 凭印象生成）。测不到的项如实写「不可用/未测」，不写「预计可用」。

## 检查项

### 1. GPU 工作站（Provider B 本地推理用，阶段 1 大头）

#### 1.0 新环境明确口径（2026-09-16 迁移后）：**GPU 工作站 = K8s GPU Container（H200），已实测可用**

| 字段 | 实测值 | 来源 |
|---|---|---|
| 是否可用 | **是——K8s GPU Container 已跑通**：`lifeos-ai-stack-0`（`runtimeClassName: nvidia`）在 `dtc-w1` 调度成功，Pod 内 `nvidia-smi` 正常输出 | kubectl get pods + Pod 内实测（2026-09-16） |
| 形态 | Pod 请求 `nvidia.com/gpu.shared`（requests=limits 同值；time-slicing 30 份/卡共享，资源名非 `nvidia.com/gpu`） | 节点标签 `gpu.replicas=30`、`gpu.sharing-strategy=time-slicing` |
| 型号 | NVIDIA H200 NVL ×3（节点 `nvidia.com/gpu.count=3`）；单 Pod 内可见 1 个 H200 实例（共享方案按分配暴露，属预期） | gpu-feature-discovery 节点标签 + Pod 内 `nvidia-smi` |
| 显存 | **143771 MiB（约 140 GiB）/卡**；time-slicing 共享下全卡显存可见、算力按份额时间片轮转 | `nvidia-smi` + `nvidia.com/gpu.memory` |
| CUDA/驱动版本 | CUDA **12.8** / Driver **570.148.08**（compute capability 9.0，hopper） | Pod 内 `nvidia-smi` 头部 |
| 宿主 | Supermicro AS--5126GS-TNRT；驱动经 gpu-operator daemonset（`nvidia-driver-daemonset`）管理 | `kubectl get node/pods -n gpu-operator` |
| 对阶段 1 的意义 | H200（141GB 级）解除旧 8GB 笔记本的候选模型瓶颈；Provider B（vLLM/llama.cpp）直接部署于本 Pod 或同形态 Pod（清单 [k8s/40-dev-stack.yaml](../../k8s/40-dev-stack.yaml)） | ADR-0004 + 迁移执行记录 |

> 旧机（RTX 4060 Laptop 8GB）记录按下表保留为历史；自 2026-09-16 起 Gate 0 的 GPU 检查项以上表为准。


| 字段 | 实测值 | 来源 |
|---|---|---|
| 是否可用 | 是（`nvidia-smi` 可见） | envcheck 2026-09-15 |
| 型号 | NVIDIA GeForce RTX 4060 Laptop GPU | envcheck 2026-09-15 |
| 显存 | 8188 MiB（8 GB） | envcheck 2026-09-15 |
| CUDA/驱动版本 | （待填：`nvidia-smi` 完整输出） | |
| 备注 | 8 GB 显存属**入门级**：7B 级模型 Q4 量化可跑，14B+ 困难。阶段 1 S2 候选清单按此前提筛选；若不满足实验需求，走路线图 §8 降级路径 | |

### 2. 候选本地模型清单（按显存筛选 2～3 个候选，阶段 1 S2 部署）

| 候选 | 参数量 | 量化档位 | 预估显存占用 | 中文能力初评依据 | 状态 |
|---|---|---|---|---|---|
| **Qwen3.6-35B-A3B-FP8**（官方原生 FP8，单卡副本 ×2）✅首选 | 35.95B 总参 MoE / 激活 3B | FP8 原生（F8_E4M3） | 权重约 **35.95GB**（HF API 实测 safetensors total），单卡 141GB 放置后 KV 余量极大；2 卡 = 2 个独立副本，无 TP 依赖 | Qwen 官方模型卡（2026-04-24 发布，HF API 实测抓取）：原生 262,144 上下文（可扩展至 1,010,000）、Thinking Preservation、推荐 vllm>=0.19.0、Apache-2.0、下载量 1094 万+；Qwen 系中文能力一贯为官方榜单强项（以模型卡为准） | **候选 1（推荐首选）**：MoE 激活小→高吞吐低延迟，对话型场景理想；FP8 与 H200（Hopper）原生匹配 |
| **Qwen3.8-Flash-Next-FP8**（新增独立节点；推荐 4×H200 TP=4，可选 2×H200 TP=2） | 176B 总参 / 6B 激活 MoE（Qwen4 架构预览，负责人已决策列入 2026-09-16） | FP8 原生（F8_E4M3） | checkpoint **172.78 GiB**（recipes 原文）：4×H200 → 43.2 GiB 权重/卡、余 ~97 GiB KV（推荐）；2×H200 → 86.4 GiB 权重/卡、余 ~55 GiB KV（显存成立，官方未验证） | Qwen 官方模型卡/recipes（2026-08-27 发布，HF API 实测）：262K 原生上下文（可扩 1M）、内置 MTP、多模态、Apache 之外的 Qwen 自有 license「other」（需过审）、需 vLLM 0.29.0+ | **候选 2（需新节点）**：与 Qwen3.6 构成阶段 1「跨模型连续性」本地两端点；TP 形态部署时实测验证 |

> **估算口径（诚实边界）**：以上显存数字来自各官方模型卡公开数据 + 通用估算式（BF16 ≈ 2 bytes/param、INT4 ≈ 0.5 bytes/param，另加激活与 KV cache 预留），**不是本集群实测**；阶段 1 S2 部署时以 vLLM 实际占用为准校准后更新本表并定案签署。
> **部署形态说明（2026-09-16 负责人决策后）**：候选 1（Qwen3.6）在现有 dtc-w1 以单卡副本 ×2 运行（time-slicing `gpu.shared` 每副本 1 份，互不依赖，最稳；需 vLLM >= 0.19.0）。候选 2（Qwen3.8）部署目标为**新增独立节点**（2×H200 或 4×H200），**强烈建议该节点采用整卡资源（`nvidia.com/gpu`，不启用 time-slicing）**以消除 TP rank 跨物理卡份额的不确定性；TP=4 为推荐形态，TP=2 显存成立但官方未验证，部署时实测。集群仓库已有 `dtc/vllm-*` 镜像，版本需按各模型卡要求核对（Qwen3.6: ≥0.19.0；Qwen3.8: ≥0.29.0）。
> **2 卡部署形态说明**：本集群 GPU 为 time-slicing 共享（`nvidia.com/gpu.shared`，30 份/卡）。单卡副本（候选 1/3）每个 Pod 请求 1 份、互不依赖，最稳；张量并行 TP=2（候选 2/或 GLM 系 MoE）要求同一 Pod 获得两份来自**不同物理卡**的份额，time-slicing 模式下分配策略不保证跨卡——已记入阶段 1 S2 待验证项。集群仓库已有 `dtc/vllm-*` 镜像（含 glm45），vLLM 实践基础已具备。
> **Qwen3.8-Flash-Next 查证结论（2026-09-16，vLLM recipes 官方页 + HF API 实测）**：176B 总参/6B 激活多模态 MoE（Qwen4 架构预览，262K 原生上下文，MIT 之外的 Qwen 自有 license「other」，需 vLLM 0.29.0+）——FP8 checkpoint **172.78 GiB**：单卡 H200（141 GiB）放不下；2×H200 理论勉强（TP=2 每卡 ~86 GiB 权重）但 H200 官方 FP8 配置为 **8 卡 TEP8**，2 卡未经验证，叠加 time-slicing 跨卡不确定性 → **当前 dtc-w1（3 卡）环境不适用**。负责人决策（2026-09-16）：以「新增独立节点 2×/4×H200」形态列入候选清单（见上表候选 2），TP 形态未验证项转为部署实测项；dtc-w1 上不部署本模型。
> 备选方向（如需替换）：GLM-4.5-Air（106B MoE/激活 12B，BF16 约 212GB，TP=2 偏紧且同样受 TP 跨卡约束；集群有 `dtc/vllm-glm45` 镜像实践基础）、GLM-4-32B 系（中文对话强）。License 与锁定版本以官方模型卡为准。
> **Qwen3.8-Flash-Next「新增 4×H200 节点」条件备选方案（2026-09-16 记录，决策人意向：负责人）**：显存上 TP=4 可行——172.78 GiB / 4 ≈ **43.2 GiB 权重/卡**，每卡剩余约 97 GiB 供 KV cache（262K 上下文可用）。**当前不可行的硬约束：dtc-w1/dtc-w2 物理卡均为 3 张**（`nvidia.com/gpu.count=3` 实测），vLLM 张量并行不能跨节点。**方案形态（负责人意向确认）**：新购/接入一台 **≥4 卡 H200 的独立节点**（不在现节点扩卡），Qwen3.8-Flash-Next 以 TP=4 部署于该节点，与 dtc-w1（Qwen3.6 单卡副本）物理隔离、双模型并存——恰好构成阶段 1「跨模型连续性」实验的本地两端点。**触发前提**：① 新节点到位并加入集群（建议沿用 570.x 驱动 / CUDA 12.8 栈与 gpu-operator 约定）；② H200 TP=4 部署实测通过（recipes 官方 H200 配置为 8 卡 TEP8，TP4 未验证需自测；GB300 上 TP2 为最小验证）；③ TP rank 份额跨物理卡分配确认——**建议新节点采用整卡资源（`nvidia.com/gpu`，不启用 time-slicing）**，从根上消除共享份额跨卡不确定性；④ license「other」（Qwen 自有协议）过审。满足后升级为正式候选；未满足前回退路径为 Qwen3.6-35B-A3B-FP8 单卡副本（dtc-w1）。
> **GLM-5.3-Flash 查证结论（2026-09-16，vLLM recipes 官方页 + HF API 实测）**：320B 总参/18B 激活多模态 MoE，1M 上下文，MIT license——但原生 FP8 权重约 **306 GiB**（recipes 原文），超过 2×H200 的 282 GiB 总显存；NVFP4 变体（RedHatAI，专家 4-bit）要求 **NVIDIA Blackwell** 原生格式，Hopper H200 不支持；官方目标硬件均为 8 卡级（H100/B200/GB200/MI355X）。**结论：2×H200 不可部署本模型**；若需 GLM 系本地能力，现阶段走云端 Provider（智谱/硅基流动）或评估 GLM-4.5-Air。

> 注意：初评依据须写明来源（如官方模型卡、公开榜单），禁止写「据说/应该不错」。**禁止由 AI 凭印象填写本表。**

### 3. 云端 Provider（Provider A）

#### 3.0 新环境实测（2026-09-16 迁移后）

| 字段 | 实测值 |
|---|---|
| 主选择 | 硅基流动 SiliconFlow（`https://api.siliconflow.cn/v1/`，OpenAI 兼容协议） |
| 备选择 | 智谱 BigModel（`https://open.bigmodel.cn/api/coding/paas/v4`） |
| API key 是否已配置（只写 是/否，**不写 key 本身**） | 是——K8s Secret `lifeos-provider-a-siliconflow` / `lifeos-provider-a-zhipu`（key 值只存在于集群 Secret，不入仓库/文档。**注意**：两个 key 曾在配置沟通中明文暴露，已提示负责人在各自控制台轮换，轮换后须同步更新上述 Secret） |
| 候选模型（锁版本目标） | 待阶段 1 定标（硅基流动托管 Qwen/GLM 系列，智谱为 GLM 系列；以 §2 本地模型候选 + Gate 评测结果联动锁定） |
| 计费告警是否已配置（阈值=） | 待配置（遗留：两家控制台分别设置阈值后回填） |
| 合规初评（境内可合规使用？依据） | 两家均为境内备案服务，符合规格书 §9.4「优先境内可合规使用」方向；正式合规评审在阶段 3 |
| 探测方式 | envcheck 以 K8s Secret **存在性**探测（`lifeos-provider*` 前缀，只报名字不报值，HANDOVER §5） |

> 旧机记录（下表）保留为历史：当时未检出任何 provider key 环境变量。


| 字段 | 实测值 |
|---|---|
| 服务商与候选模型（锁版本目标） | （待填） |
| API key 是否已配置（只写 是/否，**不写 key 本身**） | 否（envcheck 2026-09-15：未检出任何已配置的 provider key 环境变量） |
| 计费告警是否已配置（阈值=） | （待填） |
| 合规初评（境内可合规使用？依据） | 规格书 §9.4：优先境内可合规使用的服务 |

### 4. 基础工具

| 字段 | 实测值 | 检查命令 |
|---|---|---|
| Docker 版本 | 29.1.3（**位于 WSL2 Ubuntu 22.04 内**；Windows 主机 PATH 无 docker 命令） | `wsl docker --version`（2026-09-15 实测） |
| Docker Compose 版本 | （待填：`wsl docker compose version`） | |
| PostgreSQL 16 + pgvector 容器健康 | 健康（`lifeos-postgres`，pgvector/pgvector:pg16；pgvector 扩展已创建；迁移 0001 已应用，16 表齐备） | `docker compose ps`；`lifeos.cli db wait`；gate0_report 2026-09-15 |
| Python 版本 | 3.12.7（Windows venv，`.venv`） | envcheck 2026-09-15 |

## 后果

- Postgres/基础工具/GPU 探测合格 → 阶段 0 工程验证已实际跑通（见 gate0_report.json，除 gold set 材料外全部 PASS）；
- **云 Provider key 未配置**：阶段 0 不依赖任何 LLM，不阻塞；阶段 1 前必须配齐并配置计费告警；
- GPU 8 GB 偏小：不阻塞阶段 0；阶段 1 S2 本地推理部署前须完成候选清单筛选，不达标走路线图 §8 降级路径（Provider B 降级为另一云端固定版本模型，记录偏差）。

---

## 追记（2026-09-16）：部署环境迁移至 K8s 集群（决策：[ADR-0004](ADR-0004_部署环境迁移至K8s集群.md)，决策人 Jiang Haipeng）

决策层认定笔记本 GPU（RTX 4060 8GB）构成阶段 1 本地推理的瓶颈，将 Gate 0 环境与阶段 1 推理目标迁移至 K8s 管理的 H200 集群：

| 项 | 决策值 | 实测状态 |
|---|---|---|
| 命名空间 | `lifeos-dev` | 待创建/确认 |
| `dtc-w1` | 推理 GPU 节点，**3× H200**（阶段 1 Provider B：vLLM/llama.cpp） | 待实测：型号确认/驱动/CUDA/`nvidia-smi` 输出/devicePlugin 容量 |
| `aisi-w7` | 数据库节点（PostgreSQL 16 + pgvector Pod） | 待实测：规格/存储类/网络策略 |
| docker-compose | 降级为本地开发备选，不再作为 Gate 0 验收路径 | 历史记录保留（本 ADR 上文） |

**新环境实测回填（2026-09-16，执行者：接手 AI 协作；全部为 kubectl/API 实测，命令与输出存档见 [reports/migration_20260916_k8s.md](../reports/migration_20260916_k8s.md)）**：

- [x] K8s 集群/节点版本：server 与全部节点 **v1.28.15**（`kubectl get nodes`，10 节点 Ready；containerd 1.6.38）
- [x] `aisi-w7`：384 CPU / 2377564432Ki（约 2.2TiB）内存 / 3689506824Ki（约 3.4TiB）磁盘；StorageClass **huawei-sc**（csi.huawei.com，RWX，Immediate）；postgres Pod `lifeos-postgres-0` 1/1 Running（readinessProbe pg_isready）；资源 requests 2C/4Gi、limits 4C/16Gi；节点带 taint `mpc-cpt-role=infra:NoSchedule`（postgres 清单加 toleration 应对，节点未改）；PGDATA 指向子目录 `/var/lib/postgresql/data/pgdata`（规避 huawei-sc 卷根只读 `.snapshot` 对入口脚本 chown 的破坏）
- [x] pgvector 扩展在新库可用（`SELECT extname FROM pg_extension` → `vector`）；alembic 0001 迁移在新库执行成功（16 表 = 15 实体 + alembic_version；`lifeos_app` 角色建立，raw/interpreted/domain 三表 UPDATE/DELETE 均已回收）
- [x] `dtc-w1`：**3× NVIDIA H200 NVL**（`nvidia.com/gpu.count=3`，gpu-feature-discovery 节点标签实测），单卡显存 **143771 MiB**（`nvidia.com/gpu.memory`）；Pod 内 `nvidia-smi` 实测 Driver **570.148.08** / CUDA **12.8** / compute capability 9.0（hopper）；共享方案 **time-slicing 30 份/卡**（`nvidia.com/gpu.replicas=30`、`gpu.sharing-strategy=time-slicing`），资源名 `nvidia.com/gpu.shared`，节点 capacity=90（3×30 ✓）；单 Pod 内 nvidia-smi 可见 1 个 H200 实例（共享方案按分配暴露，属预期）；整机 Supermicro AS--5126GS-TNRT
- [x] 云 Provider（Provider A）：**API key 未配置**（`kubectl get secrets -n lifeos-dev` 无 `lifeos-provider*` 前缀 Secret；envcheck 只报 Secret 名不报值）——阶段 1 前须配齐并配置计费告警（遗留）
- [ ] 本地模型候选清单：候选 1 = Qwen3.6-35B-A3B-FP8（现有 dtc-w1，单卡副本 ×2）、候选 2 = Qwen3.8-Flash-Next-FP8（新增独立节点，推荐 4×H200 TP=4 / 可选 2×H200 TP=2）——Qwen2.5 系按负责人决策移出（2026-09-16）。**定案签署待负责人确认**；候选 2 的 TP 形态为部署实测项。显存档位分析（依据=上方实测值 + 模型卡通用估算式「BF16 权重 ≈ 2×参数量 GB + KV cache」）：H200 NVL 单卡 141GB（time-slicing 共享下全卡显存可见、算力按时间片轮转）→ 单卡可承载 ≤32B 级 BF16、≤72B 级 INT4/INT8 量化；72B 级 BF16（约 145GB）需 2 卡张量并行或量化。候选方向示例：Qwen2.5-32B/72B-Instruct、GLM-4-32B 系（**锁定版本待查官方模型卡**）
- [x] 重跑 `gate0_check --with-db` → 新环境 gate0_report **verdict=PASS**（2026-09-16T03:15Z；7 项工程检查 + 2 个 gold set 全 pass；旧报告已归档 `gate0_report.20260915.local.json`）。**双人签署（架构负责人 + 非编写成员）仍为遗留人工项**；独立保留集圈定（≥10 事实 + ≥6 场景）未做（遗留）

> 实测补充：数据库密码于 2026-09-16 迁移中生成并轮换一次（K8s Secret `lifeos-postgres`，值不入仓库/文档）；gold set 注册行（`gold_set_registry` 表）只存在于旧机库，新库该表为空——材料与注册 manifest 完好（items hash 与 [reports/goldset_*.manifest.json](../reports/) 逐字一致），是否在新库补注册行由决策层定。

> 2026-09-15 的旧机记录（上文 §1–§4）保留为历史，不再作为 Gate 0 引用依据；新报告落 `phases/phase-0/reports/`（旧报告归档改名）。
