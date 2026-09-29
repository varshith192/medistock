# Starts the MediStock 360 backend (FastAPI :8000) and frontend (Vite :5173) in two windows.
$root = $PSScriptRoot

if (-not (Test-Path "$root\backend\.venv")) {
    Write-Host "Creating backend virtual environment..."
    python -m venv "$root\backend\.venv"
    & "$root\backend\.venv\Scripts\python.exe" -m pip install -r "$root\backend\requirements.txt"
}
if (-not (Test-Path "$root\backend\.env")) {
    Copy-Item "$root\backend\.env.example" "$root\backend\.env"
    Write-Host "Created backend\.env - add GROQ_API_KEY and HINDSIGHT_API_KEY, then run this script again." -ForegroundColor Yellow
}
if (-not (Test-Path "$root\frontend\node_modules")) {
    Write-Host "Installing frontend dependencies..."
    Push-Location "$root\frontend"; npm install; Pop-Location
}

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\backend'; .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\frontend'; npm run dev"
Start-Sleep -Seconds 4
Start-Process "http://localhost:5173"
Write-Host "MediStock 360 is starting: http://localhost:5173 (API docs: http://127.0.0.1:8000/docs)"
