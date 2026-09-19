# 🚆 Personal IRCTC Booking Assistant + CRM

A lightweight, production-ready personal railway ticket booking assistant and CRM dashboard designed to operate within strict compliance boundaries.

---

## 🛡️ IRCTC Compliance & Security Policy

> [!IMPORTANT]
> **Zero Bot Evasion & Zero Bypass Guarantee**:
> This assistant strictly adheres to IRCTC's security policies, rate limits, and terms of service:
> - **No CAPTCHA Bypassing**: It does NOT OCR, solve, or outsource CAPTCHAs.
> - **No OTP Interception**: It does NOT intercept or read OTPs automatically.
> - **No Automated Payments**: It NEVER touches banking credentials or automates payments.
> - **Human-In-The-Loop**: Whenever a login, CAPTCHA, OTP, or Payment step is reached, automation pauses completely and hands visible control over to you. Once you manually complete the step in the browser, you simply click **"Continue"** in the dashboard.

---

## ⚡ Low-Spec Hardware Target
- **RAM**: Minimum 4 GB RAM (runs smoothly even when 2 GB is used by other apps).
- **CPU**: 2 Cores.
- **Resource Footprint**: < 250 MB RAM for the server and single browser instance.
- **No AI / GPU dependencies**: Does NOT require Ollama, local LLMs, Docker, or external GPUs.

---

## 🚀 Beginner-Friendly Installation Guide

### Prerequisites
1. **Python 3.10+** (Tested on Python 3.14)
2. **Node.js 18+** (Tested on Node.js v26)

---

### Method A: One-Click Setup (Windows)

1. Open a terminal or Command Prompt in the project folder:
   ```cmd
   cd C:\Users\Depk\.gemini\antigravity\scratch\irctc-assistant-crm
   ```
2. Run the setup script:
   ```cmd
   scripts\setup.bat
   ```
3. Start the application:
   ```cmd
   scripts\start.bat
   ```
4. Open your browser:
   - Dashboard: **http://localhost:5173**
   - API Docs: **http://127.0.0.1:8000/docs**

---

### Method B: Manual Step-by-Step (Windows & Linux)

#### 1. Setup Backend
```bash
cd backend
python -m pip install -r requirements.txt
python -m playwright install chromium
```

#### 2. Setup Frontend
```bash
cd ../frontend
npm install
```

#### 3. Configure Environment
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

#### 4. Run Servers
Terminal 1 (Backend):
```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Terminal 2 (Frontend):
```bash
cd frontend
npm run dev
```

---

## 🧪 Safe Demo / Mock Mode

By default, the application runs in **Demo Mode (`DEMO_MODE=true`)**.
- Tests the entire booking state machine, manual action pauses, CRM database, and Excel export.
- Does NOT send real network traffic to IRCTC or charge bank cards.
- Allows you to safely explore all 10 dashboard screens, simulate verification, and inspect `bookings.xlsx`.

To toggle live official IRCTC automation, switch the toggle in the **New Booking** screen or update **Settings**.

---

## 📊 Features & UI Screens

1. **Dashboard**: Live booking metrics, upcoming journey calendar, and recent activity.
2. **New Booking**: Step-by-step booking form with duplicate booking prevention and summary review modal.
3. **Booking History**: Tabular historical records with deep search, multi-field filters, and Excel/CSV export.
4. **CRM**: Complete relationship records with passenger seat assignments and notification delivery logs.
5. **Passengers**: Master list of family/frequent traveler profiles with 1-click autofill.
6. **Saved Journeys**: Stored routine corridors (e.g., Delhi ➔ Bhopal, 3A).
7. **Notifications**: Telegram Bot API and official Meta WhatsApp Cloud API integrations.
8. **Settings**: IRCTC username pre-fill, browser speed (SlowMo), visible/headless mode.
9. **Logs**: Real-time audit terminal with automatic masking of credit cards, CVVs, OTPs, and passwords.
10. **System Status**: Live connectivity diagnostics for FastAPI, SQLite, Playwright, Telegram, and Excel.

---

## 🧪 Running Automated Tests

Run the full Pytest test suite:
```bash
cd backend
python -m pytest tests
```

---

## 🔒 Security & Privacy

- **Safe Logging**: The log sanitizer strips 13-19 digit card numbers, CVVs, and OTPs before writing to disk.
- **Local Secret Encryption**: Uses AES-GCM (Fernet) for credential keys.
- **Privacy Purge**: The Settings page includes a **"Permanently Delete All Data"** button to wipe all local records, passenger profiles, and Excel history.
