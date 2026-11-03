"""
Main FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import init_db
from app.logging_config import setup_logging
from app.routes.contacts import router as contacts_router
from app.routes.campaigns import router as campaigns_router
from app.routes.webhook import router as webhook_router
from app.routes.telegram_webhook import router as telegram_webhook_router
from app.routes.ui import router as ui_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager that runs startup and shutdown logic.
    Ensures all database tables exist when the server starts.
    """
    setup_logging()
    try:
        init_db()
    except Exception as exc:
        logger.error(f"Database initialization warning on startup: {exc}")
    yield


app = FastAPI(
    title="OmniBroadcast Pro",
    description="Enterprise Multi-Channel Broadcast Platform for WhatsApp Cloud API & Telegram Bot",
    version="0.2.0",
    lifespan=lifespan,
)

# Enable encrypted session cookies for admin login
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="wa_admin_session",
    max_age=14 * 24 * 3600,  # 14 days
)

# Register route modules
app.include_router(ui_router)
app.include_router(contacts_router)
app.include_router(campaigns_router)
app.include_router(webhook_router)
app.include_router(telegram_webhook_router)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    """
    Health check endpoint to verify that the API server is up and running.
    Returns:
        JSON response with status "ok".
    """
    return {"status": "ok"}
