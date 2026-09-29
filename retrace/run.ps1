$ErrorActionPreference = 'Stop'

if (-not (Test-Path '.venv')) {
  py -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

if (-not (Test-Path '.env')) {
  Copy-Item '.env.example' '.env'
  Write-Host 'Created .env from .env.example. Add HINDSIGHT_API_KEY and GROQ_API_KEY, then run this script again.' -ForegroundColor Yellow
  exit 0
}

& .\.venv\Scripts\python.exe -m uvicorn app:app --reload
