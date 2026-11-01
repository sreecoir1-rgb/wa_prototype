"""
Main FastAPI application entry point.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.database import init_db
from app.routes.contacts import router as contacts_router
from app.routes.campaigns import router as campaigns_router


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

# Register route modules
app.include_router(contacts_router)
app.include_router(campaigns_router)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    """
    Health check endpoint to verify that the API server is up and running.
    Returns:
        JSON response with status "ok".
    """
    return {"status": "ok"}
