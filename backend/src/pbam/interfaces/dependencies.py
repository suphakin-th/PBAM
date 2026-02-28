"""FastAPI dependency injection: DB session, current user, and PBAMFacade."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from pbam.infrastructure.auth.jwt import decode_access_token, hash_jti
from pbam.infrastructure.database.connection import get_db_session
from pbam.interfaces.facade import PBAMFacade

# ── Session ───────────────────────────────────────────────────────────────────

_bearer = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with get_db_session() as session:
        yield session


# ── Repositories (lazy imports to avoid circular) ────────────────────────────

def _build_facade(session: AsyncSession) -> PBAMFacade:
    from pbam.infrastructure.database.repositories.identity import (
        UserRepository,
        UserSessionRepository,
    )
    from pbam.infrastructure.database.repositories.finance import (
        AccountRepository,
        TransactionCategoryRepository,
        TransactionRepository,
        TransactionCommentRepository,
        TransactionGroupRepository,
    )
    from pbam.infrastructure.database.repositories.document import (
        OcrJobRepository,
        StagingTransactionRepository,
    )

    return PBAMFacade(
        user_repo=UserRepository(session),
        session_repo=UserSessionRepository(session),
        account_repo=AccountRepository(session),
        category_repo=TransactionCategoryRepository(session),
        transaction_repo=TransactionRepository(session),
        comment_repo=TransactionCommentRepository(session),
        group_repo=TransactionGroupRepository(session),
        ocr_job_repo=OcrJobRepository(session),
        staging_repo=StagingTransactionRepository(session),
    )


async def get_facade(session: Annotated[AsyncSession, Depends(get_db)]) -> PBAMFacade:
    return _build_facade(session)


# ── Auth ──────────────────────────────────────────────────────────────────────

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    facade: Annotated[PBAMFacade, Depends(get_facade)],
) -> UUID:
    if credentials is None:
        raise _CREDENTIALS_EXCEPTION

    try:
        payload = decode_access_token(credentials.credentials)
        user_id = UUID(payload["sub"])
        jti = payload["jti"]
    except (JWTError, KeyError, ValueError):
        raise _CREDENTIALS_EXCEPTION

    # Check session not revoked
    jti_hash = hash_jti(jti)
    session = await facade._session_repo.get_by_jti_hash(jti_hash)
    if session is None or not session.is_active:
        raise _CREDENTIALS_EXCEPTION

    return user_id


# Type aliases for cleaner signatures
DbSession = Annotated[AsyncSession, Depends(get_db)]
Facade = Annotated[PBAMFacade, Depends(get_facade)]
CurrentUserId = Annotated[UUID, Depends(get_current_user_id)]
