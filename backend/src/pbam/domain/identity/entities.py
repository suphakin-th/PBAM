"""Domain entities for the Identity bounded context."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from .value_objects import Email, PasswordHash, Username


@dataclass
class User:
    id: UUID
    email: Email
    username: Username
    password_hash: PasswordHash
    is_active: bool = True
    is_verified: bool = False
    biometric_public_key: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: datetime | None = None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        self.deleted_at = datetime.now(timezone.utc)
        self.is_active = False


@dataclass
class UserSession:
    id: UUID
    user_id: UUID
    jti_hash: str
    expires_at: datetime
    device_fingerprint: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    revoked_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > datetime.now(timezone.utc)

    def revoke(self) -> None:
        self.revoked_at = datetime.now(timezone.utc)
