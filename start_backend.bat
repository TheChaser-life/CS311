@echo off
echo ========================================
echo   Starting AI Resume Analyzer Backend
echo ========================================
echo.

cd /d "%~dp0"

echo Installing Python dependencies...
pip install fastapi uvicorn python-multipart -q

echo.
echo Starting FastAPI server on http://localhost:8000
echo.

cd backend
python -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload

pause

