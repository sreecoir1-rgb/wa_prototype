"""
API routes for managing templates, campaigns, and triggering broadcasts.
"""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Template, Campaign
from app.schemas import (
    TemplateCreate,
    TemplateResponse,
    CampaignCreate,
    CampaignResponse,
    CampaignSendSummary,
)
from app.services.campaign_sender import CampaignSender

router = APIRouter(prefix="/api", tags=["Broadcast Campaigns"])
sender_service = CampaignSender()


# --- TEMPLATES ---

@router.post(
    "/templates",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a pre-approved WhatsApp template",
)
def create_template(
    template_in: TemplateCreate,
    db: Annotated[Session, Depends(get_db)],
) -> Template:
    """Registers an approved template name and language to use in campaigns."""
    existing = db.scalar(select(Template).where(Template.name == template_in.name))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Template with name '{template_in.name}' already exists (ID: {existing.id}).",
        )

    template = Template(
        name=template_in.name,
        language=template_in.language,
        body_preview=template_in.body_preview,
        variables=template_in.variables,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.get(
    "/templates",
    response_model=list[TemplateResponse],
    summary="List all registered templates",
)
def list_templates(
    db: Annotated[Session, Depends(get_db)],
) -> list[Template]:
    """Retrieves all registered templates."""
    return list(db.scalars(select(Template).order_by(Template.id.asc())).all())


# --- CAMPAIGNS ---

@router.post(
    "/campaigns",
    response_model=CampaignResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new broadcast campaign",
)
def create_campaign(
    campaign_in: CampaignCreate,
    db: Annotated[Session, Depends(get_db)],
) -> Campaign:
    """Creates a new broadcast campaign linked to a template."""
    template = db.get(Template, campaign_in.template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with ID {campaign_in.template_id} not found.",
        )

    campaign = Campaign(
        name=campaign_in.name,
        template_id=campaign_in.template_id,
        audience_filter=campaign_in.audience_filter,
        media_url=campaign_in.media_url,
        media_type=campaign_in.media_type,
        status="draft",
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign


@router.get(
    "/campaigns",
    response_model=list[CampaignResponse],
    summary="List all broadcast campaigns",
)
def list_campaigns(
    db: Annotated[Session, Depends(get_db)],
) -> list[Campaign]:
    """Retrieves all broadcast campaigns."""
    return list(db.scalars(select(Campaign).order_by(Campaign.id.desc())).all())


@router.get(
    "/campaigns/{campaign_id}",
    response_model=CampaignResponse,
    summary="Get campaign details by ID",
)
def get_campaign(
    campaign_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> Campaign:
    """Retrieves details of a specific campaign."""
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign with ID {campaign_id} not found.",
        )
    return campaign


@router.post(
    "/campaigns/{campaign_id}/send",
    response_model=CampaignSendSummary,
    summary="Execute a broadcast send for a campaign",
)
def send_campaign(
    campaign_id: int,
    db: Annotated[Session, Depends(get_db)],
    dry_run: bool | None = Query(
        None,
        description="If True, simulates sends without contacting Meta. If omitted, uses DRY_RUN from .env.",
    ),
) -> CampaignSendSummary:
    """
    Triggers broadcast delivery for the campaign.
    Selects only opted-in recipients matching the audience filter.
    """
    try:
        return sender_service.send_campaign(
            campaign_id=campaign_id,
            db=db,
            dry_run=dry_run,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
