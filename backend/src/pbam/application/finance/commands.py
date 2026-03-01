"""Finance use-case commands: accounts, categories, transactions, groups, comments."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from pbam.domain.finance.entities import (
    Account,
    AccountType,
    CategoryType,
    Transaction,
    TransactionCategory,
    TransactionComment,
    TransactionGroup,
    TransactionType,
)
from pbam.domain.finance.repositories import (
    IAccountRepository,
    ITransactionCategoryRepository,
    ITransactionCommentRepository,
    ITransactionGroupRepository,
    ITransactionRepository,
)
from pbam.domain.finance.value_objects import Currency, Money


class FinanceError(Exception):
    pass


class NotFoundError(FinanceError):
    pass


class PermissionError(FinanceError):
    pass


# ── Accounts ─────────────────────────────────────────────────────────────────

async def create_account(
    *,
    user_id: UUID,
    name: str,
    account_type: str,
    currency: str = "THB",
    initial_balance: Decimal = Decimal("0"),
    metadata: dict | None = None,
    repo: IAccountRepository,
) -> Account:
    account = Account(
        id=uuid4(),
        user_id=user_id,
        name=name,
        account_type=AccountType(account_type),
        currency=currency,
        initial_balance=Money.in_thb(initial_balance),
        metadata=metadata or {},
    )
    return await repo.save(account)


async def update_account(
    *,
    account_id: UUID,
    user_id: UUID,
    name: str | None = None,
    is_active: bool | None = None,
    metadata: dict | None = None,
    repo: IAccountRepository,
) -> Account:
    account = await repo.get_by_id(account_id, user_id)
    if account is None:
        raise NotFoundError("Account not found")
    if name is not None:
        account.name = name
    if is_active is not None:
        account.is_active = is_active
    if metadata is not None:
        account.metadata = metadata
    return await repo.save(account)


async def delete_account(*, account_id: UUID, user_id: UUID, repo: IAccountRepository) -> None:
    account = await repo.get_by_id(account_id, user_id)
    if account is None:
        raise NotFoundError("Account not found")
    account.soft_delete()
    await repo.save(account)


# ── Categories ────────────────────────────────────────────────────────────────

async def create_category(
    *,
    user_id: UUID,
    name: str,
    category_type: str,
    parent_id: UUID | None = None,
    color: str | None = None,
    icon: str | None = None,
    sort_order: int = 0,
    repo: ITransactionCategoryRepository,
) -> TransactionCategory:
    category = TransactionCategory(
        id=uuid4(),
        user_id=user_id,
        parent_id=parent_id,
        name=name,
        category_type=CategoryType(category_type),
        color=color,
        icon=icon,
        sort_order=sort_order,
    )
    return await repo.save(category)


async def update_category(
    *,
    category_id: UUID,
    user_id: UUID,
    name: str | None = None,
    color: str | None = None,
    icon: str | None = None,
    sort_order: int | None = None,
    parent_id: UUID | None = None,
    repo: ITransactionCategoryRepository,
) -> TransactionCategory:
    category = await repo.get_by_id(category_id, user_id)
    if category is None:
        raise NotFoundError("Category not found")
    if name is not None:
        category.name = name
    if color is not None:
        category.color = color
    if icon is not None:
        category.icon = icon
    if sort_order is not None:
        category.sort_order = sort_order
    if parent_id is not None:
        category.parent_id = parent_id
    return await repo.save(category)


async def delete_category(*, category_id: UUID, user_id: UUID, repo: ITransactionCategoryRepository) -> None:
    category = await repo.get_by_id(category_id, user_id)
    if category is None:
        raise NotFoundError("Category not found")
    category.deleted_at = __import__("datetime").datetime.utcnow()
    await repo.save(category)


# ── Transactions ──────────────────────────────────────────────────────────────

def _build_money(
    amount: Decimal,
    currency: str,
    exchange_rate: Decimal | None,
) -> Money:
    if currency == "THB":
        return Money.in_thb(amount)
    if exchange_rate is None:
        raise FinanceError("exchange_rate is required for non-THB transactions")
    return Money.foreign(amount, Currency(currency), exchange_rate)


async def create_transaction(
    *,
    user_id: UUID,
    account_id: UUID,
    amount: Decimal,
    currency: str = "THB",
    exchange_rate: Decimal | None = None,
    transaction_type: str,
    description: str,
    transaction_date: date,
    category_id: UUID | None = None,
    payment_method: str | None = None,
    counterparty_ref: str | None = None,
    counterparty_name: str | None = None,
    tags: list[str] | None = None,
    is_recurring: bool = False,
    source_document_id: UUID | None = None,
    metadata: dict | None = None,
    repo: ITransactionRepository,
) -> Transaction:
    money = _build_money(amount, currency, exchange_rate)
    tx = Transaction(
        id=uuid4(),
        user_id=user_id,
        account_id=account_id,
        money=money,
        transaction_type=TransactionType(transaction_type),
        description=description,
        transaction_date=transaction_date,
        category_id=category_id,
        payment_method=payment_method,
        counterparty_ref=counterparty_ref,
        counterparty_name=counterparty_name,
        tags=tags or [],
        is_recurring=is_recurring,
        source_document_id=source_document_id,
        metadata=metadata or {},
    )
    return await repo.save(tx)


async def update_transaction(
    *,
    transaction_id: UUID,
    user_id: UUID,
    description: str | None = None,
    category_id: UUID | None = None,
    transaction_type: str | None = None,
    payment_method: str | None = None,
    tags: list[str] | None = None,
    transaction_date: date | None = None,
    counterparty_name: str | None = None,
    repo: ITransactionRepository,
) -> Transaction:
    tx = await repo.get_by_id(transaction_id, user_id)
    if tx is None:
        raise NotFoundError("Transaction not found")
    if description is not None:
        tx.description = description
    if category_id is not None:
        tx.category_id = category_id
    if transaction_type is not None:
        tx.transaction_type = TransactionType(transaction_type)
    if payment_method is not None:
        tx.payment_method = payment_method
    if tags is not None:
        tx.tags = tags
    if transaction_date is not None:
        tx.transaction_date = transaction_date
    if counterparty_name is not None:
        tx.counterparty_name = counterparty_name
    return await repo.save(tx)


async def link_transfer(
    *,
    tx_id: UUID,
    pair_id: UUID,
    user_id: UUID,
    repo: ITransactionRepository,
) -> tuple[Transaction, Transaction]:
    tx = await repo.get_by_id(tx_id, user_id)
    if tx is None:
        raise NotFoundError("Transaction not found")
    pair = await repo.get_by_id(pair_id, user_id)
    if pair is None:
        raise NotFoundError("Pair transaction not found")
    tx.transfer_pair_id = pair_id
    pair.transfer_pair_id = tx_id
    await repo.save(tx)
    await repo.save(pair)
    return tx, pair


async def unlink_transfer(
    *,
    tx_id: UUID,
    user_id: UUID,
    repo: ITransactionRepository,
) -> Transaction:
    tx = await repo.get_by_id(tx_id, user_id)
    if tx is None:
        raise NotFoundError("Transaction not found")
    if tx.transfer_pair_id:
        pair = await repo.get_by_id(tx.transfer_pair_id, user_id)
        if pair:
            pair.transfer_pair_id = None
            await repo.save(pair)
    tx.transfer_pair_id = None
    await repo.save(tx)
    return tx


async def delete_transaction(*, transaction_id: UUID, user_id: UUID, repo: ITransactionRepository) -> None:
    tx = await repo.get_by_id(transaction_id, user_id)
    if tx is None:
        raise NotFoundError("Transaction not found")
    tx.soft_delete()
    await repo.save(tx)


# ── Comments ──────────────────────────────────────────────────────────────────

async def add_comment(
    *,
    transaction_id: UUID,
    user_id: UUID,
    content: str,
    repo: ITransactionCommentRepository,
) -> TransactionComment:
    comment = TransactionComment(
        id=uuid4(),
        transaction_id=transaction_id,
        user_id=user_id,
        content=content,
    )
    return await repo.save(comment)


async def delete_comment(*, comment_id: UUID, user_id: UUID, repo: ITransactionCommentRepository) -> None:
    # Soft-delete handled by repo
    await repo.delete(comment_id, user_id)


# ── Groups ────────────────────────────────────────────────────────────────────

async def create_group(
    *,
    user_id: UUID,
    name: str,
    description: str | None = None,
    color: str | None = None,
    repo: ITransactionGroupRepository,
) -> TransactionGroup:
    group = TransactionGroup(id=uuid4(), user_id=user_id, name=name, description=description, color=color)
    return await repo.save(group)


async def add_transaction_to_group(
    *,
    group_id: UUID,
    transaction_id: UUID,
    user_id: UUID,
    group_repo: ITransactionGroupRepository,
) -> None:
    group = await group_repo.get_by_id(group_id, user_id)
    if group is None:
        raise NotFoundError("Group not found")
    await group_repo.add_member(group_id, transaction_id)


async def remove_transaction_from_group(
    *,
    group_id: UUID,
    transaction_id: UUID,
    user_id: UUID,
    group_repo: ITransactionGroupRepository,
) -> None:
    group = await group_repo.get_by_id(group_id, user_id)
    if group is None:
        raise NotFoundError("Group not found")
    await group_repo.remove_member(group_id, transaction_id)
