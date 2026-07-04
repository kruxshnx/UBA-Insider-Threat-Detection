@echo off
echo ============================================================
echo   VIGILANT LENS - UBA Insider Threat Detection System
echo ============================================================
echo.
echo Starting API Server...
echo.

start "Vigilant Lens API" cmd /k "cd /d %~dp0 && python -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000"

echo API Server starting...
echo.
echo Waiting 3 seconds...
timeout /t 3 /nobreak

echo.
echo Opening API documentation in your browser...
start http://localhost:8000/docs

echo.
echo ============================================================
echo   API Server is running!
echo ============================================================
echo.
echo   API Docs: http://localhost:8000/docs
echo   API Health: http://localhost:8000/health
echo.
echo Next Steps:
echo   1. Open http://localhost:8000/docs to view API
echo   2. Run telemetry agent: python -m src.telemetry.agent --user-id U001 --debug
echo   3. Start frontend: cd website && npm run dev
echo.
echo Press Ctrl+C to stop this window (API server will keep running)
echo ============================================================
echo.
pause
