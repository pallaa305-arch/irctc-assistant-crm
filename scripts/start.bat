@echo off
echo =========================================================
echo  Starting Personal IRCTC Booking Assistant + CRM
echo =========================================================
cd /d "%~dp0\.."

set PATH=C:\Users\Depk\AppData\Local\Programs\Python\Python314;C:\Users\Depk\AppData\Local\Programs\Python\Python314\Scripts;C:\Program Files\nodejs;%PATH%

echo [1/3] Checking and clearing port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo Clearing existing process on port 8000 (PID: %%a)...
    taskkill /F /PID %%a >nul 2>&1
)

echo [2/3] Starting Unified Server (Backend + UI) on http://127.0.0.1:8000 ...
start "IRCTC Assistant Server" cmd /k "cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

timeout /t 2 /nobreak >nul

echo [3/3] Opening Dashboard in browser...
start http://127.0.0.1:8000

echo.
echo =========================================================
echo  Server is now RUNNING!
echo  Dashboard: http://127.0.0.1:8000
echo  API Documentation: http://127.0.0.1:8000/docs
echo =========================================================
