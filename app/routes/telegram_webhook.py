"""
API routes for Telegram Bot Webhook.
Handles user opt-in (/start), user opt-out (STOP), and multi-channel message routing.
"""
import logging
from datetime import datetime
from typing import Annotated, Any
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Contact
from app.services.telegram_client import TelegramClient, mask_chat_id

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Telegram Bot Webhook"])
telegram_client = TelegramClient()

OPT_OUT_KEYWORDS = {"STOP", "/STOP", "UNSUBSCRIBE", "CANCEL", "QUIT"}


@router.post("/telegram/webhook", summary="Telegram Bot Event Receiver")
async def telegram_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """
    Receives incoming updates from the Telegram Bot API.
    Handles /start subscription opt-ins and STOP opt-outs idempotently.
    """
    # Optional secret token verification
    if settings.SECRET_KEY and x_telegram_bot_api_secret_token:
        if x_telegram_bot_api_secret_token != settings.SECRET_KEY:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid secret token.",
            )

    try:
        payload = await request.json()
    except Exception:
        return {"ok": True}

    message = payload.get("message")
    if not message:
        return {"ok": True}

    chat = message.get("chat", {})
    chat_id = chat.get("id")
    if not chat_id:
        return {"ok": True}

    text = message.get("text", "").strip()
    user_info = message.get("from", {})
    first_name = user_info.get("first_name") or user_info.get("username") or "Telegram User"

    tg_phone_key = f"tg_{chat_id}"
    masked = mask_chat_id(chat_id)

    # 1. HANDLE /start (Opt-in)
    if text.startswith("/start"):
        contact = db.scalar(select(Contact).where(Contact.phone == tg_phone_key))
        if contact:
            contact.consent_status = "opted_in"
            contact.consent_date = datetime.now()
            contact.consent_source = "telegram_start"
            if "channel:telegram" not in (contact.tags or ""):
                contact.tags = f"{contact.tags},channel:telegram" if contact.tags else "channel:telegram"
            if first_name and not contact.name:
                contact.name = first_name
        else:
            contact = Contact(
                name=first_name,
                phone=tg_phone_key,
                consent_status="opted_in",
                consent_date=datetime.now(),
                consent_source="telegram_start",
                tags="channel:telegram,auto_opt_in",
            )
            db.add(contact)

        db.commit()
        logger.info(f"Telegram contact {masked} opted in via /start.")

        try:
            telegram_client.send_message(
                chat_id=chat_id,
                text=(
                    f"👋 <b>Welcome, {first_name}!</b>\n\n"
                    "You are now subscribed to our official rate & referral offers.\n\n"
                    "Reply <b>STOP</b> or <b>/stop</b> at any time to unsubscribe."
                ),
            )
        except Exception as exc:
            logger.warning(f"Failed to send Telegram welcome message: {exc}")

        return {"ok": True, "action": "opted_in"}

    # 2. HANDLE STOP (Opt-out)
    if text.upper() in OPT_OUT_KEYWORDS:
        contact = db.scalar(select(Contact).where(Contact.phone == tg_phone_key))
        if contact:
            contact.consent_status = "opted_out"
            db.commit()
            logger.info(f"Telegram contact {masked} opted out via STOP.")

        try:
            telegram_client.send_message(
                chat_id=chat_id,
                text=(
                    "🛑 <b>Unsubscribed</b>\n\n"
                    "You have been successfully opted out from our broadcasts.\n\n"
                    "Send <b>/start</b> anytime if you wish to resubscribe."
                ),
            )
        except Exception as exc:
            logger.warning(f"Failed to send Telegram opt-out confirmation: {exc}")

        return {"ok": True, "action": "opted_out"}

    # 3. OTHER MESSAGES (Helpful automated reply)
    try:
        telegram_client.send_message(
            chat_id=chat_id,
            text=(
                "ℹ️ <i>Automated Broadcast Channel</i>\n\n"
                "• Send <b>/start</b> to subscribe to our rate alerts.\n"
                "• Send <b>STOP</b> to unsubscribe."
            ),
        )
    except Exception:
        pass

    return {"ok": True}


@router.post("/telegram/set-webhook", summary="Register live webhook URL with Telegram")
def set_telegram_webhook(webhook_url: str) -> dict[str, Any]:
    """Helper endpoint to register the public Vercel webhook URL with Telegram."""
    client = TelegramClient()
    return client.set_webhook(webhook_url)
