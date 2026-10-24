$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
# Use the provider configured in .env; do not silently force demo mode.
& "$PSScriptRoot\.venv312\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8010
