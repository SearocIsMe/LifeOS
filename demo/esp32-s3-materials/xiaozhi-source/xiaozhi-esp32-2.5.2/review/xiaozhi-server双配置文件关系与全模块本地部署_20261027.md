# xiaozhi-server 双配置文件关系与全模块本地部署（2026-10-27）

> **回应问题**：① `config_from_api.yaml` 与 `config.yaml` 的关系；② 本地部署 manager-web / manager-api / manager-mobile / xiaozhi-server 时，两个 yaml 能否合并、具体步骤。
> **研究对象**：[`demo/esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server)（`config.yaml` / `config_from_api.yaml` / `config/config_loader.py` / `config/settings.py` / `app.py`）+ [`docs/Deployment_all.md`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment_all.md) + [`docker-compose_all.yml`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/docker-compose_all.yml)。
> **实事求是纪律**：全部论断挂真相源（文件路径+行号）；外部行为（阿里云控制台等）为工程常识条目；判定为本项目技术判断（可争论）。
> **说明**：你的消息里第 3 条为空——如有后续问题请补充，本文只答 ①②。

---

## 0. 一句话结论（TL;DR）

| 问题 | 结论 |
|---|---|
| **Q1** 两个 yaml 的关系 | **不是"一个配置的两层"，而是"两种互斥模式的两个模板"**。`config.yaml`=本地模式默认全集；`config_from_api.yaml`=manager-api 模式的最小引导模板（复制改名为 `data/.config.yaml` 使用）。分流开关是 `.config.yaml` 里**有没有 `manager-api.url`**。**API 模式下 config.yaml 的模型配置全部失效**，配置改由智控台（MySQL）下发 |
| **Q2** 能否合并 | **不能合并——代码级禁止混合**（[`settings.py:23-33`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config/settings.py:23)：API 模式 + 文件里出现 `selected_module` → 直接抛错）。切换 = **用 config_from_api.yaml 的内容整体替换 `.config.yaml`**，模型 key 搬进智控台网页填 |
| **Q2** 部署方式 | 本地跑 4 个模块有两条路：**Docker 全模块（推荐，4 容器一次拉起）** 或 **源码全模块（MySQL+Redis+Java+Node+Python 各自起）**。`manager-mobile` 不作为本地服务——它是 uni-app 打包的移动端，连 manager-api 用 |

---

## 1. Q1：`config_from_api.yaml` 与 `config.yaml` 的关系

### 1.1 两个文件的身份

| | [`config.yaml`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml)（1176 行） | [`config_from_api.yaml`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config_from_api.yaml)（27 行） |
|---|---|---|
| **身份** | **本地模式**的"默认全集"模板 | **manager-api 模式**的"最小引导"模板 |
| **内容** | server/log/**selected_module**/**LLM/ASR/TTS/VAD/VLLM/Memory/Intent**/plugins/prompt 全套 | 只有 4 段：`server`（局部覆盖）+ `manager-api.url` + `manager-api.secret` + `prompt_template`（[`config_from_api.yaml:8-27`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config_from_api.yaml:8)） |
| **怎么用** | 不动它；用户覆盖写在 `data/.config.yaml` | **复制到 `data/` 改名 `.config.yaml`**（不是 import、不是合并） |
| **谁生效** | 本地模式下生效（全部） | API 模式下**模型配置不生效**，只剩 `server` 与 `prompt_template` 作为本地回落 |

### 1.2 运行时加载逻辑（真相源 [`config/config_loader.py:26-52`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config/config_loader.py:26)）

```python
# config_loader.py:35-46（简化）
default_config = read_config("config.yaml")           # 两个文件都被读
custom_config  = read_config("data/.config.yaml")

if custom_config.get("manager-api", {}).get("url"):   # ← 分流开关！
    config = await get_config_from_api_async(custom_config)   # API 模式
else:
    config = merge_configs(default_config, custom_config)     # 本地模式：深合并，用户层优先（:150-178）
```

**分流开关 = `data/.config.yaml` 里有没有 `manager-api.url` 这一个键。** 由此分成两种模式：

| | 本地模式（你现在的基线） | manager-api 模式（全模块） |
|---|---|---|
| `.config.yaml` 内容 | `selected_module` + `LLM/ASR/TTS` 等 key | `manager-api.url` + `manager-api.secret`（+ `server` 局部） |
| 模型配置来自 | **本地 YAML**（`config.yaml` 默认 + 覆盖） | **manager-api（Java + MySQL）**，在智控台网页改 |
| `read_config_from_api` | `False` | `True`（[`config_loader.py:65`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config/config_loader.py:65)） |
| `config.yaml` 的作用 | 默认全集（被覆盖合并） | **模型段全部被忽略**；仅 `server`(ip/port/http_port/vision_explain/auth_key) 与 `prompt_template` 本地回落（[`config_loader.py:71-83`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config/config_loader.py:71)） |
| 换模型的方式 | 改 YAML | 智控台【模型配置】网页 |
| OTA 端口 | `8003`（server 自带简单 OTA） | **`8002`**（manager 接管 OTA，见 Q2） |

### 1.3 代码级"防混线"（为什么不能合并）

两处明确禁止：

1. **启动检查直接抛错**（[`config/settings.py:23-33`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config/settings.py:23)）：

```python
if config.get("read_config_from_api", False):
    old_config_origin = read_config(custom_config_file)
    if old_config_origin.get("selected_module") is not None:   # API 模式 + 本地模型段
        raise ValueError("您的配置文件好像既包含智控台的配置又包含本地配置：…")
```

2. **config.yaml 头部声明**（[`config.yaml:5`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:5)）："如果你使用了智控台，那么以下所有配置，都不会生效，请在智控台中修改配置"。

> **因此**：`config_from_api.yaml` 与 `config.yaml` **在运行时不发生任何合并**——它们分属两条互斥路径。`config_from_api.yaml` 存在的唯一目的，就是替你把 `.config.yaml` 里可能残留的 `selected_module` 清干净，防止触发 1.3 的抛错。

### 1.4 `manager-api.secret` 是什么（澄清）

- 智控台部署时会生成一个 `server.secret` 参数（**每次从零部署都变**）；
- 把它填进 `.config.yaml` 的 `manager-api.secret`，xiaozhi-server 就用这个 token 调 manager-api 拉配置（[`config_from_api.yaml:24-25`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config_from_api.yaml:24)、[`Deployment_all.md:154-180`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment_all.md:154)）；
- 它同时兼作 JWT auth_key 的首选来源（[`app.py:50-62`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/app.py:50)）。

### 1.5 谁在消费这两个文件？（代码级核查 · 全仓 grep 实证）

> **核心结论先行**：**全仓只有一个模块在运行时读这两个 yaml——Python 的 `xiaozhi-server`（入口 `app.py`）**。`config_from_api.yaml` **不被任何代码读取**（`.py` 中零引用）；manager-api（Java）/ manager-web（Vue）/ manager-mobile（uni-app）**都不读这两个文件**。

**① `config_from_api.yaml`：零代码消费者（纯人工模板）**

全仓 `.py` 检索 `config_from_api`，命中 **0 处代码引用**——它只出现在两类地方：
1. 它自己的头部注释（[`config_from_api.yaml:1-7`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config_from_api.yaml:1)，教人"复制改名"）；
2. 错误提示文案（[`config/settings.py:31`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config/settings.py:31)：触发防混线时，错误信息里建议"将根目录的config_from_api.yaml文件复制到data下"）。

**它的"消费者"是部署文档与工程师的手——不是任何进程。**

**② `config.yaml` + `data/.config.yaml`：唯一的运行时读者 = Python xiaozhi-server**

| 消费点（全部在 `main/xiaozhi-server/` 内） | 角色 | 真相源 |
|---|---|---|
| `app.py`（进程入口）→ `load_config()` | 启动时读两个文件 → 得到全局 config dict | [`app.py:48`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/app.py:48)、[`config_loader.py:35-46`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config/config_loader.py:35) |
| `config/logger.py` → `check_config_file()` + `load_config()` | 日志初始化也经同一入口（顺带执行防混线检查） | [`logger.py:6,52-57`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config/logger.py:6)、[`settings.py:10-34`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config/settings.py:10) |
| `core/websocket_server.py` | API 模式下的配置热更新（重新 `get_config_from_api_async`） | [`websocket_server.py:34,168`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/websocket_server.py:34) |
| `core/connection.py` | 每连接读取 `read_config_from_api` 标志 + 拉设备私有配置 | [`connection.py:40,102`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/connection.py:40) |
| `core/http_server.py` | **OTA 分流**：本地模式由 8003 提供简单 OTA；API 模式交给 manager(8002) | [`http_server.py:37-46`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/http_server.py:37) |
| `core/api/vision_handler.py`、`core/handle/reportHandle.py`、`serverMessageHandler.py` | 视觉接口、ASR/TTS 上报、secret 校验——均按 `read_config_from_api` 分支 | [`vision_handler.py:104-108`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/api/vision_handler.py:104) |
| `performance_tester/*.py`（LLM/TTS/ASR/VLLM 压测） | 各测试脚本同样经 `load_config()` 取 provider 配置 | [`performance_tester_llm.py:538-540`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/performance_tester/performance_tester_llm.py:538) |
| `tests/conftest.py` | 测试**强制走文件合并路径**，且 fail-fast 拒绝 API 模式（避免 pytest 触发远程调用） | [`conftest.py:19-21,74-91`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/tests/conftest.py:19) |

**③ manager-api（Java）不读 yaml——它反而是"配置的提供方"**

API 模式的数据流向是**反向**的：

```
data/.config.yaml（只含 url+secret，引导用）
        |  HTTP GET（带 secret）
        v
manager-api ConfigController.java   <- 类注释原文："xiaozhi-server 配置获取"
        |  读 MySQL（你在智控台网页改的 selected_module/LLM/ASR/TTS 都存这里）
        v
xiaozhi-server 内存 config dict -> 初始化各 provider
```

真相源：[`manager-api/.../config/controller/ConfigController.java:20-22`](../esp32-s3-materials/xiaozhi-esp32-server/main/manager-api/src/main/java/xiaozhi/modules/config/controller/ConfigController.java:20)（类注释："xiaozhi-server 配置获取"）。manager-api 自己的运行配置是其 Spring Boot 的 `application.yml` + MySQL/Redis 连接参数（docker 里经环境变量注入，[`docker-compose_all.yml:45-52`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/docker-compose_all.yml:45)），与本项目的两个 yaml 无关。

**④ 一图总览（谁是读者、谁被读）**

```
                 +-- 只有 Python xiaozhi-server 读 --+
config.yaml -----|                                   |
（默认全集，总被读）|  app.py -> load_config()          |
                 |    |- 本地模式: merge 两个文件      |
data/.config.yaml|    |- API 模式: 只当"引导钥匙"      |
（用户覆盖层）     |        |  url + secret            |
                 +--------------|--------------------+
                                v HTTP
             manager-api(Java, 8002) --读--> MySQL <--写-- 智控台网页(manager-web / mobile)
```

> **直接回答你的问题**："谁会用到这两个 yaml？哪个 module？"——**只有 `xiaozhi-server` 这一个 Python 模块用**。`config.yaml` 是它每次启动都读的"默认底稿"；`data/.config.yaml` 是你的"覆盖层"（本地模式）或"引导钥匙"（API 模式）；`config_from_api.yaml` **没有任何模块读**，它是给人复制用的模板；manager 三件套（api/web/mobile）不读 yaml——它们是配置的**存储与编辑界面**（MySQL + 网页），其产物经 HTTP 被 xiaozhi-server 消费。

---

## 2. Q2：本地部署 manager-web / manager-api / manager-mobile / xiaozhi-server

### 2.1 先回答"能否合并两个 yaml"

**不能。** 正确动作是**替换，不是合并**：

```
① 备份基线：data/.config.yaml → data/.config.yaml.local-backup（保留你的智谱/阿里 key 备查）
② 删除/清空 data/.config.yaml
③ 复制 config_from_api.yaml → data/.config.yaml
④ 只改两个键：manager-api.url、manager-api.secret（见 2.4 第 ④⑤ 步）
⑤ 把基线里的 key 逐个搬进智控台网页【模型配置】（不是写回 yaml！）
```

> 若你把 `selected_module`/`LLM`/`ASR` 留在 API 模式的 `.config.yaml` 里，服务**启动即抛错**（§1.3）。

### 2.2 四个模块的部署形态（先认清谁是什么）

| 模块 | 形态 | 端口 | Docker 全模块里的角色 | 真相源 |
|---|---|---|---|---|
| **xiaozhi-server** | Python（conda/源码或镜像） | 8000 (WS) / 8003 (HTTP) | 独立容器 `xiaozhi-esp32-server` | [`docker-compose_all.yml:5-28`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/docker-compose_all.yml:5) |
| **manager-api** | Java Spring Boot | 8002 | 与 manager-web **合成一个镜像** `web_latest`（容器 `xiaozhi-esp32-server-web`） | [`docker-compose_all.yml:30-55`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/docker-compose_all.yml:30) |
| **manager-web** | Vue（构建后由 manager-api 静态托管） | 同 8002 | 同上（一个容器） | 同上 |
| **manager-mobile** | uni-app（Android/iOS/微信小程序） | — | **不作为本地服务**——用 HBuilderX 打包成 App，连 manager-api 的 8002 | [`main/README.md:63-69`](../esp32-s3-materials/xiaozhi-esp32-server/main/README.md:63) |
| （依赖）MySQL | 数据库 | 3306 | 容器 `xiaozhi-esp32-server-db` | [`docker-compose_all.yml:56-76`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/docker-compose_all.yml:56) |
| （依赖）Redis | 缓存 | 6379 | 容器 `xiaozhi-esp32-server-redis` | [`docker-compose_all.yml:77-90`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/docker-compose_all.yml:77) |

> **注意**：Docker 镜像仅 **x86**（[`Deployment_all.md:4`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment_all.md:4)）；arm64（RK3576）需自编译（[`docs/docker-build.md`](../esp32-s3-materials/xiaozhi-esp32-server/docs/docker-build.md)）。本机 x86 PC 无此问题。

### 2.3 路线 A：Docker 全模块（推荐，最省事）

真相源 [`Deployment_all.md` 方式一](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment_all.md)（手动部署 1.2 节）：

```
① 建目录：xiaozhi-server/{data, models/SenseVoiceSmall}
② 下载 docker-compose_all.yml → 放 xiaozhi-server/
③ 下载 config_from_api.yaml → 放 xiaozhi-server/data/ 改名 .config.yaml
   （⚠️ 若 data 下已有基线的 .config.yaml，先备份再替换——见 2.1）
④ （可选）下载 SenseVoiceSmall/model.pt 放 models/SenseVoiceSmall/（本地 ASR 备用）
⑤ 启动：docker compose -f docker-compose_all.yml up -d
⑥ 浏览器开 http://127.0.0.1:8002 → 注册第一个账号（=超级管理员）
```

**然后做"三件重要的事"**（真相源 [`Deployment_all.md:152-221`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment_all.md:152)，与 `config_from_api.yaml` 头部注释一致）：

| # | 事 | 操作 |
|---|---|---|
| ① | **打通 server↔manager-api** | 智控台【参数管理】→ 复制 `server.secret` 参数值 → 填入 `data/.config.yaml` 的 `manager-api.secret`；同时把 `manager-api.url` 改为 `http://xiaozhi-esp32-server-web:8002/xiaozhi`（容器内 DNS） |
| ② | **填模型 key** | 智控台【模型配置】→ 大语言模型 → 智谱AI → 填你的 key；ASR/TTS 同页配置（把基线 `.config.yaml` 里的 key 搬过来） |
| ③ | **下发设备地址** | 智控台【参数管理】→ `server.websocket` = `ws://<宿主机局域网IP>:8000/xiaozhi/v1/`；`server.ota` = `http://<宿主机局域网IP>:8002/xiaozhi/ota/` |

**重启 server 并自检**（真相源 [`Deployment_all.md:189-215`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment_all.md:189)）：

```
docker restart xiaozhi-esp32-server
docker logs -f xiaozhi-esp32-server      # 见 "Websocket地址是 ws://…:8000/xiaozhi/v1/" 即成功

设备端烧录地址：
  OTA:       http://<宿主机IP>:8002/xiaozhi/ota/     ← 全模块下 OTA 走 8002（manager 接管）
  WebSocket: ws://<宿主机IP>:8000/xiaozhi/v1/
```

> **与基线（单模块）的端口差别**：单模块 OTA=`8003`；**全模块 OTA=`8002`**（`8003` 只剩视觉接口）——设备里填 OTA 地址时必须区分（[`Deployment.md:241-246`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment.md:241) vs [`Deployment_all.md:205-215`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment_all.md:205)）。

### 2.4 路线 B：源码全模块（可调试，适合开发）

真相源 [`Deployment_all.md:230-493` 方式二](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment_all.md)：

```
① MySQL：本机安装或 docker run mysql:latest（建库 xiaozhi_esp32_server，utf8mb4）
② Redis：docker run redis（或本机）
③ manager-api：JDK + Maven，跑 main/manager-api（Spring Boot，8002）
④ manager-web：Node + npm，跑 main/manager-web（开发模式或 build 后由 manager-api 托管）
⑤ xiaozhi-server：按基线文档 §1 准备 conda 环境（libopus/ffmpeg + requirements.txt）
⑥ data/.config.yaml：用 config_from_api.yaml 内容替换，manager-api.url = http://127.0.0.1:8002/xiaozhi
⑦ manager-web 注册第一个账号（超级管理员）→ 按 2.3 三件事操作
⑧ python app.py 启动 xiaozhi-server
⑨ manager-mobile：HBuilderX 打开 main/manager-mobile 打包 App（可选，连 8002）
```

> 源码路线下 `manager-api.url` 用 **`http://127.0.0.1:8002/xiaozhi`**（非 docker 的容器名）；OTA=`http://127.0.0.1:8002/xiaozhi/ota/`（给设备填时换成宿主机局域网 IP）。

### 2.5 两条路线怎么选（对本项目）

| 场景 | 推荐 | 理由 |
|---|---|---|
| 当前基线验证（你正在做） | **保持本地模式（单模块）** | 最少依赖、配置即文件、不引入 MySQL/Redis/Java——符合"基线先跑起来"的目标 |
| 需要多用户/多设备/网页管理 | Docker 全模块（路线 A） | 4 容器一次拉起；模型 key 网页化；OTA/设备管理完备 |
| 要改 xiaozhi-server 源码（如 LifeOS 接缝） | 源码全模块（路线 B） | 可断点/热改；manager 部分仍可独立源码跑 |
| RK3576 边缘（场景 b） | **本地模式（单模块）** | 边缘轻量纪律（上位交底文档 §4.4 已裁决）；MySQL/Java 不进边缘 |

> **关键提醒**：**智控台一旦启用，`data/.config.yaml` 里的模型配置全部失效**（`config.yaml:5` + `settings.py` 防混线）。你现在的基线是"本地模式"，升级到"全模块"时 key 要**搬家**（YAML → 智控台网页），不要两边都留。

---

## 3. 你当前仓库状态的核验（顺手检查）

| 项 | 状态 | 依据 |
|---|---|---|
| `data/.config.yaml` 是否会进 git | ✅ **不会**——子模块自身 `.gitignore:156` 忽略 `main/xiaozhi-server/data` | `git check-ignore` 实测：`.gitignore:156:main/xiaozhi-server/data → main/xiaozhi-server/data/.config.yaml` |
| 子模块内已改动文件 | `Dockerfile-server`、`manager-web/package-lock.json`、`config_from_api.yaml`（你改了 `vision_explain` 为局域网 IP） | `git status --porcelain`（子模块内） |
| 密钥安全 | 智谱 key 与阿里 key 只存在于被忽略的 `.config.yaml` 中 | 同上 |

> 建议保持习惯：**密钥只写在 `data/.config.yaml`（被忽略）或智控台**，不要写进 `config.yaml`/`config_from_api.yaml` 这类**会被提交**的模板文件。

---

## 4. 决策建议（一句话）

1. **基线阶段（现在）**：留在本地模式，`data/.config.yaml` 用你已填的（智谱 + 阿里百炼 + EdgeTTS）——这是最短路径，`config_from_api.yaml` **不需要理会**（其头部第 1 行原话："如果你只想轻量化安装xiaozhi-server，只使用本地的配置文件，不需要理会这个文件"）。
2. **要智控台/多设备管理时**：整体**替换**（非合并）`.config.yaml` 为 config_from_api.yaml 内容，按 2.3 三件事操作，key 搬进网页。
3. **场景 b（RK3576 边缘）**：坚持本地模式单模块——MySQL/Redis/Java 不进边缘（对齐上位文档轻量纪律）。

---

## 5. 追问澄清：智控台是哪个 module？四种运行态有何区别？（2026-10-27 增补）

### 5.1 "智控台"是哪个 module？

**"智控台"= manager 三件套的统称**（管理控制台），不是一个独立的第五模块：

| 模块 | 在"智控台"里的角色 | 端口 | 真相源 |
|---|---|---|---|
| **manager-api**（Java） | 控制台的**后端**：REST API + 配置存储（MySQL）+ 给 xiaozhi-server 下发配置 | 8002 | [`main/README.md:90`](../esp32-s3-materials/xiaozhi-esp32-server/main/README.md:90)、[`ConfigController.java:20`](../esp32-s3-materials/xiaozhi-esp32-server/main/manager-api/src/main/java/xiaozhi/modules/config/controller/ConfigController.java:20) |
| **manager-web**（Vue） | 控制台的**网页前端**（你在浏览器开的那个界面） | 源码开发态 8001 / Docker 态由 manager-api 同容器托管（统一 8002） | [`main/README.md:89`](../esp32-s3-materials/xiaozhi-esp32-server/main/README.md:89)、[`docker-compose_all.yml:31-44`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/docker-compose_all.yml:31) |
| **manager-mobile**（uni-app） | 同一控制台的**移动版**（Android/iOS/小程序），连 manager-api | 无独立服务端口 | [`main/README.md:91`](../esp32-s3-materials/xiaozhi-esp32-server/main/README.md:91) |

> Docker 全模块里 `web_latest` 镜像 = manager-api + manager-web **打包在同一容器**，对外只开 8002（[`docker-compose_all.yml:31-44`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/docker-compose_all.yml:31)）——所以"打开 8002 就是智控台"。
> xiaozhi-server **不是**智控台的一部分——它是被智控台"管理"的引擎。

### 5.2 运行态辨析：先纠正一个前提

你的两种状态划分有一个**需要修正的点**：**"哪些模块在跑"不是状态的区分依据——`data/.config.yaml` 的内容才是**。manager 三件套在两种状态下都可以跑；真正的分岔在 xiaozhi-server 读到的那份 `.config.yaml` 里**有没有 `manager-api.url`**（[`config_loader.py:42`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config/config_loader.py:42)）。

因此实际存在**三种**（而非两种）有意义的运行态：

| 运行态 | `.config.yaml` 内容 | 在跑的模块 | xiaozhi-server 与 manager 的关系 |
|---|---|---|---|
| **S-A 单模块（你的基线）** | 从 `config.yaml` 摘的本地覆盖（selected_module + key，**无 manager-api 块**） | 只有 xiaozhi-server | 无 manager（不部署） |
| **S-B manager 空转** ⚠️ | 同 S-A（本地覆盖，无 manager-api 块） | 4 个模块全跑 | **manager 在跑但管不到它**——xiaozhi-server 从不连 manager-api（"半吊子"状态，能跑但白跑 manager） |
| **S-C 全模块（API 模式）** | 从 `config_from_api.yaml` 复制（url + secret，**无 selected_module**） | 4 个模块全跑 | 完整打通：启动拉配置、每设备拉私有配置、网页改即热生效 |

> 你提的"状态1"= S-B，"状态2"= S-C。**S-B 合法但不产生任何管理效果**——除非 `.config.yaml` 里有 `manager-api.url`，否则 xiaozhi-server 与 manager 之间没有任何运行时联系。

### 5.3 S-B 与 S-C 的运行时差异（逐条挂源）

| 维度 | S-B：manager 运行 + 本地模式 `.config.yaml` | S-C：manager 运行 + API 模式 `.config.yaml` | 真相源 |
|---|---|---|---|
| 启动时配置来源 | `config.yaml` + `.config.yaml` 文件合并 | HTTP 从 manager-api 拉取（url+secret 引导） | [`config_loader.py:42-46`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config/config_loader.py:42) |
| `read_config_from_api` | `False` | `True` | [`config_loader.py:65`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config/config_loader.py:65) |
| **改模型/换 provider** | 改 YAML 文件 + **重启** | 智控台网页改，**热生效**（websocket_server 重新拉取重建） | [`websocket_server.py:167-168`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/websocket_server.py:167) |
| **设备绑定/用户体系** | **无**——设备匿名直连 8000；manager 里的设备列表是空的 | **必须**——设备首次连接触发绑定码流程（`DeviceNotFoundException`/`DeviceBindException` → `need_bind=True`） | [`connection.py:800-830`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/connection.py:800)（本地模式直接 `need_bind=False` 返回，`:802-805`） |
| 每设备差异化配置 | 无（全设备共用同一份 YAML 配置） | 有（按 device-id/client-id 从 manager-api 拉私有配置） | [`connection.py:808-812`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/connection.py:808) |
| ASR/TTS 会话上报 | **关闭**（上报线程不启动） | 开启（上报到 manager 存 MySQL，智控台可查历史） | [`connection.py:733-736`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/connection.py:733)（`if not self.read_config_from_api ...: return`） |
| 对话记忆落盘 | 存**本地文件**（`save_to_file=True`） | 存 manager 侧（`save_to_file=False`） | [`connection.py:966-967`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/connection.py:966) |
| **OTA 接口** | xiaozhi-server **自己**在 8003 提供简单 OTA | 交给 manager（8002 的 `/xiaozhi/ota/`，参数 `server.ota` 下发）；8003 只剩视觉接口 | [`http_server.py:45-46`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/http_server.py:45)（注释原文："如果没有开启智控台，只是单模块运行，就需要再添加简单OTA接口"） |
| 消息 secret 校验 | 不校验 | 校验（serverMessageHandler 验 secret） | [`serverMessageHandler.py:19-21`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/handle/textHandler/serverMessageHandler.py:19) |
| 智控台网页的作用 | **零作用**（能登录、能看空列表，管不到这台 server） | **完全体**（改配置/绑设备/看会话/OTA/固件管理） | 综合 |
| 防混线检查 | 通过（无 manager-api.url，不触发） | 必须通过（文件里不得有 `selected_module`，否则启动抛错） | [`settings.py:23-33`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config/settings.py:23) |

### 5.4 一句话裁决

- **"哪些模块在跑"不重要，"`.config.yaml` 里有没有 `manager-api.url`"才是一切**——它把 xiaozhi-server 切成"文件驱动"（S-A/S-B）与"数据库驱动"（S-C）两种形态。
- **S-B 是最常见的误区**：把 4 个模块都跑起来，以为智控台就能管设备——实际上 xiaozhi-server 根本不看它；要么补上 url+secret 升级为 S-C，要么干脆别跑 manager（回到 S-A）。
- 对本项目：**基线与场景 b 用 S-A**（文件驱动、边缘轻量、设备匿名直连）；**需要多用户/多设备运营时才升 S-C**，且模型 key 要从 YAML"搬家"到智控台。

---

## 6. 览器打开 http://127.0.0.1:8002/

实战调试记录：`http://127.0.0.1:8002/xiaozhi/` 返回 401（2026-10-27）

> **现象**：Docker 全模块 4 容器全部 Healthy/Running，浏览器访问 `http://127.0.0.1:8002/xiaozhi/` 返回 `{"code":401,"msg":"Unauthorized","data":null}`，看不到智控台界面。
> **结论先行**：**这不是故障——是 URL 打错了。智控台网页在根路径 `http://127.0.0.1:8002/`，`/xiaozhi/` 是 API 上下文路径。401 恰恰证明整套链路是通的。**


### 6.2 正确操作（三步看到界面）

```
① 浏览器打开 http://127.0.0.1:8002/          ← 根路径，Vue 界面（注册/登录页）
② 注册第一个账号（= 超级管理员）                ← Deployment_all.md:150
③ 按本文 §2.3"三件事"继续（server.secret → 模型key → websocket/ota 参数）
```

**命令行自检（WSL 内）**：

```bash
# ① 静态界面：应返回 200 + HTML（Vue 的 index.html）
curl -i http://127.0.0.1:8002/

# ② API 文档页（白名单，应 200）
curl -i http://127.0.0.1:8002/xiaozhi/doc.html

# ③ 受保护 API（未带 token，返回 401 JSON = 正常）
curl -i http://127.0.0.1:8002/xiaozhi/

# ④ 看容器日志确认 Java 启动完成
docker logs --tail 50 xiaozhi-esp32-server-web
#   期望看到: Started AdminApplication in ... seconds
```

### 6.3 若根路径 `http://127.0.0.1:8002/` 也没有界面（排查清单）

| 症状 | 原因 | 处置 |
|---|---|---|
| 根路径 404 / whitelabel | 镜像里没有前端产物（本地构建镜像时 `npm run build` 失败或用了旧镜像） | 重新构建：`docker build -f Dockerfile-web -t xiaozhi-esp32-server:web_latest .`；确认构建日志无 npm 报错 |
| 根路径 502 | Nginx 起了但 Java 没起来（DB/Redis 未就绪） | `docker logs xiaozhi-esp32-server-web` 看 Java 报错；确认 db/redis 健康（你的 compose 已加 `condition: service_healthy`） |
| 界面能开但登录报错 | Redis/MySQL 连接异常 | 检查 compose 环境变量（`SPRING_DATASOURCE_DRUID_URL` 等）与容器网络 |
| 浏览器缓存旧页面 | — | Ctrl+F5 强刷 |

### 6.4 关于你发现"Deployment_all.md 4.运行manager-web程序似乎有错误"

该节属于**方式二（源码运行）**，与你当前的 Docker 方式**不适用**——两节的身份对不上是文档结构造成的混淆：

| | Docker 全模块（你当前） | 源码全模块（该节） |
|---|---|---|
| manager-web 形态 | 构建产物进镜像，由容器内 Nginx 托管 | `npm run serve` 起 **Vue 开发服务器** |
| 智控台地址 | **http://127.0.0.1:8002/**（根路径） | **http://127.0.0.1:8001**（Vue dev 端口，[`Deployment_all.md:320`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment_all.md:320)） |
| API 地址 | 同域 8002（Nginx 反代） | manager-api 独立 8002（前端经 `.env.development` 指向，[`Deployment_all.md:317-318`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment_all.md:317)） |

该节确实存在**文档缺陷**（本项目核实）：①"重要：注册成功后…填写智谱AI密钥"整段**重复粘贴了 3 次**（[`Deployment_all.md:323-330`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment_all.md:323)）；②未提示"Docker 方式下跳过本节"——建议向上游提 issue。另注意源码方式下 **Java 默认端口是 8002**（`application-dev.yml`/启动日志 `http://localhost:8002/xiaozhi/doc.html`，[`Deployment_all.md:298`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment_all.md:298)），与 Docker 内 8003 不同——两套端口体系不要混记。

### 6.5 下一步提醒（S-C 升级前置）

你现在跑的是 4 容器（S-B 空转态：`data/.config.yaml` 仍是基线本地模式）。要真正接入智控台：
1. 打开根路径注册超管 → 【参数管理】复制 `server.secret`；
2. **备份并替换** `data/.config.yaml` 为 `config_from_api.yaml` 内容（§2.1 步骤），`manager-api.url` 填 `http://xiaozhi-esp32-server-web:8002/xiaozhi`（容器内 DNS，Nginx→Java 同理）或 `http://host.docker.internal:8002/xiaozhi`（视网络模式）；
3. `docker restart xiaozhi-esp32-server` 后看日志确认"从API读取配置"；
4. 模型 key 在智控台【模型配置】里填（YAML 里的智谱/阿里 key 搬家）。

### 6.6 已确认打通 + 下一步精确值（2026-10-27 实测更新）

> **实测确认**：浏览器已打开 `http://127.0.0.1:8002/#/server-side-management`（Vue hash 路由），智控台界面正常——§6.1 的 Nginx(:8002)→Java(:8003)→MySQL 链路验证通过。

**接下来按序做（每步都有"为什么"）**：

| 步骤 | 操作 | 关键值/理由 |
|---|---|---|
| ① 注册超管 | 界面上注册第一个账号 | 第一个注册的账号自动成为超级管理员（[`Deployment_all.md:150`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment_all.md:150)） |
| ② 复制 secret | 【参数管理】→ 找参数编码 `server.secret` → 复制参数值 | 每次从零部署 manager 该值随机变化 |
| ③ 替换 `.config.yaml` | **备份** `data/.config.yaml` → 用 `config_from_api.yaml` 内容替换 → 填入： | 见下"两个易错值" |
| ④ 重启 server | `docker restart xiaozhi-esp32-server` → `docker logs -f xiaozhi-esp32-server` | 期望日志无 manager-api 连接报错；设备侧开始走绑定流程 |
| ⑤ 填模型 key | 智控台【模型配置】→ 大语言模型→智谱AI 填 key；语音识别→阿里百炼填 key | YAML 里的 key **搬家**到网页（S-C 模式下 YAML 模型段失效） |
| ⑥ 下发设备地址 | 【参数管理】→ `server.websocket` = `ws://<宿主机局域网IP>:8000/xiaozhi/v1/`；`server.ota` = `http://<宿主机局域网IP>:8002/xiaozhi/ota/` | 影响设备 websocket 发放与 OTA（[`Deployment_all.md:450-454`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment_all.md:450)） |

**两个易错值（针对你的 `docker-compose_all_local.yml`）**：

1. **`manager-api.url` 必须用容器 DNS，不能用 127.0.0.1**：
   ```yaml
   manager-api:
     url: http://xiaozhi-esp32-server-web:8002/xiaozhi   # ✅ 容器网络内可达（同 default 网络）
     # url: http://127.0.0.1:8002/xiaozhi               # ❌ 容器内的 127.0.0.1 是 xiaozhi-server 自己
     secret: <步骤②复制的 server.secret>
   ```
   依据：你的 compose 未声明独立网络 → 4 容器同在 `default` 网络，可用服务名互访（[`docker-compose_all_local.yml:13-14,35-36,89-90`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/docker-compose_all_local.yml:13)）；`/xiaozhi` 前缀由容器内 Nginx 反代到 Java:8003（[`nginx.conf:38-39`](../esp32-s3-materials/xiaozhi-esp32-server/docs/docker/nginx.conf:38)）。
2. **`server.websocket`/`server.ota` 必须填宿主机的局域网 IP**（不是 127.0.0.1）——这两个值会被 OTA 下发给 ESP32 设备，设备在自己网络里要用可路由地址。WSL 环境注意：Docker Desktop 端口映射后 `127.0.0.1` 仅本机有效；给真机用请填 Windows 主机的局域网 IP（`ipconfig` 查看），并确认防火墙放行 8000/8002/8003。

**验证 S-C 打通的标志**（`docker logs -f xiaozhi-esp32-server`）：
- 不再出现 `OTA接口是 http://...:8003/...`（该日志仅 S-A 本地模式打印，[`app.py:80-85`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/app.py:80)）；
- 设备连接时日志出现"异步获取差异化配置成功"（[`connection.py:815-817`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/connection.py:815)）或未绑定设备的绑定码提示。
- 测试不接真机也可：启动 `digital-human` 模块在浏览器走一轮对话（见 [`docs/digital-human-wakeword.md`](../esp32-s3-materials/xiaozhi-esp32-server/docs/digital-human-wakeword.md)）。

### 6.7 `.config.yaml` 核对结论与 `vision_explain` 该填什么（2026-10-28）

**① 用户替换后的 `.config.yaml` 核对：结构正确 ✅**

| 项 | 现值 | 判定 |
|---|---|---|
| 整体结构 | 与 `config_from_api.yaml` 一致，**无 `selected_module`**（防混线通过） | ✅ |
| `manager-api.url` | `http://xiaozhi-esp32-server-web:8002/xiaozhi` | ✅ 正确（容器 DNS；同 default 网络；Nginx→Java 同理） |
| `manager-api.secret` | 已填 UUID | ✅（应与智控台【参数管理】`server.secret` 一致，可回查核对） |
| `server.ip/port/http_port` | `0.0.0.0 / 8000 / 8003` | ✅ 默认即可（S-C 下这些以本地为准，[`config_loader.py:71-79`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config/config_loader.py:71)） |
| 无 `server.websocket` 键 | — | ✅ 正确——S-C 下 websocket/OTA 地址由智控台参数 `server.websocket`/`server.ota` 下发（8003 的简单 OTA 已停用） |
| `vision_explain` | `http://172.30.245.36:8003/mcp/vision/explain` | ⚠️ **需确认**（见②） |

**② `vision_explain` 该填什么——先明确"谁访问它"**

`vision_explain` 是**发给 ESP32 设备**的"拍照解释接口"地址：设备拍完照把 JPEG `multipart/form-data POST` 到这个 URL（对接小智 `Esp32Camera::Explain`）。**访问者是局域网里的设备，不是容器、不是你浏览器**——所以它必须是"设备可达"的地址：

```
ESP32(家里Wi-Fi) ──POST JPEG──> http://<地址>:8003/mcp/vision/explain
                                     └─ 8003 端口由 Python xiaozhi-server 提供（视觉分析接口）
                                        你的 compose 已映射 "8003:8003" ✅
```

**三种场景的正确填法**：

| 场景 | 填什么 | 说明 |
|---|---|---|
| **真机（推荐目标）** | `http://<Windows主机局域网IPv4>:8003/mcp/vision/explain` | Windows `ipconfig` 查"无线局域网适配器 WLAN"的 IPv4（如 `192.168.1.23`）；**Windows 防火墙需放行 8003 入站** |
| 只在本机测试 | `http://127.0.0.1:8003/mcp/vision/explain` | 仅本机可达 |
| 暂不用视觉 | 保留模板默认（含"你"字） | 系统启动时自动生成本机地址并打印在日志 |

**⚠️ 你现在的 `172.30.245.36` 很可能不对**：`172.16.0.0/12` 私有段常见于 **WSL2/Hyper-V 虚拟网卡**（Docker Desktop 后端）——**家里 Wi-Fi 的 ESP32 无法路由到它**。判定方法：Windows `ipconfig` 看 `172.30.245.36` 挂在哪个适配器下——
- 挂在 `vEthernet (WSL)` / `vEthernet (WSL (Hyper-V firewall))` → **LAN 设备不可达，必须换成物理网卡 IP**；
- 恰好是你物理网卡（校园网/企业网有时用 172.16/12）→ 可用，但设备须与主机同网段且防火墙放行。

**③ 连带提醒**：视觉接口要真正出结果，还需在智控台【模型配置】→ **视觉模型（VLLM）** 配一个多模态模型（如 `glm-4v-flash` 免费档）——否则接口通了也会因无 VLLM 报错；且 ESP32-S3-CAM 固件侧 `vision_explain` 地址是 OTA/初始化时下发的，**改完此值需重启 xiaozhi-server 并让设备重新拉取 OTA**。

### 6.8 对"vision_explain 两种填法"理解的修正（2026-10-28）

> 用户理解：① WSL 本机启动用 `172.30.245.36:8003`；② Docker 启动用 `http://xiaozhi-esp32-server:8003/...`。
> **修正：填写依据不是"server 用什么方式启动"，而是"谁要访问这个 URL"。** `vision_explain` 的消费者是**局域网里的 ESP32 设备**（它把 JPEG POST 过来），不是任何容器、也不是 server 自己。

**逐条判定**：

| 提法 | 判定 | 原因 |
|---|---|---|
| ① `http://172.30.245.36:8003/...`（WSL IP） | **半对**——仅当访问者也在 WSL/Windows 本机时成立 | WSL2 是 NAT 网络，**家里 Wi-Fi 的 ESP32 路由不到 WSL IP**；真机场景不可用（除非 Windows 加 `netsh portproxy` 转发或启用 WSL 镜像网络模式） |
| ② `http://xiaozhi-esp32-server:8003/...`（容器 DNS） | **错**——任何场景都不该用 | 容器 DNS 只在 Docker 网络内可解析；**ESP32 在容器网络之外**，根本解析不了这个名字。`vision_explain` 的消费者不是容器，用容器 DNS 毫无意义 |
| 真机正确值（Docker 或 WSL 启动皆同） | `http://<Windows主机局域网IPv4>:8003/mcp/vision/explain` | Docker Desktop 会把 8003 发布到 Windows 主机（compose `"8003:8003"`），LAN 设备经主机 IP 访问；WSL 直跑则需 `netsh portproxy` 把主机端口转发进 WSL |

**统一的判定规则（三个外发地址一起看）——"看消费者在哪里"**：

| 配置项 | 消费者 | 该填什么 | 你的现值 |
|---|---|---|---|
| `manager-api.url` | **xiaozhi-server 容器** | 容器 DNS：`http://xiaozhi-esp32-server-web:8002/xiaozhi` | ✅ 已对 |
| `server.vision_explain` | **局域网 ESP32 设备** | Windows 主机局域网 IP（非容器 DNS、非 WSL IP） | ⚠️ 需改 |
| 智控台 `server.websocket` / `server.ota` | **局域网 ESP32 设备** | Windows 主机局域网 IP（8000 / 8002） | 待在网页填 |

> 一句话：**容器间互访用容器 DNS；凡是"发给设备"的地址（vision_explain / websocket / ota）一律用设备的可路由地址（Windows 主机局域网 IP）**——这与 server 是 Docker 启动还是 WSL 启动无关。

### 6.9 浏览器实测解读：GET 返回的地址与 `.config.yaml` 不一致（2026-10-28）

> **现象**：浏览器打开 `http://172.30.245.36:8003/mcp/vision/explain`，返回"MCP Vision 接口运行正常，视觉解释接口地址是：`http://xiaozhi-esp32-server:8003/mcp/vision/explain`"——与文件里写的 `172.30.245.36` 不一样。
> **两条新信息**：① 视觉接口进程活着且 Windows 能访问 172.30.245.36；② **运行中容器内存里的 `vision_explain` 是 `xiaozhi-esp32-server:8003`（容器 DNS）——不是当前文件里的值**。

**① 根因：配置只在容器启动时加载一次——你现在文件里的值还没被加载**

- `get_vision_url` 只读 `config["server"]["vision_explain"]`，仅当值里含"你"占位符时才自动生成本机地址（[`core/utils/util.py:590-605`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/utils/util.py:590)）；
- `get_local_ip()` 走 UDP-connect 拿**容器 IP**，不可能返回容器名（[`util.py:68-77`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/utils/util.py:68)）；
- 所以 `http://xiaozhi-esp32-server:8003/...` 只能是**容器启动那一刻文件里就写着这个值**（对应你此前的"理解②"手动填过）——此后你把文件改回 `172.30.245.36`，但 **bind-mount 的文件改动不会进入已运行进程的内存**（配置有缓存，热更新仅在 API 模式由智控台触发，[`websocket_server.py:167-168`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/websocket_server.py:167)）。
- 你的 compose 输出也印证：`Container xiaozhi-esp32-server Running 0.0s`（**未被重建**，还是旧进程旧配置）。

**② 修复动作（顺序固定）**：

```
① 把 data/.config.yaml 的 vision_explain 定稿为设备可达地址：
     vision_explain: http://<Windows主机局域网IPv4>:8003/mcp/vision/explain   # 真机
     （仅本机测试可用 http://127.0.0.1:8003/...）
② docker restart xiaozhi-esp32-server          # 让新配置进内存
③ 浏览器重访 http://<同上地址>/mcp/vision/explain
     → 应回显"MCP Vision 接口运行正常，视觉解释接口地址是：<你刚填的值>"
④ 真机验证：从 ESP32 所在 Wi-Fi 的另一台电脑 curl 该地址，确认可达
```

**③ 三个地址的最终裁决（重申）**：

| 值 | 谁能访问 | 结论 |
|---|---|---|
| `http://xiaozhi-esp32-server:8003/...` | 仅 Docker 网络内容器 | ❌ 永远不要填——设备不可达 |
| `http://172.30.245.36:8003/...` | Windows 主机（WSL/Docker NAT 内部） | ⚠️ 仅本机测试；LAN 设备不可达 |
| `http://<Windows局域网IPv4>:8003/...` | Windows + 家里 Wi-Fi 的 ESP32 | ✅ 真机正确值（防火墙放行 8003） |

> 你浏览器能打开 172.30.245.36 只证明"Windows ↔ WSL/Docker 网络"互通，**不证明设备可达**——这正是 §6.8 规则的实际教训。

---

## 7. S-C（全模块/API 模式）联调测试步骤（2026-10-28）

> **前置状态**（你已完成）：4 容器运行；智控台可开（8002）；`.config.yaml` 已替换为 config_from_api 内容（url=容器 DNS、secret 已填、vision_explain 已定稿）。
> **测试目标**：验证 S-C 打通——xiaozhi-server 从 manager-api 拉配置、设备可绑定、一轮语音对话闭环、（可选）视觉闭环。

### 7.1 阶段一：重启 server 并确认"从API读取配置"

```bash
docker ps                                    # 确认 4 容器 Up/Healthy
docker restart xiaozhi-esp32-server
docker logs -f xiaozhi-esp32-server
```

**通过标准**：
- ✅ 日志出现 `从API读取配置`（[`settings.py:26`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config/settings.py:26)）；
- ✅ **不再出现** `OTA接口是 http://…:8003/…`（该行仅本地模式打印，[`app.py:80-85`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/app.py:80)）；
- ✅ 仍打印 `Websocket地址是 ws://…:8000/xiaozhi/v1/` 与 `视觉分析接口是 http://…:8003/mcp/vision/explain`（本机视角，正常）。

**失败对照**：`Failed to fetch server config from API` → url/secret 错（检查容器名拼写 `xiaozhi-esp32-server-web`、secret 是否为最新 `server.secret`）；防混线抛错 → 文件里残留 `selected_module`。

### 7.1.1 阶段一实测通过（2026-10-28 日志解读）——三个"看起来异常其实正常"的信号

实测日志（节选）：`从API读取配置` → `初始化组件: vad成功 VAD_SileroVAD` → `asr成功 ASR_FunASR`（FunASR 本地，SenseVoiceSmall 加载成功）→ **无 llm/intent/memory/tts 初始化行** → 无 `OTA接口是…8003` 行。

| 日志现象 | 判定 | 机制真相源 |
|---|---|---|
| `从API读取配置` 出现 | ✅ S-C 生效 | [`settings.py:26`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config/settings.py:26) |
| `OTA接口是…8003` 消失 | ✅ 预期（该行仅本地模式打印） | [`app.py:80-85`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/app.py:80) |
| provider 名变成 `VAD_SileroVAD` / `ASR_FunASR`（带前缀） | ✅ 正常——**这些是 manager-api 数据库里的默认模型条目名**（不再是 YAML 里的 `SileroVAD`/`AliyunBLStreamASR`） | 启动全局 init 按拉取的 `selected_module` 实例化（[`websocket_server.py:47-56`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/websocket_server.py:47)） |
| **YAML 里的 Aliyun ASR / 智谱 key 不再被加载** | ⚠️ **关键认知**：S-C 下 YAML 的模型段已让位于智控台——当前实际生效的是 **manager 默认的 FunASR（本地）**；要用阿里云/智谱，**必须去智控台【模型管理】配置并绑定到智能体** | [`config_loader.py:55-84`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config/config_loader.py:55) |
| 启动日志**没有** llm/intent/memory/tts 初始化行 | ✅ 正常——S-C 下这四类**按设备连接初始化**（设备连上后按其智能体私有配置实例化），启动只全局初始化共享的 VAD/ASR | [`connection.py:832-889`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/connection.py:832)（private_config 逐项 `init_llm/init_tts/init_memory/init_intent`）、[`websocket_server.py:53`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/core/websocket_server.py:53)（TTS 恒为 False） |
| FunASR 本地加载成功（`models/SenseVoiceSmall/model.pt`） | ✅ 离线兜底可用（compose 已挂载模型） | [`docker-compose_all_local.yml:27-28`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/docker-compose_all_local.yml:27) |
| 视觉 GET 200（来自 172.20.0.1 网关/172.30.240.1） | ✅ 接口健康；`172.20.0.4` 是 server 容器的 bridge IP | — |

> **阶段一判定：通过。** 当前生效的 ASR 是**智控台默认的 FunASR（本地）**——这就是"配置搬家"的实锤：下一步（阶段二）去智控台把阿里云 ASR / 智谱 LLM / EdgeTTS 配进【模型管理】并绑到智能体，才会真正用到你在 YAML 里准备的那套 key。

### 7.2 阶段二：智控台补配置（超管身份）

| # | 页面 | 操作 | 关键值 |
|---|---|---|---|
| ① | 参数管理 | `server.websocket` | `ws://<Windows局域网IP>:8000/xiaozhi/v1/` |
| ② | 参数管理 | `server.ota` | `http://<Windows局域网IP>:8002/xiaozhi/ota/` |
| ③ | 模型配置→大语言模型 | 智谱AI 填 key；模型名按你账号可用项（如 glm-5.3-flash） | YAML 里的 key 搬家到这 |
| ④ | 模型配置→语音识别 | 阿里百炼 Paraformer 填 key | — |
| ⑤ | 模型配置→语音合成 | EdgeTTS（免费，默认） | — |
| ⑥ | 模型配置→视觉模型 | glm-4v-flash（免费档）填 key | 不做视觉可跳过（拍照会报"未设置视觉模块"） |
| ⑦ | 智能体 | 给自己建一个智能体并绑定默认模型 | 设备绑定后按智能体配置跑 |

> **WSL/防火墙提醒**：①② 的 IP 必须是 Windows 物理网卡 IP（`ipconfig`），且放行 8000/8002/8003 入站——这两个值会下发给设备。

### 7.3 阶段三：设备接入（二选一，建议先 A 后 B）

**路线 A（无硬件，先验证服务端闭环）——digital-human 模块**：
```bash
# 在 main/digital-human 下按 docs/digital-human-wakeword.md 启动本地测试页
# 浏览器打开测试页 → 填服务器地址（websocket 用 ws://127.0.0.1:8000/xiaozhi/v1/ 本机可测）
# 页面上说话 → 观察识别文本与语音回复
```
> digital-human 走与小智固件相同的 WebSocket 协议（[`Deployment.md:244`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment.md:244)"如想测试websocket请启动digital-human模块"）。

**路线 B（真机 ESP32-S3-CAM）**：
```
① 烧录固件（虾哥 1.6.1+ 或自编译，docs/firmware-build.md）
② 设备配网（热点/BluFi）
③ 配网页面【高级选项】填 OTA 地址：http://<Windows局域网IP>:8002/xiaozhi/ota/   ← 注意是 8002！
④ 设备重启 → 自动从 OTA 拿 websocket 地址并连接
⑤ 智控台【设备管理】出现待绑定设备 → 输入设备播报的 6 位验证码完成绑定
```

### 7.4 阶段四：闭环验证清单（S-C 特有项打 ★）

| # | 验证项 | 通过标准 | S-C 特有 |
|---|---|---|---|
| V1 | 设备上线 | 智控台设备列表显示在线 | ★ 绑定流程走通 |
| V2 | 一轮语音对话 | 说话→回复音频；回答内容符合智能体人设 |  |
| V3 | 会话上报 | 智控台可见 ASR/TTS 会话记录 | ★（`connection.py:733-736` 仅 S-C 开上报） |
| V4 | 网页改配置热生效 | 智控台改 TTS 音色/人设 → 无需重启设备，下一轮生效 | ★（`websocket_server.py:168`） |
| V5 | 视觉闭环 | 对设备说"看看这是什么"→ 拍照上传 → VLLM 回答 | 依赖 ⑥+vision_explain 正确 |
| V6 | 记忆 | 关闭再打开设备，记忆延续（agent 记忆存 manager 侧） | ★（`connection.py:966` S-C 不落本地文件） |
| V7 | OTA | 智控台上传固件 → 设备自动升级 | ★ 走 8002 |

**失败速查**：设备连不上 → OTA 地址填成 8003（S-C 必须 8002）/ IP 不是局域网 IP / 防火墙拦截；识别成韩文 → ASR key 无效或未选模型；TTS 超时 → 关代理；401 → manager 重装过导致 `server.secret` 变了，重新复制并重启 server。

### 7.5 测试完成后的记录物（对齐 LifeOS 纪律）

- 截图/日志归档：`docker logs xiaozhi-esp32-server` 启动段、智控台设备列表、V2~V7 各一条证据；
- 在 [`技术交底_小智AI与ESP32-S3-CAM可行性_20261026.md`](技术交底_小智AI与ESP32-S3-CAM可行性_20261026.md) §5.2 场景 b 下补一条"实测记录"——把本文档从"代码级判断"升级为"真机验证"；
- 遗留问题（如 WSL 端口转发、防火墙策略）记入待办，供 RK3576 部署（§4.4）复用。
> WSL 直跑 + 真机的端口转发（若不用 Docker）：管理员 PowerShell 执行 `netsh interface portproxy add v4tov4 listenport=8003 listenaddress=0.0.0.0 connectport=8003 connectaddress=<WSL_IP>`（8000/8002 同理），并放行防火墙；Windows 11 22H2+ 也可在 `%UserProfile%\.wslconfig` 里设 `networkingMode=mirrored` 免转发。

---

## 附：真相源清单

| 论断 | 真相源 |
|---|---|
| 加载与分流逻辑 | [`config/config_loader.py:26-52`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config/config_loader.py:26)、深合并 [`:150-178`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config/config_loader.py:150) |
| API 模式回落规则 | [`config/config_loader.py:55-84`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config/config_loader.py:55) |
| 防混线抛错 | [`config/settings.py:23-33`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config/settings.py:23) |
| auth_key 优先级 | [`app.py:50-62`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/app.py:50) |
| config_from_api.yaml 用途注释 | [`config_from_api.yaml:1-7`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config_from_api.yaml:1) |
| 智控台覆盖声明 | [`config.yaml:5`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml:5) |
| Docker 全模块 4 容器 | [`docker-compose_all.yml:4-93`](../esp32-s3-materials/xiaozhi-esp32-server/main/xiaozhi-server/docker-compose_all.yml:4) |
| 全模块部署三件事 | [`docs/Deployment_all.md:152-221`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment_all.md:152) |
| manager-mobile 形态 | [`main/README.md:63-69`](../esp32-s3-materials/xiaozhi-esp32-server/main/README.md:63) |
| 单模块 vs 全模块 OTA 端口 | [`docs/Deployment.md:241-246`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment.md:241) vs [`docs/Deployment_all.md:205-215`](../esp32-s3-materials/xiaozhi-esp32-server/docs/Deployment_all.md:205) |
| 关联文档 | [`xiaozhi-esp32-server基线运行配置清单_20261026.md`](xiaozhi-esp32-server基线运行配置清单_20261026.md)、[`xiaozhi-esp32-server模型替换与独立部署指南_20261026.md`](xiaozhi-esp32-server模型替换与独立部署指南_20261026.md) |

---

## 8. 六位验证码不显示的排查（2026-10-29 实测）

> **现象**：ESP32-S3-CAM（面包板 `bread-compact-wifi-s3cam`）烧录固件、连上 Wi-Fi、reset 后，智控台【添加设备】（`http://127.0.0.1:8002`）一直等不到设备；设备端既没有在 LCD 上显示 6 位验证码，也没有语音播报。
> **本轮问题**：① `server.fronted_url` 要不要设？② [`main/Kconfig.projbuild:3`](../../main/Kconfig.projbuild:3) 的 `CONFIG_OTA_URL` 是否必须改？③ 主机的 `172.29.242.56` 与 portal 里填的地址对不上。

### 8.1 结论先行

**验证码由 manager-api（8002）生成，并通过设备 OTA 检查的响应下发；本轮实测服务端完全正常（能返回 `367761`），但没有任何设备 OTA 请求到达服务端**（DB `ai_device` 计数 = 0、`xiaozhi-esp32-server-web` 日志无 OTA POST 记录）。因此**根因在"设备没能成功请求到你们的 OTA 端点"**，而不是服务端不生成码。

具体是两个**地址问题**：
1. 主机 Wi-Fi 的 IPv4 现在是 **`10.87.159.102`**，但智控台里 `server.ota` / `server.websocket` 仍是**旧值 `172.29.242.56`**（DHCP 变更导致）。
2. 设备端 portal 里填的「自定义 OTA 地址」必须与"设备实际可达的 manager OTA 地址"一致，且要**真正持久化成功**（NVS `wifi/ota_url`）。

### 8.2 真相源（本轮实测）

**① 服务端直连测试（WSL 内 `curl POST /xiaozhi/ota/`，模拟设备）——服务端返回了验证码：**

```json
{"server_time":{"timestamp":1793248865170,"timeZone":"Asia/Shanghai","timezone_offset":480},
 "activation":{"code":"367761","message":"http://xiaozhi.server.com\n367761","challenge":"aa:bb:cc:dd:ee:ff"},
 "firmware":{"version":"1.0.0","url":"http://xiaozhi.server.com:8002/xiaozhi/otaMag/download/NOT_ACTIVATED_FIRMWARE_THIS_IS_A_INVALID_URL"},
 "websocket":{"url":"ws://172.29.242.56:8000/xiaozhi/v1/","token":"..."}}
```

由此可证：**验证码流程本身正常**；且响应里 `message` 前缀仍是默认 `http://xiaozhi.server.com`、`websocket.url` 仍是旧 IP `172.29.242.56`。

**② DB `sys_params`（`xiaozhi-esp32-server-db` 容器内查询）——三个值确认未更新：**

| param_code | param_value | 判定 |
|---|---|---|
| `server.fronted_url` | `http://xiaozhi.server.com` | ⚠️ 仍是默认（仅显示用） |
| `server.ota` | `http://172.29.242.56:8002/xiaozhi/ota/` | ❌ 旧 IP |
| `server.websocket` | `ws://172.29.242.56:8000/xiaozhi/v1/` | ❌ 旧 IP |
| `server.mqtt_gateway` | `null` | ✅（未用 MQTT） |

**③ DB `ai_device` 计数 = 0** → 设备从未成功完成过一次 OTA 注册（否则 `checkDeviceActive` 会入库）。

**④ 代码依据（为什么服务端一定能出码，而 DB 为空就说明没请求到）：**
- 入口：`OTAController.checkOTAVersion`（`POST /ota/`，[`OTAController.java:42-60`](../esp32-s3-materials/xiaozhi-esp32-server/main/manager-api/src/main/java/xiaozhi/modules/device/controller/OTAController.java:42)）。
- 分支：`DeviceServiceImpl.checkDeviceActive` —— **设备 MAC 不在库中（未绑定）→ 调 `buildActivation` 生成 6 位码**（[`DeviceServiceImpl.java:268-279`](../esp32-s3-materials/xiaozhi-esp32-server/main/manager-api/src/main/java/xiaozhi/modules/device/service/impl/DeviceServiceImpl.java:268)、[`:472-512`](../esp32-s3-materials/xiaozhi-esp32-server/main/manager-api/src/main/java/xiaozhi/modules/device/service/impl/DeviceServiceImpl.java:472)）。
- `buildActivation` 内部（[:483-486](../esp32-s3-materials/xiaozhi-esp32-server/main/manager-api/src/main/java/xiaozhi/modules/device/service/impl/DeviceServiceImpl.java:483)）：`RandomUtil.randomNumbers(6)` → `code`；`message = fronted_url + "\n" + code`；`challenge = deviceId`。
- 固件侧：`Ota::CheckVersion` 解析 `activation.code/message/challenge`（[`main/ota.cc:137-157`](../../main/ota.cc:137)）→ `Application::CheckNewVersion` 调 `ShowActivationCode`（[`main/application.cc:507-511`](../../main/application.cc:507)）→ **LCD 显示 + 逐个播报数字**（[`main/application.cc:728-750`](../../main/application.cc:728)）。

> **推断链**：服务端能出码（①）但 DB 为空（③）⇒ **设备从未成功 POST 到 `/ota/`** ⇒ 卡在"设备→OTA 端点的网络/地址"环节，而非服务端逻辑。

### 8.3 关键澄清：三个 server 参数各管什么

| 参数 | 作用 | 与验证码的关系 |
|---|---|---|
| **设备端 OTA 地址**（portal「自定义 OTA 地址」→ NVS `wifi/ota_url`） | 设备去"哪个地址"做 OTA 检查 | **决定能否拿到验证码**（S-C 必须指向 manager `:8002`） |
| `server.fronted_url` | `activation.message` 的**前缀文本**（"下发六位验证码时显示的控制面板地址"） | **不影响验证码本身**——不设也能收到/显示/播报 6 位码，只是 LCD 上那行 URL 显示为默认值 |
| `server.ota` | manager 侧固件下载 URL 重写（[:529-541](../esp32-s3-materials/xiaozhi-esp32-server/main/manager-api/src/main/java/xiaozhi/modules/device/service/impl/DeviceServiceImpl.java:529)）+ `GET /ota/` 健康检查（[`OTAController.java:77-93`](../esp32-s3-materials/xiaozhi-esp32-server/main/manager-api/src/main/java/xiaozhi/modules/device/controller/OTAController.java:77)） | 与验证码无关，但应改为当前 IP |
| `server.websocket` | 绑定成功后设备要连的 WebSocket 地址 | 旧 IP 会导致"码出现且绑定成功，但随后连不上" |

### 8.4 修复动作（按序）

```
① 智控台【参数管理】改三个值（把旧 IP 172.29.242.56 全部换成 10.87.159.102）：
     server.ota          = http://10.87.159.102:8002/xiaozhi/ota/
     server.websocket    = ws://10.87.159.102:8000/xiaozhi/v1/
     server.fronted_url  = http://10.87.159.102:8002          （可选，仅显示用）
② 设备重新进入配网模式 → 门户【高级选项 / Advanced】→「自定义 OTA 地址 / Custom OTA URL」
     填 http://10.87.159.102:8002/xiaozhi/ota/  → 保存 → 重启设备
③ 用 COM5 串口日志确认（关键判据）：
     - Ota: "Current version: ..." 与 HTTP 200（说明 OTA URL 正确、可达）
     - 屏幕出现"激活"页 + 6 位数字，并听到逐个数字播报
④ 智控台【设备管理】出现待绑定设备 → 输入 6 位验证码完成绑定
```

### 8.5 Q2 回答：`CONFIG_OTA_URL` 是否必须改？——**不必须**

运行优先级为 **NVS `ota_url`（门户保存） > `CONFIG_OTA_URL`（编译默认）**（[`main/ota.cc:56-63`](../../main/ota.cc:56)：先读 NVS，空则回落到 `CONFIG_OTA_URL`）。门户已成功保存自定义 OTA 地址，则编译默认值 `https://api.tenclass.net/xiaozhi/ota/` **不会被使用**。

若希望"烧录即默认连自建服务器、免门户设置"，则在 [`main/Kconfig.projbuild:3`](../../main/Kconfig.projbuild:3) 把 `OTA_URL` 默认值改为 `http://10.87.159.102:8002/xiaozhi/ota/` 后**重新编译烧录**；否则**无需重编译**。

### 8.6 一个必须留意的坑（本轮 IP 漂移的根因）

`172.29.242.56`（上一轮）与 `10.87.159.102`（本轮）都是**主机的 Wi-Fi IPv4**，由 DHCP 下发；主机重连 Wi-Fi / 换网络后 IP 会变，而智控台里 `server.ota`/`server.websocket`、设备门户里的 OTA 地址**都不会自动跟着变**。建议：
- 给主机 Wi-Fi 配置**静态 IP 或路由器 DHCP 保留**，锁定一个局域网 IP；
- 每次换网络后，核对"智控台参数 + 设备门户 OTA 地址"两处是否都指向当前 IP。

### 8.7 本轮诚实声明（边界）

- 已实测：服务端直连 `POST /ota/` 返回验证码；DB `sys_params` 现值；DB `ai_device` 计数 = 0；主机 Wi-Fi IPv4 = `10.87.159.102`；`172.29.242.56` 在本机不可路由。
- **未实测**：读取 ESP32 的 COM5 串口日志（未在本轮采集），因此"设备当前实际使用的 OTA URL / 失败原因"未逐字节确证——**§8.4 ③ 的串口日志是闭环的最后一环**。
- 用户反馈"另一台电脑可访问 `172.29.242.56:8002`"与"本机只能 `127.0.0.1:8002`"并不矛盾：前者走了 Windows→WSL 的端口发布，后者受本机回环/镜像网络策略影响；**关键不是本机能否访问，而是 ESP32 所在的 Wi-Fi 子网能否路由到该 IP**。

---

## 9. 复刷后仍无验证码——COM5 串口日志定位到"NVS 被清空"（2026-10-29 第二轮实测）

> **现象（用户回报）**：Wi-Fi 已切到 `netsecure`、IP = `10.87.159.102`；智控台【参数管理】四个 `server.*` 都已改为 `10.87.159.102`；**重新刷写设备固件后**，仍然没有出现"激活页 + 6 位码 + 语音播报"。
> **本轮动作**：抓取 COM5 串口日志（115200）+ 复查服务端。

### 9.1 结论先行（决定性证据）

**根因：复刷动作清空了设备的 NVS，Wi-Fi 凭据与门户里保存的自定义 OTA 地址一并丢失；设备因此停在 Wi-Fi 配网 AP 模式，根本没有连上 `netsecure`，也就从未发起 OTA 检查 → 不可能拿到验证码。**

串口日志关键行（实测）：

```
W (1019) SsidManager: NVS namespace wifi doesn't exist        ← NVS 里连 wifi 命名空间都没有
I (2529) StateMachine: State: starting -> wifi_configuring    ← 直接进入"配网模式"
I (2529) WifiManager: Starting config AP
I (2599) WifiConfigurationAp: Access Point started with SSID Xiaozhi-1189
I (2629) Application: Alert [gear] ... Xiaozhi-1189 ... http://192.168.4.1
```

- `SsidManager: NVS namespace wifi doesn't exist`（[`main/boards/common/wifi_board.cc:100-104`](../../main/boards/common/wifi_board.cc:100) 的 `TryWifiConnect()` 在 `GetSsidList()` 为空时进入配网）——**保存的 Wi-Fi SSID 列表为空**。
- 因此设备没有连接任何 AP，而是把自己变成热点 `Xiaozhi-1189`，等待用户扫码/连热点填 Wi-Fi。
- **没有任何 `Ota:` 日志**（没有 `Current version:`、没有 HTTP 200），印证"未发起 OTA 检查"。

### 9.2 服务端侧佐证（同一时间窗，无设备请求）

| 证据 | 值 | 含义 |
|---|---|---|
| `POST /ota/` 直连测试（WSL 内 curl） | 返回 `activation.code`（如 `367761`） | 服务端逻辑正常 |
| `docker logs xiaozhi-esp32-server-web`（近 90 分钟） | **无任何 OTA POST/activation 记录** | 设备没请求 8002 |
| `docker logs xiaozhi-esp32-server`（近 90 分钟） | 仅启动日志；8000/8003 无设备连接 | 设备也没连 WebSocket |
| DB `ai_device` 计数 | **0** | 设备从未注册成功 |

> DB `sys_params` 现值复核：`server.ota = http://172.29.242.56:8002/xiaozhi/ota/`、`server.websocket = ws://172.29.242.56:8000/xiaozhi/v1/`——**注意：查询时仍显示旧 IP `172.29.242.56`**，与"用户称已在智控台改成 10.87.159.102"不一致。需用户在智控台 UI 复核并**保存**（见 §9.4 ④）。

### 9.3 为什么"复刷会把 NVS 清空"——这是关键机制

本板 `sdkconfig` 里 `CONFIG_OTA_URL="https://api.tenclass.net/xiaozhi/ota/"`（编译默认仍是公网地址）。运行优先级为 **NVS `ota_url`（门户保存） > `CONFIG_OTA_URL`**（[`main/ota.cc:56-63`](../../main/ota.cc:56)）。

- 若刷新时执行了 **`idf.py erase-flash` / `idf.py erase_flash`**，或烧录脚本带 `--erase-all`，则**整个 NVS 分区被抹掉**：`wifi` 命名空间消失 → 无线凭据 + 门户 OTA 地址全部归零。
- 重新烧录 `xiaozhi.bin` 只写 app 分区，**不会**自动重建 NVS；设备从空白 NVS 启动即进入配网。
- 结果：即便你此前在门户里设过 `ota_url`，复刷后也没了，设备回到"首次使用"状态。

> **判据**：日志里 `SsidManager: NVS namespace wifi doesn't exist` 就是"配网状态无法从 NVS 读取"的直接证据；若 NVS 仍在，这里应读到已保存 SSID 并直接尝试连接。

### 9.4 修复动作（按序，必须重做配网）

```
① 设备当前处于配网 AP：用手机/电脑连热点 SSID = Xiaozhi-1189（无密码），
   浏览器打开 http://192.168.4.1
② 在门户【Wi-Fi 配置】页：选择并连接 netsecure（输入密码）→ 保存
   （此时设备才会真正连上 10.87.159.102 所在网段）
③ 在门户【高级选项 / Advanced】→「自定义 OTA 地址 / Custom OTA URL」：
   填 http://10.87.159.102:8002/xiaozhi/ota/  → 保存
④ （务必先做）在智控台 UI 复核并"保存"参数（DB 现仍显示旧 IP）：
     server.ota          = http://10.87.159.102:8002/xiaozhi/ota/
     server.websocket    = ws://10.87.159.102:8000/xiaozhi/v1/
     server.fronted_url  = http://10.87.159.102:8002          （可选）
⑤ 复位设备。COM5 期望日志：
     SsidManager 读到已保存 SSID → WifiBoard: Connected to netsecure
     Ota: Current version: 2.5.2  →  HTTP 200
     StateMachine: -> activating → LCD 显示 6 位码 + 逐个数字播报
⑥ 智控台【设备管理】出现待绑定设备 → 输入 6 位码完成绑定
```

### 9.5 避免复刷再次踩坑

- **改 OTA 地址请优先用"门户设置"或"智控台参数"**，不要依赖编译默认值；但要知道**任何 erase-flash 都会清掉门户设置**。
- 如需"烧录即用"（免每次配网）：把 [`main/Kconfig.projbuild:3`](../../main/Kconfig.projbuild:3) 的 `OTA_URL` 默认值改成 `http://10.87.159.102:8002/xiaozhi/ota/`，再编译；并把 Wi-Fi 凭据在代码/脚本中注入（或改用 BluFi 配网）。**同时给主机 Wi-Fi 设静态 IP / DHCP 保留**，否则 IP 再变又会失效。
- 若只是想保留 NVS：刷新时用 `idf.py flash`（不要 `erase-flash`），且确认未传 `--erase-all`。

### 9.6 本轮诚实声明（边界）

- 已实测：COM5 串口日志（NVS 缺失 + 进入配网 AP `Xiaozhi-1189` + 无 Ota 日志）；服务端无设备请求；DB `ai_device`=0；DB `sys_params` 仍为旧 IP。
- **未实测**：用户"已在智控台改成 10.87.159.102"与 DB 现值的差异原因（可能是未点保存 / 改了但未生效 / 查询时序差），需用户在 UI 复核；设备实际发起的 OTA URL（因当前处于配网态，尚未发起）亦未采到。
- 本板固件的板型与摄像头（日志示 `bread-compact-wifi-s3cam` + OV3660）与预期一致，非本次故障点。

---

## 10. 根因升级：本固件不支持 Wi-Fi Enterprise（802.1X），`netsecure` 无法连接（2026-10-29 第三轮）

> **新线索（用户提供）**：目标网络 `netsecure` 需要**用户名 + 密码**（即企业级认证 / 802.1X / WPA-Enterprise），与普通家用 WPA2-Personal（仅密码）不同。
> **用户追问**：是不是"配置界面没有配置 NVS"？

### 10.1 直接回答

**不是"界面没配置 NVS"——门户确实会把 SSID/密码写进 NVS。**（[`ssid_manager.cc:65-85`](../../managed_components/78__esp-wifi-connect/ssid_manager.cc:65) 的 `SaveToNvs` 写 `wifi` 命名空间的 `ssid/password/channel`；[`wifi_configuration_ap.cc:604-667`](../../managed_components/78__esp-wifi-connect/wifi_configuration_ap.cc:604) 也把 OTA URL 写进 NVS。）

**真正原因：本固件（`esp-wifi-connect` v3.3.1 + 本仓 main）根本不支持 Wi-Fi 企业级认证（802.1X / EAP），只能连"仅密码"的 WPA2-Personal。** 因此 `netsecure`（用户名+密码）**连不上**，设备只能停在配网 AP（`Xiaozhi-1189`），自然拿不到验证码。

> 附带说明：`SsidManager: NVS namespace wifi doesn't exist` 说明 NVS 里**没有已保存的网络**；这与"复刷清空 NVS"以及"从未成功保存过 netsecure"两个事实都吻合。但**即便手动往 NVS 里写 `netsecure` 的 SSID+密码也没用**，因为缺的是"企业认证所需的身份/证书"这一整套字段。

### 10.2 代码级证据（本固件没有 enterprise 通路）

| 检查点 | 结果 | 真相源 |
|---|---|---|
| 门户 Wi-Fi 表单字段 | **只有** `ssid` + `password`（无 username/identity/EAP/证书） | [`wifi_configuration.html:530-535`](../../managed_components/78__esp-wifi-connect/assets/wifi_configuration.html:530) |
| 门户提交 JSON | 只有 `ssid`、`password` | [`wifi_configuration.html:1619-1620`](../../managed_components/78__esp-wifi-connect/assets/wifi_configuration.html:1619) |
| NVS 存储结构 | 仅 `ssid/password/channel`（`ssid1..9` 同构），**无 identity/username/eap** | [`ssid_manager.cc:33-61`](../../managed_components/78__esp-wifi-connect/ssid_manager.cc:33) |
| STA 连接参数 | 只填 `wifi_config.sta.ssid` + `.password`（+channel/bssid），**未调用任何 `esp_eap_client_*` / `esp_wifi_sta_enterprise_enable()`** | [`wifi_station.cc:280-332`](../../managed_components/78__esp-wifi-connect/wifi_station.cc:280) |
| 全仓 `main/` 检索 `enterprise/802.1x/WPA2_ENT/esp_eap_client/sta.eap/identity` | **无 Wi-Fi EAP 实现**（命中项均为无关文件） | grep 实测 |
| 组件版本 | `78/esp-wifi-connect` **v3.3.1**（MIT） | [`idf_component.yml:18`](../../managed_components/78__esp-wifi-connect/idf_component.yml:18) |

> ESP-IDF 里连 WPA-Enterprise 需要：`esp_eap_client_set_identity/username/password/...` → `esp_wifi_sta_enterprise_enable()` → 再 `esp_wifi_connect()`。本固件这三步**一个都没有**。

### 10.3 判据：设备被卡在这一步

- 若 `netsecure` 是 **WPA2-Enterprise**：STA 只带密码去连，认证必然失败 → 反复重连 / 最终回落配网态。
- 若 `netsecure` 是 **开放 SSID + 网页门户认证（captive portal）**：STA 能"关联"上，但 TCP/HTTP 会被门户拦截，OTA 请求也到不了 8002 → 同样拿不到验证码。
- 两种情形下，串口都会表现为"没连上/连上但出不去"，与我们看到的"无 `Ota:` 日志、服务端零请求"一致。

### 10.4 可行方案（按推荐度）

| # | 方案 | 说明 | 代价 |
|---|---|---|---|
| **A（推荐）** | **给设备用 WPA2-Personal 网络**：手机热点、家用路由器、或另开一个仅密码的 Wi-Fi | 固件原生支持，立即可用：配网填 SSID+密码 → 连上 → OTA 出码 | 需一个仅密码 AP |
| **B** | 用一个 **WPA2-Personal 迷你路由器 / 手机热点做桥接**（AP 侧 PSK，上行接到 `netsecure`），设备连这个 PSK 网络 | 设备侧零改动；`10.87.159.102` 主机与该 PSK 网络同网段即可 | 需额外路由/热点，注意 NAT 后设备能否路由到主机 IP |
| **C（改动大）** | **给固件加 Wi-Fi Enterprise 支持**：扩展 `esp-wifi-connect`（门户加 identity/username/password/EAP 类型字段 → 存 NVS → 连接前调用 `esp_eap_client_set_*` + `esp_wifi_sta_enterprise_enable()`），并同步 `ssid_manager`/`wifi_station` | 只能解决"能连上 netsecure" | 属**共享组件改动**（跨所有板子），需回归测试；且常需 CA 证书/PEAP 配置，工程量 ★★★ |
| **D（不推荐）** | 直接改 `config.h` 去适配这台设备 | 违反 AGENTS.md「不得为适配不同硬件改板子引脚」精神，且 Wi-Fi 认证不是**板子引脚**问题，改板无用 | — |

> **结论**：这不是"界面漏配 NVS"，而是**能力缺口**。**最快路径是方案 A/B**（换一个仅密码的 Wi-Fi）。若必须用 `netsecure`，只能走方案 C 自行给固件加 802.1X 支持。

### 10.5 如何自证（下一步）

1. **确认 `netsecure` 的安全类型**：门户扫描接口 `/ap-list` 会返回每个 AP 的 `authmode`（[`wifi_configuration_ap.cc:337-341`](../../managed_components/78__esp-wifi-connect/wifi_configuration_ap.cc:337)）；或在手机 Wi-Fi 详情里看是否为"WPA2-Enterprise / 802.1X / EAP"。
2. **换到 WPA2-Personal 网络**（方案 A）后重做配网，观察 COM5 是否出现：
   - `SsidManager` 读到已保存 SSID → `WifiBoard: Connected to <ssid>`
   - `Ota: Current version: 2.5.2` + HTTP 200 → `activating` → LCD 出 6 位码 + 语音播报
3. 若必须用 `netsecure` 且愿改代码：走方案 C（改 `esp-wifi-connect`），改动完成后按 AGENTS.md 要求跑**代表性网络路径的构建 + 回归**。

### 10.6 本轮诚实声明（边界）

- 已核实：门户表单/提交/NVS/STA 连接四处**均无** enterprise 字段或调用；`main/` 无 EAP 实现；组件版本 v3.3.1。
- **未实测**：`netsecure` 的确切安全类型（Enterprise vs 开放+门户）与 ESP32 的实际失败码——建议按 §10.5 第 1 步确认；也未实测方案 A/B/C 的最终连通性。
- 结论"固件不支持 802.1X"为**源码级判定**；"因此连不上 netsecure"为**基于该判定的推断**，与串口/服务端两侧现象自洽。

---

## 11. 行动方案：主机保持 NTUsecure，另开 WPA2-Personal 热点给设备（2026-10-29 第四轮）

> **硬约束（用户明确）**：主机**必须留在 NTUsecure**——只有这样这个大模型（VSCode 里的 coding 助手）才可达；切到 `myoppo` 后助手就断线、无法协助调试。
> **矛盾**：NTUsecure 是**企业网（用户名+密码 / 802.1X）**，本固件不支持（§10）；而设备又必须连到一个 **WPA2-Personal** 网络才能出验证码。
> **用户问题**：我下一步要做什么？

### 11.1 裁决：用"主机同时做 STA + 软 AP"

一台主机**可以同时**：
- 以 **STA** 身份连 NTUsecure（→ 大模型可达，助手在线）；
- **额外广播一个 WPA2-Personal 软 AP（SSID+密码）**给 ESP32 连。

这样两个约束同时满足：**主机不离开 NTUsecure，设备又能连上"仅密码"网络**。

本机 Wi-Fi 硬件（实测）：`Killer(R) Wi-Fi 6E AX1675x`，驱动 `24.40.0.4`。
- `netsh wlan show drivers` 里 `Hosted network supported: No` **只代表旧的 `netsh wlan hostednetwork`（WLAN Hosted Network）API 被弃用**；
- Intel AX 系列改走 **Wi-Fi Direct / Windows 移动热点（Mobile Hotspot）**，**仍可用**。因此首选 **Windows 移动热点**。

### 11.2 首选路径：Windows 移动热点（Mobile Hotspot）——与 NTUsecure 并行

**步骤：**
```
① 保持主机 Wi-Fi 连在 NTUsecure（不要切走）。
② 打开：设置 → 网络和 Internet → 移动热点
   - "从以下位置共享我的 Internet 连接" = Wi-Fi（即 NTUsecure）
   - 编辑：设置网络名（如 Xiaozhi-AP）与密码（≥8 位，WPA2-Personal）
   - 打开"移动热点"
③ 记下热点网关 IP：Windows Mobile Hotspot 默认网段为 192.168.137.0/24，
   主机侧地址通常是 192.168.137.1（用 `ipconfig` 的"本地连接* N / Microsoft Wi-Fi Direct Virtual Adapter"确认）。
④ 智控台【参数管理】把三个值改为"设备可达"的热点网关 IP（不是 NTUsecure 的 10.87.159.102！）：
     server.ota         = http://192.168.137.1:8002/xiaozhi/ota/
     server.websocket   = ws://192.168.137.1:8000/xiaozhi/v1/
     server.fronted_url = http://192.168.137.1:8002            （可选）
⑤ 防火墙放行 8000/8002/8003 入站（已见有规则；确认对 192.168.137.0/24 生效）。
⑥ 设备复位 → 连热点 Xiaozhi-AP（填密码）→ 门户【高级选项】OTA 地址填
     http://192.168.137.1:8002/xiaozhi/ota/
⑦ COM5 期望：Connected to Xiaozhi-AP → Ota: ... HTTP 200 → activating → 6 位码 + 播报
⑧ 智控台【设备管理】输入 6 位码绑定。
```

**为什么地址要用 `192.168.137.1`（热点网关）而不是 `10.87.159.102`（NTUsecure）**：
- ESP32 连的是**热点网段** `192.168.137.0/24`，它去访问 `10.87.159.102`（NTUsecure 网段）通常**不可路由**（NTUsecure 通常会隔离客户端、禁止客户端互访）；
- 而 `192.168.137.1` 就是**主机在热点网段的自身地址**，设备在同一热点网段内可直达；
- xiaozhi 服务跑在 WSL（`networkingMode=mirrored`，监听 `0.0.0.0`），镜像网络下主机的 `192.168.137.1:8002` 应能转发到 WSL 的服务（若不通，见 11.4 备选）。

### 11.3 关键校验点（做之前先确认）

| 检查 | 命令 | 期望 |
|---|---|---|
| 移动热点能否开启 | 设置里"移动热点"开关是否可打开 | 可打开即支持 |
| 热点网段 | 开热点后 `ipconfig` 看 `192.168.137.1` 出现 | 出现该地址 |
| 服务是否在监听 | `netstat -ano \| findstr :8002`（Windows） | 有监听 |
| 设备能否到主机 | 设备串口看 DHCP 是否拿到 `192.168.137.x` + 是否 `Connected` | 拿到并可连 |

### 11.4 若移动热点不可用 / 不稳（备选）

| 备选 | 做法 | 说明 |
|---|---|---|
| **B1 第二块 USB Wi-Fi 网卡** | 用一根 USB Wi-Fi dongle 专做软 AP（`NETSH wlan set hostednetwork` 或第三方热点工具），主网卡保持 NTUsecure | 硬件方案，最稳；避免与主网卡争用 |
| **B2 手机热点** | 手机开 WPA2-Personal 热点，**但需手机同时能上网到大模型**（否则助手断线） | 只在手机热点也能访问大模型时可用 |
| **B3 带 4G/上行的小路由** | 旅行路由器 WAN 走手机热点/USB 供网，LAN 给设备；主机不参与 | 主机仍留在 NTUsecure |
| **B4 WSL 端口转发兜底** | 若镜像网络下 `192.168.137.1:8002` 不通：管理员 PowerShell `netsh interface portproxy add v4tov4 listenaddress=192.168.137.1 listenport=8002 connectaddress=<WSL_IP> connectport=8002`（8000/8003 同） | 确保热点网段能到 WSL 服务 |

### 11.5 为什么不选其它

- **不改主机网络**（不切 myoppo）：保证大模型/VSCode 助手在线——这是用户的核心约束。
- **不指望设备直连 NTUsecure**：固件无 802.1X（§10），此路不通。
- **不改固件加 802.1X**（§10 方案 C）：工作量大、且改的是跨所有板子的共享组件；非必要不推荐。

### 11.6 下一步清单（给用户）

1. 主机**保持 NTUsecure**。
2. 开 **Windows 移动热点**（SSID+密码，共享源=Wi-Fi），`ipconfig` 记下 `192.168.137.1`。
3. 智控台三参数改为 `192.168.137.1`（保存）。
4. 设备复位连热点 → 门户填 OTA `http://192.168.137.1:8002/xiaozhi/ota/`。
5. 看 COM5 出 6 位码 → 智控台绑设备。
6. 若第 3~5 步网络不通，按 11.4 B4 做端口转发，或改用 B1 第二网卡。

### 11.7 诚实声明

- 已实测：本机 Wi-Fi 型号（AX1675x）与驱动版本；`Hosted network supported: No`（旧 API）；当前 NTUsecure 的 IPv4；防火墙有 8000/8002/8003 入站规则。
- **未实测**：Windows 移动热点在本机/NTUsecure 策略下能否成功开启；热点开启后 `192.168.137.1:8002` 是否可达 WSL 服务；ESP32 连热点后的实际连通性。这些需按 §11.3 逐项验证。
- 未读取 `review/pic/wifi-ntusecure.png`（本会话模型无法解码图片）；对 NTUsecure 为"企业网"的判断来自用户文字描述（"需要用户名和密码"）与 §10 的固件能力判定。

---

## 12. §11 方案实测受阻：单射频 + 5GHz 企业网下 Mobile Hotspot 不可用（2026-10-29 第五轮）

> **用户实测**：`Xiaozhi-AP` 移动热点已创建并"启动"，但①**手机连接 `Xiaozhi-AP` 总是失败**；②智控台里**打不开 `http://192.168.137.1:8002/xiaozhi/ota/`**。

### 12.1 三条实测证据

| # | 证据 | 命令/来源 | 结果 |
|---|---|---|---|
| 1 | 本机 Wi-Fi 当前连接 | `netsh wlan show interfaces` | SSID=**NTUSECURE**，`Authentication = WPA2-Enterprise`，`Band = 5 GHz`，`Channel = 100`，速率 866.7Mbps |
| 2 | 只有一块物理 Wi-Fi 射频 | `Get-NetAdapter` | 物理仅 `Wi-Fi`（AX1675x）；其余为 Hyper-V 虚拟网卡与蓝牙；**无第二块物理网卡** |
| 3 | 热点网段地址存在 | `ipconfig` | `Local Area Connection* 2 (Microsoft Wi-Fi Direct Virtual Adapter #2) = 192.168.137.1`（Up/Connected） |
| 4 | 服务仅回环可达 | `Test-NetConnection` / WSL curl | `127.0.0.1:8002`=**True**；`192.168.137.1:8002`=**False**；WSL→`192.168.137.1:8002`=**000**（超时），WSL→`127.0.0.1:8002`=**200** |
| 5 | 转发脚本绑定失败 | `python scripts/hotspot_port_forward.py` | 绑定 `192.168.137.1` 报 `WinError 10049`（该地址在 Wi-Fi Direct 适配器上不可直接 bind）；已加 `0.0.0.0` 回退 |

> 注：`netsh interface portproxy` 需管理员权限（本会话无 UAC，无法执行）；`netsh wlan show drivers` 的 `Hosted network supported: No` 只代表旧 `hostednetwork` API 不可用。

### 12.2 根因（两层，叠加）

**第一层（硬件/驱动）：单射频并发不可靠。**
AX1675x 是**单射频**，当前以 **5GHz + WPA2-Enterprise** 锁定在 NTUSECURE 上。Windows 移动热点走 Wi-Fi Direct 虚拟适配器，需与主射频并发（STA+SoftAP）。在"5GHz 企业网 STA"下开 SoftAP，**很多 Intel/Killer 驱动会失败或只在受限频段广播**——这解释了"手机连 `Xiaozhi-AP` 总是失败"。`Local Area Connection* 2` 显示 Up 只代表虚拟适配器存在，**不代表 SoftAP 真的在对外广播可被关联的 BSS**。

**第二层（网络命名空间）：WSL mirrored 不暴露热点子网。**
`netsh wlan show interfaces` 证明服务仅经**回环**可达（`127.0.0.1:8002` OK），而 **Windows→`192.168.137.1:8002` 与 WSL→`192.168.137.1:8002` 均失败**。即便热点能广播，**热点客户端(192.168.137.x)也到不了运行在 WSL 里的 8002**——除非做端口转发（需管理员 portproxy，或运行用户态转发脚本）。

### 12.3 结论：单网卡无法同时满足"模型可达 + 设备可连"

用户的硬约束是"主机留在 NTUSECURE（否则 VSCode 里的模型断线）"，而设备只能连 WPA2-Personal。二者要同时成立，**主机必须同时处于两条网络路径**：
- 路径 P1：NTUSECURE ←→ 模型/互联网（现有内置 Wi-Fi）
- 路径 P2：某个 WPA2-Personal ←→ ESP32 设备 + xiaozhi 服务

**只有一块物理射频时，P1/P2 无法可靠共存。** 这就是本轮卡住的本质。

### 12.4 方案（按推荐度重排）

| # | 方案 | 是否需额外硬件 | 关键点 |
|---|---|---|---|
| **A（最简，零硬件）** | **换到一个"普通 WPA2-Personal 且有互联网"的 Wi-Fi**（家用/办公室路由器，非企业网） | 否 | 主机与该网络同网段→**模型可达**；ESP32 也连同一网络→**设备可连**；xiaozhi 服务地址=主机在该网络的 IPv4。**一步解决所有矛盾** |
| **B（需一块 USB Wi-Fi 网卡）** | 内置 Wi-Fi 留 NTUSECURE（模型）；**USB 网卡**广播 `Xiaozhi-AP`（WPA2-Personal）给设备 | 是（~¥几十的 USB Wi-Fi dongle） | 主机双网卡：P1=NTUSECURE，P2=dongle 热点；服务对 P2 子网可达（必要时用 `scripts/hotspot_port_forward.py` 或管理员 portproxy） |
| **C（需一台小路由）** | 旅行/迷你路由器：LAN 侧给设备 WPA2-Personal；主机经**第二网卡**(USB-Ethernet 或 USB-Wi-Fi)接入该路由 LAN | 是（路由 + 第二网卡） | 主机双归属：P1=NTUSECURE，P2=路由 LAN |
| **D（临时，可接受"模型离线几分钟"）** | 主机**临时切到 `myoppo` 手机热点**完成配网/绑定，再切回 NTUSECURE | 否 | 期间模型不可用；但步骤已在 §9/§10 写全，可离线照做；**绑定后设备仍需与服务器同网**，长期不可行 |
| ~~E~~ | 继续在内置单卡上折腾 Mobile Hotspot | 否 | 实测已失败（§12.1），且即便成功还要叠加 WSL 转发；**不建议** |

> **裁决**：**首选 A**——如果身边有任何"普通加密 Wi-Fi + 能上网（能访问到该模型）"的网络，主机与设备同连它即可，无需任何额外硬件与转发。若必须留在 NTUSECURE，则**必须走 B 或 C**（给主机增加第二条网络路径）。

### 12.5 若选 A：具体步骤（零硬件，最省事）

```
① 主机 Wi-Fi 连到"普通 WPA2-Personal + 有互联网"的路由器（设为 R）。
   - 验证：VSCode 里的模型仍可访问（说明 R 能出网到该模型）。
② 查看主机在 R 上的 IPv4：ipconfig 找到 Wi-Fi 的 IPv4（如 192.168.1.x）。
③ 智控台【参数管理】三个值改为该 IPv4：
     server.ota         = http://<R上的IPv4>:8002/xiaozhi/ota/
     server.websocket   = ws://<R上的IPv4>:8000/xiaozhi/v1/
     server.fronted_url = http://<R上的IPv4>:8002            （可选）
④ 确认 Windows 防火墙放行 8000/8002/8003 入站（已有规则）。
⑤ 若 R 上也访问不到 WSL 服务（mirrored 未暴露该网卡）：
   用管理员 PowerShell 做 portproxy，或运行 scripts/hotspot_port_forward.py：
     netsh interface portproxy add v4tov4 listenaddress=<R上的IPv4> listenport=8002 connectaddress=127.0.0.1 connectport=8002
     （8000/8003 同）
⑥ 设备配网连 R（WPA2-Personal）→ 门户填 OTA 地址（同③）→ COM5 出 6 位码 → 智控台绑定。
```

> 若 R 是家用路由器，通常**同一子网内客户端互访是允许的**，比 NTUSECURE 的企业隔离策略宽松得多，成功率最高。

### 12.6 若选 B（USB 网卡做设备专用 AP）

1. 插入 USB Wi-Fi 网卡，装好驱动（`Get-NetAdapter` 应出现第二块 Wi-Fi）。
2. 在"设置 → 移动热点"里，热点会使用**某一块** Wi-Fi 网卡；或改用虚拟 AP 工具指定 USB 网卡广播 `Xiaozhi-AP`（WPA2-Personal）。
3. 主机保持内置 Wi-Fi 连 NTUSECURE（模型在线）。
4. 服务对 `Xiaozhi-AP` 子网可达：用 `scripts/hotspot_port_forward.py`（已含 `0.0.0.0` 回退）或管理员 portproxy，把热点网关 IP 的 8000/8002/8003 转发到 `127.0.0.1`。
5. 设备连 `Xiaozhi-AP` → OTA 指向热点网关 IP → 出码 → 绑定。

### 12.7 下一步（请用户决策）

- 若**有普通可上网的 Wi-Fi** → 选 **A**（推荐，零硬件）。
- 若要**坚定留在 NTUSECURE** → 准备 **一块 USB Wi-Fi 网卡**（选 B），或一台小路由+第二网卡（选 C）。
- 仅当"只想先把设备绑上、可接受模型短暂离线"→ 选 **D**（临时），但长期仍需 A/B/C 之一。

### 12.8 本轮诚实声明

- 已实测：NTUSECURE = WPA2-Enterprise/5GHz/ch100；仅一块物理 Wi-Fi；`192.168.137.1` 存在但服务仅回环可达；热点 IP 无法直接 bind（10049）。
- **未实测**：不同硬件（USB 网卡/路由）下的成功率；方案 A 的 R 是否有；`portproxy` 在授权后是否彻底打通（本会话无管理员权限）。
- 本轮**未改动任何固件/服务配置**；仅新增用户态转发脚本 [`scripts/hotspot_port_forward.py`](../../scripts/hotspot_port_forward.py) 供方案 A/B 复用。
