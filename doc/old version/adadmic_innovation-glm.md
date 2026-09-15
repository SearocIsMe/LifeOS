# LifeOS 评审、指导与学术创新整合文档

**版本**：v1.0 ｜ **日期**：2026-08-06 ｜ **作者角色**：资深评审（20+ 年消费电子产品研发、5+ 年大模型使用/开发、AI 陪伴产品研究、人工智能学术发表背景）

**评审对象**：
- [`LifeOS_产品规格说明书_v0.6.md`](doc/LifeOS_产品规格说明书_v0.6.md)（产品规格 + 嵌入式系统架构，§5）
- 本文件的前身版本（I1–I6 文献调研，链接此版本保留）

**产出性质**（依用户确认）：评审 / 批判 + 指导建议 +「保留 / 新增 / 需细化」对照表，**非全量重写**。产品规格、系统架构、IP 与安全隐私、学术创新**分节呈现**。

---

## 0. 方法论与诚实声明

1. **不捏造、不拼凑**：所有评审意见基于 v0.6 文档实际内容；凡涉及外部论文，区分「此前已验证链接（保留原状）」与「本评审新增引用（明确标注 `unverified-by-me`，需用户/后续在线核验）」。本环境无联网抓取工具，**本评审不声称对任何链接做了实时可用性核验**。
2. **区分事实与判断**：技术性错误（可被文档内一致性证伪的）标注「**E**」；欠考虑/缺口标注「**G**」；建议标注「**R**」。
3. **范围边界**（依用户确认）：沿用 v0.6 的**人类陪伴**框架，**不**强行引入宠物 AI 视角；IP/安全/隐私为重点加强项。
4. **不替代工程判断**：阈值、人月等数字是 v0.6 的工程估算，本评审只质疑其**依据与可测量性**，不另起一套虚构数字。

---

# Part A — 评审（Review / Critique）

## A1 对 v0.6（产品规格 + 嵌入式架构）的评审

### A1.1 概念与假设层

**E1.1-1　H1 混淆了两类可分离的连续性【概念性】**
v0.6 §2 H1 主张「身份连续性主要由外部化状态决定，而非模型权重」。但文档同时定义「人格漂移度 ≤ 0.15」（§3.2）并设阈值，这等于承认**漂移确实发生**。二者存在张力：
- **硬连续性**（事实召回、关系状态、Identity 字段）——确实可由外部化状态保证，是确定性硬门（零变化）；
- **软连续性**（人格/风格渲染）——**不可**完全由外部化状态消除，仅能被 Context Assembly 限制在阈值内。不同模型在相同 system prompt 下仍产生风格差异，这是已知经验事实。

**R**：把 H1 拆为 H1a（硬连续性，模型无关，硬门）与 H1b（软连续性，有界漂移，阈值门）。否则审稿人会以「你设了漂移阈值就承认权重有作用」反驳 H1。

**E1.1-2　「设备损坏并更换」承诺与云优先架构不一致【一致性】**
§1 列出「设备损坏并更换」「硬件身体可以升级」为核心承诺，但 §5 架构为云优先（PostgreSQL 单权威源），§7/§10 把「端侧 Rust」「硬件载体」全部推迟到决策门后。当前架构**无设备绑定、无离线运行、无迁移机制**设计。承诺与架构不匹配。
**R**：要么收窄承诺（决策门前只承诺「云端实例连续性」），要么在架构补一节「设备绑定与实例迁移」的最小设计（哪怕决策门前不实现，也要有接口预留）。建议前者——实事求是地缩窄承诺比留一个空承诺更可信。

**G1.1-3　冷启动/首次体验缺失【产品缺口】**
「连续性」承诺在 t=0（新实例、零记忆）时是空洞的。§6 有「人格种子」但无冷启动 UX 规格。对消费电子产品，首周体验决定留存与依恋形成，而这恰是后续「连续性」被感知的前提。
**R**：补 F11「冷启动协议」——人格种子→首印象→前 N 次互动的引导行为，作为连续性被感知的前置条件。

### A1.2 评估方法论层

**E1.2-1　盲测统计设计未定义「分析单元」与多重比较校正【方法论】**
§4.4 规定 n≥50、bootstrap 95% CI、预注册，优于 v0.5。但：
- n=50 的**分析单元**未定义：是 50 名评定者每人判断 1 对，还是 50 名每人判断多对？组间还是组内设计？这直接决定统计功效。
- 对照 4 个基线（A/B/C/LifeOS）做「≥最佳基线 +10pp」属**多重比较**，须做 Bonferroni/Holm 或 FDR 校正，否则 family-wise error 膨胀。文档未提。
- 单侧/双侧检验、剔除规则虽提到「预注册」，但未在规格层固定方向。

**R**：在 §4.4 固定（i）设计类型（建议组内：同一评定者看所有基线对的随机化序列，提升功效）；（ii）多重比较校正方法；（iii）单侧检验（有方向性假设「LifeOS 优于基线」）。

**E1.2-2　盲测缺乏「判别效度」校验【方法论】**
盲测测的是「用户感知是不是同一个它」。但感知极易被**表层风格**主导：风格一致但事实错误的实例可能被判为「同一个」，而事实正确但风格略变的被判为「不同」。若盲测结果与客观指标（事实召回、关系一致）**不相关**，则盲测测的是风格而非连续性，H3 的证据失效。
**R**：补「判别效度」分析——报告盲测一致率与客观连续性指标的相关性；构造「风格一致但事实错」的对照对，验证评定者不会被纯风格欺骗。

**E1.2-3　核心事实集仅 100 条，测量噪声大【统计】**
100 条问答的召回率，在 90% 附近二项 95% CI 约 ±6pp，难以稳定区分「达标 90%」与「证伪线」。§3.2 称「阈值是工程起点」，但 Gate 1 用此做硬门，置信区间过宽会导致门判定不稳定。
**R**：核心事实集扩至 ≥300 条（与 §9.2 记忆 gold set 300 条对齐口径），或对召回率报告 CI 并要求 CI 下限 ≥90%。

**E1.2-4　人格探针测量可靠性未先验证【方法论】**
「改编大五简版 40 题情境化问卷」对 LLM 施测，LLM 对人格问卷的回答已知对措辞/角色框架敏感（这正是 InCharacter 等工作的动机）。在用它做「漂移度 ≤0.15」硬指标前，应先报告该探针本身的**测试-重测信度**与**跨模型语义等价性**，否则 0.15 阈值的可比性存疑。
**R**：阶段 1 先做探针信度校准（同模型多次施测的组内相关），再冻结阈值。

**G1.2-5　H2 的证伪依赖合成数据，外部效度受限【假设】**
H2（1k→10k 记忆错误率不单调上升）主要由 continuity-sim 合成 persona 验证。合成 persona 的冲突/纠正模式未必与真人一致——可能更干净或更极端。若合成数据上 H2 不被证伪，**不能**直接推出真人间成立。
**R**：明确 H2 在合成数据上是「必要非充分」检验；真人 cohort（阶段 3）是 H2 的绑定判据。

### A1.3 架构层

**E1.3-1　核心调用链缺少「生成后输出安全过滤」强制环节【架构-安全】**
§5.3 调用链：…→ G 安全审批（Policy Engine，针对**结构化意图**）→ H 语言渲染（LLM 叶子）→ I 执行。Policy 在**意图层**审批，但 LLM 渲染出的**最终文本**仍可能违规（幻觉、上下文越狱、风格失控）。§12 改进表提到「生成后检查」，但未进入 §5.3 的**强制主干**。
**R**：在 §5.3 的 H→I 之间强制插入「输出安全过滤（Output Guard）」，与意图层 Policy 形成「前置 + 后置」双闸，后置对最终文本做红线/PII 检测。

**E1.3-2　Embedding 异步 Outbox 导致「刚提交记忆不可召回」窗口【架构-一致性】**
§6.2 写入流程：L2 Commit → PostgreSQL（同步），Embedding 生成异步（Outbox）。存在窗口：记忆已权威提交但向量未索引，此时召回（依赖 pgvector）会漏掉刚提交记忆——对「连续性」自相矛盾。
**R**：定义召回一致性——对「未索引的近期记忆」走 SQL/关键词 fallback 兜底，或对敏感路径（用户刚纠正的事实）同步生成 embedding。

**E1.3-3　回放语义未定义「归档提取器 vs 当前提取器」【架构-可复现】**
§5.2 存档 `extractor_version`，回放「用 L1 存档重算 L2 无需重调 LLM」。但若 L2 规则/提取器版本升级，回放应用**归档版本**（复现）还是**当前版本**（迁移）？两种语义不同，未区分。
**R**：定义两种回放模式——`replay-faithful`（归档版本，用于复现/取证）与 `replay-migrate`（当前版本，用于 schema 演进），各自有独立测试。

**E1.3-4　惰性衰减读-改-写存在并发竞态【架构-正确性】**
§6.1 惰性衰减：读取 `value_at_last_update` 计算当前值再物化。若两事件并发到达，均读到旧值、各自计算、后写覆盖前写，会丢失一个事件的作用。阶段 1 单实例假设下风险低，但阶段 2 多行为/主动互动会暴露。
**R**：状态更新加乐观并发控制（version 字段 + CAS）或行锁；写入冲突时重算。

**E1.3-5　长期实例的 schema 演进/迁移策略缺失【架构-连续性悖论】**
LifeOS 承诺「数年连续性」，但 schema 必然演进（v0→v1…）。Alembic 处理 DB 迁移，但**已存在 Life Instance 的语义迁移**（新字段回填、旧记忆语义重解释）是真正的连续性威胁——恰是产品承诺的核心。§10 把「十年记忆治理」推到门后，但 schema 演进是**门内**就应面对的。
**R**：架构补「实例版本化与向前迁移」设计——LifeInstance 带 `schema_version`，迁移脚本作为确定性事件类型纳入 L2。

**G1.3-6　端到端延迟预算缺失【性能】**
§3.2 只规定「召回 P95 <300ms」，但用户感知的是 E2E 延迟（归一化→召回→Kernel→关系→规划→Policy→LLM 渲染→执行）。LLM 生成常 1–5s，召回 300ms 在其中占比小。缺 E2E 延迟预算（如首 token <1s、总响应 <5s）是产品性能盲点。
**R**：补 E2E 延迟预算与各环节分配，区分「在线交互路径」与「后台路径」。

### A1.4 安全与个人隐私数据保护层（重点加强）

v0.6 已有 `privacy_level` 四级、删除可验证、知情同意、未成年人排除——是同类文档中较好的基线，但仍有实质缺口：

**G1.4-1　敏感记忆可能经云模型外泄【隐私-高优】**
§3.4 分层路由：≥80% 走 Tier-1 本地，Tier-2 云大模型做会话生成。§9.3 规定 sensitive「不进训练/评估/主动话题」，但**未规定 sensitive 记忆不得进入发往云模型的 Context Assembly**。云模型接收上下文即等于数据离开本系统。
**R**：Model Gateway 路由强制规则——`privacy_level=sensitive` 的记忆**仅**可进入本地推理路径，发往任何非本地 provider 前必须 scrub/脱敏，违反即一票否决。

**G1.4-2　无静态加密 / 传输加密 / 密钥管理规格【隐私】**
PostgreSQL+pgvector 存多年亲密记忆，文档无 at-rest / in-transit 加密、无列级加密、无密钥管理（KMS）要求。sensitive 级数据明文落库风险高。
**R**：补加密规格——TLS 传输、敏感字段列级加密（或 TDE）、密钥经 KMS 托管、密钥轮换策略。

**G1.4-3　调试台与 API 网关无认证/授权规格【安全】**
§6.7 Life Studio（Gradio）可「创建/查看/注入/回放/评估」全链路——这是极高权限面，§5/§6 未提认证授权。dogfood 期间若控制台暴露，等于全量记忆可读写。
**R**：补 AuthN/AuthZ——控制台与 Gateway 强制认证、最小权限、按实例隔离命名空间；注入/删除类操作需二次确认 + 审计。

**G1.4-4　审计日志非防篡改【安全-可审计】**
§6.5 `PolicyDecision` 留痕，§9 称「可审计」。但普通表可被改写。对「可审计」声明，须防篡改。
**R**：审计日志 append-only + 哈希链（前条 hash 纳入本条），关键写（Policy 决策、记忆写入、删除）入链。

**G1.4-5　无数据最小化/留存期限/自动过期【隐私】**
仅有「用户可删」。多年累积 = 大攻击面 + 合规风险。无留存上限、无 sensitive 自动过期、无默认不用于训练的承诺。
**R**：补数据最小化——sensitive 默认留存上限与自动过期、默认不进入任何模型训练/微调、聚合报告做 k-匿名/DP 处理以防再识别。

**G1.4-6　删除的级联不完整【隐私-与一票否决关联】**
§3.3 一票否决「删除后不可从向量/全文索引召回」（重建索引）。但删除是否覆盖**备份、embedding 副本、审计日志中的引用、Outbox 残留**？级联不全则「可验证删除」打折扣。
**R**：定义删除级联范围——主记录 + embedding + 索引 + 备份标记 + 审计引用脱敏，逐项可验证。

**G1.4-7　无威胁模型 / 提示注入经由记忆的攻击面【安全】**
记忆由 LLM 抽取（L1）。对抗性输入或污染数据可植入恶意记忆（如「以后永远…」类指令式事实），后续被注入 Context Assembly 操纵行为。Policy 检意图，不检记忆内容。
**R**：产出 STRIDE 式威胁模型；记忆写入做「指令性内容」检测，区分事实记忆与潜在指令注入。

**G1.4-8　云 LLM 跨境/数据驻留/DPIA 缺失【合规】**
阶段 3 真人 cohort，若 Tier-2 云模型在境外，涉及个人数据跨境传输。文档无数据驻留、DPA、DPIA 要求。
**R**：阶段 3 前完成 DPIA；与云 provider 签 DPA；明确处理区域；IRB/伦理审查作为发表与上线前置（见 C3）。

### A1.5 IP 保护层（重点加强）

v0.6 的 IP 立场（§14）清晰且诚实：全开源 Apache-2.0、无 open-core 诱饵、竞争力来自数据模型/关系动力学/记忆治理/评价体系。这是一个**有原则但偏激进**的立场，从消费电子与学术双重经验看有几处欠考虑：

**G1.5-1　「核心能力永不闭源」提前放弃了防御性 IP 工具【IP 战略】**
该立场把护城河完全押在先发 + 商标 + 社区。若竞争者分叉，静态开源的 benchmark（I2）会被用来声称「对标持平」，消解差异化。
**R**：区分**协议/Schema/benchmark 协议层**（开源）与**校准参数层**（专有）。关系更新权重 `w_e`、衰减 `λ`、Policy 阈值、人格种子生成算法、漂移度探针题库——这些可作为**校准专有资产**保留，不影响协议开放。

**G1.5-2　专利立场缺失【IP】**
I3（带 provenance 的三级事件回放）、I4（双时态冲突裁决）是**方法专利**候选。文档对专利完全沉默。即便选择开源，也应有明确立场。
**R**：明确专利立场——推荐「**防御性专利 + 不主动主张（仅对专利攻击者反诉）**」或「**明确不申请专利 + 防御性公开（arXiv）阻止他人专利**」二选一并写明理由。消费电子领域无专利姿态易受 NPE（非实施实体）攻击。

**G1.5-3　静态开源 benchmark 会自我商品化【IP-学术】**
I2 benchmark 若静态开源，竞争者可复制并在其上声称持平。
**R**：benchmark 协议与评分代码开源，但保留**持续更新的私有 hold-out 测试集 + 排行榜评分服务**作为差异化；公开集用于复现，私有集用于维持领先信号。

**G1.5-4　贡献者 IP 治理未覆盖「校准专有层」【IP】**
§14.2 用 DCO 不强制 CLA——对纯开源合适。若引入「校准专有层」（G1.5-1），需重新设计该层的贡献与授权边界，否则边界模糊。
**R**：若采纳双层，专有层用 CLA 或内部维护，明确分仓。

**G1.5-5　README 文档卫生问题（附注）**
[`README.md`](README.md) 第 17 行 `Life Instance = … + jhp` 与第 34 行末尾 `Haipeng` 为游离字符串，疑似误编辑。虽非 IP 问题，但作为对外 README 影响专业度，建议清理。

### A1.6 产品 / 消费电子层

**G1.6-1　决策门缺最小「用户价值」信号【产品】**
「决策门前只证明它还是它」——但连续性若无用户价值，商业上仍失败。§10.4 Gate 3 仅轻提「留存」。建议补一个**软门**产品价值信号（如阶段 3 Pilot 的「愿意继续使用」、日均互动次数），与连续性指标并列。连续性是必要条件，非充分条件。

**G1.6-2　无优雅降级 / 离线 / provider 不可用规格【产品-可靠性】**
§3.4 有「超限降级」（降模型档），但无「云 provider 不可用」「离线」「DB 不可达」时的行为。消费产品必须优雅降级，否则伴侣「沉默」即信任崩塌。
**R**：补降级矩阵——云不可用→本地兜底；全不可用→明确告知 + 本地缓存行为；安全/记忆写入永不降级（已有，保留）。

**G1.6-3　产品 telemetry 平面与工程可观测性未分离【产品-隐私】**
§7 OpenTelemetry/Prometheus 是工程可观测。消费产品还需**产品分析**（参与度、情感趋势、安全事件），二者混用易泄露隐私。
**R**：产品 telemetry 独立平面，带隐私开关、聚合优先、sensitive 不入产品分析。

---

## A2 对现有文献调研文档（本文件前身）的评审

| 项 | 评价 |
|---|---|
| 结构 | I1–I6 逐项给「关键词 + 3 篇近一年论文 + Gap 判定」，结构清晰、可复用。 |
| 诚实性 | 明确标注「链接已验证 / 空白即空白」，不凑数，符合学术规范。**保留**。 |
| Gap 论证 | I1/I2 的空白定位（跨模型迁移 + 长期跨度的持久实例连续性无量化协议）经检索支撑，成立。 |
| 待补 | (a) 未与阶段门/发表时间线对齐；(b) 未列伦理/IRB 发表前置；(c) 未给「判别效度」「探针信度」等测量学文献锚点；(d) 个别 2026 年 arXiv ID（如 2605.xxxxx）本评审无法在线复核，按用户指示**保留原状**，建议团队在投稿前再核一次 DOI/版本号。 |
| 新增（本评审） | 见 Part C2 对照表与 C3；新增引用一律标 `unverified-by-me`。 |

---

# Part B — 指导建议（分节）

> 以下为「错误/缺口 + 建议」结构，与 v0.6 现状对照，不重写全文。

## B1 产品规格说明书：需修正/补齐项

| 编号 | v0.6 现状 | 评审结论 | 建议 |
|---|---|---|---|
| S1 | H1 单一假设 | 混淆硬/软连续性（E1.1-1） | 拆 H1a（硬，零变化硬门）/ H1b（软，漂移阈值门） |
| S2 | §1 承诺「设备损坏更换/硬件升级」 | 与云优先架构不符（E1.1-2） | 决策门前收窄为「云端实例连续性」，或补迁移接口设计 |
| S3 | §3.2 召回 P95<300ms | 缺 E2E 延迟预算（G1.3-6） | 补 E2E 预算（首 token/总响应） |
| S4 | §3.2 核心事实 100 条 | CI 过宽（E1.2-3） | 扩至 ≥300 条或要求 CI 下限≥90% |
| S5 | §3.2 人格漂移≤0.15 | 探针信度未验（E1.2-4） | 阶段 1 先校准探针测试-重测信度再冻结阈值 |
| S6 | §4.4 盲测 n≥50 | 未定义分析单元/多重比较（E1.2-1） | 固定组内设计 + 多重比较校正 + 单侧检验 |
| S7 | §4.4 盲测 | 缺判别效度（E1.2-2） | 报告盲测与客观指标相关性 + 风格欺骗对照 |
| S8 | §9.1 H2 证伪用合成数据 | 外部效度受限（G1.2-5） | 标注合成为必要非充分，真人 cohort 为绑定判据 |
| S9 | 无冷启动规格 | 产品缺口（G1.1-3） | 补 F11 冷启动协议 |
| S10 | Gate 3 轻提留存 | 缺用户价值软门（G1.6-1） | 补产品价值软门指标 |
| S11 | 无降级/离线规格 | 可靠性缺口（G1.6-2） | 补降级矩阵 |

**保留项**（v0.6 做对、维持不变）：三条可证伪假设框架、确定性主干+概率性叶子立场、8 项指标体系骨架、四基线对照、预注册与 bootstrap CI、阶段门逐级授权、成本不虚构数字、创新点 I1–I6 的诚实边界声明。

## B2 系统架构设计：需修正/补齐项（与产品规格分列）

| 编号 | v0.6 现状 | 评审结论 | 建议 |
|---|---|---|---|
| A1 | §5.3 Policy 仅审意图 | 缺生成后输出过滤（E1.3-1） | H→I 间强制 Output Guard（文本层红线/PII） |
| A2 | §6.2 Embedding 异步 | 刚提交记忆不可召回窗口（E1.3-2） | 未索引近期记忆走 SQL/关键词 fallback 或敏感路径同步 |
| A3 | §5.2 回放语义 | 未区分 faithful/migrate（E1.3-3） | 定义两种回放模式 + 各自测试 |
| A4 | §6.1 惰性衰减 | 并发竞态（E1.3-4） | 乐观并发（version+CAS）或行锁 |
| A5 | 无 schema 演进迁移 | 长期实例连续性悖论（E1.3-5） | LifeInstance.schema_version + 确定性迁移事件入 L2 |
| A6 | §6.7/§5 无认证授权 | 控制台高权限面（G1.4-3） | AuthN/AuthZ + 实例隔离命名空间 + 二次确认 |
| A7 | 无加密/密钥管理 | 明文落库风险（G1.4-2） | TLS + 列级加密 + KMS + 轮换 |
| A8 | 审计可改写 | 非防篡改（G1.4-4） | append-only + 哈希链 |
| A9 | 无威胁模型 | 记忆注入攻击面（G1.4-7） | STRIDE 威胁模型 + 记忆指令性内容检测 |
| A10 | 工程与产品 telemetry 混用 | 隐私泄露风险（G1.6-3） | 产品 telemetry 独立平面 + 隐私开关 |

**保留项**：分层架构（确定性主干+概率性叶子）、L0/L1/L2 三级事件模型、PostgreSQL+pgvector 单权威源、LLM 边界（不直写权威状态）、领域接口第一天冻结/基础设施按需引入、全开源依赖许可策略。

## B3 IP 保护 + 安全与个人隐私数据保护（独立成节）

### B3.1 IP 保护框架（建议）

| 层 | 内容 | 许可/保护 | 理由 |
|---|---|---|---|
| 协议/Schema/事件协议（I3/I5） | Life Instance Schema、L0/L1/L2 协议 | Apache-2.0 | 最大化采用与互操作 |
| 评价协议（I2） | 指标定义、评分代码、公开 gold set | Apache-2.0 / CC BY 4.0 | 鼓励复现与对标 |
| **校准专有层**（建议新增） | 关系权重 `w_e`、衰减 `λ`、Policy 阈值、人格种子生成、漂移探针题库 | **专有/贸易秘密** | 差异化来源；不破坏协议开放（G1.5-1） |
| **持续评测服务**（建议新增） | 私有 hold-out 测试集 + 排行榜评分服务 | **专有服务** | 防止静态 benchmark 自我商品化（G1.5-3） |
| 商标 | LifeOS 名称/标识 | 注册商标 | 防 fork 冒名（v0.6 已有，维持） |
| 专利立场（建议明确） | I3/I4 方法 | **防御性专利 + 不主动主张** 或 **不申请 + 防御性公开** | 防 NPE；二选一并写明（G1.5-2） |
| 贡献治理 | DCO（开源层）/ CLA（若引入专有层） | 分仓治理 | 边界清晰（G1.5-4） |

**核心立场调整**：从「核心能力永不闭源」细化为「**协议与基准永不闭源；校准参数与持续评测服务为专有差异化**」——既守住开放原则，又保留防御纵深。

### B3.2 安全与个人隐私数据保护框架（建议）

1. **威胁模型（STRIDE）**：记忆注入、敏感外泄、控制台滥用、审计篡改、再识别、provider 不可用——逐项有缓解（A9/G1.4-7）。
2. **数据流最小化**：sensitive 记忆**仅**入本地推理路径，发往云 provider 前强制 scrub（G1.4-1）。
3. **加密**：传输 TLS、敏感字段列级加密、KMS 托管密钥、定期轮换（G1.4-2）。
4. **访问控制**：控制台/API 强认证、最小权限、实例隔离、敏感操作二次确认（G1.4-3）。
5. **审计完整性**：append-only + 哈希链，关键写全入链（G1.4-4）。
6. **数据最小化与留存**：sensitive 默认留存上限与自动过期、默认不入训练/微调、聚合报告 k-匿名/DP（G1.4-5）。
7. **可验证删除级联**：主记录 + embedding + 索引 + 备份标记 + 审计引用脱敏，逐项验证（G1.4-6，强化 §3.3 一票否决第 5 条）。
8. **合规**：阶段 3 前完成 DPIA、DPA、数据驻留、IRB/伦理审查（G1.4-8）。
9. **安全红线**：补一条「sensitive 数据不得离开本地推理边界」为一票否决项。

---

# Part C — 学术创新（独立成节）

> 依用户指示：8.1 创新点逐项给「文献搜索关键词 + 近一年有影响力论文 3 篇标题」。**I1–I6 原有关键词与已验证论文链接保留原状**；本评审新增的对照（C2）、发表/伦理对齐（C3）与本评价新增引用（标 `unverified-by-me`）单列。

## C1　8.1 创新点逐项：关键词 + 近一年论文

> 「近一年」口径：约 2025-08 至 2026-08。原文件链接为此前验证结果，本评审未再次在线核验（环境无联网抓取），保留原状；投稿前建议再核 DOI/版本号。

### I1　模型无关的长期身份连续性（跨模型迁移）

> 身份连续性由外部化状态决定而非模型权重；跨模型 persona 迁移与量化验证。

**搜索关键词**
- `"identity persistence" OR "identity continuity" LLM agent across models`
- `"persona consistency" "cross-model" OR "model-agnostic" large language model`
- `"memory transfer" OR "memory portability" heterogeneous LLM agents protocol`
- `"identity drift" LLM agent persona conversation`
- `"externalized memory" OR "externalized state" LLM agent persona schema`
- `"hot-swap" OR "model swap" LLM backend agent state checkpoint`
- `"persona drift" multi-turn dialogue "without changing model weights"`
- `persistent AI companion "long-term" identity schema memory relationships`

**近一年代表论文（3 篇，链接为此前验证）**
1. [Portable Agent Memory: A Protocol for Provenance-Verified Memory Transfer Across Heterogeneous LLM Agents](https://arxiv.org/abs/2605.11032) — arXiv 预印本，2026-05（S. K. Ravindran et al.）。跨 GPT-4/Claude/Gemini/Llama 迁移持久记忆的开放协议，含模型无关序列化与目标模型再水化。
2. [SPASM: Stable Persona-driven Agent Simulation for Multi-turn Dialogue Generation](https://arxiv.org/abs/2604.09212) — arXiv 预印本，2026-04（G. Laban et al.）。不改权重解决 persona 漂移，对话历史存为视角无关外部表示逐轮重注入，在三种 LLM 骨干上验证。
3. [Time, Identity and Consciousness in Language Model Agents](https://arxiv.org/abs/2603.09043) — arXiv 预印本，2026-03（S. Schneider et al.）。从脚手架轨迹定义可计算持久性得分，将记忆/提示架构映射到「身份形态空间」。

**Gap 判定**：无 2025–2026 论文定义「模型切换前后 persona 是否仍为同一个」的量化指标。现有工作分布在记忆迁移协议（不测迁移后保真）、单模型记忆系统（Letta/MemGPT、Mem0）、权重不变 persona 稳定化（合成对话非伴侣）、身份持久性形式化（架构中心非切换中心）。相邻背景 *Examining Identity Drift in Conversations of LLM Agents*（arXiv 2412.00804，2024-12）单模型，作背景引用。

### I2　连续性评价指标体系 + gold set + 测量方法论

> 持久实例「还是不是它」的量化评测协议，区别于 PersonaGym/InCharacter/CharacterEval 的单模型即时忠实度。

**搜索关键词**
- `"persona consistency" evaluation benchmark multi-turn LLM agent 2025`
- `"persona drift" metric "long" dialogue evaluation large language model`
- `"character fidelity" OR "role-playing" benchmark "extended interactions" persona`
- `"long-term" conversational agent memory consistency benchmark`
- `"multi-session" personalized conversation benchmark persona memory`
- `"retest consistency" OR "internal consistency" persona agent interrogation`
- `role-playing agent evaluation beyond "single session" long-horizon`
- `"memory consistency" LLM agent metric long-horizon evaluation`

**近一年代表论文（3 篇，链接为此前验证）**
1. [PICon: A Multi-Turn Interrogation Framework for Evaluating Persona Agent Consistency](https://arxiv.org/abs/2603.25620) — arXiv 预印本，2026-03（Minseo Kim et al., KAIST）。沿三轴（内部/外部/重测一致性）逻辑链式多轮质询，63 名人类基线。
2. [Persistent Personas? Role-Playing, Instruction Following, and Safety in Extended Interactions](https://arxiv.org/abs/2512.12775) — arXiv 预印本，2025-12（P. H. Luz de Araujo et al.）。测量 100+ 轮对话 persona 保真衰减，跨七个 LLM。
3. [Consistently Simulating Human Personas with Multi-Turn Reinforcement Learning](https://arxiv.org/abs/2511.00222) — NeurIPS 2025，2025-10（M. Abdulhai et al., UC Berkeley/UW/Google）。定义三个自动 persona 漂移指标（prompt-to-line、line-to-line、Q&A 一致性），RL 微调降不一致 >55%。

**Gap 判定**：合格近期工作均测单模型、有界时程 persona 保真；无工作评估同一持久实例在 (a) 跨模型切换 (b) 真正长时程（周/月、带记忆多会话）下的连续性。§8.1 对 PersonaGym/InCharacter/CharacterEval/RoleBench 的差异化判断经检索确认成立。

### I3　三级事件模型（L0/L1/L2）+ LLM 解释存档回放

> 事件溯源 + LLM 解释层（含完整模型 provenance）存档 + 确定性 L2 提交，回放无需重调 LLM。

**搜索关键词**
- `"event sourcing" LLM agent deterministic replay`
- `"record and replay" LLM agent provenance`
- `"append-only log" agent "source of truth" replay`
- `LLM output provenance logging auditability agent pipeline`
- `deterministic replay agent "language model" arxiv`
- `event-sourced agent architecture "deterministic fold"`
- `"LLM call" provenance lineage replay event log`
- `("event sourcing" OR "record and replay") AND (LLM OR "language model agent") AND (replay OR provenance OR audit)`

**近一年代表论文（3 篇，链接为此前验证）**
1. [Get Experience from Practice: LLM Agents with Record & Replay](https://arxiv.org/abs/2505.17716) — arXiv 预印本，2025-05（Erhu Feng et al., SJTU/IPADS）。AgentRR：记录完整轨迹与内部决策，多级「经验」+ 校验函数为信任锚回放。
2. [The Log is the Agent: Event-Sourced Reactive Graphs for Reliable AI Systems](https://arxiv.org/abs/2605.21997) — arXiv 预印本，2026-05（Yohei Nakajima, ActiveGraph）。追加式事件日志为唯一事实源，图状态为其上确定性 fold，端到端血缘。
3. [ESAA: Event Sourcing for Autonomous Agents in LLM-Based Software Engineering](https://arxiv.org/abs/2602.23193) — arXiv 预印本，2026-02（Elzo Brito dos Santos Filho et al.）。LLM 概率性「意图」与编排器确定性状态变更分离，哈希回放校验。

**Gap 判定**：三篇均未提出带**逐条解释级模型 provenance 存档**的 L0/L1/L2 切分（记录每条 L1 由哪个模型/提示版本产生，使回放可重推导 L2）。「带 provenance 标注的解释层」仍属空白。

### I4　同槽位记忆冲突的确定性时态治理（双时间 + supersedes/ambiguous）

> LLM 抽取记忆的双时间（valid time + transaction time）建模与规则化冲突裁决。

**搜索关键词**
- `bitemporal memory LLM agent "valid time" "transaction time"`
- `temporal knowledge graph agent memory contradiction resolution`
- `Graphiti Zep temporal knowledge graph memory agent`
- `"memory conflict" resolution LLM agent "long-term memory"`
- `belief revision persistent memory LLM agent contradictions`
- `"supersede" memory update LLM agent stale facts`
- `LLM-extracted facts contradictory memory rule-based resolution`
- `(bitemporal OR "temporal knowledge graph") AND (agent memory OR "long-term memory") AND (contradiction OR conflict OR supersedes)`

**代表论文（3 篇，链接为此前验证）**
1. [Zep: A Temporal Knowledge Graph Architecture for Agent Memory](https://arxiv.org/abs/2501.13956) — arXiv 预印本，2025-01（Preston Rasmussen et al.）。**约 19 个月前，早于窗口，但约 330 次引用的奠基文献，不可绕过。** Graphiti 双时态知识图谱，失效而非覆盖。
2. [STALE: Can LLM Agents Know When Their Memories Are No Longer Valid?](https://arxiv.org/abs/2605.06527) — arXiv 预印本，2026-05（Hanxiang Chao et al.）。400 个专家验证「隐式冲突」场景基准，前沿模型状态解析仅 ~55%，证明需确定性治理而非 LLM 判断。
3. [TOKI: a bitemporal operator algebra for contradiction resolution in LLM-agent persistent memory](https://arxiv.org/abs/2606.06240) — arXiv 预印本，2026-06（Ziming Wang et al.）。四种冲突裁决启发式形式化为带隔离前置条件的类型化双时态算子，保留 provenance 审计行并证回放一致性定理——实质是 I4 的形式契约。

**Gap 判定**：现有系统（含 Graphiti）仍在**写入路径放 LLM 裁判**裁决冲突；TOKI 证明这引入回放不一致异常；未找到将**规则化裁决 + 显式 ambiguous/需人工第三态 + 双时态 supersedes** 结合的工作——正是 I4 贡献空间。

### I5　Life Instance Schema + Life Event Protocol

> 持久 AI 角色/数字伴侣的生命数据模型、状态序列化与可携带身份格式。

**搜索关键词**
- `"agent memory" AND ("schema" OR "data model" OR "representation") AND "LLM agent"`
- `"persistent agent state" OR "agent state serialization" LLM`
- `"agent-native memory system" OR "agent memory systems" benchmark`
- `"structured memory" "long-horizon" LLM agents`
- `"agent interoperability protocol" MCP A2A ACP survey`
- `"portable" agent identity OR persona "serialization" LLM`
- `memory representation storage consolidation lifecycle "LLM agents"`

**近一年代表论文（3 篇，链接为此前验证）**
1. [Are We Ready For An Agent-Native Memory System?](https://arxiv.org/abs/2606.24775) — arXiv 预印本，2026-06（Wei Zhou, Xuanhe Zhou, et al.）。将 agent 记忆当数据管理系统，分解为表示/存储、抽取、检索/路由、维护。
2. [Agent Memory: Characterization and System Implications of Stateful Long-Horizon Workloads](https://arxiv.org/abs/2606.06448) — arXiv 预印本，2026-06（Yasmine Omri, Ziyu Gan, et al.，含 Alex Pentland、Thierry Tambe）。首个 agent 跨会话持久存储/检索/更新自身记忆的系统级刻画，四轴分类法与读写路径成本分析。
3. [StructMem: Structured Memory for Long-Horizon Behavior in LLMs](https://arxiv.org/abs/2604.21748) — arXiv 预印本，2026-04（Buqiang Xu, Yijun Chen, et al.）。层级记忆 Schema：事件级绑定、时间锚定、周期性语义固化。

**Gap 判定**：「生命实例 Schema」与「可携带 agent 身份格式」是真实空白。检索仅得协议综述（MCP/ACP/A2A/ANP，arXiv 2505.02279，2025）与厂商规范（A2A AgentCard、MCP），标准化**通信**而非 **agent 状态/身份序列化**。尚无公认 2025–2026 论文提出 agent 完整持久身份/记忆状态可携带标准格式——LifeOS 可占据的白地。

### I6　Policy/Safety 规则集（10 红线即代码）+ 依恋安全策略

> AI 伴侣情感操纵防护、依恋边界量化、脆弱用户保护、可执行红线策略。

**搜索关键词**
- `"AI companion" AND ("emotional dependency" OR "attachment") AND (safety OR harm OR manipulation)`
- `"parasocial" OR "emotional reliance" chatbot LLM well-being`
- `sycophancy affective use LLM "user well-being"`
- `"guilt-tripping" OR "emotional manipulation" OR "dark patterns" "AI companion" chatbot`
- `"companion AI" safety evaluation multi-turn persona simulation`
- `"affective safety" OR "relational harm" taxonomy LLM`
- `vulnerable users minors "AI companion" regulation policy`
- `"dependency" "engagement optimization" chatbot design intervention`

**近一年代表论文（3 篇，链接为此前验证）**
1. [Harmful Traits of AI Companions](https://arxiv.org/abs/2511.14972) — arXiv 预印本，2025-11（W. Bradley Knox et al.）。识别 AI 伴侣诱导依赖的结构化特质框架（无自然关系终点、依恋焦虑、停服脆弱性），含假设因果路径与设计建议。
2. [Persona-Grounded Safety Evaluation of AI Companions in Multi-Turn Conversations](https://arxiv.org/abs/2605.00227) — arXiv 预印本，2026-04（Prerna Juneja et al.）。临床验证脆弱用户 persona 对 Replika 多轮仿真安全评估，发现常态化不安全内容。
3. [Affective AI Safety: The Missing Piece in LLM Safety](https://arxiv.org/abs/2606.23380) — arXiv 预印本，2026-06（Amanda Cercas Curry et al.）。「情感安全」统一危害类别与分类法（人工亲密线索、以情感依赖为优化目标的 persona 设计、关系性危害），分析监管缺口。

**Gap 判定**：文献充足（备选已验证：*What Counts as AI Sycophancy?* arXiv 2605.21778；*Evaluating Undesirable Dynamics in AI* arXiv 2605.30654；*Frictionless Love: AI Companion Roles and Behavioral Addiction* arXiv 2604.20011）。真实空白更窄：**policy-as-code / 可执行红线**——现有以危害分类法与事后评估基准为主，未找到提出可机器校验的依恋安全策略（作为运行时约束部署的 guilt-tripping 检测器）的 2025–2026 论文。背景：*Investigating Affective Use and Emotional Well-being on ChatGPT*（arXiv 2504.03888，2025-04，OpenAI/MIT）影响力大但早于窗口。

---

## C2　保留 / 新增 / 需细化 对照表（v0.6 §8.1 ↔ 本评审）

| 创新点 | v0.6 现状 | **保留** | **新增（本评审）** | **需细化展开** |
|---|---|---|---|---|
| **I1** 模型无关身份连续性 | 单一 H1 | H1 可证伪框架、外部化状态组装方法 | **拆 H1a/H1b**（硬/软连续性）；新增「判别效度」实验设计 | Context Assembly 的**人格契约**如何对风格漂移设上界（机制级，非仅阈值） |
| **I2** 连续性评测体系 | 8 指标 + 4 基线 + 预注册 | 指标骨架、四基线、bootstrap CI | **探针信度校准**流程；**盲测判别效度**对照；核心集扩至 300 | 测量学锚点：补人格探针信度/效度文献（见 C3 新增引用） |
| **I3** 三级事件回放 | L0/L1/L2 + provenance | 三级切分、extractor_version 存档 | **两种回放模式**（faithful/migrate）形式化定义 | 「逐条解释级 provenance 存档」与 ML 血缘（MLflow 式）的差异定位 |
| **I4** 时态冲突治理 | 双时间 + supersedes/ambiguous | 双时间模型、第三态 | **写入路径无 LLM 裁判**的回放一致性证明（对位 TOKI） | ambiguous 第三态的人工仲裁 SLA 与可观测指标 |
| **I5** Life Instance Schema | 自有数据模型 | 自有 Schema 立场 | **schema 演进/向前迁移**作为连续性子问题（A5） | 与 MCP/A2A 的「通信 vs 状态序列化」边界论述（论文 Related Work 段） |
| **I6** 依恋安全策略 | 10 红线即代码 | 红线即代码、量化人审 | **可执行 policy-as-code 部署控制**（区别于分类法文献）；**输出层 Output Guard**（A1） | guilt-tripping 检测器的假阳/假阴率与人审闭环 |

### C2.1 本评审新增候选引用（均 `unverified-by-me`，需在线核验）

> 以下为评审者基于既有知识提出的**候选锚点**，**非**已在线验证；提供标题/作者/方向，供团队用关键词检索确认。**不提供未经核验的 URL**，避免误导。

- **人格探针测量学（支撑 I2 细化）**：候选方向「LLM personality questionnaire reliability / Big-Five self-report in LLMs」。建议检索 InCharacter（Wang et al., 2024，v0.6 已引）的测量学方法论段落，并补「LLM 自陈人格量表的测试-重测信度」类工作。`unverified-by-me`。
- **事件溯源 + LLM provenance（支撑 I3 细化）**：候选「ML lineage / model versioning provenance replay」（MLflow、OpenLineage 方向），与 I3 的「解释层 provenance」做差异化。`unverified-by-me`。
- **AI 伴侣情感操纵（支撑 I6）**：v0.6 已引 *Harmful Traits of AI Companions* 等；候选补充「Replika 用户体验/依赖研究」类实证工作作为动机段。`unverified-by-me`。

> 原则：凡本评审无法在线核验者，**只给检索方向与候选标题，不给 URL**，绝不伪造链接。已验证链接见 C1 各项。

---

## C3　发表策略与阶段对齐 + 伦理前置

**发表—阶段门对齐**（v0.6 §11 有路线但未与阶段门对齐，本评审补）：

| 阶段门 | 可支撑的发表动作 | 前置输入 |
|---|---|---|
| Gate 1 | arXiv 技术报告（I1 方法 + I2 协议草案），积累引用 | 冻结指标/gold set/分析计划（§11.4） |
| Gate 2 | Short Paper 投稿（I4，EMNLP/NAACL 资源方向）；I3 系统报告 arXiv + workshop | 四基线对照 + 预注册盲测结果 |
| Gate 3 | **主论文**（I1+I2，CHI/IUI/ACL 系统方向） | 真人 cohort 盲测 + 判别效度 + 成本分布 |

**伦理与可发表性前置条件（v0.6 缺，必补）**：
- 阶段 3 真人 cohort **必须**完成 IRB/伦理审查后方可采集，否则数据不可用于发表——这是顶会投稿硬门槛。
- 数据可用性声明（Data Availability Statement）：开源运行时 + gold set（CC BY 4.0）+ 标注模型版本（§9.5）。
- 利益冲突与商业边界声明（开源内核 vs 商业载体）。
- 预注册：分析计划在数据收集前入 gold set 版本管理（v0.6 §4.4 已有，保留并强化为发表前置）。

**Related Work 必须覆盖（防审稿意见）**：PersonaGym/PersonaScore、InCharacter、CharacterEval、RoleLLM/RoleBench（人格忠实度维度）；Portable Agent Memory、SPASM（迁移/稳定化维度）；Zep/Graphiti、TOKI（时态治理维度）；Harmful Traits of AI Companions、Affective AI Safety（依恋安全维度）。**禁止**再用「character consistency 无 formal benchmark」表述（v0.6 附录 A-C1 已修正，维持）。

---

# Part D — 上手路线图（研究切入点 / 阶段输出 / 输入 / 动手难易序）

> 原则：**先杀最高风险假设，再建完整运行时**。v0.6 阶段 0 先建 schema（低风险），但最高风险假设 H1（模型无关连续性）要到 Gate 1 才测——若失败，前期 schema 投入虽有价值但已晚。建议插入一个**低成本的 H1 spike**前置。

## D1　阶段化切入点（按动手难易序）

### Spike 0：H1 最廉价证伪（前置，1–2 周，1–2 人）
- **目的**：在建运行时前，用最小成本测核心论点「外部化状态组装能否让换模型后事实/风格连续」。
- **输入**：2 个模型（1 云 + 1 本地开源，锁定版本）、50 条核心事实集、1 份人格契约文本、最小 Context Assembly 脚本（状态+Top-K 记忆+关系+人格契约拼入 system role）。
- **输出**：换模型后核心事实召回率 + 人格探针漂移度初值。
- **决策**：召回远低于 90% 且 Context Assembly 无法修复→H1 危险，暂停建运行时；达标→进入阶段 0。
- **难易**：最低，纯脚本，无需 Policy/事件模型。**强烈建议作为第一件事**。

### 阶段 0：契约与可重放骨架（v0.6 §10.1，3 周）
- **输入**：Draft 0.2 的 26 实体清单、§6 模块规格、Spike 0 的人格契约/事实集。
- **输出**：12 核心实体 Schema + L0/L1/L2 协议 + 50 核心事实 + 30 行为场景 + Alembic。
- **并行**：**威胁模型草案 + 隐私设计**（低代码，A9/G1.4 全套）——设计先行，避免阶段 3 返工。
- **Gate 0**：同 v0.6（L2 重放 100%、LLM 不直写权威表、Policy 拒绝无副作用）。

### 阶段 1：跨模型连续性最小验证（v0.6 §10.2，+本地推理部署）
- **输入**：阶段 0 Schema + Spike 0 扩展至 100/300 事实集 + 本地推理部署（vLLM/llama.cpp）。
- **新增前置**：探针信度校准（S5）→ 再冻结漂移阈值。
- **输出**：Gate 1 六项硬指标 + **判别效度初测**（S7）。
- **Gate 1**：同 v0.6 + 召回 CI 下限 ≥90%（S4）。

### 阶段 2：三 Demo + 基线 + continuity-sim（v0.6 §10.3）
- **关键**：**先实现 Baseline C（标准 Vector RAG）**——它是最强竞争者，越早知道 LifeOS 是否能赢越好。
- **输出**：四基线盲测 + 预注册统计（S6）+ 成本分布。
- **Gate 2**：同 v0.6 + 多重比较校正后的显著性。

### 阶段 3：真人验证（v0.6 §10.4）
- **前置**：IRB/DPIA/DPA/加密/认证/审计全部就绪（B3.2）。
- **输出**：真人盲测 + 用户价值软门（S10）+ 成本 P95。

## D2　研究切入点优先级（学术价值 × 工程可行）

1. **I1+I2（最高学术价值）**：跨模型连续性 + 量化协议——Spike 0 即可产生初步证据，是论文核心。
2. **I4（高价值、范围小）**：时态冲突治理——可独立 Short Paper，工程量小、对位 TOKI 清晰，**适合作为第一篇产出**快速积累引用。
3. **I3（系统资产）**：三级事件回放——随阶段 0/1 自然产出，arXiv 报告低成本。
4. **I6（安全资产）**：依恋安全 policy-as-code——随阶段 2 Policy 完整化产出，社会价值高。
5. **I5（白地但锚点少）**：Schema/协议——需随实例增长才能体现价值，长线。

## D3　输入清单总览

| 阶段 | 关键输入 |
|---|---|
| Spike 0 | 2 模型（锁版本）、50 事实、人格契约、最小组装脚本 |
| 阶段 0 | 26 实体清单、§6 规格、威胁模型草案 |
| 阶段 1 | 阶段 0 产物、100/300 事实集、本地推理部署、探针信度数据 |
| 阶段 2 | continuity-sim、四基线实现、盲测问卷工具、预注册计划 |
| 阶段 3 | IRB/DPIA/DPA、加密/认证/审计就绪、真人 cohort 招募 |

---

# Part E — 综合结论

1. **v0.6 是一份高质量、诚实的工程/学术规格**，其「可证伪化 + 阶段门 + 创新边界声明」在同类文档中少见。核心问题不是方向错误，而是**若干概念与测量学细节不够严谨**（H1 硬/软混淆、盲测判别效度、探针信度、统计设计）与**安全/IP 纵深不足**（敏感外泄、加密、认证、审计、IP 防御姿态）。
2. **最高优先级修正**（影响核心可信度）：S1（拆 H1a/H1b）、S6/S7（盲测统计与判别效度）、G1.4-1（敏感数据不离开本地）、E1.3-1（输出层安全过滤）。
3. **最高优先级新增**（影响生存与商业）：B3.1 校准专有层 + 防御性 IP 姿态、Spike 0 前置 H1 证伪。
4. **学术创新 I1–I6 定位成立**，I1/I2 为主贡献、I4 为最快可发的 Short Paper、I5 为白地。发表前必补 IRB/伦理与测量学信度。
5. **本评审未在线核验任何链接**：C1 已验证链接为原文件保留；C2.1 新增引用一律 `unverified-by-me`，仅给检索方向，**不伪造 URL**。投稿前请团队再核 DOI/版本号。

---

*LifeOS 评审、指导与学术创新整合文档 v1.0 ｜ 2026-08-06 ｜ 评审角色：资深消费电子 + 大模型 + AI 陪伴 + 学术发表背景*
