$ErrorActionPreference = "Stop"

$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
$nodeExecutable = if ($nodeCommand) {
    $nodeCommand.Source
} else {
    Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
}

if (-not (Test-Path -LiteralPath $nodeExecutable)) {
    throw "Node.js was not found. Install Node.js 22 or newer, then run pnpm run pair."
}

& $nodeExecutable (Join-Path $PSScriptRoot "pair-device.mjs")

Write-Host ""
Read-Host "Keep this code private. Press Enter to close this window"
