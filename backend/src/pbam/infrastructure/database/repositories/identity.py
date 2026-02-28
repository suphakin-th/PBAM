"""Concrete SQLAlchemy repository implementations for the identity context."""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from pbam.domain.identity.entities import User, UserSession
from pbam.domain.identity.value_objects import Email, PasswordHash, Username
from pbam.infrastructure.database.models.identity import UserModel, UserSessionModel


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self._session.get(UserModel, user_id)
        return _to_user(result) if result else None

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(UserModel).where(UserModel.email == email, UserModel.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _to_user(row) if row else None

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(UserModel).where(UserModel.username == username, UserModel.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _to_user(row) if row else None

    async def save(self, user: User) -> User:
        existing = await self._session.get(UserModel, user.id)
        if existing:
            existing.email = str(user.email)
            existing.username = str(user.username)
            existing.password_hash = str(user.password_hash)
            existing.is_active = user.is_active
            existing.is_verified = user.is_verified
            existing.biometric_public_key = user.biometric_public_key
            existing.updated_at = datetime.now(timezone.utc)
            existing.deleted_at = user.deleted_at
        else:
            model = UserModel(
                id=user.id,
                email=str(user.email),
                username=str(user.username),
                password_hash=str(user.password_hash),
                is_active=user.is_active,
                is_verified=user.is_verified,
                biometric_public_key=user.biometric_public_key,
                created_at=user.created_at,
                updated_at=user.updated_at,
                deleted_at=user.deleted_at,
            )
            self._session.add(model)
        await self._session.flush()
        return user

    async def delete(self, user_id: UUID) -> None:
        model = await self._session.get(UserModel, user_id)
        if model:
            model.deleted_at = datetime.now(timezone.utc)
            model.is_active = False
            await self._session.flush()


class UserSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_jti_hash(self, jti_hash: str) -> UserSession | None:
        stmt = select(UserSessionModel).where(UserSessionModel.jti_hash == jti_hash)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _to_session(row) if row else None

    async def get_active_by_user_id(self, user_id: UUID) -> list[UserSession]:
        now = datetime.now(timezone.utc)
        stmt = select(UserSessionModel).where(
            UserSessionModel.user_id == user_id,
            UserSessionModel.revoked_at.is_(None),
            UserSessionModel.expires_at > now,
        )
        result = await self._session.execute(stmt)
        return [_to_session(r) for r in result.scalars()]

    async def save(self, session: UserSession) -> UserSession:
        model = UserSessionModel(
            id=session.id,
            user_id=session.user_id,
            jti_hash=session.jti_hash,
            device_fingerprint=session.device_fingerprint,
            ip_address=session.ip_address,
            user_agent=session.user_agent,
            expires_at=session.expires_at,
            created_at=session.created_at,
            revoked_at=session.revoked_at,
        )
        self._session.add(model)
        await self._session.flush()
        return session

    async def revoke(self, session_id: UUID) -> None:
        model = await self._session.get(UserSessionModel, session_id)
        if model:
            model.revoked_at = datetime.now(timezone.utc)
            await self._session.flush()

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        now = datetime.now(timezone.utc)
        stmt = (
            update(UserSessionModel)
            .where(UserSessionModel.user_id == user_id, UserSessionModel.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        await self._session.execute(stmt)


# ── Mappers ───────────────────────────────────────────────────────────────────

def _to_user(m: UserModel) -> User:
    return User(
        id=m.id,
        email=Email(m.email),
        username=Username(m.username),
        password_hash=PasswordHash(m.password_hash),
        is_active=m.is_active,
        is_verified=m.is_verified,
        biometric_public_key=m.biometric_public_key,
        created_at=m.created_at,
        updated_at=m.updated_at,
        deleted_at=m.deleted_at,
    )


def _to_session(m: UserSessionModel) -> UserSession:
    return UserSession(
        id=m.id,
        user_id=m.user_id,
        jti_hash=m.jti_hash,
        device_fingerprint=m.device_fingerprint,
        ip_address=str(m.ip_address) if m.ip_address else None,
        user_agent=m.user_agent,
        expires_at=m.expires_at,
        created_at=m.created_at,
        revoked_at=m.revoked_at,
    )
