"""
Data Migration Tool: Supabase (PostgreSQL) -> Local SQLite (app.db)
Safely transfers all contacts, templates, campaigns, and delivery logs to your local database.
"""
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.database import Base, get_normalized_database_url
from app.models import Contact, Template, Campaign, MessageLog


def run_migration() -> None:
    source_url = get_normalized_database_url(settings.DATABASE_URL)
    sqlite_url = "sqlite:///./app.db"

    print("=" * 60)
    print(" 🔄 Starting Data Migration: Supabase -> Local SQLite")
    print("=" * 60)

    if not source_url.startswith("postgres"):
        print("ℹ️ Your current DATABASE_URL is already SQLite. No remote data to pull.")
        return

    print("1. Connecting to Supabase...")
    source_engine = create_engine(source_url, pool_pre_ping=True)
    SourceSession = sessionmaker(bind=source_engine)

    print("2. Initializing Local SQLite database (app.db)...")
    target_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=target_engine)
    TargetSession = sessionmaker(bind=target_engine)

    with SourceSession() as src_db, TargetSession() as dst_db:
        # A. Copy Templates
        src_templates = list(src_db.scalars(select(Template).order_by(Template.id)).all())
        print(f"3. Found {len(src_templates)} templates in Supabase. Migrating...")
        for tmpl in src_templates:
            existing = dst_db.scalar(select(Template).where(Template.name == tmpl.name))
            if not existing:
                dst_tmpl = Template(
                    id=tmpl.id,
                    name=tmpl.name,
                    language=tmpl.language,
                    body_preview=tmpl.body_preview,
                    variables=tmpl.variables,
                    created_at=tmpl.created_at,
                )
                dst_db.add(dst_tmpl)
        dst_db.commit()

        # B. Copy Contacts
        src_contacts = list(src_db.scalars(select(Contact).order_by(Contact.id)).all())
        print(f"4. Found {len(src_contacts)} contacts in Supabase. Migrating...")
        contacts_copied = 0
        for contact in src_contacts:
            existing = dst_db.scalar(select(Contact).where(Contact.phone == contact.phone))
            if not existing:
                dst_contact = Contact(
                    id=contact.id,
                    name=contact.name,
                    phone=contact.phone,
                    consent_status=contact.consent_status,
                    consent_date=contact.consent_date,
                    consent_source=contact.consent_source,
                    tags=contact.tags,
                    created_at=contact.created_at,
                )
                dst_db.add(dst_contact)
                contacts_copied += 1
        dst_db.commit()

        # C. Copy Campaigns
        src_campaigns = list(src_db.scalars(select(Campaign).order_by(Campaign.id)).all())
        print(f"5. Found {len(src_campaigns)} campaigns in Supabase. Migrating...")
        for camp in src_campaigns:
            existing = dst_db.get(Campaign, camp.id)
            if not existing:
                dst_camp = Campaign(
                    id=camp.id,
                    name=camp.name,
                    template_id=camp.template_id,
                    audience_filter=camp.audience_filter,
                    status=camp.status,
                    scheduled_at=camp.scheduled_at,
                    created_at=camp.created_at,
                )
                dst_db.add(dst_camp)
        dst_db.commit()

        # D. Copy Message Logs
        src_logs = list(src_db.scalars(select(MessageLog).order_by(MessageLog.id)).all())
        print(f"6. Found {len(src_logs)} message logs in Supabase. Migrating...")
        for log_entry in src_logs:
            existing = dst_db.get(MessageLog, log_entry.id)
            if not existing:
                dst_log = MessageLog(
                    id=log_entry.id,
                    campaign_id=log_entry.campaign_id,
                    contact_id=log_entry.contact_id,
                    whatsapp_message_id=log_entry.whatsapp_message_id,
                    status=log_entry.status,
                    error=log_entry.error,
                    timestamp=log_entry.timestamp,
                )
                dst_db.add(dst_log)
        dst_db.commit()

    print("=" * 60)
    print(" ✅ Migration Completed Successfully!")
    print(f" • Transferred Contacts:  {len(src_contacts)}")
    print(f" • Transferred Templates: {len(src_templates)}")
    print(f" • Transferred Campaigns: {len(src_campaigns)}")
    print(f" • Transferred Logs:      {len(src_logs)}")
    print(" Local SQLite database (app.db) is fully populated and ready!")
    print("=" * 60)


if __name__ == "__main__":
    run_migration()
