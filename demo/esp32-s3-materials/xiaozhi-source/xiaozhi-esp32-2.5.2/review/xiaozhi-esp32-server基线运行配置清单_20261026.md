# xiaozhi-esp32-server 基线运行配置清单（本机部署 · 待填充）（2026-10-26）

> **目标**：在你**本地电脑**上把 `xiaozhi-esp32-server`（仅 `xiaozhi-server` 核心引擎）**基线跑起来**——**不做独立部署**（不碰 manager 控制台/MySQL/Redis/Java），只用 `data/.config.yaml` 配置。
> **你的选择（已采纳）**：LLM = 智谱（`ChatGLMLLM`，填你的 `glm-5.3-flash`）｜ASR = **阿里云**｜TTS = **保留免费 EdgeTTS**｜其余用免费/本地默认。
> **真相源**：全部配置键来自 [`main/xiaozhi-server/config.yaml`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml) 与各 provider 源码；判定为工程常识条目。
> **用法**：本文给出**一个 list**——你按表逐项填写 `data/.config.yaml`。带 🔲 的是**必须你填**的；带 ✅ 的是**保持默认/免费、无需改动**的。

---

## 0. 基线最小配置总览（先看这个）

**基线原则**：只覆盖"要改的"，其余靠 `config.yaml` 默认值自动回落。
**最小可用改动只有 3 处**：① LLM 换智谱填 key；② ASR 选阿里云填 key；③ TTS 保持 EdgeTTS（不动）。VAD/Memory/Intent 用默认。

```yaml
# data/.config.yaml  ← 你只需创建这一个文件并填下面内容
selected_module:
  ASR: AliyunASR          # 🔲 阿里云（也可选 AliyunBLStreamASR / AliyunStreamASR）
  LLM: ChatGLMLLM         # 🔲 智谱（保持块名，只填 key + 模型名）
  TTS: EdgeTTS            # ✅ 免费，保持不变

server:
  websocket: ws://你电脑局域网IP:8000/xiaozhi/v1/     # 🔲 设备要连的地址
  vision_explain: http://你电脑局域网IP:8003/mcp/vision/explain  # 🔲（可用视觉时）

LLM:
  ChatGLMLLM:
    api_key: 🔲你的智谱key
    model_name: glm-5.3-flash   # 🔲 你的模型名

ASR:
  AliyunASR:
    appkey: 🔲你的阿里云NLS Appkey
    access_key_id: 🔲你的AccessKeyId
    access_key_secret: 🔲你的AccessKeySecret
```

> ⚠️ **两个"坑"先记住**（真相源 [`config.yaml:5`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:5)）：
> 1. **文件必须叫 `data/.config.yaml`**（前面有个点），不是 `config.yaml`；系统优先读它，缺项回落到项目根的 `config.yaml`。
> 2. **不要启用智控台（manager）**——一旦启用，`config.yaml` 全部失效。基线只跑 `python app.py`（或 server-only docker）。

---

## 1. 运行前准备（填充之前先做，3 步）

| # | 步骤 | 命令/来源 | 真相源 |
|---|---|---|---|
| P0.1 | 建 conda 环境 + 装外部依赖 | `conda create -n xiaozhi-esp32-server python=3.10 -y` → `conda activate xiaozhi-esp32-server` → `conda install libopus -y` → `conda install ffmpeg -y` | [`Deployment.md:130-144`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment.md:130) |
| P0.2 | 装 Python 依赖 | `cd main/xiaozhi-server` → `pip install -r requirements.txt` | [`Deployment.md:160-167`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment.md:160) |
| P0.3 | 下载本地 ASR 模型 **（可选）** | 基线若用**阿里云 ASR**，则**不必**下载 SenseVoiceSmall；若想同时保留本地 ASR 备选，再下 `model.pt` 到 `models/SenseVoiceSmall/` | [`Deployment.md:226-235`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment.md:226) |

> ✅ **好消息**：选择**阿里云 ASR** 后，P0.3 的模型下载**可跳过**（阿里云在云端识别）。VAD 的 SileroVAD 模型通常首次运行自动准备（本地 ONNX，见 §3）。

---

## 2. 待填充清单（核心表格 · 逐项填）

### 2.1 `server` 段（🔲 必填 2 项）

| 键 | 填什么 | 说明 | 真相源 |
|---|---|---|---|
| `server.websocket` | 🔲 `ws://<你电脑局域网IP>:8000/xiaozhi/v1/` | 设备/数字人测试要连的 WebSocket 地址。**本机测试**可填 `ws://127.0.0.1:8000/xiaozhi/v1/`；**真机**须填电脑局域网 IP | [`config.yaml:20`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:20) |
| `server.vision_explain` | 🔲 `http://<IP>:8003/mcp/vision/explain` | 视觉理解接口（拍照识物用）；基线可先留默认，用到再改 | [`config.yaml:27`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:27) |
| `server.ip` / `port` / `http_port` | ✅ 保持 `0.0.0.0` / `8000` / `8003` | 默认即可 | [`config.yaml:11-14`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:11) |
| `server.auth.enabled` | ✅ `false` | 基线不启用 token 校验 | [`config.yaml:31-33`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:31) |

### 2.2 `selected_module` 段（🔲 选 3 项）

| 模块 | 你选的值 | 备选 | 真相源 |
|---|---|---|---|
| `ASR` | 🔲 `AliyunASR`（**推荐**，简单） | `AliyunBLStreamASR`（百炼，更简单）/ `AliyunStreamASR`（流式） | [`config.yaml:236`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:236)、[`config.yaml:458-493`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:458) |
| `LLM` | 🔲 `ChatGLMLLM` | `DeepSeekLLM`/`DoubaoLLM`/`AliLLM` 等 | [`config.yaml:239`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:239) |
| `TTS` | ✅ `EdgeTTS`（免费，不动） | — | [`config.yaml:243`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:243) |
| `VAD` | ✅ `SileroVAD`（本地，不动） | — | [`config.yaml:235`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:235) |
| `VLLM` | ✅ `ChatGLMVLLM`（视觉，基线可不启用） | 阿里 `QwenVLVLLM` | [`config.yaml:241`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:241) |
| `Memory` | ✅ `nomem` 或改 `mem_local_short`（本地） | `powermem`（本地 sqlite） | [`config.yaml:245`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:245) |
| `Intent` | ✅ `function_call` | 若所选 LLM 不支持 tools → `intent_llm` / `nointent` | [`config.yaml:251`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:251) |

### 2.3 `LLM` 段（智谱 ChatGLM，🔲 必填 2 项）

现有默认块（真相源 [`config.yaml:656-663`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:656)）：

| 键 | 默认 | 🔲 你填 | 说明 |
|---|---|---|---|
| `type` | `openai` | ✅ 保持 `openai`（智谱兼容 OpenAI 协议） | 适配器用标准 OpenAI 客户端 |
| `url` | `https://open.bigmodel.cn/api/paas/v4/` | ✅ 保持（智谱端点） | 注意键名是 `url`（非 base_url）也可 |
| `model_name` | `glm-4-flash` | 🔲 `glm-5.3-flash`（你的模型名） | 以智谱控制台可用模型名为准 |
| `api_key` | `你的chat-glm web key` | 🔲 `<你的智谱 API Key>` | 申请：https://bigmodel.cn/usercenter/proj-mgmt/apikeys |

> **说明**：`glm-4-flash` 是智谱**免费**模型（需注册 key）；你填 `glm-5.3-flash` 即用你的模型。若该模型**不支持 function_call**，把 `selected_module.Intent` 改为 `intent_llm` 或 `nointent`（[`config.yaml:247-251`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:247)）。

### 2.4 `TTS` 段（✅ 免费 EdgeTTS，无需改动）

| 键 | 值 | 说明 | 真相源 |
|---|---|---|---|
| `selected_module.TTS` | ✅ `EdgeTTS` | 微软 Edge 免费 TTS | [`config.yaml:243`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:243) |
| `TTS.EdgeTTS.voice` | ✅ `zh-CN-XiaoxiaoNeural`（可换音色） | 无需 key | [`config.yaml:772-776`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:772) |

> ⚠️ EdgeTTS **受代理影响**：若开了梯子导致失败，请关闭代理（真相源 [`FAQ.md:19-22`](../esp32-s3-materials/xiaozhi-esp32-server/docs/FAQ.md:19)）。

### 2.5 `VAD` 段（✅ 本地，无需改动）

| 键 | 值 | 真相源 |
|---|---|---|
| `VAD.SileroVAD.threshold` | ✅ `0.5` | [`config.yaml:605-611`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:605) |
| `VAD.SileroVAD.model_dir` | ✅ `models/snakers4_silero-vad` | 同上 |
| `VAD.SileroVAD.min_silence_duration_ms` | 可选调大（老人说话慢 → `700`~`1000`） | [`FAQ.md:50-60`](../esp32-s3-materials/xiaozhi-esp32-server/docs/FAQ.md:50) |

### 2.6 `Memory` 段（✅ 基线用 nomem 或本地）

| 键 | 值 | 说明 | 真相源 |
|---|---|---|---|
| `selected_module.Memory` | ✅ `nomem`（基线）或 `mem_local_short` | `mem_local_short` **数据不出机**（隐私友好）；`nomem` 最简 | [`config.yaml:293-356`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:293) |
| `Memory.mem_local_short.llm` | ✅ `ChatGLMLLM` | 用你已配的智谱做记忆总结 | [`config.yaml:350-356`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:350) |

---

## 3. 阿里云 ASR 配置（重点）——需要"在阿里云做哪些步骤"

阿里云有**两条不同产品线**，对应两个 provider，**选一条即可**：

### 方案 A（推荐·最简）：阿里百炼 DashScope → `AliyunBLStreamASR`

**特点**：只需一个 `api_key`，Paraformer 实时流式，配置最简。
**代码依据**：[`core/providers/asr/aliyunbl_stream.py:30-48`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/providers/asr/aliyunbl_stream.py:30)（只读 `api_key`/`model`/`sample_rate`/`format`）。

**要在阿里云做的步骤**：
1. 注册/登录阿里云账号，实名认证；
2. 开通**阿里云百炼（Model Studio / DashScope）**：https://bailian.console.aliyun.com/ ；
3. 在百炼控制台**创建 API-KEY**：https://bailian.console.aliyun.com/#/api-key ；
4. 确认已开通 **Paraformer 实时语音识别**模型（`paraformer-realtime-v2`）；
5. 复制 API-KEY → 填到配置。

**`config.yaml` 填法**（真相源 [`config.yaml:579-604`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:579)）：

```yaml
selected_module:
  ASR: AliyunBLStreamASR
ASR:
  AliyunBLStreamASR:
    type: aliyunbl_stream
    api_key: 🔲你的阿里云百炼 API-KEY
    model: paraformer-realtime-v2     # 推荐
    format: pcm
    sample_rate: 16000
    # 可选：semantic_punctuation_enabled / vocabulary_id / language_hints 等
```

### 方案 B：阿里云智能语音交互 NLS → `AliyunASR` / `AliyunStreamASR`

**特点**：传统 NLS 产品线，需 **Appkey + AccessKeyId/Secret**（或长期 token）。
**代码依据**：[`core/providers/asr/aliyun.py:96-113`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/providers/asr/aliyun.py:96)（非流式，读 `appkey` + `access_key_id/secret` 或 `token`）、[`core/providers/asr/aliyun_stream.py:82-105`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/providers/asr/aliyun_stream.py:82)（流式，同上 + `host`）。

**要在阿里云做的步骤**：
1. 登录阿里云，开通**智能语音交互（NLS）**：https://nls-portal.console.aliyun.com/ ；
2. 在 NLS 控制台**创建项目**，拿到 **Appkey**（项目列表页）：https://nls-portal.console.aliyun.com/applist ；
3. 在 **RAM 控制台**创建 AccessKey（**AccessKey ID + AccessKey Secret**）：https://ram.console.aliyun.com/manage/ak ；
   - （可选）用上面的 AccessKey 生成**长期 token**，避免代码自动刷新：NLS 概览页 https://nls-portal.console.aliyun.com/overview ；
4. 给该 RAM 用户授予 `AliyunNLSFullAccess`（或最小权限）。

**`config.yaml` 填法**（选其一）：

```yaml
# 方案 B-1：非流式（AliyunASR）
selected_module:
  ASR: AliyunASR
ASR:
  AliyunASR:
    type: aliyun
    appkey: 🔲你的NLS Appkey
    access_key_id: 🔲你的AccessKeyId
    access_key_secret: 🔲你的AccessKeySecret
    # token: 🔲（可选）若用长期token代替上面的id/secret
    output_dir: tmp/
```
```yaml
# 方案 B-2：流式（AliyunStreamASR，实时性更好）
selected_module:
  ASR: AliyunStreamASR
ASR:
  AliyunStreamASR:
    type: aliyun_stream
    appkey: 🔲你的NLS Appkey
    access_key_id: 🔲你的AccessKeyId
    access_key_secret: 🔲你的AccessKeySecret
    # token: 🔲（可选）
    host: nls-gateway-cn-shanghai.aliyuncs.com   # 就近地域可换 hangzhou 等
    max_sentence_silence: 800
    output_dir: tmp/
```

> **选型建议**：**基线用方案 A（百炼）**——只需 1 个 key，最少步骤；且 Paraformer 为流式，体验好。方案 B 适合已有 NLS 账号/Appkey 的情况。
> **诚实声明**：阿里云各产品**当前页面路径、免费额度、是否需实名**以官网实时为准（本文为工程常识条目，未逐步截图核验）。

---

## 4. 填充完成后的运行与自检

```bash
# 1) 确认在 main/xiaozhi-server 目录，且存在 data/.config.yaml
cd main/xiaozhi-server
python app.py

# 2) 看到如下日志即为成功（真相源 Deployment.md:236-246）
#    OTA接口是     http://<ip>:8003/xiaozhi/ota/
#    Websocket地址是 ws://<ip>:8000/xiaozhi/v1/
```

**基线自检清单**：

| # | 检查项 | 通过标准 |
|---|---|---|
| C1 | `data/.config.yaml` 存在且拼写正确（有点号） | 启动日志显示读取了你的配置 |
| C2 | 依赖齐全 | 无 `libopus`/`ffmpeg` 报错（[`FAQ.md:8-17`](../esp32-s3-materials/xiaozhi-esp32-server/docs/FAQ.md:8)） |
| C3 | LLM key 有效 | 对话能返回文本（非 `system_error_response`） |
| C4 | ASR key 有效 | 说话能被识别成正确中文（不再"识别成韩文/日文"，[`FAQ.md:3-6`](../esp32-s3-materials/xiaozhi-esp32-server/docs/FAQ.md:3)） |
| C5 | TTS 正常 | 能听到 EdgeTTS 语音（失败先关代理，[`FAQ.md:19`](../esp32-s3-materials/xiaozhi-esp32-server/docs/FAQ.md:19)） |
| C6 | 用 `digital-human` 浏览器端测试 | 能完整走通一轮问答（[`docs/digital-human-wakeword.md`](../esp32-s3-materials/xiaozhi-esp32-server/docs/digital-human-wakeword.md)） |

---

## 5. 常见坑（基线段）

| 坑 | 现象 | 解决 | 真相源 |
|---|---|---|---|
| 智控台抢占配置 | 改了 `.config.yaml` 不生效 | 别启用 manager；只跑 `app.py` | [`config.yaml:5`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:5) |
| EdgeTTS 失败 | TTS 超时/报错 | 关闭系统代理 | [`FAQ.md:19-22`](../esp32-s3-materials/xiaozhi-esp32-server/docs/FAQ.md:19) |
| ASR 乱识别语种 | 识别成韩/日/英 | ① 若用本地 FunASR，检查 `models/SenseVoiceSmall/model.pt`；② 用阿里云则检查 key | [`FAQ.md:3-6`](../esp32-s3-materials/xiaozhi-esp32-server/docs/FAQ.md:3) |
| function_call 报错 | Intent 不支持 tools | `selected_module.Intent` 改 `intent_llm`/`nointent` | [`config.yaml:247-251`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:247) |
| 老人说话慢被抢话 | VAD 过早断句 | `min_silence_duration_ms` 调大 | [`FAQ.md:50-60`](../esp32-s3-materials/xiaozhi-esp32-server/docs/FAQ.md:50) |
| 模型键名混淆 | `url` vs `base_url` | 智谱块用 `url`；OpenAI 块两者都认（[`llm/openai/openai.py:26-29`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/providers/llm/openai/openai.py:26)） | 源码 |

---

## 6. 你的"填空 list"汇总（可直接复制去填）

```
【必填】data/.config.yaml
  selected_module.ASR           = AliyunBLStreamASR      ← 推荐（或 AliyunASR / AliyunStreamASR）
  selected_module.LLM           = ChatGLMLLM
  selected_module.TTS           = EdgeTTS                (✅ 免费，保持)
  server.websocket              = ws://<你的IP>:8000/xiaozhi/v1/
  LLM.ChatGLMLLM.api_key        = <你的智谱 API Key>
  LLM.ChatGLMLLM.model_name     = glm-5.3-flash
  ASR.AliyunBLStreamASR.api_key = <你的阿里云百炼 API-KEY>

【阿里云步骤（方案A·百炼）】
  1. 登录阿里云 →  2. 开通百炼 →  3. 创建 API-KEY →  4. 确认 paraformer-realtime-v2 可用

【阿里云步骤（方案B·NLS，若选 AliyunASR/AliyunStreamASR）】
  1. 开通智能语音交互 →  2. 创建项目取 Appkey →  3. RAM 创建 AccessKey(Id/Secret)
  4. （可选）生成长期 token

【保持默认·无需填】
  VAD=SileroVAD(local) | Memory=nomem 或 mem_local_short | Intent=function_call
  TTS.EdgeTTS.voice=zh-CN-XiaoxiaoNeural
```

---

## 附：真相源清单

| 论断 | 真相源 |
|---|---|
| 配置读取优先级 | [`config.yaml:1-5`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:1) |
| selected_module 默认值 | [`config.yaml:233-251`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:233) |
| LLM 智谱块 | [`config.yaml:656-663`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:656) |
| OpenAI 适配器（url/base_url） | [`llm/openai/openai.py:22-72`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/providers/llm/openai/openai.py:22) |
| TTS EdgeTTS | [`config.yaml:770-776`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:770) |
| 阿里 NLS ASR 键 | [`asr/aliyun.py:96-113`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/providers/asr/aliyun.py:96)、[`asr/aliyun_stream.py:82-105`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/providers/asr/aliyun_stream.py:82) |
| 阿里百炼 ASR 键 | [`asr/aliyunbl_stream.py:30-48`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/providers/asr/aliyunbl_stream.py:30)、[`config.yaml:579-604`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:579) |
| 本地部署步骤 | [`docs/Deployment.md:114-188`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment.md:114) |
| 常见问题 | [`docs/FAQ.md`](../esp32-s3-materials/xiaozhi-esp32-server/docs/FAQ.md) |
| 关联文档 | [`xiaozhi-esp32-server模型替换与独立部署指南_20261026.md`](xiaozhi-esp32-server模型替换与独立部署指南_20261026.md) |
