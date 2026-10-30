# read_serial.ps1 -- capture serial output from an ESP32 (ASCII only, PS 5.1 safe)
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\read_serial.ps1 -Port COM10 -Seconds 45
#   ... -Baud 115200 (default)
param(
    [string]$Port = "COM10",
    [int]$Baud = 115200,
    [int]$Seconds = 45,
    [string]$OutFile = ""
)

$ErrorActionPreference = "Stop"

Write-Host "Opening $Port @ $Baud ..." -ForegroundColor Cyan
$sp = New-Object System.IO.Ports.SerialPort $Port, $Baud, 'None', 8, 'One'
$sp.ReadTimeout = 500
$sp.DtrEnable = $false
$sp.RtsEnable = $false

try {
    $sp.Open()
} catch {
    Write-Host "[FAIL] Cannot open $Port : $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "  - close any other serial monitor (idf.py monitor / Arduino IDE / PuTTY)" -ForegroundColor Yellow
    Write-Host "  - verify the port name in Device Manager" -ForegroundColor Yellow
    exit 1
}

Write-Host "Capturing for $Seconds s. RESET the device now (press RST/EN). Ctrl+C to stop." -ForegroundColor Yellow
$deadline = (Get-Date).AddSeconds($Seconds)
$lines = New-Object System.Collections.Generic.List[string]
$buf = ""

while ((Get-Date) -lt $deadline) {
    try {
        $chunk = $sp.ReadExisting()
        if ($chunk) {
            $buf += $chunk
            while ($buf.Contains("`n")) {
                $idx = $buf.IndexOf("`n")
                $line = $buf.Substring(0, $idx).TrimEnd("`r")
                $buf = $buf.Substring($idx + 1)
                $lines.Add($line)
                Write-Host $line
            }
        }
    } catch { Start-Sleep -Milliseconds 50 }
}
if ($buf.Length -gt 0) { $lines.Add($buf); Write-Host $buf }

$sp.Close()
$sp.Dispose()

Write-Host ""
Write-Host ("Captured {0} lines." -f $lines.Count) -ForegroundColor Cyan

if ($OutFile) {
    $lines | Set-Content -Path $OutFile -Encoding UTF8
    Write-Host "Saved to $OutFile"
}

# --- quick signal summary (what the operator usually needs first) ---
Write-Host ""
Write-Host "=== signal scan ===" -ForegroundColor Cyan
$patterns = @{
    "wifi connected"     = "wifi|Wi-Fi|WIFI|sta ip|got ip|IP:"
    "ota request"        = "Ota|OTA"
    "ota http status"    = "HTTP/1\.1|status|200|404|401|500"
    "activation"         = "activat|激活|验证码|code"
    "websocket"          = "websocket|ws://|Hello"
    "error/fail"         = "error|ERROR|fail|FAIL|failed|失败"
}
foreach ($k in $patterns.Keys) {
    $hits = $lines | Where-Object { $_ -match $patterns[$k] }
    if ($hits) {
        Write-Host ("  [{0}] {1} hit(s)" -f $k, $hits.Count) -ForegroundColor Green
        $hits | Select-Object -Last 3 | ForEach-Object { Write-Host ("      " + $_) -ForegroundColor Gray }
    } else {
        Write-Host ("  [{0}] none" -f $k) -ForegroundColor DarkGray
    }
}
