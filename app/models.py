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
        # Mask phone number in representation to avoid leaking PII in debug output
        masked = self.phone[:3] + "****" + self.phone[-4:] if len(self.phone) >= 7 else "****"
        return f"<Contact id={self.id} phone={masked} status={self.consent_status}>"


class MessageLog(Base):
    """
    Logs every outbound message attempt and its delivery lifecycle.
    """
    __tablename__ = "messages_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id"), nullable=False, index=True)
    whatsapp_message_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="sent", nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    # Many-to-one relationship: Each message belongs to a specific contact
    contact: Mapped["Contact"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"<MessageLog id={self.id} contact_id={self.contact_id} status={self.status}>"
