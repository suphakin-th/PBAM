"""Identity use-case commands: register, login, logout."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from jose import JWTError

from pbam.domain.identity.entities import User, UserSession
from pbam.domain.identity.repositories import IUserRepository, IUserSessionRepository
from pbam.domain.identity.value_objects import Email, PasswordHash, Username
from pbam.infrastructure.auth.jwt import (
    create_access_token,
    get_jti_from_token,
    hash_jti,
)
from pbam.infrastructure.auth.password import hash_password, verify_password


class AuthError(Exception):
    pass


class UserAlreadyExistsError(AuthError):
    pass


class InvalidCredentialsError(AuthError):
    pass


@dataclass
class RegisterResult:
    user: User
    token: str
    expires_at: datetime


@dataclass
class LoginResult:
    user: User
    token: str
    expires_at: datetime


async def register_user(
    *,
    email: str,
    username: str,
    password: str,
    user_repo: IUserRepository,
    session_repo: IUserSessionRepository,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> RegisterResult:
    """Register a new user and return an access token."""
    if await user_repo.get_by_email(email):
        raise UserAlreadyExistsError("Email already registered")
    if await user_repo.get_by_username(username):
        raise UserAlreadyExistsError("Username already taken")

    user = User(
        id=uuid4(),
        email=Email(email),
        username=Username(username),
        password_hash=hash_password(password),
    )
    user = await user_repo.save(user)

    token, jti, expires_at = create_access_token(user.id)
    session = UserSession(
        id=uuid4(),
        user_id=user.id,
        jti_hash=hash_jti(jti),
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await session_repo.save(session)

    return RegisterResult(user=user, token=token, expires_at=expires_at)


async def login_user(
    *,
    username_or_email: str,
    password: str,
    user_repo: IUserRepository,
    session_repo: IUserSessionRepository,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> LoginResult:
    """Authenticate a user and return a fresh access token."""
    # Try email first, then username
    user = await user_repo.get_by_email(username_or_email)
    if user is None:
        user = await user_repo.get_by_username(username_or_email)
    if user is None or user.is_deleted or not user.is_active:
        raise InvalidCredentialsError("Invalid credentials")

    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Invalid credentials")

    token, jti, expires_at = create_access_token(user.id)
    session = UserSession(
        id=uuid4(),
        user_id=user.id,
        jti_hash=hash_jti(jti),
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    await session_repo.save(session)

    return LoginResult(user=user, token=token, expires_at=expires_at)


async def logout_user(
    *,
    token: str,
    session_repo: IUserSessionRepository,
) -> None:
    """Revoke the JWT session associated with the given token."""
    try:
        jti = get_jti_from_token(token)
    except JWTError:
        return  # Already invalid — silently succeed

    jti_hash = hash_jti(jti)
    session = await session_repo.get_by_jti_hash(jti_hash)
    if session:
        await session_repo.revoke(session.id)
