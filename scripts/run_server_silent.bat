@echo off
cd /d "%~dp0\..\backend"
if exist "%~dp0\..\.venv\Scripts\activate.bat" call "%~dp0\..\.venv\Scripts\activate.bat"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
