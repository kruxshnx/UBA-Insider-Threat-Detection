@echo off
REM ============================================================
REM   VIGILANT LENS - UBA Insider Threat Detection
REM   One-shot local launcher: backend API + frontend dashboard
REM ============================================================
setlocal
cd /d "%~dp0"

REM Prefer the project virtualenv if it exists
set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo Starting backend API on http://localhost:8000 ...
start "UBA API" cmd /k "cd /d %~dp0 && %PY% -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload"

echo Starting frontend dashboard on http://localhost:5173 ...
start "UBA Frontend" cmd /k "cd /d %~dp0website && npm install && npm run dev"

echo Waiting for services to come up...
timeout /t 6 /nobreak >nul

start http://localhost:5173
start http://localhost:8000/docs

echo.
echo ============================================================
echo   API Docs  : http://localhost:8000/docs
echo   API Health: http://localhost:8000/health
echo   Dashboard : http://localhost:5173
echo ============================================================
echo Close the two spawned windows to stop the servers.
endlocal
