"""Transaction groups router."""
from uuid import UUID

from fastapi import APIRouter, status

from pbam.interfaces.api.v1.schemas.finance import GroupCreate, GroupResponse
from pbam.interfaces.dependencies import CurrentUserId, Facade

router = APIRouter(prefix="/groups", tags=["groups"])


@router.get("", response_model=list[GroupResponse])
async def list_groups(facade: Facade, current_user_id: CurrentUserId):
    groups = await facade.list_groups(current_user_id)
    return [GroupResponse(id=g.id, name=g.name, description=g.description,
                          color=g.color, created_at=g.created_at) for g in groups]


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(body: GroupCreate, facade: Facade, current_user_id: CurrentUserId):
    group = await facade.create_group(
        current_user_id, name=body.name, description=body.description, color=body.color
    )
    return GroupResponse(id=group.id, name=group.name, description=group.description,
                         color=group.color, created_at=group.created_at)


@router.post("/{group_id}/members/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_member(
    group_id: UUID, transaction_id: UUID, facade: Facade, current_user_id: CurrentUserId
):
    await facade.add_to_group(group_id, transaction_id, current_user_id)


@router.delete("/{group_id}/members/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    group_id: UUID, transaction_id: UUID, facade: Facade, current_user_id: CurrentUserId
):
    await facade.remove_from_group(group_id, transaction_id, current_user_id)
