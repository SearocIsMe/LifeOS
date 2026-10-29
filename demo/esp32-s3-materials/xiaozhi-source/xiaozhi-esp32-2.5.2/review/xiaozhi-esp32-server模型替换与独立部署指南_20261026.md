# xiaozhi-esp32-server 模型替换与独立部署指南（2026-10-26）

> **文档定位**：承接 [`技术交底_小智AI与ESP32-S3-CAM可行性_20261026.md`](技术交底_小智AI与ESP32-S3-CAM可行性_20261026.md) 的 §5.2（场景 b），把"把 xiaozhi-esp32-server 跑在 RK3576 上"从一句建议落为**可操作的替换/部署手册**（**不含编码**，为工程实施做准备）。
> **研究对象**：[`demo/esp32-s3-materials/xiaozhi-esp32-server`](../esp32-s3-materials/xiaozhi-esp32-server)（`main/xiaozhi-server` 为核心 Python 引擎）。
> **实事求是纪律**：全部论断挂**真相源**（文件路径 + 行号）；外部/未逐行核验的部分（如各类云 API 行为、硬件实测）明确标注"工程常识条目"；判定类结论为本项目技术判断（可争论，欢迎挑战）。

---

## 0. 结论速览（TL;DR）

| 问题 | 一句话结论 |
|---|---|
| **Q1** 默认模型是否自部署？如何替换？ | **不是全部自部署**——ASR 默认用**本地离线模型**（FunASR/SenseVoiceSmall），LLM/TTS 默认**连云端 API**（ChatGLM/EdgeTTS）。替换 = 改 `config.yaml` 的 `selected_module` + 对应 provider 配置块（**改配置即可，零改代码**） |
| **Q2** 能否部署 LLM、适配 LifeOS 的 LLM？ | **能**——支持 `openai`（兼容 OpenAI Chat Completions，可指向任意本地 vLLM/llama.cpp/LM Studio 端点）、`ollama`、`xinference` 三种本地/兼容适配器。**只要 LifeOS 的 LLM 暴露 OpenAI 兼容接口，改一段配置即可接入** |
| **Q3** 独立部署自己的 server？ | **能**——三种方式：① Docker 只跑 Server（最快）；② 本地源码 + conda（可调试）；③ 全量 Docker Compose（含 manager 控制台）。**场景 b（RK3576）推荐方式一/二**，arm64 需自编译镜像 |

**核心洞察**：xiaozhi-esp32-server 的 AI 能力是**Provider 模式（可插拔适配器）**驱动——`selected_module` 决定"用哪个"，各 provider 配置块决定"怎么连"。**替换模型 = 编辑 YAML，不碰代码**。这就是它能"从云换成 RK3576 本地"的机制基础。

---

## 1. 架构与配置模型（先理解"在哪改"）

### 1.1 组件构成（真相源 [`main/README.md:86-93`](../esp32-s3-materials/xiaozhi-esp32-server/main/README.md:86)）

```
xiaozhi-esp32-server
  ├─ xiaozhi-server  8000  Python  负责与 ESP32 通信（核心 AI 引擎）★本文重点
  ├─ manager-web     8001  Node/Vue 控制台 web 界面
  ├─ manager-api     8002  Java    控制台 API（配置存储于 MySQL）
  ├─ manager-mobile        uni-app 移动管理端
  └─ digital-human         Python  数字人测试模块
```

> **重要**：若**只用 `xiaozhi-server`**（方式一/二），则**直接读 `config.yaml` / `data/.config.yaml`**；若启用**智控台（manager）**，则**所有配置以智控台为准，config.yaml 不生效**（真相源 [`config.yaml:5`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:5)）。**场景 b 建议只跑 xiaozhi-server，用 YAML 配置**。

### 1.2 配置读取优先级（真相源 [`config.yaml:1-5`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:1)）

```
data/.config.yaml（优先，用户覆盖项）  →  缺失项回落  →  config.yaml（默认全集）
```

推荐做法：**在 `data/.config.yaml` 只写要覆盖的项**（最简、保护密钥），其余用 `config.yaml` 默认值。

### 1.3 Provider 工厂机制（真相源 [`core/utils/modules_initialize.py:9-98`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/utils/modules_initialize.py:9)）

服务器启动时按 `selected_module` 的**类型名（`type` 字段）**动态实例化 provider：

```python
# 以 LLM 为例（modules_initialize.py:37-48）
select_llm_module = config["selected_module"]["LLM"]        # 例如 "ChatGLMLLM"
llm_type = config["LLM"][select_llm_module]["type"]         # 例如 "openai"
modules["llm"] = llm.create_instance(llm_type, config["LLM"][select_llm_module])
```

**即：`selected_module.LLM = "XXX"` 选中 `LLM.XXX` 配置块；该块的 `type` 决定用哪个适配器类。** 六类模块（VAD/ASR/LLM/VLLM/TTS/Memory/Intent）都遵循此模式。

### 1.4 默认 `selected_module`（真相源 [`config.yaml:233-251`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:233)）

| 模块 | 默认选择 | 类型（type） | 本地/云 |
|---|---|---|---|
| VAD | `SileroVAD` | silero | **本地**（ONNX） |
| ASR | `FunASR` | fun_local | **本地**（SenseVoiceSmall 模型） |
| LLM | `ChatGLMLLM` | openai | **云**（智谱 glm-4-flash） |
| VLLM（视觉） | `ChatGLMVLLM` | openai | **云** |
| TTS | `EdgeTTS` | edge | **云**（微软 Edge，免费） |
| Memory | `nomem` | nomem | 无 |
| Intent | `function_call` | function_call | 依赖所选 LLM |

> **结论（Q1 上半）**：**默认就是"半本地"**——ASR/VAD 本地，LLM/TTS 云端。要"全本地"，需替换 LLM/TTS/VLLM。

---

## 2. 任务 1：如何替换模型（按模块逐一说明）

> **替换总原则**：① 在 `config.yaml` 的对应模块下**已存在多个候选配置块**（见下）；② 把 `selected_module.<模块>` 改成你要的块名；③ 若候选块缺少你需要的字段（如换端点），**直接编辑该块**或**新增一个块**（复制现有块改名即可）。**全程不改 `.py` 代码**。

### 2.1 ASR（语音识别）替换

**现有候选**（真相源 [`config.yaml:358-604`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:358)）：

| 块名 | type | 本地/云 | 说明 |
|---|---|---|---|
| `FunASR` | fun_local | **本地** | 默认；SenseVoiceSmall（`models/SenseVoiceSmall/model.pt`），支持 zh/en/ja/ko/yue |
| `FunASRServer` | fun_server | 本地（独立部署） | 独立 FunASR 服务（Docker），适合高并发 |
| `SherpaASR` | sherpa_onnx_local | **本地** | sherpa-onnx sense-voice 多语言 |
| `SherpaParaformerASR` | sherpa_onnx_local | **本地** | **中文专用，低性能设备可跑（注释点名 RK3566-2g）** ★场景 b 首选 |
| `VoskASR` | vosk | **本地** | 完全离线，中文模型需自下 |
| `DoubaoASR`/`DoubaoStreamASR`/`DoubaoStreamASRV2` | doubao[_stream] | 云 | 火山引擎 |
| `AliyunASR`/`AliyunStreamASR`/`AliyunBLStreamASR` | aliyun* | 云 | 阿里云 |
| `BaiduASR` | baidu | 云 | 百度（★对照方案，见交底文档 Q3） |
| `OpenaiASR` | openai | 云 | OpenAI / 任意 OpenAI 兼容（`base_url` 可改） |
| `GroqASR` | openai | 云 | Groq whisper（base_url 改指向） |
| `TencentASR`/`XunfeiStreamASR`/`Qwen3ASRFlash` | * | 云 | 腾讯/讯飞/通义 |

**替换示例（场景 b：用 RK3576 友好的 Paraformer）**：
```yaml
# data/.config.yaml
selected_module:
  ASR: SherpaParaformerASR          # 从 FunASR 改为中文小模型
ASR:
  SherpaParaformerASR:
    type: sherpa_onnx_local
    model_dir: models/sherpa-onnx-paraformer-zh-small-2024-03-09  # 需先下载模型
    model_type: paraformer
```
> 真相源候选块：[`config.yaml:388-394`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:388)。

### 2.2 LLM（对话/意图）替换 ★重点

**现有候选**（真相源 [`config.yaml:613-744`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:613)）：

| 块名 | type | 本地/云 | 端点 | 说明 |
|---|---|---|---|---|
| `ChatGLMLLM` | openai | 云 | bigmodel.cn | **默认**，glm-4-flash 免费 |
| `AliLLM` | openai | 云 | dashscope | 通义千问 |
| `DoubaoLLM` | openai | 云 | volces.com | 豆包（**推荐支持 function_call**） |
| `DeepSeekLLM` | openai | 云 | deepseek.com | deepseek-v4-flash |
| **`OllamaLLM`** | **ollama** | **本地** | localhost:11434 | ★本地部署首选（`ollama pull qwen2.5`） |
| **`LMStudioLLM`** | **openai** | **本地** | localhost:1234/v1 | ★LM Studio 本地 |
| **`XinferenceLLM`/`XinferenceSmallLLM`** | **xinference** | **本地** | localhost:9997 | ★本地推理框架，72b/3b 两档 |
| `DifyLLM`/`FastgptLLM`/`CozeLLM` | * | 云/自建 | * | 平台编排 |
| `VolcesAiGatewayLLM`/`HomeAssistant`/`GeminiLLM` | * | * | * | 其他 |

**关键代码事实**：`openai` 类型适配器（[`llm/openai/openai.py:22-72`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/providers/llm/openai/openai.py:22)）用标准 `openai.OpenAI(base_url=...)` 客户端——**任何兼容 OpenAI Chat Completions 的端点都能接**（`base_url` 换成你的地址 + `model_name` 换成你的模型名 + 任意 `api_key` 占位）。

**替换示例（场景 b：本地 Ollama）**：
```yaml
# data/.config.yaml
selected_module:
  LLM: OllamaLLM
LLM:
  OllamaLLM:
    type: ollama
    model_name: qwen2.5:3b        # 需先 ollama pull qwen2.5:3b
    base_url: http://localhost:11434
```

### 2.3 TTS（语音合成）替换

**现有候选**（真相源 [`config.yaml:770-`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:770)）：

| 块名 | type | 本地/云 | 说明 |
|---|---|---|---|
| `EdgeTTS` | edge | 云（免费） | **默认**，微软 edge-tts |
| `DoubaoTTS`/`HuoshanDoubleStreamTTS` | doubao / huoshan_double_stream | 云 | 火山引擎 |
| `FishSpeechTTS` | fishspeech | **可本地** | Fish-Speech 自部署（有集成文档 `docs/fish-speech-integration.md`） |
| `GPT_SOVITS_v2/v3` | gpt_sovits_v2/v3 | **可本地** | GPT-SoVITS 自部署 |
| `PaddleSpeechTTS` | paddle_speech | **可本地** | PaddleSpeech（有 `docs/paddlespeech-deploy.md`） |
| `IndexStreamTTS` | index_stream | **可本地** | Index-TTS（有集成文档） |
| `SiliconFlowTTS`/`MinimaxTTS`/`AliyunTTS`/`TencentTTS`/`XunfeiTTS`/`OpenaiTTS`/`AlibabaBLTTS`/`CustomTTS` | * | 云/自定义 | 多厂商 + 自定义 |

> **对照 LifeOS 上位文档 §5.2**：主控侧规划的是 **sherpa-onnx vits-zh / Piper**（Apache/MIT）。`xiaozhi-server` 的 TTS provider 列表**原生不含 sherpa-onnx vits**，但含 **PaddleSpeech / Fish-Speech / GPT-SoVITS / IndexTTS / CustomTTS** 等本地选项——**若要落地"全开源本地 TTS"，用 CustomTTS 适配 vits-zh，或选 PaddleSpeech**（详见 §5.1 差距项）。

### 2.4 VAD / Memory / Intent 替换

- **VAD**：默认 `SileroVAD`（[`config.yaml:605-611`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:605)），本地 ONNX，通常无需换。
- **Memory**：`nomem`（无）→ **`mem_local_short`（本地短期，数据不出机，注释点名"注重隐私请使用本地"）**/ `mem0ai`（云）/ `powermem`（本地 LLM + sqlite 可全免费）（[`config.yaml:293-356`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:293)）。**对齐 LifeOS"隐私封闭为默认"，场景 b 选 `mem_local_short` 或 `powermem`（sqlite）**。
- **Intent**：`nointent` / `intent_llm` / `function_call`（[`config.yaml:253-292`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:253)）。`function_call` 需要所选 LLM 支持 function calling（本地 3B 级模型此能力弱，必要时降级为 `intent_llm` 或 `nointent`）。

### 2.5 替换的"避坑清单"

| 坑 | 说明 | 规避 |
|---|---|---|
| 模型文件未下载 | 本地 ASR/TTS 需先放模型到 `models/` 对应目录 | 按 [`Deployment.md:226-235`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment.md:226) 下载 |
| 智控台覆盖 | 启用 manager 后 config.yaml 不生效 | 场景 b 只跑 xiaozhi-server |
| function_call 依赖 LLM 能力 | 小模型不支持 tools | 降级 Intent 或换更大本地模型 |
| 采样率不匹配 | 前端 16k/24k、模型自定 | 交给 VAD/ASR provider 内部处理（代码已封装） |
| arm64 无官方镜像 | `Deployment.md:5` 明确 docker 镜像只支持 x86 | arm64 需自编译（[`docs/docker-build.md`](../esp32-s3-materials/xiaozhi-esp32-server/docs/docker-build.md)） |

---

## 3. 任务 2：能否部署 LLM 并适配 LifeOS 的 LLM？

### 3.1 结论：**能，且有三条路径**

xiaozhi-server 的 LLM 层是**开放适配器 + OpenAI 兼容**双保险：

1. **`openai` 适配器（最通用）**——[`llm/openai/openai.py:72`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/providers/llm/openai/openai.py:72) 用 `openai.OpenAI(api_key, base_url, timeout)`。**只要 LifeOS 的 LLM 服务暴露 OpenAI 兼容的 `/v1/chat/completions`，配 `base_url` + `model_name` 即可**。
2. **`ollama` 适配器**——[`llm/ollama/ollama.py:19-22`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/providers/llm/ollama/ollama.py:19) 也是 `openai.OpenAI(base_url=..., api_key="ollama")`，并做了 qwen3 的 `/no_think` 与 ` thinking` 标签过滤。
3. **`xinference` 适配器**——本地推理框架（[`llm/xinference/`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/providers/llm/xinference)）。

### 3.2 适配 LifeOS LLM 的判定

| 若 LifeOS 的 LLM 是… | 接入方式 | 工作量 |
|---|---|---|
| **vLLM**（上位文档 §5.2 云档规划） | vLLM 原生提供 OpenAI 兼容 API → 用 `openai` 适配器，`base_url` 指向 vLLM | ★（配 YAML） |
| **llama.cpp server**（上位文档 §5.2 边缘档） | `llama-server` 提供 OpenAI 兼容 `/v1` → 同上 | ★ |
| **自研 LifeOS Model Gateway**（封装 `deterministic_commit` 等） | **需在 Gateway 侧暴露 OpenAI 兼容端点**，或用 `CustomTTS` 式的自定义 provider 思路新增 `type` | ★★（Gateway 侧适配） |
| **非 OpenAI 协议的自定义 API** | 新增一个 provider 类（继承 `LLMProviderBase`，[`llm/base.py:7-34`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/providers/llm/base.py:7)），在 `core/utils/llm.py` 注册 | ★★（写代码） |

### 3.3 关键：LifeOS 身份内核与 xiaozhi-server 的接缝

> **LifeOS 的"身份连续性"（15 实体 + L0/L1/L2 事件 + `deterministic_commit` + 人格契约）在合并架构中不应塞进 xiaozhi-server 的 LLM provider，而应作为 LLM 背后的"上下文与提交层"**。

**接缝方案（对齐交底文档 §5.1 场景 a/b）**：

```
ESP32-S3-CAM 前端 ──小智协议──▶ xiaozhi-server（ASR/意图/TTS 管线）
                                     │
                                     ├─ 上下文注入：用 context_providers（config.yaml:126-129）
                                     │   把 LifeOS 的"人格契约 + Kernel 状态 + top-k 记忆"注入 system prompt
                                     │
                                     ├─ LLM：指向 LifeOS Model Gateway / vLLM / llama.cpp（OpenAI 兼容）
                                     │   由 LifeOS 的 deterministic_commit 处理"提交"（事件入库）
                                     │
                                     └─ Memory：用 mem_local_short / powermem（本地，不出机）
```

- **`context_providers`**（[`config.yaml:126-129`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:126)）：xiaozhi-server **原生支持在 system prompt 注入动态上下文**（注释："健康数据、股票信息等"）——**这正是把 LifeOS 人格契约/Kernel 状态注入对话的现成钩子**。
- **`agent-base-prompt.txt`**（[`main/xiaozhi-server/agent-base-prompt.txt`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/agent-base-prompt.txt)）：系统提示词模板，可对齐 LifeOS 人格契约。
- **`prompt` / `end_prompt`**（[`config.yaml:204-230`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:204)）：角色人设与结束语。

> **裁决**：**xiaozhi-server 完全可作为 LifeOS 在场景 b 的"语音管线宿主"**——但需明确二者分工：**xiaozhi-server 管"听/说/意图"（管道层），LifeOS 管"身份/记忆/提交"（内核层）**，通过 `context_providers` + OpenAI 兼容 LLM 端点 + 本地 Memory 三者接缝。**不要试图把 LifeOS 的逻辑写进 xiaozhi-server 的 provider 里**（会破坏两边的验证纪律）。

---

## 4. 任务 3：如何独立部署自己的 xiaozhi-esp32-server

> 真相源：[`docs/Deployment.md`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment.md)、[`docs/Deployment_all.md`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment_all.md)、[`main/xiaozhi-server/docker-compose.yml`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/docker-compose.yml)、[`docs/docker-build.md`](../esp32-s3-materials/xiaozhi-esp32-server/docs/docker-build.md)。

### 4.1 方式一：Docker 只跑 Server（最快，场景 b 首选）

真相源 [`Deployment.md:3-113`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment.md:3)：

```
① 建目录：xiaozhi-server/{data, models/SenseVoiceSmall}
② 下载 ASR 模型 model.pt 放入 models/SenseVoiceSmall/（Deployment.md:226-235）
③ 下载 docker-compose.yml 放入 xiaozhi-server/
④ 下载 config.yaml 改名为 data/.config.yaml
⑤ 按 §2 配置 selected_module（改模型）
⑥ docker compose up -d
⑦ docker logs -f xiaozhi-esp32-server   # 看启动日志
```

docker-compose.yml 关键点（真相源 [`docker-compose.yml:4-22`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/docker-compose.yml:4)）：
- 镜像 `ghcr.nju.edu.cn/xinnan-tech/xiaozhi-esp32-server:server_latest`（**仅 x86**）；
- 端口 `8000`（WebSocket）、`8003`（HTTP：OTA + 视觉分析）；
- 挂载 `./data`（配置）+ `./models/SenseVoiceSmall/model.pt`（ASR 模型）。

### 4.2 方式二：本地源码 + conda（可调试，推荐开发期）

真相源 [`Deployment.md:114-188`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment.md:114)：

```
① conda create -n xiaozhi-esp32-server python=3.10 -y && conda activate 同名
② conda install libopus -y && conda install ffmpeg -y   # 关键外部依赖
③ cd main/xiaozhi-server && pip install -r requirements.txt
④ 下载 ASR 模型（同方式一）
⑤ 建 data/.config.yaml（最简配置见 Deployment.md:206-221）
⑥ python app.py
```

启动成功标志（真相源 [`Deployment.md:236-246`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment.md:236)）：日志打印 `OTA接口是 http://<ip>:8003/xiaozhi/ota/` 与 `Websocket地址是 ws://<ip>:8000/xiaozhi/v1/`。

### 4.3 方式三：全量 Docker Compose（含管理控制台）

真相源 [`main/docker-compose_all.yml`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/docker-compose_all.yml) 与 [`docs/Deployment_all.md`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment_all.md)：一键拉起 xiaozhi-server + manager-api（Java + MySQL + Redis）+ manager-web，适合**多人/多设备管理**。**场景 b（单宠/单主控）不建议**——增加 MySQL/Redis/Java 依赖，与"边缘轻量"目标冲突。

### 4.4 场景 b（RK3576）部署要点

| 要点 | 说明 | 真相源 |
|---|---|---|
| **arm64 镜像** | 官方 docker 镜像仅 x86，RK3576（aarch64）**必须自编译** | [`Deployment.md:5`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment.md:5)、[`docs/docker-build.md`](../esp32-s3-materials/xiaozhi-esp32-server/docs/docker-build.md) |
| **建议源码部署** | 方式二（conda/venv）在 RK3576 上更可控，也便于替换本地模型 | [`Deployment.md:114`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment.md:114) |
| **ASR 换轻量** | 用 `SherpaParaformerASR`（注释点名 RK3566-2g 可跑） | [`config.yaml:388-390`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:388) |
| **LLM 换本地** | Ollama / LM Studio / 任意 OpenAI 兼容 | [`config.yaml:664-744`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:664) |
| **Memory 换本地** | `mem_local_short` 或 `powermem`（sqlite） | [`config.yaml:299-356`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:299) |
| **前端指向** | ESP32-S3-CAM 的 OTA/WebSocket 地址指向 RK3576 局域网 IP | [`config.yaml:20-27`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:20) |

### 4.5 部署后与前端对接

```yaml
# data/.config.yaml（场景 b：指向 RK3576 自身，局域网）
server:
  ip: 0.0.0.0
  port: 8000
  http_port: 8003
  # ESP32-S3-CAM 将连接的地址（RK3576 局域网 IP）
  websocket: ws://192.168.4.1:8000/xiaozhi/v1/       # 私有 Wi-Fi SoftAP 场景
  vision_explain: http://192.168.4.1:8003/mcp/vision/explain
```

> **前端侧**：ESP32-S3-CAM 固件（小智）的 OTA 地址栏填入 `http://192.168.4.1:8003/xiaozhi/ota/`，设备即从 RK3576 拉取 WebSocket 地址——**前端零改造**（对齐交底文档 §5.2）。

---

## 5. 差距清单：本地化的"最后一公里"

| # | 差距 | 现状 | 缺口 | 工作量 |
|---|---|---|---|---|
| L1 | **全本地 ASR** | 默认 FunASR 本地，但 SenseVoiceSmall 在 RK3576 需验证速度 | 换 `SherpaParaformerASR`（点名 RK3566-2g 可跑） | ★ |
| L2 | **全本地 LLM** | 适配器齐全（ollama/openai/xinference） | 需 RK3576 起 Ollama/vLLM/llama.cpp，并验证 3B function_call | ★★ |
| L3 | **全本地 TTS** | 默认 EdgeTTS（云）；本地有 PaddleSpeech/Fish-Speech/GPT-SoVITS/IndexTTS/CustomTTS | **无 sherpa-onnx vits-zh 原生 provider**——用 CustomTTS 适配或选 PaddleSpeech | ★★ |
| L4 | **视觉理解本地化** | VLLM provider 默认云（glm-4v/qwen-vl） | 需本地 VLM 或改走 RK3576 的 RTMPose 跌倒检测（对齐上位文档 §5.2） | ★★★ |
| L5 | **Memory 出 LifeOS 化** | 原生 mem_local_short/powermem | 与 LifeOS 15 实体/Kernel 衰减对齐（接缝见 §3.3） | ★★★ |
| L6 | **context_providers 注入 LifeOS 状态** | 原生钩子存在 | 需实现 LifeOS 侧 HTTP 上下文源 | ★★ |
| L7 | **arm64 部署** | 官方镜像仅 x86 | RK3576 自编译镜像或源码部署 | ★ |
| L8 | **验证纪律** | 无 Gate/CI | 把 LifeOS Gate 断言套在语音管线指标 | ★ |

---

## 6. 结论与建议下一步（不 coding）

### 6.1 三句话结论

1. **默认不是全自部署**：VAD/ASR 本地，LLM/TTS 云端；**替换 = 改 `selected_module` + provider 块（零改代码）**。
2. **能部署 LLM 且能适配 LifeOS 的 LLM**：`openai` / `ollama` / `xinference` 三种适配器，**只要 LifeOS 的 LLM 暴露 OpenAI 兼容端点即可接入**；LifeOS 的身份/记忆/提交应作为"上下文与提交层"通过 `context_providers` + 本地 Memory 接缝，**不写进 provider**。
3. **能独立部署**：Docker（快）/ 源码 conda（可控）/ 全量 Compose（重）；**场景 b 用 Docker 或源码，arm64 需自编译，只跑 xiaozhi-server**。

### 6.2 建议下一步（不 coding）

| 顺序 | 动作 | 产出 |
|---|---|---|
| S1 | 在 PC/WSL 按 §4.1/4.2 跑通 xiaozhi-server，用 `digital-human` 模块浏览器测对话 | 后端跑通实证 |
| S2 | 按 §2.2 把 LLM 换成本地 Ollama（qwen2.5:3b），验证对话与 function_call | 本地 LLM 可行性 |
| S3 | 按 §2.1 换 `SherpaParaformerASR`，验证中文识别与速度 | 轻量 ASR 可行性 |
| S4 | 写一个最小的 LifeOS 侧 `context_providers` HTTP 端点，注入人格契约 | LifeOS 接缝实证 |
| S5 | 在 RK3576 上按 §4.4 部署（arm64），实测端到端时延 | 场景 b 真机结论 |

### 6.3 诚实声明

- 本文**未实际部署、未联调、未上板**；可行性与工作量为**代码/配置级判断**。
- 各云 API（豆包/阿里/百度等）行为按配置注释为**工程常识条目**，未逐个调用验证。
- 本地模型在 RK3576 的**真实 token/s、时延、内存**须真机实测（S2/S3/S5）。
- TTS 的"无 sherpa-onnx vits-zh 原生 provider"为**源码目录核实**（`core/providers/tts/` 无 vits 文件），但可经 CustomTTS 适配。

---

## 附：真相源清单

| 论断 | 真相源 |
|---|---|
| 组件架构 | [`main/README.md:86-93`](../esp32-s3-materials/xiaozhi-esp32-server/main/README.md:86) |
| 部署三方式 | [`docs/Deployment.md`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment.md)、[`docs/Deployment_all.md`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment_all.md)、[`docs/docker-build.md`](../esp32-s3-materials/xiaozhi-esp32-server/docs/docker-build.md) |
| 配置优先级/selected_module | [`config.yaml:1-5`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:1)、[`config.yaml:233-251`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:233) |
| Provider 工厂 | [`core/utils/modules_initialize.py:9-98`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/utils/modules_initialize.py:9) |
| LLM 适配器 | [`core/providers/llm/openai/openai.py:22-72`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/providers/llm/openai/openai.py:22)、[`llm/ollama/ollama.py:19-22`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/providers/llm/ollama/ollama.py:19)、[`llm/base.py:7-34`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/providers/llm/base.py:7) |
| ASR/TTS/VAD/Memory/Intent 候选 | [`config.yaml:358-604`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:358)、[`config.yaml:605-611`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:605)、[`config.yaml:770-`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:770)、[`config.yaml:253-356`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:253) |
| context_providers / prompt | [`config.yaml:126-129`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:126)、[`config.yaml:204-230`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:204)、[`agent-base-prompt.txt`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/agent-base-prompt.txt) |
| docker-compose | [`main/xiaozhi-server/docker-compose.yml:4-22`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/docker-compose.yml:4) |
| 上位交底文档 | [`技术交底_小智AI与ESP32-S3-CAM可行性_20261026.md`](技术交底_小智AI与ESP32-S3-CAM可行性_20261026.md)、[`review/LifeOS_elderly-companion合并可行性研究_20261004.md`](../../review/LifeOS_elderly-companion合并可行性研究_20261004.md) |
