"""
Tests for WhatsApp Cloud API webhooks: verification handshake, HMAC security,
delivery status tracking, and STOP opt-out processing.
"""
import hmac
import hashlib
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.config import settings
from app.database import Base, get_db
from app.models import Contact, MessageLog
from app.services.webhook_service import verify_signature


@pytest.fixture
def client_and_db():
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
    with TestClient(app) as client:
        yield client, TestingSession

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


# --- 1. VERIFICATION HANDSHAKE TESTS ---

def test_webhook_verification_success(client_and_db) -> None:
    client, _ = client_and_db
    params = {
        "hub.mode": "subscribe",
        "hub.challenge": "1158201444",
        "hub.verify_token": settings.WEBHOOK_VERIFY_TOKEN,
    }
    response = client.get("/webhook", params=params)
    assert response.status_code == 200
    assert response.text == "1158201444"


def test_webhook_verification_invalid_token(client_and_db) -> None:
    client, _ = client_and_db
    params = {
        "hub.mode": "subscribe",
        "hub.challenge": "1158201444",
        "hub.verify_token": "wrong_token",
    }
    response = client.get("/webhook", params=params)
    assert response.status_code == 403


# --- 2. SIGNATURE VERIFICATION TESTS ---

def test_hmac_signature_verification() -> None:
    secret = "my_test_secret"
    body = b'{"object": "whatsapp_business_account"}'
    valid_hash = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    valid_header = f"sha256={valid_hash}"

    assert verify_signature(body, valid_header, secret) is True
    # Tampered body
    assert verify_signature(b'{"tampered": true}', valid_header, secret) is False
    # Missing prefix
    assert verify_signature(body, valid_hash, secret) is False


# --- 3. STOP OPT-OUT HANDLING TESTS ---

def test_webhook_stop_opts_out_contact(client_and_db) -> None:
    """CRITICAL TEST: An incoming 'STOP' message must immediately mark contact as opted_out."""
    client, TestingSession = client_and_db
    session = TestingSession()

    contact = Contact(name="Sam", phone="+919876500099", consent_status="opted_in")
    session.add(contact)
    session.commit()

    webhook_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "test_waba_id",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "messages": [
                                {
                                    "from": "919876500099",
                                    "id": "wamid.incoming_1",
                                    "timestamp": "1730000000",
                                    "text": {"body": "STOP"},
                                    "type": "text",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    response = client.post("/webhook", json=webhook_payload)
    assert response.status_code == 200

    # Verify contact was opted out
    updated_contact = session.scalar(select(Contact).where(Contact.phone == "+919876500099"))
    assert updated_contact.consent_status == "opted_out"


def test_webhook_normal_message_does_not_opt_out(client_and_db) -> None:
    client, TestingSession = client_and_db
    session = TestingSession()

    contact = Contact(name="Leo", phone="+919876500088", consent_status="opted_in")
    session.add(contact)
    session.commit()

    webhook_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "test_waba_id",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "messages": [
                                {
                                    "from": "919876500088",
                                    "id": "wamid.incoming_2",
                                    "text": {"body": "Hello, what are your rates?"},
                                    "type": "text",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    response = client.post("/webhook", json=webhook_payload)
    assert response.status_code == 200

    contact_check = session.scalar(select(Contact).where(Contact.phone == "+919876500088"))
    assert contact_check.consent_status == "opted_in"


# --- 4. DELIVERY STATUS UPDATES & IDEMPOTENCY ---

def test_webhook_delivery_status_and_idempotency(client_and_db) -> None:
    client, TestingSession = client_and_db
    session = TestingSession()

    contact = Contact(name="Meera", phone="+919876500077", consent_status="opted_in")
    session.add(contact)
    session.commit()

    log_entry = MessageLog(
        contact_id=contact.id,
        whatsapp_message_id="wamid.test_status_123",
        status="sent",
    )
    session.add(log_entry)
    session.commit()

    # 1. Update to 'delivered'
    payload_delivered = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "test_waba_id",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "statuses": [
                                {
                                    "id": "wamid.test_status_123",
                                    "status": "delivered",
                                    "timestamp": "1730000010",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
    res1 = client.post("/webhook", json=payload_delivered)
    assert res1.status_code == 200

    refreshed_log = session.scalar(select(MessageLog).where(MessageLog.whatsapp_message_id == "wamid.test_status_123"))
    assert refreshed_log.status == "delivered"

    # 2. Update to 'read'
    payload_read = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "test_waba_id",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "statuses": [
                                {
                                    "id": "wamid.test_status_123",
                                    "status": "read",
                                    "timestamp": "1730000020",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }
    res2 = client.post("/webhook", json=payload_read)
    assert res2.status_code == 200
    session.expire_all()
    refreshed_log = session.scalar(select(MessageLog).where(MessageLog.whatsapp_message_id == "wamid.test_status_123"))
    assert refreshed_log.status == "read"

    # 3. Idempotency check: Re-sending 'delivered' must NOT downgrade 'read'
    res3 = client.post("/webhook", json=payload_delivered)
    assert res3.status_code == 200
    session.expire_all()
    refreshed_log = session.scalar(select(MessageLog).where(MessageLog.whatsapp_message_id == "wamid.test_status_123"))
    assert refreshed_log.status == "read"
