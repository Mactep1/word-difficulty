param([switch]$WithModel)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'Please install uv first: https://docs.astral.sh/uv/getting-started/installation/'
}
if ($WithModel) {
    uv sync --python 3.12 --extra model
} else {
    uv sync --python 3.12
}
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
if ($WithModel) {
    & '.\.venv\Scripts\python.exe' -m word_difficulty setup --with-model
} else {
    & '.\.venv\Scripts\python.exe' -m word_difficulty setup
}
if ($LASTEXITCODE -ne 0) { throw 'Resource setup failed. Retry setup to resume.' }
Write-Output 'Ready. Run .\start.ps1 to launch the app.'
