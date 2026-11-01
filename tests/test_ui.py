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
