# probe_ports.ps1 -- xiaozhi service reachability probe (ASCII only, PS 5.1 safe)
#
# IMPORTANT (mirrored mode): probing "host LAN IP from the host itself" gives a
# FALSE NEGATIVE under WSL networkingMode=mirrored. The authoritative test is
# done inside WSL via its eth2 (LAN) interface:
#     wsl bash -c "curl --interface 192.168.1.3 http://192.168.1.3:8002/"
# This script therefore runs the LAN probe through WSL, plus the local ones.
param([string]$ListenAddress = "192.168.1.3")

function Probe([string]$target, [int]$port) {
    $c = New-Object System.Net.Sockets.TcpClient
    try { return ($c.ConnectAsync($target, $port).Wait(3000) -and $c.Connected) }
    catch { return $false } finally { $c.Dispose() }
}

function HttpProbe([string]$url) {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5 -MaximumRedirection 0 -ErrorAction Stop
        return [string]$r.StatusCode
    } catch {
        $resp = $_.Exception.Response
        if ($resp) { return ([string][int]$resp.StatusCode) }
        return "NO_RESPONSE"
    }
}

function WslHttp([string]$url, [string]$iface) {
    $cmd = "curl -s -o /dev/null -w '%{http_code}' --interface $iface --max-time 6 '$url' || echo FAIL"
    $out = & wsl bash -c $cmd 2>$null
    if (-not $out) { return "NO_RESPONSE" }
    return ($out | Select-Object -Last 1).ToString().Trim()
}

Write-Host "=== 1) local loopback (host -> WSL) ===" -ForegroundColor Cyan
foreach ($p in @(8000, 8002, 8003)) {
    $ok = Probe "127.0.0.1" $p
    Write-Host ("  127.0.0.1:{0}  {1}" -f $p, $(if ($ok) { "OK" } else { "FAIL" })) -ForegroundColor $(if ($ok) { "Green" } else { "Red" })
}

Write-Host ""
Write-Host "=== 2) LAN (authoritative: from WSL eth2) ===" -ForegroundColor Cyan
# NOTE: "${ListenAddress}" braces are REQUIRED - "$ListenAddress:8002" is parsed
# by PowerShell as a scope/drive qualifier ($var:) and silently yields empty.
foreach ($u in @(
    "http://${ListenAddress}:8002/",
    "http://${ListenAddress}:8002/xiaozhi/ota/",
    "http://${ListenAddress}:8000/xiaozhi/v1/",
    "http://${ListenAddress}:8003/mcp/vision/explain"
)) {
    $code = WslHttp $u $ListenAddress
    Write-Host ("  {0,-50} {1}" -f $u, $code) -ForegroundColor $(if ($code -match '^\d{3}$') { "Green" } else { "Red" })
}

Write-Host ""
Write-Host "=== 3) note ===" -ForegroundColor Yellow
Write-Host "  Host->own-LAN-IP probes (Invoke-WebRequest to $ListenAddress from Windows)"
Write-Host "  are NOT meaningful under mirrored mode; use a second LAN device (phone/ESP32)."
