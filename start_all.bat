@echo off
echo ========================================
echo   AI Resume Analyzer - Full Stack
echo ========================================
echo.
echo Starting Backend and Frontend...
echo.

cd /d "%~dp0"

:: Start Backend in new window
start "Backend Server" cmd /k "cd /d %~dp0 && pip install fastapi uvicorn python-multipart -q && cd backend && python -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload"

:: Wait a bit for backend to start
timeout /t 3 /nobreak > nul

:: Start Frontend in new window
start "Frontend Server" cmd /k "cd /d %~dp0frontend && npm install && npm run dev"

echo.
echo ========================================
echo   Servers Starting...
echo ========================================
echo.
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo API Docs: http://localhost:8000/docs
echo.
echo Press any key to exit this window...
pause > nul

