"""SQLAlchemy ORM models for the identity schema."""
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import INET, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from pbam.infrastructure.database.connection import Base


class UserModel(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_email_active", "email", postgresql_where="deleted_at IS NULL"),
        {"schema": "identity"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    biometric_public_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserSessionModel(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        Index(
            "ix_user_sessions_user_expires",
            "user_id", "expires_at",
            postgresql_where="revoked_at IS NULL",
        ),
        {"schema": "identity"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    jti_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    device_fingerprint: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
