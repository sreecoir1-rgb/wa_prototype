"""
API route controllers for contact management, consent handling, and CSV imports.
"""
import csv
import io
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Contact
from app.schemas import (
    ContactCreate,
    ContactUpdate,
    ContactResponse,
    CSVImportSummary,
    ConsentStatus,
)
from app.services.phone_utils import normalize_phone_number
from app.services.whatsapp_client import mask_phone_number

router = APIRouter(prefix="/api/contacts", tags=["Contacts"])


@router.post(
    "",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new contact",
)
def create_contact(
    contact_in: ContactCreate,
    db: Annotated[Session, Depends(get_db)],
) -> Contact:
    """
    Creates a new contact with phone validation and duplicate checking.
    If the initial consent status is 'opted_in', records the current timestamp.
    """
    existing = db.scalar(select(Contact).where(Contact.phone == contact_in.phone))
    if existing:
        masked = mask_phone_number(contact_in.phone)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Contact with phone number {masked} already exists (ID: {existing.id}).",
        )

    consent_date = None
    if contact_in.consent_status == "opted_in":
        consent_date = datetime.now(timezone.utc)

    contact = Contact(
        name=contact_in.name,
        phone=contact_in.phone,
        consent_status=contact_in.consent_status,
        consent_date=consent_date,
        consent_source=contact_in.consent_source,
        tags=contact_in.tags,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.get(
    "",
    response_model=list[ContactResponse],
    summary="List contacts with filtering and pagination",
)
def list_contacts(
    db: Annotated[Session, Depends(get_db)],
    consent_status: ConsentStatus | None = Query(
        None, description="Filter by consent status ('opted_in', 'opted_out', 'pending')"
    ),
    tag: str | None = Query(None, description="Filter contacts containing this tag"),
    limit: int = Query(50, ge=1, le=200, description="Maximum contacts to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> list[Contact]:
    """
    Returns a paginated list of contacts with optional filtering by status and tag.
    """
    query = select(Contact)

    if consent_status:
        query = query.where(Contact.consent_status == consent_status)
    if tag:
        query = query.where(Contact.tags.like(f"%{tag}%"))

    query = query.order_by(Contact.id.desc()).offset(offset).limit(limit)
    return list(db.scalars(query).all())


@router.get(
    "/{contact_id}",
    response_model=ContactResponse,
    summary="Get a single contact by ID",
)
def get_contact(
    contact_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> Contact:
    """
    Retrieves a single contact by primary key ID.
    """
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact with ID {contact_id} not found.",
        )
    return contact


@router.patch(
    "/{contact_id}",
    response_model=ContactResponse,
    summary="Update contact details",
)
def update_contact(
    contact_id: int,
    update_in: ContactUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> Contact:
    """
    Updates editable fields of an existing contact (name, consent status, tags, source).
    """
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact with ID {contact_id} not found.",
        )

    if update_in.name is not None:
        contact.name = update_in.name
    if update_in.consent_source is not None:
        contact.consent_source = update_in.consent_source
    if update_in.tags is not None:
        contact.tags = update_in.tags
    if update_in.consent_status is not None:
        contact.consent_status = update_in.consent_status
        if update_in.consent_status == "opted_in" and not contact.consent_date:
            contact.consent_date = datetime.now(timezone.utc)

    db.commit()
    db.refresh(contact)
    return contact


@router.post(
    "/{contact_id}/opt-out",
    response_model=ContactResponse,
    summary="Mark a contact as opted-out immediately",
)
def opt_out_contact(
    contact_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> Contact:
    """
    Honors customer opt-out immediately by setting consent_status to 'opted_out'.
    """
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact with ID {contact_id} not found.",
        )

    contact.consent_status = "opted_out"
    db.commit()
    db.refresh(contact)
    return contact


@router.post(
    "/import-csv",
    response_model=CSVImportSummary,
    summary="Bulk import contacts from a CSV file",
)
async def import_contacts_csv(
    file: UploadFile = File(..., description="CSV file with contacts (columns: phone, name, consent_status, tags)"),
    db: Session = Depends(get_db),
) -> CSVImportSummary:
    """
    Parses an uploaded CSV file, normalizes phone numbers, skips duplicates,
    and bulk-inserts valid new contacts.
    """
    content_bytes = await file.read()
    try:
        # Handle utf-8 with or without BOM (Byte Order Mark from Excel)
        text_content = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text_content = content_bytes.decode("latin-1")

    csv_reader = csv.DictReader(io.StringIO(text_content))

    total_rows = 0
    imported = 0
    skipped_duplicates = 0
    errors: list[str] = []
    seen_in_batch: set[str] = set()

    for row_index, raw_row in enumerate(csv_reader, start=2):  # start=2 accounts for header row
        total_rows += 1
        # Normalize header keys: lowercase and strip spaces
        row = {k.strip().lower(): (v.strip() if v else "") for k, v in raw_row.items() if k}

        # Look for the phone number column under common names
        raw_phone = (
            row.get("phone")
            or row.get("mobile")
            or row.get("phone_number")
            or row.get("contact")
        )

        if not raw_phone:
            errors.append(f"Row {row_index}: Missing phone number.")
            continue

        try:
            phone_e164 = normalize_phone_number(raw_phone)
        except ValueError as exc:
            errors.append(f"Row {row_index}: {exc}")
            continue

        # Check duplicate within this upload batch
        if phone_e164 in seen_in_batch:
            skipped_duplicates += 1
            continue

        # Check duplicate in database
        existing_in_db = db.scalar(select(Contact.id).where(Contact.phone == phone_e164))
        if existing_in_db:
            skipped_duplicates += 1
            seen_in_batch.add(phone_e164)
            continue

        # Determine consent details
        raw_status = row.get("consent_status", "opted_in").lower()
        consent_status: ConsentStatus = "opted_in" if raw_status in ("opted_in", "yes", "true", "1") else "pending"
        consent_date = datetime.now(timezone.utc) if consent_status == "opted_in" else None
        consent_source = row.get("consent_source") or "csv_import"
        name = row.get("name") or None
        tags = row.get("tags") or None

        contact = Contact(
            name=name,
            phone=phone_e164,
            consent_status=consent_status,
            consent_date=consent_date,
            consent_source=consent_source,
            tags=tags,
        )
        db.add(contact)
        seen_in_batch.add(phone_e164)
        imported += 1

    db.commit()

    return CSVImportSummary(
        total_rows=total_rows,
        imported=imported,
        skipped_duplicates=skipped_duplicates,
        errors=errors,
    )
