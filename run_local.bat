@echo off
title OmniBroadcast Pro (Local Server)
echo ========================================================
echo   OmniBroadcast Pro - Local Secure Studio
echo   Bound exclusively to 127.0.0.1 (NOT exposed to internet)
echo ========================================================
echo.
cd /d "%~dp0"
echo Opening server at http://127.0.0.1:8000 ...
echo Press Ctrl+C in this window anytime to stop the server.
echo.
.\.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
