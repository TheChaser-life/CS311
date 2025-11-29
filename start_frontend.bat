@echo off
echo ========================================
echo   Starting AI Resume Analyzer Frontend
echo ========================================
echo.

cd /d "%~dp0frontend"

echo Installing Node.js dependencies...
call npm install

echo.
echo Starting React dev server on http://localhost:3000
echo.

call npm run dev

pause

