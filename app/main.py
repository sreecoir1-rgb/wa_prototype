"""
Main FastAPI application entry point.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager that runs startup and shutdown logic.
    Ensures all database tables exist when the server starts.
    """
    init_db()
    yield


app = FastAPI(
    title="WhatsApp Broadcaster",
    description="Broadcast rate offers and referral offers via WhatsApp Business Cloud API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    """
    Health check endpoint to verify that the API server is up and running.
    Returns:
        JSON response with status "ok".
    """
    return {"status": "ok"}
