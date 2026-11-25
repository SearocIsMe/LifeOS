# 额外的信任根（项目内自定义 CA bundle）

本目录的 PEM 会被 ESP-IDF 的 `gen_crt_bundle.py` **合并进固件内置 CA bundle**，
用于补齐「预置 bundle 里没有、但我们的服务端链路需要」的信任根。

启用方式（`sdkconfig.defaults` 已配置）：

```
CONFIG_MBEDTLS_CUSTOM_CERTIFICATE_BUNDLE=y
CONFIG_MBEDTLS_CUSTOM_CERTIFICATE_BUNDLE_PATH="certs/root_ye.pem"
```

> 路径**相对项目根目录**（即 `xiaozhi-esp32-2.5.2/`），不是相对 `main/`。
> 也可以指向本目录（`"certs"`），脚本会读取目录内所有 `.pem`/`.der`。

## 为什么需要 `root_ye.pem`

`tokynflow.com` 当前的 Let's Encrypt 证书链是：

```
tokynflow.com  <-  YE2  <-  Root YE  <-  ISRG Root X2  <-  ISRG Root X1
```

其中 `Root YE` 的完整 DN 是 `C=US, O=ISRG, CN=Root YE`，属于 ISRG 的新根，
**不在**任何 ESP-IDF 预置 bundle（`cacrt_all.pem` / `cacrt_deprecated.pem` /
`cacrt_local.pem`）中。ESP32 的 `esp_crt_find_cert()` 只按 issuer 的 DER 名字
在 bundle 里做二分查找，查不到就报：

```
esp-x509-crt-bundle: No matching trusted root certificate found
esp-tls-mbedtls: mbedtls_ssl_handshake returned -0x3000
```

## 为什么不用 `cacrt_local.pem`

`components/mbedtls/CMakeLists.txt` 里有明确条件：

```cmake
if((CONFIG_MBEDTLS_CERTIFICATE_BUNDLE_DEFAULT_FULL OR ..._CMN)
    AND NOT CONFIG_MBEDTLS_CERTIFICATE_BUNDLE_CROSS_SIGNED_VERIFY)
    list(APPEND crt_paths ${DEFAULT_CRT_DIR}/cacrt_local.pem)
endif()
```

本固件开启了 `CONFIG_MBEDTLS_CERTIFICATE_BUNDLE_CROSS_SIGNED_VERIFY=y`，
**所以 `cacrt_local.pem` 根本不会被并入**。而且它在 ESP-IDF 安装目录内，
会被 `install.bat` / IDF 升级覆盖。`CONFIG_MBEDTLS_CUSTOM_CERTIFICATE_BUNDLE`
没有这两个问题。

## 重新签发证书后要做什么

1. 重新抓链并确认新的根：

```bat
(echo Q | C:\ProgramData\anaconda3\Library\bin\openssl.exe s_client ^
  -connect tokynflow.com:443 -servername tokynflow.com -showcerts -tls1_2) ^
  > reports\chain_new.pem 2>nul

C:\ProgramData\anaconda3\python.exe scripts\tls_chain_probe.py ^
  reports\chain_new.pem --host tokynflow.com
```

2. 若新根仍不在预置 bundle 里，替换本目录的 PEM 并重新构建：

```bat
C:\ProgramData\anaconda3\python.exe scripts\extract_chain_cert.py ^
  reports\chain_new.pem certs\root_new.pem --index <根所在的序号>
```

3. 构建后**必须验构建产物**（不是看源 PEM）：

```bat
C:\ProgramData\anaconda3\python.exe scripts\crt_bundle_inspect.py ^
  build\x509_crt_bundle.S --want "Root YE"
```

判据：`PRESENT`，且证书总数比改动前多 1（当前为 145，改后应为 146）。
