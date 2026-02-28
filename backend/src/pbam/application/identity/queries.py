"""Identity use-case queries."""
from uuid import UUID

from pbam.domain.identity.entities import User
from pbam.domain.identity.repositories import IUserRepository


async def get_user_by_id(user_id: UUID, user_repo: IUserRepository) -> User | None:
    return await user_repo.get_by_id(user_id)
