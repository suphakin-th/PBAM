"""PBAMFacade — the single entry point to the application layer.

All routers go through this facade instead of calling application functions directly.
This enforces the Facade pattern and keeps the API layer thin.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from pbam.application.document import commands as doc_commands
from pbam.application.document import queries as doc_queries
from pbam.application.finance import commands as fin_commands
from pbam.application.finance import queries as fin_queries
from pbam.application.identity import commands as id_commands
from pbam.application.identity import queries as id_queries
from pbam.domain.document.entities import OcrJob, StagingTransaction
from pbam.domain.finance.entities import (
    Account,
    Transaction,
    TransactionCategory,
    TransactionComment,
    TransactionGroup,
)
from pbam.domain.identity.entities import User

if TYPE_CHECKING:
    from pbam.application.finance.queries import FlowTree
    from pbam.application.identity.commands import LoginResult, RegisterResult


class PBAMFacade:
    """Aggregates all application use cases. Injected via FastAPI dependency."""

    def __init__(
        self,
        user_repo,
        session_repo,
        account_repo,
        category_repo,
        transaction_repo,
        comment_repo,
        group_repo,
        ocr_job_repo,
        staging_repo,
    ) -> None:
        self._user_repo = user_repo
        self._session_repo = session_repo
        self._account_repo = account_repo
        self._category_repo = category_repo
        self._transaction_repo = transaction_repo
        self._comment_repo = comment_repo
        self._group_repo = group_repo
        self._ocr_job_repo = ocr_job_repo
        self._staging_repo = staging_repo

    # ── Identity ──────────────────────────────────────────────────────────────

    async def register(
        self, email: str, username: str, password: str,
        ip_address: str | None = None, user_agent: str | None = None,
    ) -> "RegisterResult":
        return await id_commands.register_user(
            email=email, username=username, password=password,
            user_repo=self._user_repo, session_repo=self._session_repo,
            ip_address=ip_address, user_agent=user_agent,
        )

    async def login(
        self, username_or_email: str, password: str,
        ip_address: str | None = None, user_agent: str | None = None,
    ) -> "LoginResult":
        return await id_commands.login_user(
            username_or_email=username_or_email, password=password,
            user_repo=self._user_repo, session_repo=self._session_repo,
            ip_address=ip_address, user_agent=user_agent,
        )

    async def logout(self, token: str) -> None:
        await id_commands.logout_user(token=token, session_repo=self._session_repo)

    async def get_current_user(self, user_id: UUID) -> User | None:
        return await id_queries.get_user_by_id(user_id, self._user_repo)

    # ── Accounts ──────────────────────────────────────────────────────────────

    async def list_accounts(self, user_id: UUID) -> list[Account]:
        return await self._account_repo.list_by_user(user_id)

    async def create_account(self, user_id: UUID, **kwargs) -> Account:
        return await fin_commands.create_account(user_id=user_id, repo=self._account_repo, **kwargs)

    async def update_account(self, account_id: UUID, user_id: UUID, **kwargs) -> Account:
        return await fin_commands.update_account(account_id=account_id, user_id=user_id, repo=self._account_repo, **kwargs)

    async def delete_account(self, account_id: UUID, user_id: UUID) -> None:
        await fin_commands.delete_account(account_id=account_id, user_id=user_id, repo=self._account_repo)

    # ── Categories ────────────────────────────────────────────────────────────

    async def list_categories(self, user_id: UUID) -> list[TransactionCategory]:
        return await fin_queries.get_category_tree(user_id=user_id, repo=self._category_repo)

    async def create_category(self, user_id: UUID, **kwargs) -> TransactionCategory:
        return await fin_commands.create_category(user_id=user_id, repo=self._category_repo, **kwargs)

    async def update_category(self, category_id: UUID, user_id: UUID, **kwargs) -> TransactionCategory:
        return await fin_commands.update_category(category_id=category_id, user_id=user_id, repo=self._category_repo, **kwargs)

    async def delete_category(self, category_id: UUID, user_id: UUID) -> None:
        await fin_commands.delete_category(category_id=category_id, user_id=user_id, repo=self._category_repo)

    # ── Transactions ──────────────────────────────────────────────────────────

    async def list_transactions(self, user_id: UUID, **kwargs) -> list[Transaction]:
        return await self._transaction_repo.list_by_user(user_id, **kwargs)

    async def list_transactions_with_count(
        self, user_id: UUID, *, limit: int = 50, offset: int = 0, **filter_kwargs
    ) -> tuple[list[Transaction], int]:
        txs = await self._transaction_repo.list_by_user(user_id, limit=limit, offset=offset, **filter_kwargs)
        total = await self._transaction_repo.count_by_user(user_id, **filter_kwargs)
        return txs, total

    async def create_transaction(self, user_id: UUID, **kwargs) -> Transaction:
        return await fin_commands.create_transaction(user_id=user_id, repo=self._transaction_repo, **kwargs)

    async def update_transaction(self, transaction_id: UUID, user_id: UUID, **kwargs) -> Transaction:
        return await fin_commands.update_transaction(transaction_id=transaction_id, user_id=user_id, repo=self._transaction_repo, **kwargs)

    async def delete_transaction(self, transaction_id: UUID, user_id: UUID) -> None:
        await fin_commands.delete_transaction(transaction_id=transaction_id, user_id=user_id, repo=self._transaction_repo)

    async def link_transfer(self, tx_id: UUID, pair_id: UUID, user_id: UUID) -> tuple[Transaction, Transaction]:
        return await fin_commands.link_transfer(tx_id=tx_id, pair_id=pair_id, user_id=user_id, repo=self._transaction_repo)

    async def unlink_transfer(self, tx_id: UUID, user_id: UUID) -> Transaction:
        return await fin_commands.unlink_transfer(tx_id=tx_id, user_id=user_id, repo=self._transaction_repo)

    async def count_transactions(self, user_id: UUID, **kwargs) -> int:
        return await self._transaction_repo.count_by_user(user_id, **kwargs)

    async def get_flow_tree(self, user_id: UUID, date_from: date | None, date_to: date | None) -> "FlowTree":
        return await fin_queries.get_flow_tree(
            user_id=user_id, date_from=date_from, date_to=date_to,
            account_repo=self._account_repo,
            category_repo=self._category_repo,
            transaction_repo=self._transaction_repo,
        )

    # ── Comments ──────────────────────────────────────────────────────────────

    async def list_comments(self, transaction_id: UUID, user_id: UUID) -> list[TransactionComment]:
        return await self._comment_repo.list_by_transaction(transaction_id, user_id)

    async def add_comment(self, transaction_id: UUID, user_id: UUID, content: str) -> TransactionComment:
        return await fin_commands.add_comment(
            transaction_id=transaction_id, user_id=user_id,
            content=content, repo=self._comment_repo,
        )

    async def delete_comment(self, comment_id: UUID, user_id: UUID) -> None:
        await fin_commands.delete_comment(comment_id=comment_id, user_id=user_id, repo=self._comment_repo)

    # ── Groups ────────────────────────────────────────────────────────────────

    async def list_groups(self, user_id: UUID) -> list[TransactionGroup]:
        return await self._group_repo.list_by_user(user_id)

    async def create_group(self, user_id: UUID, **kwargs) -> TransactionGroup:
        return await fin_commands.create_group(user_id=user_id, repo=self._group_repo, **kwargs)

    async def add_to_group(self, group_id: UUID, transaction_id: UUID, user_id: UUID) -> None:
        await fin_commands.add_transaction_to_group(
            group_id=group_id, transaction_id=transaction_id,
            user_id=user_id, group_repo=self._group_repo,
        )

    async def remove_from_group(self, group_id: UUID, transaction_id: UUID, user_id: UUID) -> None:
        await fin_commands.remove_transaction_from_group(
            group_id=group_id, transaction_id=transaction_id,
            user_id=user_id, group_repo=self._group_repo,
        )

    # ── OCR / Document ────────────────────────────────────────────────────────

    async def submit_ocr_job(self, user_id: UUID, filename: str, file_bytes: bytes) -> OcrJob:
        return await doc_commands.submit_ocr_job(
            user_id=user_id, filename=filename, file_bytes=file_bytes,
            job_repo=self._ocr_job_repo, staging_repo=self._staging_repo,
        )

    async def get_ocr_job(self, job_id: UUID, user_id: UUID) -> OcrJob | None:
        return await doc_queries.get_ocr_job(job_id, user_id, self._ocr_job_repo)

    async def list_ocr_jobs(self, user_id: UUID) -> list[OcrJob]:
        return await doc_queries.list_ocr_jobs(user_id, self._ocr_job_repo)

    async def get_staging_rows(self, job_id: UUID, user_id: UUID) -> list[StagingTransaction]:
        return await doc_queries.get_staging_rows(job_id, user_id, self._staging_repo)

    async def update_staging_row(self, staging_id: UUID, user_id: UUID, updates: dict) -> StagingTransaction:
        return await doc_commands.update_staging_row(
            staging_id=staging_id, user_id=user_id,
            updates=updates, staging_repo=self._staging_repo,
        )

    async def discard_staging_row(self, staging_id: UUID, user_id: UUID) -> None:
        await doc_commands.discard_staging_row(
            staging_id=staging_id, user_id=user_id, staging_repo=self._staging_repo,
        )

    async def commit_staging(
        self, job_id: UUID, user_id: UUID, default_account_id: UUID
    ) -> int:
        return await doc_commands.commit_staging(
            job_id=job_id, user_id=user_id, default_account_id=default_account_id,
            job_repo=self._ocr_job_repo, staging_repo=self._staging_repo,
            transaction_repo=self._transaction_repo,
        )
