"""
Campaign sender service.
Executes broadcasts, enforces strict consent filtering, performs dry-run simulations,
applies rate limiting/exponential backoff, and records delivery logs.
"""
import time
import logging
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Contact, Campaign, MessageLog
from app.schemas import CampaignSendSummary
from app.services.whatsapp_client import WhatsAppClient
from app.services.telegram_client import TelegramClient
from app.services.telegram_user_client import TelegramUserClient

logger = logging.getLogger(__name__)


class CampaignSender:
    """
    Service responsible for orchestrating broadcasts to opted-in audiences.
    """

    def get_targeted_contacts(
        self,
        campaign: Campaign,
        db: Session,
        channel_filter: str | None = None,
    ) -> list[Contact]:
        """
        Selects contacts for the campaign strictly enforcing consent.
        Rule: ONLY contacts with consent_status == 'opted_in' are returned.
        Contacts with 'pending' or 'opted_out' are NEVER returned.
        """
        query = select(Contact).where(Contact.consent_status == "opted_in")

        if campaign.audience_filter:
            # Filter contacts having the specified tag
            query = query.where(Contact.tags.like(f"%{campaign.audience_filter}%"))

        if channel_filter == "telegram":
            query = query.where(Contact.phone.like("tg_%"))
        elif channel_filter in ("whatsapp", "telegram_user"):
            query = query.where(~Contact.phone.like("tg_%"))

        query = query.order_by(Contact.id.asc())
        return list(db.scalars(query).all())

    def send_campaign(
        self,
        campaign_id: int,
        db: Session,
        dry_run: bool | None = None,
        throttle_delay: float = 0.05,
        max_retries: int = 2,
        custom_message: str | None = None,
        channel_filter: str | None = None,
    ) -> CampaignSendSummary:
        """
        Dispatches a broadcast to the campaign's targeted audience.
        In dry_run mode, simulates sends and logs results without calling Meta/Telegram.
        """
        campaign = db.get(Campaign, campaign_id)
        if not campaign:
            raise ValueError(f"Campaign with ID {campaign_id} does not exist.")

        if not campaign.template and not custom_message:
            raise ValueError(f"Campaign {campaign_id} has no associated template or custom message.")

        is_dry_run = dry_run if dry_run is not None else settings.DRY_RUN

        campaign.status = "sending"
        db.commit()

        contacts = self.get_targeted_contacts(campaign, db, channel_filter=channel_filter)
        sent_success = 0
        failed = 0

        wa_client = WhatsAppClient(dry_run=is_dry_run)
        tg_client = TelegramClient(dry_run=is_dry_run)
        user_tg_client = TelegramUserClient(dry_run=is_dry_run)

        for contact in contacts:
            success = False
            wamid = None
            last_error = None
            msg_text = custom_message or (campaign.template.body_preview if campaign.template else None) or f"📢 <b>{campaign.name}</b>"

            for attempt in range(max_retries + 1):
                try:
                    if channel_filter == "telegram_user":
                        # Explicitly targeted to personal Telegram user account (mobile numbers)
                        user_res = user_tg_client.send_message(
                            to_phone=contact.phone,
                            text=msg_text,
                            media_path=campaign.media_url,
                        )
                        wamid = f"tg_user_{user_res.get('message_id', 'simulated')}"
                    elif contact.phone.startswith("tg_"):
                        # Send via Telegram Bot API
                        raw_chat_id = contact.phone.replace("tg_", "")
                        if campaign.media_url:
                            if campaign.media_type == "video":
                                tg_res = tg_client.send_video(chat_id=raw_chat_id, video=campaign.media_url, caption=msg_text)
                            else:
                                tg_res = tg_client.send_photo(chat_id=raw_chat_id, photo=campaign.media_url, caption=msg_text)
                        else:
                            tg_res = tg_client.send_message(chat_id=raw_chat_id, text=msg_text)
                        wamid = f"tg_{tg_res.get('message_id', 'simulated')}"
                    else:
                        # Non-tg contact (E.164 mobile phone number)
                        if channel_filter == "whatsapp":
                            # Explicit WhatsApp channel requested
                            tmpl_name = campaign.template.name if campaign.template else "hello_world"
                            tmpl_lang = campaign.template.language if campaign.template else "en_US"
                            result = wa_client.send_template(
                                to_phone=contact.phone,
                                template_name=tmpl_name,
                                language_code=tmpl_lang,
                            )
                            messages = result.get("messages", [])
                            wamid = messages[0].get("id") if messages else ("simulated_wamid" if is_dry_run else None)
                        elif settings.BROADCAST_PROVIDER == "telegram_user" or (user_tg_client.is_session_authorized() and not settings.WHATSAPP_TOKEN):
                            # Smart fallback: Telegram user session is authorized and WhatsApp token is empty
                            user_res = user_tg_client.send_message(
                                to_phone=contact.phone,
                                text=msg_text,
                                media_path=campaign.media_url,
                            )
                            wamid = f"tg_user_{user_res.get('message_id', 'simulated')}"
                        else:
                            # Send via WhatsApp Cloud API
                            tmpl_name = campaign.template.name if campaign.template else "hello_world"
                            tmpl_lang = campaign.template.language if campaign.template else "en_US"
                            result = wa_client.send_template(
                                to_phone=contact.phone,
                                template_name=tmpl_name,
                                language_code=tmpl_lang,
                            )
                            messages = result.get("messages", [])
                            wamid = messages[0].get("id") if messages else ("simulated_wamid" if is_dry_run else None)
                    success = True
                    break
                except Exception as exc:
                    last_error = str(exc)
                    if attempt < max_retries:
                        time.sleep(0.1 * (2 ** attempt))  # Exponential backoff

            status_str = "simulated" if is_dry_run else ("sent" if success else "failed")
            log_entry = MessageLog(
                campaign_id=campaign.id,
                contact_id=contact.id,
                whatsapp_message_id=wamid,
                status=status_str,
                error=None if success else last_error,
            )
            db.add(log_entry)

            if success:
                sent_success += 1
            else:
                failed += 1

            if throttle_delay > 0:
                time.sleep(throttle_delay)

        campaign.status = "completed"
        db.commit()

        return CampaignSendSummary(
            campaign_id=campaign.id,
            campaign_name=campaign.name,
            total_targeted=len(contacts),
            sent_success=sent_success,
            failed=failed,
            dry_run=is_dry_run,
            status=campaign.status,
        )
