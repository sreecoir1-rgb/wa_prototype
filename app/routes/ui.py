"""
Server-rendered UI controllers for Admin dashboard, authentication, contacts, and campaigns.
"""
import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, UploadFile, File, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Contact, Template, Campaign, MessageLog
from app.services.phone_utils import normalize_phone_number
from app.services.whatsapp_client import WhatsAppClient, mask_phone_number
from app.services.telegram_client import TelegramClient
from app.services.telegram_user_client import TelegramUserClient
from app.services.auth_service import (
    verify_password,
    get_admin_password_hash,
    is_authenticated,
    require_admin,
)
from app.services.campaign_sender import CampaignSender
from pathlib import Path
from app.routes.contacts import import_contacts_csv

router = APIRouter(include_in_schema=False)
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
campaign_sender = CampaignSender()


# --- AUTHENTICATION ROUTES ---

@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> Response:
    """Root redirect to admin panel or login."""
    if is_authenticated(request):
        return RedirectResponse(url="/admin/contacts", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> Response:
    """Renders the admin login page."""
    if is_authenticated(request):
        return RedirectResponse(url="/admin/contacts", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request=request, name="login.html")


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
) -> Response:
    """Validates admin credentials and initiates a session."""
    if username == settings.ADMIN_USERNAME and verify_password(password, get_admin_password_hash()):
        request.session["admin_logged_in"] = True
        return RedirectResponse(url="/admin/contacts", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "Invalid username or password."},
        status_code=status.HTTP_401_UNAUTHORIZED,
    )


@router.post("/logout")
def logout(request: Request) -> Response:
    """Clears the session cookie and redirects to login."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


# --- CONTACTS & CSV IMPORT ---

@router.get("/admin/contacts", response_class=HTMLResponse)
def admin_contacts_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    status: str | None = None,
    tag: str | None = None,
    message: str | None = None,
    error: str | None = None,
) -> Response:
    """Renders the contacts list with filters and consent status badges."""
    require_admin(request)

    query = select(Contact)
    if status:
        query = query.where(Contact.consent_status == status)
    if tag:
        query = query.where(Contact.tags.like(f"%{tag}%"))

    query = query.order_by(Contact.id.desc())
    contacts = list(db.scalars(query).all())

    total_count = len(contacts)
    opted_in_count = sum(1 for c in contacts if c.consent_status == "opted_in")
    telegram_count = sum(1 for c in contacts if c.phone.startswith("tg_") or "telegram" in (c.tags or ""))
    whatsapp_count = total_count - telegram_count

    return templates.TemplateResponse(
        request=request,
        name="contacts.html",
        context={
            "contacts": contacts,
            "current_status": status,
            "current_tag": tag,
            "stats": {
                "total": total_count,
                "opted_in": opted_in_count,
                "telegram": telegram_count,
                "whatsapp": whatsapp_count,
            },
            "message": message,
            "error": error,
        },
    )


@router.post("/admin/contacts/new")
def admin_create_single_contact(
    request: Request,
    phone: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
    name: Annotated[str | None, Form()] = None,
    consent_status: Annotated[str, Form()] = "opted_in",
    consent_source: Annotated[str | None, Form()] = "admin_dashboard",
    tags: Annotated[str | None, Form()] = None,
) -> Response:
    """Creates a single contact directly from the dashboard."""
    require_admin(request)

    try:
        normalized_phone = normalize_phone_number(phone)
    except ValueError as exc:
        return RedirectResponse(
            url=f"/admin/contacts?error={str(exc)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    existing = db.scalar(select(Contact).where(Contact.phone == normalized_phone))
    if existing:
        masked = mask_phone_number(normalized_phone)
        was_opted_out = existing.consent_status == "opted_out"

        # Update consent status and refresh consent timestamp on re-optin
        existing.consent_status = consent_status
        if consent_status == "opted_in":
            existing.consent_date = datetime.now()
            if was_opted_out:
                existing.consent_source = consent_source if (consent_source and consent_source != "admin_dashboard") else "admin_dashboard_reoptin"
            elif consent_source:
                existing.consent_source = consent_source

        if name and name.strip():
            existing.name = name.strip()

        if tags and tags.strip():
            new_tags = [t.strip() for t in tags.split(",") if t.strip()]
            current_tags = [t.strip() for t in (existing.tags or "").split(",") if t.strip()]
            merged = list(dict.fromkeys(current_tags + new_tags))
            existing.tags = ", ".join(merged)

        db.commit()

        if was_opted_out and consent_status == "opted_in":
            return RedirectResponse(
                url=f"/admin/contacts?message=Welcome+back!+Contact+{masked}+has+been+re-opted+in+successfully.",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        return RedirectResponse(
            url=f"/admin/contacts?message=Contact+{masked}+updated+successfully.",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    consent_date = datetime.now() if consent_status == "opted_in" else None
    new_contact = Contact(
        name=name.strip() if name and name.strip() else None,
        phone=normalized_phone,
        consent_status=consent_status,
        consent_date=consent_date,
        consent_source=consent_source or "admin_dashboard",
        tags=tags.strip() if tags and tags.strip() else None,
    )
    db.add(new_contact)
    db.commit()

    return RedirectResponse(
        url="/admin/contacts?message=Contact+successfully+added!",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/admin/contacts/{contact_id}/direct-message")
async def admin_direct_message_contact(
    request: Request,
    contact_id: int,
    channel: Annotated[str, Form()],
    message_text: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
    media_url: Annotated[str | None, Form()] = None,
    media_file: Annotated[UploadFile | None, File()] = None,
    dry_run: Annotated[str | None, Form()] = None,
) -> Response:
    """Sends a direct message directly to a contact's phone number."""
    require_admin(request)

    contact = db.get(Contact, contact_id)
    if not contact:
        return RedirectResponse(
            url="/admin/contacts?error=Contact+not+found.",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    is_dry_run = dry_run == "true"
    final_media_path = None

    if media_file and media_file.filename:
        unique_name = f"{uuid.uuid4().hex[:8]}_{media_file.filename}"
        saved_path = UPLOAD_DIR / unique_name
        file_bytes = await media_file.read()
        if file_bytes:
            with open(saved_path, "wb") as f:
                f.write(file_bytes)
            final_media_path = str(saved_path)
    elif media_url and media_url.strip():
        final_media_path = media_url.strip()

    try:
        if channel == "telegram_user":
            user_client = TelegramUserClient(dry_run=is_dry_run)
            result = await user_client.send_message_async(to_phone=contact.phone, text=message_text, media_path=final_media_path)
            wamid = f"tg_user_{result.get('message_id', 'simulated')}"
        elif channel == "whatsapp":
            wa_client = WhatsAppClient(dry_run=is_dry_run)
            result = wa_client.send_template(to_phone=contact.phone, template_name="hello_world")
            messages = result.get("messages", [])
            wamid = messages[0].get("id") if messages else ("simulated_wamid" if is_dry_run else None)
        else:
            # telegram_bot
            tg_client = TelegramClient(dry_run=is_dry_run)
            raw_chat_id = contact.phone.replace("tg_", "")
            if final_media_path:
                result = tg_client.send_photo(chat_id=raw_chat_id, photo=final_media_path, caption=message_text)
            else:
                result = tg_client.send_message(chat_id=raw_chat_id, text=message_text)
            wamid = f"tg_{result.get('message_id', 'simulated')}"

        status_str = "simulated" if is_dry_run else "sent"
        log_entry = MessageLog(
            contact_id=contact.id,
            whatsapp_message_id=wamid,
            status=status_str,
        )
        db.add(log_entry)
        db.commit()

        mode_text = "DRY RUN (Simulated)" if is_dry_run else "Sent"
        return RedirectResponse(
            url=f"/admin/contacts?message=Message+{mode_text}+to+{contact.name or contact.phone}!",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as exc:
        return RedirectResponse(
            url=f"/admin/contacts?error={str(exc)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@router.post("/admin/contacts/{contact_id}/opt-out")
def admin_opt_out_contact(
    request: Request,
    contact_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Action button to immediately opt out a contact from the UI."""
    require_admin(request)

    contact = db.get(Contact, contact_id)
    if contact:
        contact.consent_status = "opted_out"
        db.commit()
        return RedirectResponse(
            url="/admin/contacts?message=Contact+marked+as+opted+out.",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return RedirectResponse(
        url="/admin/contacts?error=Contact+not+found.",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/admin/contacts/import", response_class=HTMLResponse)
def admin_import_csv_page(request: Request) -> Response:
    """Renders the CSV upload form."""
    require_admin(request)
    return templates.TemplateResponse(request=request, name="import_csv.html")


@router.post("/admin/contacts/import")
async def admin_import_csv_submit(
    request: Request,
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Handles CSV file upload from the browser and redirects with results."""
    require_admin(request)

    summary = await import_contacts_csv(file=file, db=db)
    msg = (
        f"CSV imported successfully! Added {summary.imported} new contacts. "
        f"({summary.skipped_duplicates} duplicates skipped, {len(summary.errors)} errors)"
    )
    return RedirectResponse(
        url=f"/admin/contacts?message={msg}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# --- CAMPAIGNS & RATE OFFERS ---

@router.get("/admin/campaigns", response_class=HTMLResponse)
def admin_campaigns_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    message: str | None = None,
    error: str | None = None,
) -> Response:
    """Renders the Broadcast Studio with template preview and campaign history."""
    require_admin(request)

    # Ensure default useful templates exist in database
    DEFAULT_TEMPLATES = [
        ("hello_world", "en_US", "👋 Welcome to our official broadcast service. Reply STOP anytime to unsubscribe."),
        ("rate_alert_daily", "en_US", "📈 Daily Rate Alert: Today's 24K Gold is ₹7,850/g. USD/INR is ₹84.20. Reply to this alert to lock in your preferential rate immediately."),
        ("referral_reward_v1", "en_US", "🎁 Special Referral Reward: Refer a friend or business partner this month and both of you receive a ₹500 discount voucher on your next booking!"),
        ("exclusive_vip_offer", "en_US", "🌟 VIP Exclusive: Zero processing fee on all transactions above ₹10,000 this weekend. Valid until Sunday 11:59 PM."),
        ("system_service_notice", "en_US", "ℹ️ Service Notice: Scheduled system maintenance this Sunday from 2:00 AM to 4:00 AM IST. Broadcast alerts will resume normally at 4:00 AM."),
    ]
    for tmpl_name, tmpl_lang, tmpl_body in DEFAULT_TEMPLATES:
        if not db.scalar(select(Template).where(Template.name == tmpl_name)):
            db.add(Template(name=tmpl_name, language=tmpl_lang, body_preview=tmpl_body))
    db.commit()

    templates_list = list(db.scalars(select(Template).order_by(Template.id.asc())).all())
    campaigns_list = list(db.scalars(select(Campaign).order_by(Campaign.id.desc())).all())

    # Count eligible opted-in contacts
    opted_in_count = db.scalar(
        select(func.count(Contact.id)).where(Contact.consent_status == "opted_in")
    ) or 0

    return templates.TemplateResponse(
        request=request,
        name="campaigns.html",
        context={
            "templates": templates_list,
            "campaigns": campaigns_list,
            "opted_in_count": opted_in_count,
            "dry_run_default": settings.DRY_RUN,
            "message": message,
            "error": error,
        },
    )


@router.post("/admin/campaigns/send")
async def admin_campaign_send(
    request: Request,
    name: Annotated[str, Form()],
    template_id: Annotated[int, Form()],
    db: Annotated[Session, Depends(get_db)],
    audience_filter: Annotated[str | None, Form()] = None,
    channel_target: Annotated[str | None, Form()] = None,
    rate_offer: Annotated[str | None, Form()] = None,
    custom_message: Annotated[str | None, Form()] = None,
    media_url: Annotated[str | None, Form()] = None,
    media_file: Annotated[UploadFile | None, File()] = None,
    dry_run: Annotated[str | None, Form()] = None,
) -> Response:
    """Executes a campaign broadcast with confirmation and dry-run safety."""
    require_admin(request)

    # Process media attachment if provided
    final_media_url = None
    final_media_type = None

    if media_file and media_file.filename:
        ext = Path(media_file.filename).suffix.lower()
        is_video = ext in {".mp4", ".mov", ".avi", ".mkv", ".webm"}
        unique_name = f"{uuid.uuid4().hex[:8]}_{media_file.filename}"
        saved_path = UPLOAD_DIR / unique_name

        file_bytes = await media_file.read()
        if file_bytes:
            with open(saved_path, "wb") as f:
                f.write(file_bytes)
            final_media_url = str(saved_path)
            final_media_type = "video" if is_video else "image"
    elif media_url and media_url.strip():
        final_media_url = media_url.strip()
        ext = Path(final_media_url.split("?")[0]).suffix.lower()
        final_media_type = "video" if ext in {".mp4", ".mov", ".webm"} else "image"

    # Handle custom message or selected template
    if template_id == 0 or (custom_message and custom_message.strip()):
        custom_tmpl = db.scalar(select(Template).where(Template.name == "custom_broadcast"))
        if not custom_tmpl:
            custom_tmpl = Template(
                name="custom_broadcast",
                language="en_US",
                body_preview="Custom message composed in studio.",
            )
            db.add(custom_tmpl)
            db.commit()
            db.refresh(custom_tmpl)
        template = custom_tmpl
        template_id = custom_tmpl.id
    else:
        template = db.get(Template, template_id)
        if not template:
            return RedirectResponse(
                url="/admin/campaigns?error=Selected+template+does+not+exist.",
                status_code=status.HTTP_303_SEE_OTHER,
            )

    # Append custom rate offer text to campaign name if provided
    campaign_name = f"{name} ({rate_offer})" if rate_offer else name

    campaign = Campaign(
        name=campaign_name,
        template_id=template_id,
        audience_filter=audience_filter or None,
        media_url=final_media_url,
        media_type=final_media_type,
        status="draft",
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    # Boolean dry_run: if checkbox is checked, form sends "true", otherwise False
    is_dry_run = dry_run == "true"

    try:
        summary = campaign_sender.send_campaign(
            campaign_id=campaign.id,
            db=db,
            dry_run=is_dry_run,
            custom_message=custom_message.strip() if custom_message else None,
            channel_filter=channel_target if channel_target in ("telegram", "whatsapp") else None,
        )
        mode_text = "DRY RUN (Simulated)" if summary.dry_run else "LIVE SEND"
        msg = f"Campaign '{summary.campaign_name}' executed in {mode_text} mode! Targeted: {summary.total_targeted}, Sent: {summary.sent_success}."
        return RedirectResponse(
            url=f"/admin/campaigns?message={msg}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as exc:
        return RedirectResponse(
            url=f"/admin/campaigns?error={exc}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
