"""
Tests for SQLAlchemy models, database session management, and CRUD operations.
"""
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.database import Base
from app.models import Contact, MessageLog


@pytest.fixture
def db_session():
    """
    Creates an isolated in-memory SQLite database for each test run.
    Ensures tests are fast, repeatable, and have no side effects on disk.
    """
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_create_and_read_contact(db_session) -> None:
    """Verifies that a contact can be created and retrieved from the database."""
    now = datetime.now(timezone.utc)
    contact = Contact(
        name="Rohan Sharma",
        phone="+919876543210",
        consent_status="opted_in",
        consent_date=now,
        consent_source="website_form",
        tags="vip,rates",
    )
    db_session.add(contact)
    db_session.commit()

    # Query the contact back
    saved_contact = db_session.scalar(select(Contact).where(Contact.phone == "+919876543210"))
    assert saved_contact is not None
    assert saved_contact.name == "Rohan Sharma"
    assert saved_contact.consent_status == "opted_in"
    assert saved_contact.consent_source == "website_form"
    assert saved_contact.tags == "vip,rates"


def test_unique_phone_constraint(db_session) -> None:
    """Verifies that duplicate phone numbers are rejected by the database."""
    contact1 = Contact(name="Alice", phone="+919876543210", consent_status="opted_in")
    contact2 = Contact(name="Bob", phone="+919876543210", consent_status="opted_in")

    db_session.add(contact1)
    db_session.commit()

    db_session.add(contact2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_update_consent_status_opt_out(db_session) -> None:
    """Verifies that updating consent status (e.g. opt-out) works properly."""
    contact = Contact(name="Charlie", phone="+919123456789", consent_status="opted_in")
    db_session.add(contact)
    db_session.commit()

    # Mark as opted_out
    contact.consent_status = "opted_out"
    db_session.commit()

    updated = db_session.scalar(select(Contact).where(Contact.phone == "+919123456789"))
    assert updated.consent_status == "opted_out"


def test_message_log_relationship(db_session) -> None:
    """Verifies creating message logs linked to a contact via foreign key."""
    contact = Contact(name="Deepak", phone="+919988776655", consent_status="opted_in")
    db_session.add(contact)
    db_session.commit()

    # Add message log for Deepak
    log = MessageLog(
        contact_id=contact.id,
        campaign_id=1,
        whatsapp_message_id="wamid.HBgL123456789",
        status="sent",
    )
    db_session.add(log)
    db_session.commit()

    # Check relationship navigation
    assert len(contact.messages) == 1
    assert contact.messages[0].whatsapp_message_id == "wamid.HBgL123456789"
    assert log.contact.name == "Deepak"
