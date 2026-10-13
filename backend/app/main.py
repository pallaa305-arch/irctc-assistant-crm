import os
import sys
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

# On Windows, Playwright requires ProactorEventLoop to launch subprocesses
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    try:
        import uvicorn.loops.asyncio
        uvicorn.loops.asyncio.asyncio_loop_factory = lambda use_subprocess=False: asyncio.ProactorEventLoop
    except Exception:
        pass

def proactor_loop_factory():
    return asyncio.ProactorEventLoop()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database.connection import init_db
from app.crm.excel_exporter import init_excel_workbook
from app.automation.browser_manager import browser_manager
from app.automation.tatkal_scheduler import start_tatkal_scheduler_loop
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
from app.api.routes_chat import router as chat_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database tables, Excel file, and Telegram Bot if configured
    init_db()
    init_excel_workbook()
    if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_ENABLED:
        telegram_bot_service.start()

    # Start background Tatkal scheduler loop
    tatkal_stop_event = asyncio.Event()
    tatkal_task = asyncio.create_task(start_tatkal_scheduler_loop(poll_interval=5, stop_event=tatkal_stop_event))

    yield

    # Shutdown: Stop Telegram Bot, Tatkal loop, and clean up browser context
    tatkal_stop_event.set()
    tatkal_task.cancel()
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
app.include_router(chat_router)

# Mount static frontend build if it exists
frontend_dist = BASE_DIR / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Allow API routes to pass through
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")
        
        file_path = frontend_dist / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_dist / "index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, loop="asyncio")
