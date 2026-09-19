import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database.connection import init_db
from app.crm.excel_exporter import init_excel_workbook
from app.automation.browser_manager import browser_manager
from app.notifications.telegram_bot_service import telegram_bot_service
from app.config import settings, BASE_DIR

# Import API Routers
from app.api.routes_booking import router as booking_router
from app.api.routes_crm import router as crm_router
from app.api.routes_passengers import router as passengers_router
from app.api.routes_journeys import router as journeys_router
from app.api.routes_settings import router as settings_router
from app.api.routes_logs import router as logs_router
from app.api.routes_system import router as system_router
from app.api.routes_railway import router as railway_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database tables, Excel file, and Telegram Bot if configured
    init_db()
    init_excel_workbook()
    if settings.TELEGRAM_BOT_TOKEN:
        telegram_bot_service.start()
    yield
    # Shutdown: Stop Telegram Bot and clean up browser context
    telegram_bot_service.stop()
    await browser_manager.close()

app = FastAPI(
    title=settings.APP_NAME,
    description="Personal IRCTC Booking Assistant & CRM Backend",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for local frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers first
app.include_router(booking_router)
app.include_router(crm_router)
app.include_router(passengers_router)
app.include_router(journeys_router)
app.include_router(settings_router)
app.include_router(logs_router)
app.include_router(system_router)
app.include_router(railway_router)

@app.get("/api/health")
async def health_check():
    return {
        "status": "Online",
        "app": settings.APP_NAME,
        "mode": "DEMO" if settings.DEMO_MODE else "LIVE_IRCTC"
    }

# Serve Frontend static assets and SPA if built
DIST_DIR = BASE_DIR / "frontend" / "dist"
ASSETS_DIR = DIST_DIR / "assets"

if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith("api"):
        raise HTTPException(status_code=404, detail="Not Found")
    if DIST_DIR.exists():
        target_file = DIST_DIR / full_path
        if full_path and target_file.is_file():
            return FileResponse(target_file)
        index_file = DIST_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
    return {
        "status": "Online",
        "message": "Frontend build not found. Run 'cd frontend && npm run build' or run 'npm run dev' for development mode.",
        "api_docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
