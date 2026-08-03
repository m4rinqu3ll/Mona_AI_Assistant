$ErrorActionPreference = "Stop"

$tailscale = "C:\Program Files\Tailscale\tailscale.exe"
if (-not (Test-Path -LiteralPath $tailscale)) {
    throw "Tailscale is not installed in the expected location."
}

$localMoMo = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:3000/" -TimeoutSec 10
if ($localMoMo.StatusCode -ne 200) {
    throw "MoMo is not available on localhost port 3000."
}

Write-Host "Enabling MoMo's private Tailscale HTTPS link..." -ForegroundColor Cyan
Write-Host "This uses Tailscale Serve, not public Funnel." -ForegroundColor DarkGray
Write-Host ""

& $tailscale serve --bg 3000
if ($LASTEXITCODE -ne 0) {
    throw "Tailscale Serve setup did not complete."
}

Write-Host ""
& $tailscale serve status
Write-Host ""
Read-Host "Private setup complete. Press Enter to close this window"
