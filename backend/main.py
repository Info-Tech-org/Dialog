from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os

from models import create_db_and_tables
from models.db import run_migrations
from api import router
from api.auth_routes import router as auth_router
from api.upload_routes import router as upload_router
from api.ingest_routes import router as ingest_router
from api.ws_ingest_routes import router as ws_ingest_router
from api.ws_realtime_routes import router as ws_realtime_router
from api.device_routes import router as device_router
from api.review_routes import router as review_router
from api.roleplay_routes import router as roleplay_router
from ingest import WebSocketHandler
from config import settings
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting application...")

    # Create database tables
    create_db_and_tables()
    run_migrations()
    logger.info("Database initialized")

    # Create audio storage directory
    os.makedirs(settings.audio_storage_path, exist_ok=True)
    logger.info(f"Audio storage path: {settings.audio_storage_path}")

    yield

    # Shutdown
    logger.info("Shutting down application...")


# Create FastAPI app
app = FastAPI(
    title="Family Emotion Interaction System",
    description="MVP for real-time harmful language detection",
    version="1.0.0",
    lifespan=lifespan,
)

# Static media mount for uploaded audio
UPLOAD_DIR = (Path(__file__).resolve().parent / "data" / "audio" / "uploads").resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(UPLOAD_DIR)), name="media")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize WebSocket handler
ws_handler = WebSocketHandler()


# Include API routes
app.include_router(router, prefix="/api", tags=["api"])
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(upload_router, prefix="/api/audio", tags=["upload"])
app.include_router(ingest_router, prefix="/api/ingest", tags=["ingest"])
app.include_router(ws_ingest_router, prefix="/ws/ingest", tags=["ws-ingest"])
app.include_router(ws_realtime_router, prefix="/ws/realtime", tags=["ws-realtime"])
app.include_router(device_router, prefix="/api/devices", tags=["devices"])
app.include_router(review_router, prefix="/api", tags=["review"])
app.include_router(roleplay_router, prefix="/api", tags=["roleplay"])


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for device connections"""
    await ws_handler.handle_connection(websocket)


# Serve frontend static files (must be after all API routes)
from fastapi.responses import FileResponse

FRONTEND_DIR = Path("/home/zhuang/www/dist")
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """Catch-all route for React SPA - must be last"""
        file_path = FRONTEND_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.ws_host,
        port=settings.ws_port,
        reload=True,
        log_level="info",
    )
