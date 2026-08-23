import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

HANDLE_MAX_LENGTH = 15
EMAIL_MAX_LENGTH = 254


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH))
    handle: Mapped[str] = mapped_column(String(HANDLE_MAX_LENGTH))
    password_hash: Mapped[str] = mapped_column(String(255))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Uniqueness is case-insensitive and the database owns it: a check in the service loses
    # to two concurrent registrations, a unique index does not.
    __table_args__ = (
        Index("ix_accounts_email_lower", text("lower(email)"), unique=True),
        Index("ix_accounts_handle_lower", text("lower(handle)"), unique=True),
    )
