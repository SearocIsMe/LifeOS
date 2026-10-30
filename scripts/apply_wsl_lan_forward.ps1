# ============================================================================
# apply_wsl_lan_forward.ps1
# 用途：让局域网设备（ESP32）经 Windows 主机 IPv4 访问 WSL 内的智控台/小智服务
# 依据：review/xiaozhi-server双配置文件关系与全模块本地部署_20261027.md §12.5（方案 A）
#
# 两种模式，脚本会自动判断：
#   [A] WSL 已启用 networkingMode=mirrored  -> 通常无需 portproxy，仅校验
#   [B] 仍为 NAT（或 mirrored 未暴露该网卡） -> 建立 8000/8002/8003 portproxy 到 127.0.0.1
#
# 必须在【管理员 PowerShell】中运行：
#   powershell -ExecutionPolicy Bypass -File scripts\apply_wsl_lan_forward.ps1
# 参数：
#   -ListenAddress 192.168.1.3   （默认自动取 Wi-Fi 的 IPv4）
#   -Remove                       （删除本脚本建立的三条规则）
# ============================================================================
param(
    [string]$ListenAddress = "",
    [switch]$Remove
)

$ErrorActionPreference = "Stop"
$Ports = @(8000, 8002, 8003)

function Assert-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Host "[FAIL] 需要管理员权限。请以【管理员 PowerShell】重新运行本脚本。" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] 管理员权限已确认"
}

function Resolve-ListenAddress {
    if ($ListenAddress) { return $ListenAddress }
    $ip = Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
        Where-Object { $_.InterfaceAlias -match "Wi-?Fi|WLAN" } |
        Select-Object -First 1 -ExpandProperty IPAddress
    if (-not $ip) {
        $ip = Get-NetIPAddress -AddressFamily IPv4 |
            Where-Object { $_.IPAddress -like "192.168.*" } |
            Select-Object -First 1 -ExpandProperty IPAddress
    }
    if (-not $ip) { throw "无法自动确定局域网 IPv4，请用 -ListenAddress 指定" }
    return $ip
}

function Get-WslNetworkingMode {
    $cfg = Join-Path $env:USERPROFILE ".wslconfig"
    if (-not (Test-Path $cfg)) { return "default(NAT)" }
    $m = Select-String -Path $cfg -Pattern "^\s*networkingMode\s*=\s*(\S+)" -AllMatches
    if ($m.Matches.Count -gt 0) { return $m.Matches[0].Groups[1].Value }
    return "default(NAT)"
}

function Test-Listening([int]$port) {
    return [bool](Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
}

Assert-Admin
$listen = Resolve-ListenAddress
$mode = Get-WslNetworkingMode

Write-Host ""
Write-Host "=== 现状 ===" -ForegroundColor Cyan
Write-Host ("监听地址    : {0}" -f $listen)
Write-Host ("WSL 网络模式: {0}" -f $mode)
foreach ($p in $Ports) {
    $st = if (Test-Listening $p) { "LISTEN" } else { "未监听" }
    Write-Host ("端口 {0}     : {1}" -f $p, $st)
}

if ($Remove) {
    Write-Host ""
    Write-Host "=== 删除本脚本的 portproxy 规则 ===" -ForegroundColor Yellow
    foreach ($p in $Ports) {
        netsh interface portproxy delete v4tov4 listenaddress=$listen listenport=$p 2>$null | Out-Null
        Write-Host ("  已删除 {0}:{1}" -f $listen, $p)
    }
    Write-Host ""
    Write-Host "剩余规则：" -ForegroundColor Cyan
    netsh interface portproxy show v4tov4
    exit 0
}

Write-Host ""
if ($mode -eq "mirrored") {
    Write-Host "[INFO] mirrored 模式：主机端口应已直接映射到 WSL 进程，先做连通性校验。" -ForegroundColor Yellow
    Write-Host "       若某些端口在 LAN 不可达（个别网卡未镜像），再对本脚本加 -ForceProxy。" -ForegroundColor Yellow
    $proxy = $false
} else {
    Write-Host "[INFO] NAT 模式：需要 portproxy 转发。connectaddress 用 127.0.0.1（对 NAT/mirrored 均有效）。" -ForegroundColor Yellow
    $proxy = $true
}
if ($args -contains "-ForceProxy") { $proxy = $true }

if ($proxy) {
    Write-Host ""
    Write-Host "=== 建立 portproxy（幂等：先删后加）===" -ForegroundColor Cyan
    foreach ($p in $Ports) {
        netsh interface portproxy delete v4tov4 listenaddress=$listen listenport=$p 2>$null | Out-Null
        netsh interface portproxy add v4tov4 listenaddress=$listen listenport=$p connectaddress=127.0.0.1 connectport=$p | Out-Null
        $ok = $LASTEXITCODE -eq 0
        Write-Host ("  {0}:{1} -> 127.0.0.1:{1}  [{2}]" -f $listen, $p, $(if ($ok) { "OK" } else { "FAIL" }))
    }
    Write-Host ""
    Write-Host "=== 当前规则 ===" -ForegroundColor Cyan
    netsh interface portproxy show v4tov4
}

Write-Host ""
Write-Host "=== 防火墙入站（80/8000/8002/8003）===" -ForegroundColor Cyan
foreach ($p in @(80, 8000, 8002, 8003)) {
    $rule = Get-NetFirewallRule -DisplayName "LifeOS-WSL-$p" -ErrorAction SilentlyContinue
    if (-not $rule) {
        New-NetFirewallRule -DisplayName "LifeOS-WSL-$p" -Direction Inbound -Action Allow `
            -Protocol TCP -LocalPort $p -Profile Private,Domain | Out-Null
        Write-Host ("  已创建放行规则 TCP {0} (Private,Domain)" -f $p)
    } else {
        Write-Host ("  规则已存在 TCP {0}" -f $p)
    }
}

Write-Host ""
Write-Host "=== 完成。下一步在【本机与设备同网段的另一台机器/手机】验证： ===" -ForegroundColor Green
Write-Host ("  浏览器打开 http://{0}:8002/  （智控台根路径，不是 /xiaozhi/）" -f $listen)
Write-Host ("  设备 OTA          http://{0}:8002/xiaozhi/ota/" -f $listen)
Write-Host ("  WebSocket         ws://{0}:8000/xiaozhi/v1/" -f $listen)
Write-Host ""
Write-Host "若 mirrored 模式下仍不通：加 -ForceProxy 再跑一次。" -ForegroundColor Yellow
