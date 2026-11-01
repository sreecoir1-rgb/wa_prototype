"""
Pydantic schemas for data validation, serialization, and API request/response contracts.
"""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, field_validator

from app.services.phone_utils import normalize_phone_number

ConsentStatus = Literal["opted_in", "opted_out", "pending"]


class ContactBase(BaseModel):
    name: str | None = None
    phone: str
    consent_status: ConsentStatus = "pending"
    consent_source: str | None = None
    tags: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_and_normalize_phone(cls, value: str) -> str:
        """Validates and normalizes phone numbers into E.164 format on input."""
        return normalize_phone_number(value)


class ContactCreate(ContactBase):
    """Schema for creating a new contact."""
    pass


class ContactUpdate(BaseModel):
    """Schema for partially updating contact details."""
    name: str | None = None
    consent_status: ConsentStatus | None = None
    consent_source: str | None = None
    tags: str | None = None


class ContactResponse(BaseModel):
    """Schema for returning contact details to API callers."""
    id: int
    name: str | None
    phone: str
    consent_status: ConsentStatus
    consent_date: datetime | None
    consent_source: str | None
    tags: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CSVImportSummary(BaseModel):
    """Summary report returned after processing a CSV contacts import."""
    total_rows: int
    imported: int
    skipped_duplicates: int
    errors: list[str]


class TemplateBase(BaseModel):
    name: str
    language: str = "en_US"
    body_preview: str | None = None
    variables: str | None = None


class TemplateCreate(TemplateBase):
    """Schema for registering a pre-approved template."""
    pass


class TemplateResponse(TemplateBase):
    """Schema for returning template details."""
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CampaignBase(BaseModel):
    name: str
    template_id: int
    audience_filter: str | None = None


class CampaignCreate(CampaignBase):
    """Schema for creating a new broadcast campaign."""
    pass


class CampaignResponse(CampaignBase):
    """Schema for returning campaign details."""
    id: int
    status: str
    scheduled_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CampaignSendSummary(BaseModel):
    """Summary report returned after executing a campaign broadcast."""
    campaign_id: int
    campaign_name: str
    total_targeted: int
    sent_success: int
    failed: int
    dry_run: bool
    status: str

