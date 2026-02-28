"""Accounts router: CRUD."""
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from pbam.application.finance.commands import NotFoundError
from pbam.interfaces.api.v1.schemas.finance import AccountCreate, AccountResponse, AccountUpdate
from pbam.interfaces.dependencies import CurrentUserId, Facade

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountResponse])
async def list_accounts(facade: Facade, current_user_id: CurrentUserId):
    accounts = await facade.list_accounts(current_user_id)
    return [AccountResponse(id=a.id, name=a.name, account_type=a.account_type,
                            currency=a.currency, is_active=a.is_active, created_at=a.created_at)
            for a in accounts]


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(body: AccountCreate, facade: Facade, current_user_id: CurrentUserId):
    account = await facade.create_account(
        current_user_id,
        name=body.name,
        account_type=body.account_type,
        currency=body.currency,
        initial_balance=body.initial_balance,
        metadata=body.metadata,
    )
    return AccountResponse(id=account.id, name=account.name, account_type=account.account_type,
                           currency=account.currency, is_active=account.is_active,
                           created_at=account.created_at)


@router.patch("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: UUID, body: AccountUpdate, facade: Facade, current_user_id: CurrentUserId
):
    try:
        account = await facade.update_account(
            account_id, current_user_id, **body.model_dump(exclude_none=True)
        )
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return AccountResponse(id=account.id, name=account.name, account_type=account.account_type,
                           currency=account.currency, is_active=account.is_active,
                           created_at=account.created_at)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(account_id: UUID, facade: Facade, current_user_id: CurrentUserId):
    try:
        await facade.delete_account(account_id, current_user_id)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
