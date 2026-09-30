@echo off
echo =========================================================
echo  Personal IRCTC Booking Assistant - Setup Script
echo =========================================================
cd /d "%~dp0\.."

echo [1/4] Installing Backend Python Dependencies...
if not exist .venv\Scripts\python.exe python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -r backend\requirements.txt
if errorlevel 1 exit /b 1

echo [2/4] Installing Playwright Chromium Browser...
python -m playwright install chromium

echo [3/4] Installing Frontend NPM Dependencies...
cd frontend
call npm install
if errorlevel 1 exit /b 1
call npm run build
if errorlevel 1 exit /b 1
cd ..

echo [4/4] Setting up Environment Config...
if not exist .env (
    copy .env.example .env
    echo Created .env from .env.example
)

echo.
echo =========================================================
echo  Setup Complete! You can now run start.bat
echo =========================================================
pause
