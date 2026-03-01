"""Transactions router: CRUD + flow tree."""
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from pbam.application.finance.commands import NotFoundError
from pbam.interfaces.api.v1.schemas.finance import (
    CommentCreate,
    CommentResponse,
    FlowTreeResponse,
    TransactionCreate,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdate,
)
from pbam.interfaces.dependencies import CurrentUserId, Facade

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("/flow-tree", response_model=FlowTreeResponse)
async def flow_tree(
    facade: Facade,
    current_user_id: CurrentUserId,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
):
    tree = await facade.get_flow_tree(current_user_id, date_from, date_to)
    return FlowTreeResponse(
        nodes=[
            {"id": n.id, "label": n.label, "node_type": n.node_type,
             "total_thb": n.total_thb, "color": n.color, "icon": n.icon}
            for n in tree.nodes
        ],
        edges=[
            {"source_id": e.source_id, "target_id": e.target_id,
             "amount_thb": e.amount_thb, "label": e.label}
            for e in tree.edges
        ],
        total_income_thb=tree.total_income_thb,
        total_expense_thb=tree.total_expense_thb,
        net_thb=tree.net_thb,
    )


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    facade: Facade,
    current_user_id: CurrentUserId,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
    account_id: Annotated[UUID | None, Query()] = None,
    category_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    filter_kwargs = dict(
        date_from=date_from, date_to=date_to,
        account_id=account_id, category_id=category_id,
    )
    txs, total = await facade.list_transactions_with_count(
        current_user_id, limit=limit, offset=offset, **filter_kwargs
    )
    return TransactionListResponse(
        items=[_tx_response(tx) for tx in txs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(body: TransactionCreate, facade: Facade, current_user_id: CurrentUserId):
    tx = await facade.create_transaction(
        current_user_id,
        account_id=body.account_id,
        amount=body.amount,
        currency=body.currency,
        exchange_rate=body.exchange_rate,
        transaction_type=body.transaction_type,
        description=body.description,
        transaction_date=body.transaction_date,
        category_id=body.category_id,
        payment_method=body.payment_method,
        tags=body.tags,
        is_recurring=body.is_recurring,
    )
    return _tx_response(tx)


@router.patch("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: UUID,
    body: TransactionUpdate,
    facade: Facade,
    current_user_id: CurrentUserId,
):
    try:
        tx = await facade.update_transaction(
            transaction_id, current_user_id,
            **body.model_dump(exclude_none=True),
        )
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return _tx_response(tx)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(transaction_id: UUID, facade: Facade, current_user_id: CurrentUserId):
    try:
        await facade.delete_transaction(transaction_id, current_user_id)
    except NotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")


@router.post("/{transaction_id}/link-transfer/{pair_id}", response_model=TransactionResponse)
async def link_transfer(
    transaction_id: UUID,
    pair_id: UUID,
    facade: Facade,
    current_user_id: CurrentUserId,
):
    try:
        tx, _ = await facade.link_transfer(transaction_id, pair_id, current_user_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return _tx_response(tx)


@router.delete("/{transaction_id}/link-transfer", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_transfer(
    transaction_id: UUID,
    facade: Facade,
    current_user_id: CurrentUserId,
):
    try:
        await facade.unlink_transfer(transaction_id, current_user_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ── Comments ──────────────────────────────────────────────────────────────────

@router.get("/{transaction_id}/comments", response_model=list[CommentResponse])
async def list_comments(transaction_id: UUID, facade: Facade, current_user_id: CurrentUserId):
    return await facade.list_comments(transaction_id, current_user_id)


@router.post("/{transaction_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def add_comment(
    transaction_id: UUID,
    body: CommentCreate,
    facade: Facade,
    current_user_id: CurrentUserId,
):
    comment = await facade.add_comment(transaction_id, current_user_id, body.content)
    return CommentResponse(
        id=comment.id,
        transaction_id=comment.transaction_id,
        content=comment.content,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


@router.delete("/{transaction_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    transaction_id: UUID,
    comment_id: UUID,
    facade: Facade,
    current_user_id: CurrentUserId,
):
    await facade.delete_comment(comment_id, current_user_id)


def _tx_response(tx) -> TransactionResponse:
    return TransactionResponse(
        id=tx.id,
        account_id=tx.account_id,
        category_id=tx.category_id,
        payment_method=tx.payment_method,
        counterparty_ref=tx.counterparty_ref,
        counterparty_name=tx.counterparty_name,
        transfer_pair_id=tx.transfer_pair_id,
        amount_thb=tx.money.amount_thb,
        original_amount=tx.money.original_amount if tx.money.is_foreign_currency else None,
        original_currency=tx.money.original_currency.code if tx.money.is_foreign_currency else None,
        transaction_type=tx.transaction_type,
        description=tx.description,
        transaction_date=tx.transaction_date,
        tags=tx.tags,
        is_recurring=tx.is_recurring,
        metadata=tx.metadata or None,
        created_at=tx.created_at,
    )
