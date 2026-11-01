"""
Tests for contacts API endpoints, validation, consent handling, and CSV importing.
"""
import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models import Contact


@pytest.fixture
def client_and_db():
    """
    Sets up an in-memory database with StaticPool and provides a FastAPI TestClient configured to use it.
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


def test_create_contact_success(client_and_db) -> None:
    client, _ = client_and_db
    payload = {
        "name": "Pooja Verma",
        "phone": "9876543210",  # Will be normalized to +919876543210
        "consent_status": "opted_in",
        "consent_source": "website_form",
        "tags": "vip,rates",
    }
    response = client.post("/api/contacts", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Pooja Verma"
    assert data["phone"] == "+919876543210"
    assert data["consent_status"] == "opted_in"
    assert data["consent_date"] is not None


def test_create_contact_invalid_phone_rejected(client_and_db) -> None:
    client, _ = client_and_db
    payload = {
        "name": "Bad Phone",
        "phone": "1234",
    }
    response = client.post("/api/contacts", json=payload)
    assert response.status_code == 422  # Pydantic validation failure


def test_create_contact_duplicate_rejected(client_and_db) -> None:
    client, _ = client_and_db
    payload = {"phone": "+919876543210", "consent_status": "opted_in"}
    client.post("/api/contacts", json=payload)

    # Attempt to insert same phone number
    response = client.post("/api/contacts", json=payload)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_list_contacts_with_filters(client_and_db) -> None:
    client, _ = client_and_db
    client.post("/api/contacts", json={"phone": "+919000000001", "consent_status": "opted_in", "tags": "gold"})
    client.post("/api/contacts", json={"phone": "+919000000002", "consent_status": "opted_out", "tags": "silver"})
    client.post("/api/contacts", json={"phone": "+919000000003", "consent_status": "opted_in", "tags": "silver"})

    # Filter by opted_in
    res = client.get("/api/contacts?consent_status=opted_in")
    assert res.status_code == 200
    assert len(res.json()) == 2

    # Filter by tag
    res_tag = client.get("/api/contacts?tag=gold")
    assert res_tag.status_code == 200
    assert len(res_tag.json()) == 1
    assert res_tag.json()[0]["phone"] == "+919000000001"


def test_get_contact_by_id(client_and_db) -> None:
    client, _ = client_and_db
    res = client.post("/api/contacts", json={"name": "Aarav", "phone": "+919111111111"})
    contact_id = res.json()["id"]

    res_get = client.get(f"/api/contacts/{contact_id}")
    assert res_get.status_code == 200
    assert res_get.json()["name"] == "Aarav"

    res_404 = client.get("/api/contacts/99999")
    assert res_404.status_code == 404


def test_update_contact_patch(client_and_db) -> None:
    client, _ = client_and_db
    res = client.post("/api/contacts", json={"name": "Old Name", "phone": "+919222222222"})
    contact_id = res.json()["id"]

    patch_res = client.patch(f"/api/contacts/{contact_id}", json={"name": "New Name", "tags": "updated"})
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "New Name"
    assert patch_res.json()["tags"] == "updated"


def test_opt_out_endpoint(client_and_db) -> None:
    client, _ = client_and_db
    res = client.post("/api/contacts", json={"phone": "+919333333333", "consent_status": "opted_in"})
    contact_id = res.json()["id"]

    opt_out_res = client.post(f"/api/contacts/{contact_id}/opt-out")
    assert opt_out_res.status_code == 200
    assert opt_out_res.json()["consent_status"] == "opted_out"


def test_import_contacts_csv(client_and_db) -> None:
    client, _ = client_and_db
    # First, insert one contact into DB to test DB duplicate detection
    client.post("/api/contacts", json={"name": "Existing", "phone": "+919876500001"})

    csv_data = (
        "Name,Phone,Consent_Status,Tags\n"
        "Ravi Kumar,9876500002,opted_in,rates\n"
        "Duplicate In DB,+91 98765-00001,opted_in,test\n"  # should be skipped as duplicate
        "Duplicate In CSV,9876500002,opted_in,dup\n"       # duplicate of first row in batch
        "Invalid Phone,1234,opted_in,invalid\n"            # invalid phone error
        "Anita Roy,+919876500003,pending,leads\n"          # valid new contact
    )

    files = {"file": ("contacts.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")}
    response = client.post("/api/contacts/import-csv", files=files)

    assert response.status_code == 200
    summary = response.json()
    assert summary["total_rows"] == 5
    assert summary["imported"] == 2  # Ravi Kumar and Anita Roy
    assert summary["skipped_duplicates"] == 2  # DB duplicate + CSV duplicate
    assert len(summary["errors"]) == 1  # Invalid Phone row
