$ErrorActionPreference = "Stop"

$modelDirectory = Join-Path $PSScriptRoot "..\models"
$modelPath = Join-Path $modelDirectory "qwen2.5-1.5b-instruct-q4_k_m.gguf"
$modelUrl = "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"

New-Item -ItemType Directory -Force -Path $modelDirectory | Out-Null
if (Test-Path -LiteralPath $modelPath) {
    Write-Host "Model already exists at $modelPath"
    exit 0
}

curl.exe -L --fail --retry 3 --output $modelPath $modelUrl
if ($LASTEXITCODE -ne 0) {
    throw "Model download failed with exit code $LASTEXITCODE"
}

Write-Host "Model saved to $modelPath"
