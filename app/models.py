"""
SQLAlchemy ORM models describing the database schema.
"""
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Contact(Base):
    """
    Represents an opted-in lead or customer.
    Phone numbers must always be stored in normalized E.164 format.
    """
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    consent_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    consent_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    consent_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tags: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    # One-to-many relationship: A contact can have many logged messages
    messages: Mapped[list["MessageLog"]] = relationship(
        back_populates="contact",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        masked = self.phone[:3] + "****" + self.phone[-4:] if len(self.phone) >= 7 else "****"
        return f"<Contact id={self.id} phone={masked} status={self.consent_status}>"


class Template(Base):
    """
    Represents a pre-approved WhatsApp message template registered with Meta.
    """
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    language: Mapped[str] = mapped_column(String(20), default="en_US", nullable=False)
    body_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    variables: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    # One-to-many relationship: A template can be used by many campaigns
    campaigns: Mapped[list["Campaign"]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Template id={self.id} name={self.name} lang={self.language}>"


class Campaign(Base):
    """
    Represents a broadcast campaign sent to opted-in contacts.
    """
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    template_id: Mapped[int] = mapped_column(ForeignKey("templates.id"), nullable=False, index=True)
    audience_filter: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)  # draft, sending, completed, failed
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    template: Mapped["Template"] = relationship(back_populates="campaigns")
    messages: Mapped[list["MessageLog"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Campaign id={self.id} name='{self.name}' status={self.status}>"


class MessageLog(Base):
    """
    Logs every outbound message attempt and its delivery lifecycle.
    """
    __tablename__ = "messages_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"), nullable=True, index=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"), nullable=False, index=True)
    whatsapp_message_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="sent", nullable=False)  # sent, simulated, delivered, read, failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    contact: Mapped["Contact"] = relationship(back_populates="messages")
    campaign: Mapped["Campaign | None"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"<MessageLog id={self.id} contact_id={self.contact_id} status={self.status}>"
