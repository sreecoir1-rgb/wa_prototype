"""
Unit tests for Telegram Webhook routing and event handling.
Tests /start opt-in, STOP opt-out, and contact registration.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models import Contact


@pytest.fixture
def client_and_session():
    """Sets up an in-memory SQLite database for testing telegram webhook."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client, TestingSession

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


def test_telegram_webhook_start_opt_in(client_and_session):
    """Verifies that sending /start automatically registers an opted-in contact."""
    client, TestingSession = client_and_session

    update_payload = {
        "update_id": 1001,
        "message": {
            "message_id": 1,
            "from": {
                "id": 88877766,
                "first_name": "Satya",
                "username": "satya_coder",
            },
            "chat": {
                "id": 88877766,
                "first_name": "Satya",
                "type": "private",
            },
            "text": "/start",
        },
    }

    response = client.post("/telegram/webhook", json=update_payload)
    assert response.status_code == 200
    assert response.json()["action"] == "opted_in"

    with TestingSession() as db:
        contact = db.scalar(select(Contact).where(Contact.phone == "tg_88877766"))
        assert contact is not None
        assert contact.name == "Satya"
        assert contact.consent_status == "opted_in"
        assert contact.consent_source == "telegram_start"


def test_telegram_webhook_stop_opt_out(client_and_session):
    """Verifies that sending STOP immediately marks the contact as opted_out."""
    client, TestingSession = client_and_session

    with TestingSession() as db:
        existing = Contact(
            name="Alice",
            phone="tg_55544433",
            consent_status="opted_in",
        )
        db.add(existing)
        db.commit()

    stop_payload = {
        "update_id": 1002,
        "message": {
            "message_id": 2,
            "from": {"id": 55544433, "first_name": "Alice"},
            "chat": {"id": 55544433, "first_name": "Alice"},
            "text": "STOP",
        },
    }

    response = client.post("/telegram/webhook", json=stop_payload)
    assert response.status_code == 200
    assert response.json()["action"] == "opted_out"

    with TestingSession() as db:
        contact = db.scalar(select(Contact).where(Contact.phone == "tg_55544433"))
        assert contact.consent_status == "opted_out"
