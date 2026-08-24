import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

HANDLE_MAX_LENGTH = 15
EMAIL_MAX_LENGTH = 254
ACCOUNT_HASH_CONSTRAINT = (
    "length(password_hash) = 97 AND "
    "password_hash ~ '^[$]argon2id[$]v=19[$]m=19456,t=2,p=1"
    "[$][A-Za-z0-9+/]{22}[$][A-Za-z0-9+/]{43}$'"
)


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH))
    handle: Mapped[str] = mapped_column(String(HANDLE_MAX_LENGTH))
    password_hash: Mapped[str] = mapped_column(String(255))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Uniqueness is case-insensitive and the database owns it: a check in the service loses
    # to two concurrent registrations, a unique index does not.
    __table_args__ = (
        CheckConstraint(
            ACCOUNT_HASH_CONSTRAINT,
            name="ck_accounts_password_hash_supported",
        ),
        Index("ix_accounts_email_lower", text("lower(email)"), unique=True),
        Index("ix_accounts_handle_lower", text("lower(handle)"), unique=True),
    )


class RevokedAccessToken(Base):
    __tablename__ = "revoked_access_tokens"

    jti: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VerificationToken(Base):
    __tablename__ = "verification_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    # The digest, never the token. A stolen database yields nothing usable.
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
