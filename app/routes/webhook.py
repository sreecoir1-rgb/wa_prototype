"""
API endpoints for Meta WhatsApp Cloud API webhooks.
Includes GET handshake verification and POST event receiver.
"""
import json
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.services.webhook_service import WebhookService, verify_signature

router = APIRouter(tags=["Webhooks"])
webhook_service = WebhookService()


@router.get(
    "/webhook",
    summary="Meta Webhook Verification Handshake",
)
def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
) -> Response:
    """
    Responds to Meta's subscription challenge during webhook registration.
    Meta expects the exact hub.challenge returned with HTTP 200 when the token matches.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.WEBHOOK_VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Verification token mismatch or invalid hub.mode.",
    )


@router.post(
    "/webhook",
    summary="Meta Webhook Event Ingestion",
)
async def receive_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    """
    Receives incoming WhatsApp events from Meta (delivery receipts and replies).
    Validates X-Hub-Signature-256 and handles STOP opt-outs and status updates.
    """
    raw_body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256")

    # Cryptographic signature verification
    if settings.APP_SECRET and settings.APP_SECRET != "your_meta_app_secret_here":
        if not verify_signature(raw_body, signature_header, settings.APP_SECRET):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid X-Hub-Signature-256 signature.",
            )

    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        )

    # Process statuses and messages
    webhook_service.process_payload(payload, db)

    # Always return 200 OK to acknowledge receipt to Meta
    return {"status": "ok"}
