@echo off
cd /d "%~dp0\..\backend"
set PATH=C:\Users\Depk\AppData\Local\Programs\Python\Python314;C:\Users\Depk\AppData\Local\Programs\Python\Python314\Scripts;%PATH%
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
