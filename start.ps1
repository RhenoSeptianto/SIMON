param([int]$Port=8000)
Set-Location $PSScriptRoot
& .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port $Port
