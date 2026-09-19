@echo off
echo =========================================================
echo  Personal IRCTC Booking Assistant - Setup Script
echo =========================================================
cd /d "%~dp0\.."

echo [1/4] Installing Backend Python Dependencies...
python -m pip install -r backend\requirements.txt

echo [2/4] Installing Playwright Chromium Browser...
python -m playwright install chromium

echo [3/4] Installing Frontend NPM Dependencies...
cd frontend
call npm install
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
