"""
Tests for templates, broadcast campaigns, consent filtering, and dry-run execution.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models import Contact, Template, Campaign, MessageLog
from app.services.campaign_sender import CampaignSender


@pytest.fixture
def client_and_db():
    """
    Sets up an isolated in-memory SQLite database with StaticPool for campaign testing.
    """
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


def test_consent_filtering_strictly_honored(client_and_db) -> None:
    """
    CRITICAL TEST: Ensures ONLY 'opted_in' contacts receive messages.
    'pending' and 'opted_out' contacts must NEVER be messaged.
    """
    client, TestingSession = client_and_db
    session = TestingSession()

    # 1. Create contacts with varying consent statuses
    c1 = Contact(name="Opted In User", phone="+919876500001", consent_status="opted_in")
    c2 = Contact(name="Opted Out User", phone="+919876500002", consent_status="opted_out")
    c3 = Contact(name="Pending User", phone="+919876500003", consent_status="pending")
    session.add_all([c1, c2, c3])

    # 2. Create template and campaign
    tmpl = Template(name="hello_world", language="en_US")
    session.add(tmpl)
    session.commit()

    campaign = Campaign(name="Consent Test Broadcast", template_id=tmpl.id, status="draft")
    session.add(campaign)
    session.commit()

    # 3. Execute campaign send
    sender = CampaignSender()
    summary = sender.send_campaign(campaign.id, session, dry_run=True)

    # 4. Verify targeted audience
    assert summary.total_targeted == 1
    assert summary.sent_success == 1
    assert summary.failed == 0

    # 5. Verify database message logs
    logs = list(session.scalars(select(MessageLog).where(MessageLog.campaign_id == campaign.id)).all())
    assert len(logs) == 1
    assert logs[0].contact_id == c1.id
    assert logs[0].status == "simulated"

    # Verify that opted-out and pending contacts have zero logs
    opted_out_logs = list(session.scalars(select(MessageLog).where(MessageLog.contact_id == c2.id)).all())
    pending_logs = list(session.scalars(select(MessageLog).where(MessageLog.contact_id == c3.id)).all())
    assert len(opted_out_logs) == 0
    assert len(pending_logs) == 0


def test_audience_tag_filtering(client_and_db) -> None:
    """
    Verifies that when an audience_filter is set, only opted-in contacts
    with matching tags are targeted.
    """
    client, TestingSession = client_and_db
    session = TestingSession()

    c1 = Contact(name="Gold VIP", phone="+919876500011", consent_status="opted_in", tags="vip,rates")
    c2 = Contact(name="General Lead", phone="+919876500012", consent_status="opted_in", tags="general")
    tmpl = Template(name="hello_world", language="en_US")
    session.add_all([c1, c2, tmpl])
    session.commit()

    campaign = Campaign(name="VIP Only Broadcast", template_id=tmpl.id, audience_filter="vip")
    session.add(campaign)
    session.commit()

    sender = CampaignSender()
    summary = sender.send_campaign(campaign.id, session, dry_run=True)

    assert summary.total_targeted == 1
    assert summary.sent_success == 1

    logs = list(session.scalars(select(MessageLog).where(MessageLog.campaign_id == campaign.id)).all())
    assert len(logs) == 1
    assert logs[0].contact_id == c1.id


def test_campaign_api_endpoints(client_and_db) -> None:
    """
    Tests creating templates, creating campaigns, and triggering broadcasts via the REST API.
    """
    client, _ = client_and_db

    # 1. Create a contact
    client.post("/api/contacts", json={"name": "Alice", "phone": "+919999900001", "consent_status": "opted_in"})

    # 2. Create a template
    t_res = client.post("/api/templates", json={"name": "hello_world", "language": "en_US"})
    assert t_res.status_code == 201
    template_id = t_res.json()["id"]

    # 3. Create a campaign
    c_res = client.post("/api/campaigns", json={"name": "Daily Rate Launch", "template_id": template_id})
    assert c_res.status_code == 201
    campaign_id = c_res.json()["id"]
    assert c_res.json()["status"] == "draft"

    # 4. Trigger send via API with dry_run=true
    send_res = client.post(f"/api/campaigns/{campaign_id}/send?dry_run=true")
    assert send_res.status_code == 200
    summary = send_res.json()
    assert summary["campaign_id"] == campaign_id
    assert summary["total_targeted"] == 1
    assert summary["sent_success"] == 1
    assert summary["dry_run"] is True
    assert summary["status"] == "completed"

    # 5. Check campaign status updated to completed
    get_res = client.get(f"/api/campaigns/{campaign_id}")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "completed"
