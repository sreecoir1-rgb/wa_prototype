"""
Main FastAPI application entry point.
"""
from fastapi import FastAPI

app = FastAPI(
    title="WhatsApp Broadcaster",
    description="Broadcast rate offers and referral offers via WhatsApp Business Cloud API",
    version="0.1.0",
)


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    """
    Health check endpoint to verify that the API server is up and running.
    Returns:
        JSON response with status "ok".
    """
    return {"status": "ok"}
