"""
Tests for Admin UI: authentication, session management, contacts management, and campaigns.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models import Contact, Template


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


def test_unauthenticated_access_redirects_to_login(client_and_db) -> None:
    """Verifies that protected admin pages require authentication."""
    client, _ = client_and_db
    response = client.get("/admin/contacts", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_failure_wrong_credentials(client_and_db) -> None:
    client, _ = client_and_db
    response = client.post("/login", data={"username": "admin", "password": "wrongpassword"})
    assert response.status_code == 401
    assert "Invalid username or password" in response.text


def test_login_success_sets_session(client_and_db) -> None:
    client, _ = client_and_db
    response = client.post(
        "/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/contacts"
    assert "wa_admin_session" in response.cookies


def test_authenticated_admin_flow(client_and_db) -> None:
    client, TestingSession = client_and_db
    session = TestingSession()

    # 1. Log in
    login_res = client.post("/login", data={"username": "admin", "password": "admin123"})
    assert login_res.status_code == 200

    # 2. Seed a contact
    c = Contact(name="Vikram", phone="+919876543210", consent_status="opted_in", tags="vip")
    session.add(c)
    session.commit()

    # 3. View contacts page
    contacts_res = client.get("/admin/contacts")
    assert contacts_res.status_code == 200
    assert "Vikram" in contacts_res.text
    assert "+919876543210" in contacts_res.text

    # 4. Opt out contact via UI
    opt_out_res = client.post(f"/admin/contacts/{c.id}/opt-out")
    assert opt_out_res.status_code == 200
    session.expire_all()
    updated = session.get(Contact, c.id)
    assert updated.consent_status == "opted_out"

    # 5. View campaigns page
    camp_page = client.get("/admin/campaigns")
    assert camp_page.status_code == 200
    assert "hello_world" in camp_page.text

    # 6. Logout
    logout_res = client.post("/logout", follow_redirects=False)
    assert logout_res.status_code == 303
    assert logout_res.headers["location"] == "/login"

    # 7. Check that admin page is now blocked again
    blocked_res = client.get("/admin/contacts", follow_redirects=False)
    assert blocked_res.status_code == 303


def test_admin_create_single_contact_success(client_and_db) -> None:
    """Verifies adding a single contact via the dashboard form."""
    client, TestingSession = client_and_db
    session = TestingSession()

    # Log in
    client.post("/login", data={"username": "admin", "password": "admin123"})

    # Post new single contact
    response = client.post(
        "/admin/contacts/new",
        data={
            "name": "Priya Sharma",
            "phone": "98765 43210",  # Test raw input normalization
            "consent_status": "opted_in",
            "tags": "lead, referral",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "/admin/contacts?message=" in response.headers["location"]

    # Verify contact stored with normalized E.164 phone
    contact = session.query(Contact).filter(Contact.phone == "+919876543210").first()
    assert contact is not None
    assert contact.name == "Priya Sharma"
    assert contact.consent_status == "opted_in"
    assert contact.tags == "lead, referral"


def test_admin_create_single_contact_invalid_and_duplicate(client_and_db) -> None:
    """Verifies validation and duplicate handling on single contact addition."""
    client, TestingSession = client_and_db
    session = TestingSession()

    # Log in
    client.post("/login", data={"username": "admin", "password": "admin123"})

    # Seed existing contact
    existing = Contact(name="Existing User", phone="+919876543210", consent_status="opted_in")
    session.add(existing)
    session.commit()

    # 1. Reject invalid phone format
    invalid_res = client.post(
        "/admin/contacts/new",
        data={"name": "Bad Phone", "phone": "1234"},
        follow_redirects=False,
    )
    assert invalid_res.status_code == 303
    assert "error=" in invalid_res.headers["location"]

    # 2. Reject duplicate phone
    duplicate_res = client.post(
        "/admin/contacts/new",
        data={"name": "Duplicate", "phone": "+919876543210"},
        follow_redirects=False,
    )
    assert duplicate_res.status_code == 303
    assert "already+exists" in duplicate_res.headers["location"]


def test_admin_direct_message_contact_dry_run(client_and_db) -> None:
    """Verifies direct messaging modal action dispatching simulated dry-run message."""
    client, TestingSession = client_and_db
    session = TestingSession()

    # Log in
    client.post("/login", data={"username": "admin", "password": "admin123"})

    contact = Contact(name="Rahul Verma", phone="+919988776655", consent_status="opted_in")
    session.add(contact)
    session.commit()

    # Direct message via telegram_user in dry_run mode
    dm_res = client.post(
        f"/admin/contacts/{contact.id}/direct-message",
        data={
            "channel": "telegram_user",
            "message_text": "Hello Rahul, special rate offer today!",
            "dry_run": "true",
        },
        follow_redirects=False,
    )
    assert dm_res.status_code == 303
    import urllib.parse
    unquoted = urllib.parse.unquote_plus(dm_res.headers["location"])
    assert "Message DRY RUN (Simulated) to Rahul Verma!" in unquoted

    # Verify MessageLog entry created
    from app.models import MessageLog
    log = session.query(MessageLog).filter(MessageLog.contact_id == contact.id).first()
    assert log is not None
    assert log.status == "simulated"
    assert log.whatsapp_message_id.startswith("tg_user_")


def test_admin_direct_message_contact_not_found(client_and_db) -> None:
    """Verifies 303 redirect with error when contact does not exist."""
    client, _ = client_and_db
    client.post("/login", data={"username": "admin", "password": "admin123"})

    dm_res = client.post(
        "/admin/contacts/99999/direct-message",
        data={
            "channel": "whatsapp",
            "message_text": "Hello",
            "dry_run": "true",
        },
        follow_redirects=False,
    )
    assert dm_res.status_code == 303
    assert "Contact+not+found" in dm_res.headers["location"]
