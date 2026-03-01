"""Concrete SQLAlchemy repository implementations for the finance context."""
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func as sqlfunc, select
from sqlalchemy.ext.asyncio import AsyncSession

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
from pbam.domain.finance.value_objects import Currency, Money
from pbam.infrastructure.database.models.finance import (
    AccountModel,
    TransactionCategoryModel,
    TransactionCommentModel,
    TransactionGroupMemberModel,
    TransactionGroupModel,
    TransactionModel,
)


class AccountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_id(self, account_id: UUID, user_id: UUID) -> Account | None:
        stmt = select(AccountModel).where(
            AccountModel.id == account_id,
            AccountModel.user_id == user_id,
            AccountModel.deleted_at.is_(None),
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return _to_account(row) if row else None

    async def list_by_user(self, user_id: UUID) -> list[Account]:
        stmt = select(AccountModel).where(
            AccountModel.user_id == user_id,
            AccountModel.deleted_at.is_(None),
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [_to_account(r) for r in rows]

    async def save(self, account: Account) -> Account:
        existing = await self._s.get(AccountModel, account.id)
        if existing:
            existing.name = account.name
            existing.is_active = account.is_active
            existing.metadata_ = account.metadata
            existing.deleted_at = account.deleted_at
        else:
            self._s.add(AccountModel(
                id=account.id,
                user_id=account.user_id,
                name=account.name,
                account_type=str(account.account_type),
                currency=account.currency,
                initial_balance=account.initial_balance.amount_thb,
                metadata_=account.metadata,
                is_active=account.is_active,
                created_at=account.created_at,
                updated_at=account.updated_at,
            ))
        await self._s.flush()
        return account

    async def delete(self, account_id: UUID, user_id: UUID) -> None:
        model = await self._s.get(AccountModel, account_id)
        if model and model.user_id == user_id:
            model.deleted_at = datetime.now(timezone.utc)
            await self._s.flush()


class TransactionCategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_id(self, category_id: UUID, user_id: UUID) -> TransactionCategory | None:
        stmt = select(TransactionCategoryModel).where(
            TransactionCategoryModel.id == category_id,
            TransactionCategoryModel.user_id == user_id,
            TransactionCategoryModel.deleted_at.is_(None),
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return _to_category(row) if row else None

    async def list_tree_by_user(self, user_id: UUID) -> list[TransactionCategory]:
        stmt = select(TransactionCategoryModel).where(
            TransactionCategoryModel.user_id == user_id,
            TransactionCategoryModel.deleted_at.is_(None),
        ).order_by(TransactionCategoryModel.sort_order)
        rows = (await self._s.execute(stmt)).scalars().all()
        return [_to_category(r) for r in rows]

    async def save(self, category: TransactionCategory) -> TransactionCategory:
        existing = await self._s.get(TransactionCategoryModel, category.id)
        if existing:
            existing.name = category.name
            existing.parent_id = category.parent_id
            existing.color = category.color
            existing.icon = category.icon
            existing.sort_order = category.sort_order
            existing.deleted_at = category.deleted_at
        else:
            self._s.add(TransactionCategoryModel(
                id=category.id,
                user_id=category.user_id,
                parent_id=category.parent_id,
                name=category.name,
                category_type=str(category.category_type),
                color=category.color,
                icon=category.icon,
                sort_order=category.sort_order,
                is_system=category.is_system,
                created_at=category.created_at,
                updated_at=category.updated_at,
            ))
        await self._s.flush()
        return category

    async def delete(self, category_id: UUID, user_id: UUID) -> None:
        model = await self._s.get(TransactionCategoryModel, category_id)
        if model and model.user_id == user_id:
            model.deleted_at = datetime.now(timezone.utc)
            await self._s.flush()


class TransactionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_id(self, transaction_id: UUID, user_id: UUID) -> Transaction | None:
        stmt = select(TransactionModel).where(
            TransactionModel.id == transaction_id,
            TransactionModel.user_id == user_id,
            TransactionModel.deleted_at.is_(None),
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return _to_transaction(row) if row else None

    async def list_by_user(
        self,
        user_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        account_id: UUID | None = None,
        category_id: UUID | None = None,
        transaction_type: str | None = None,
        amount_min: Decimal | None = None,
        amount_max: Decimal | None = None,
        uncategorized: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Transaction]:
        conditions = [
            TransactionModel.user_id == user_id,
            TransactionModel.deleted_at.is_(None),
        ]
        if date_from:
            conditions.append(TransactionModel.transaction_date >= date_from)
        if date_to:
            conditions.append(TransactionModel.transaction_date <= date_to)
        if account_id:
            conditions.append(TransactionModel.account_id == account_id)
        if uncategorized:
            conditions.append(TransactionModel.category_id.is_(None))
        elif category_id:
            conditions.append(TransactionModel.category_id == category_id)
        if transaction_type:
            conditions.append(TransactionModel.transaction_type == transaction_type)
        if amount_min is not None:
            conditions.append(TransactionModel.amount_thb >= amount_min)
        if amount_max is not None:
            conditions.append(TransactionModel.amount_thb <= amount_max)

        stmt = (
            select(TransactionModel)
            .where(and_(*conditions))
            .order_by(TransactionModel.transaction_date.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [_to_transaction(r) for r in rows]

    async def save(self, transaction: Transaction) -> Transaction:
        existing = await self._s.get(TransactionModel, transaction.id)
        if existing:
            existing.description = transaction.description
            existing.category_id = transaction.category_id
            existing.payment_method = transaction.payment_method
            existing.counterparty_name = transaction.counterparty_name
            existing.counterparty_ref = transaction.counterparty_ref
            existing.transfer_pair_id = transaction.transfer_pair_id
            existing.tags = transaction.tags
            existing.transaction_date = transaction.transaction_date
            existing.deleted_at = transaction.deleted_at
            existing.updated_at = datetime.now(timezone.utc)
        else:
            self._s.add(TransactionModel(
                id=transaction.id,
                user_id=transaction.user_id,
                account_id=transaction.account_id,
                category_id=transaction.category_id,
                payment_method=transaction.payment_method,
                counterparty_ref=transaction.counterparty_ref,
                counterparty_name=transaction.counterparty_name,
                transfer_pair_id=transaction.transfer_pair_id,
                amount_thb=transaction.money.amount_thb,
                original_amount=transaction.money.original_amount if transaction.money.is_foreign_currency else None,
                original_currency=transaction.money.original_currency.code if transaction.money.is_foreign_currency else None,
                exchange_rate=transaction.money.exchange_rate,
                transaction_type=str(transaction.transaction_type),
                description=transaction.description,
                transaction_date=transaction.transaction_date,
                tags=transaction.tags,
                source_document_id=transaction.source_document_id,
                is_recurring=transaction.is_recurring,
                metadata_=transaction.metadata,
                created_at=transaction.created_at,
                updated_at=transaction.updated_at,
            ))
        await self._s.flush()
        return transaction

    async def count_by_user(
        self,
        user_id: UUID,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        account_id: UUID | None = None,
        category_id: UUID | None = None,
        transaction_type: str | None = None,
        amount_min: Decimal | None = None,
        amount_max: Decimal | None = None,
        uncategorized: bool | None = None,
    ) -> int:
        conditions = [
            TransactionModel.user_id == user_id,
            TransactionModel.deleted_at.is_(None),
        ]
        if date_from:
            conditions.append(TransactionModel.transaction_date >= date_from)
        if date_to:
            conditions.append(TransactionModel.transaction_date <= date_to)
        if account_id:
            conditions.append(TransactionModel.account_id == account_id)
        if uncategorized:
            conditions.append(TransactionModel.category_id.is_(None))
        elif category_id:
            conditions.append(TransactionModel.category_id == category_id)
        if transaction_type:
            conditions.append(TransactionModel.transaction_type == transaction_type)
        if amount_min is not None:
            conditions.append(TransactionModel.amount_thb >= amount_min)
        if amount_max is not None:
            conditions.append(TransactionModel.amount_thb <= amount_max)
        stmt = select(sqlfunc.count()).select_from(TransactionModel).where(and_(*conditions))
        result = await self._s.execute(stmt)
        return result.scalar_one()

    async def bulk_save(self, transactions: list[Transaction]) -> list[Transaction]:
        for tx in transactions:
            await self.save(tx)
        return transactions

    async def delete(self, transaction_id: UUID, user_id: UUID) -> None:
        model = await self._s.get(TransactionModel, transaction_id)
        if model and model.user_id == user_id:
            model.deleted_at = datetime.now(timezone.utc)
            await self._s.flush()


class TransactionCommentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def list_by_transaction(self, transaction_id: UUID, user_id: UUID) -> list[TransactionComment]:
        stmt = select(TransactionCommentModel).where(
            TransactionCommentModel.transaction_id == transaction_id,
            TransactionCommentModel.user_id == user_id,
            TransactionCommentModel.deleted_at.is_(None),
        ).order_by(TransactionCommentModel.created_at)
        rows = (await self._s.execute(stmt)).scalars().all()
        return [_to_comment(r) for r in rows]

    async def save(self, comment: TransactionComment) -> TransactionComment:
        self._s.add(TransactionCommentModel(
            id=comment.id,
            transaction_id=comment.transaction_id,
            user_id=comment.user_id,
            content=comment.content,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
        ))
        await self._s.flush()
        return comment

    async def delete(self, comment_id: UUID, user_id: UUID) -> None:
        model = await self._s.get(TransactionCommentModel, comment_id)
        if model and model.user_id == user_id:
            model.deleted_at = datetime.now(timezone.utc)
            await self._s.flush()


class TransactionGroupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_id(self, group_id: UUID, user_id: UUID) -> TransactionGroup | None:
        stmt = select(TransactionGroupModel).where(
            TransactionGroupModel.id == group_id,
            TransactionGroupModel.user_id == user_id,
            TransactionGroupModel.deleted_at.is_(None),
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return _to_group(row) if row else None

    async def list_by_user(self, user_id: UUID) -> list[TransactionGroup]:
        stmt = select(TransactionGroupModel).where(
            TransactionGroupModel.user_id == user_id,
            TransactionGroupModel.deleted_at.is_(None),
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [_to_group(r) for r in rows]

    async def save(self, group: TransactionGroup) -> TransactionGroup:
        self._s.add(TransactionGroupModel(
            id=group.id,
            user_id=group.user_id,
            name=group.name,
            description=group.description,
            color=group.color,
            created_at=group.created_at,
            updated_at=group.updated_at,
        ))
        await self._s.flush()
        return group

    async def add_member(self, group_id: UUID, transaction_id: UUID) -> None:
        self._s.add(TransactionGroupMemberModel(group_id=group_id, transaction_id=transaction_id))
        await self._s.flush()

    async def remove_member(self, group_id: UUID, transaction_id: UUID) -> None:
        model = await self._s.get(TransactionGroupMemberModel, (group_id, transaction_id))
        if model:
            await self._s.delete(model)
            await self._s.flush()

    async def list_group_transactions(self, group_id: UUID, user_id: UUID) -> list[Transaction]:
        stmt = (
            select(TransactionModel)
            .join(TransactionGroupMemberModel, TransactionModel.id == TransactionGroupMemberModel.transaction_id)
            .where(
                TransactionGroupMemberModel.group_id == group_id,
                TransactionModel.user_id == user_id,
                TransactionModel.deleted_at.is_(None),
            )
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [_to_transaction(r) for r in rows]

    async def delete(self, group_id: UUID, user_id: UUID) -> None:
        model = await self._s.get(TransactionGroupModel, group_id)
        if model and model.user_id == user_id:
            model.deleted_at = datetime.now(timezone.utc)
            await self._s.flush()


# ── Mappers ───────────────────────────────────────────────────────────────────

def _to_account(m: AccountModel) -> Account:
    return Account(
        id=m.id,
        user_id=m.user_id,
        name=m.name,
        account_type=AccountType(m.account_type),
        currency=m.currency,
        initial_balance=Money.in_thb(m.initial_balance),
        is_active=m.is_active,
        metadata=m.metadata_ or {},
        created_at=m.created_at,
        updated_at=m.updated_at,
        deleted_at=m.deleted_at,
    )


def _to_category(m: TransactionCategoryModel) -> TransactionCategory:
    return TransactionCategory(
        id=m.id,
        user_id=m.user_id,
        parent_id=m.parent_id,
        name=m.name,
        category_type=CategoryType(m.category_type),
        color=m.color,
        icon=m.icon,
        sort_order=m.sort_order,
        is_system=m.is_system,
        created_at=m.created_at,
        updated_at=m.updated_at,
        deleted_at=m.deleted_at,
    )


def _to_transaction(m: TransactionModel) -> Transaction:
    if m.original_currency and m.original_currency != "THB":
        money = Money(
            amount_thb=m.amount_thb,
            original_amount=m.original_amount or m.amount_thb,
            original_currency=Currency(m.original_currency),
        )
    else:
        money = Money.in_thb(m.amount_thb)

    return Transaction(
        id=m.id,
        user_id=m.user_id,
        account_id=m.account_id,
        category_id=m.category_id,
        payment_method=m.payment_method,
        counterparty_ref=m.counterparty_ref,
        counterparty_name=m.counterparty_name,
        transfer_pair_id=m.transfer_pair_id,
        money=money,
        transaction_type=TransactionType(m.transaction_type),
        description=m.description,
        transaction_date=m.transaction_date,
        tags=list(m.tags or []),
        source_document_id=m.source_document_id,
        is_recurring=m.is_recurring,
        metadata=m.metadata_ or {},
        created_at=m.created_at,
        updated_at=m.updated_at,
        deleted_at=m.deleted_at,
    )


def _to_comment(m: TransactionCommentModel) -> TransactionComment:
    from pbam.domain.finance.entities import TransactionComment
    return TransactionComment(
        id=m.id,
        transaction_id=m.transaction_id,
        user_id=m.user_id,
        content=m.content,
        created_at=m.created_at,
        updated_at=m.updated_at,
        deleted_at=m.deleted_at,
    )


def _to_group(m: TransactionGroupModel) -> TransactionGroup:
    return TransactionGroup(
        id=m.id,
        user_id=m.user_id,
        name=m.name,
        description=m.description,
        color=m.color,
        created_at=m.created_at,
        updated_at=m.updated_at,
        deleted_at=m.deleted_at,
    )
