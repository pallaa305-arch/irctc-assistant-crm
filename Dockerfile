# ==========================================
# Stage 1: Build Frontend Assets with Node
# ==========================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# ==========================================
# Stage 2: Python Backend + Playwright
# ==========================================
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Playwright & Media tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libasound2 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt
RUN playwright install --with-deps chromium

# Copy backend source code
COPY backend ./backend

# Copy built frontend assets from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Ensure data directories exist
RUN mkdir -p /app/data/bookings /app/data/tickets /app/data/invoices /app/data/exports /app/data/backups /app/data/browser_profile

WORKDIR /app/backend

ENV PYTHONPATH=/app/backend
ENV BROWSER_HEADLESS=true
ENV PYTHONUNBUFFERED=1

# Render dynamically passes PORT (defaults to 8000)
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
