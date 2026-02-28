"""Finance use-case queries, including the flow-tree aggregation."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID

from pbam.domain.finance.entities import TransactionCategory, TransactionType
from pbam.domain.finance.repositories import (
    IAccountRepository,
    ITransactionCategoryRepository,
    ITransactionCommentRepository,
    ITransactionGroupRepository,
    ITransactionRepository,
)


# ── Flow tree data structures ─────────────────────────────────────────────────

@dataclass
class FlowNode:
    """A node in the money flow DAG (income source, account, or expense category)."""
    id: str
    label: str
    node_type: str          # 'income_source' | 'account' | 'expense_category' | 'transfer'
    total_thb: Decimal
    color: str | None = None
    icon: str | None = None
    children: list["FlowNode"] = field(default_factory=list)


@dataclass
class FlowEdge:
    source_id: str
    target_id: str
    amount_thb: Decimal
    label: str | None = None


@dataclass
class FlowTree:
    """The full income→account→expense DAG for a time period."""
    nodes: list[FlowNode]
    edges: list[FlowEdge]
    total_income_thb: Decimal
    total_expense_thb: Decimal
    net_thb: Decimal


async def get_flow_tree(
    *,
    user_id: UUID,
    date_from: date | None = None,
    date_to: date | None = None,
    account_repo: IAccountRepository,
    category_repo: ITransactionCategoryRepository,
    transaction_repo: ITransactionRepository,
) -> FlowTree:
    """Build the income→account→expense flow tree."""
    transactions = await transaction_repo.list_by_user(
        user_id, date_from=date_from, date_to=date_to, limit=10000
    )
    accounts = {a.id: a for a in await account_repo.list_by_user(user_id)}
    categories = {c.id: c for c in await category_repo.list_tree_by_user(user_id)}

    # Aggregate: income category → account amounts
    income_to_account: dict[str, dict[str, Decimal]] = {}
    # Aggregate: account → expense category amounts
    account_to_expense: dict[str, dict[str, Decimal]] = {}
    # Aggregate: paired account transfers (account_from → account_to → amount)
    transfer_account_flows: list[tuple[str, str, Decimal]] = []

    total_income = Decimal("0")
    total_expense = Decimal("0")

    tx_by_id = {tx.id: tx for tx in transactions if not tx.is_deleted}
    seen_transfer_pairs: set[frozenset] = set()

    for tx in transactions:
        if tx.is_deleted:
            continue
        account_key = str(tx.account_id)
        cat_key = str(tx.category_id) if tx.category_id else "uncategorized"

        if tx.transaction_type == TransactionType.INCOME:
            total_income += tx.money.amount_thb
            income_to_account.setdefault(cat_key, {}).setdefault(account_key, Decimal("0"))
            income_to_account[cat_key][account_key] += tx.money.amount_thb

        elif tx.transaction_type == TransactionType.EXPENSE:
            total_expense += tx.money.amount_thb
            account_to_expense.setdefault(account_key, {}).setdefault(cat_key, Decimal("0"))
            account_to_expense[account_key][cat_key] += tx.money.amount_thb

        elif tx.transaction_type == TransactionType.TRANSFER and tx.transfer_pair_id:
            pair_key = frozenset([tx.id, tx.transfer_pair_id])
            if pair_key not in seen_transfer_pairs:
                seen_transfer_pairs.add(pair_key)
                paired = tx_by_id.get(tx.transfer_pair_id)
                if paired:
                    transfer_account_flows.append((
                        str(tx.account_id),
                        str(paired.account_id),
                        tx.money.amount_thb,
                    ))

    # Build nodes and edges
    nodes: list[FlowNode] = []
    edges: list[FlowEdge] = []

    # Income source nodes (categories of type income)
    for cat_key, account_flows in income_to_account.items():
        cat = categories.get(UUID(cat_key)) if cat_key != "uncategorized" else None
        total = sum(account_flows.values())
        node = FlowNode(
            id=f"income_{cat_key}",
            label=cat.name if cat else "Other Income",
            node_type="income_source",
            total_thb=total,
            color=cat.color if cat else "#52c41a",
            icon=cat.icon if cat else None,
        )
        nodes.append(node)

        for account_key, amount in account_flows.items():
            edges.append(FlowEdge(
                source_id=f"income_{cat_key}",
                target_id=f"account_{account_key}",
                amount_thb=amount,
            ))

    # Account nodes (include accounts that only appear in transfers)
    all_account_keys = set(
        k for flows in income_to_account.values() for k in flows
    ) | set(account_to_expense.keys())
    for from_key, to_key, _ in transfer_account_flows:
        all_account_keys.add(from_key)
        all_account_keys.add(to_key)

    for account_key in all_account_keys:
        account = accounts.get(UUID(account_key))
        total_in = sum(
            flows.get(account_key, Decimal("0")) for flows in income_to_account.values()
        )
        node = FlowNode(
            id=f"account_{account_key}",
            label=account.name if account else "Unknown Account",
            node_type="account",
            total_thb=total_in,
            color="#1677ff",
        )
        nodes.append(node)

    # Expense category nodes
    all_expense_keys: set[str] = set()
    for expense_flows in account_to_expense.values():
        all_expense_keys.update(expense_flows.keys())

    for cat_key in all_expense_keys:
        cat = categories.get(UUID(cat_key)) if cat_key != "uncategorized" else None
        total = sum(
            flows.get(cat_key, Decimal("0")) for flows in account_to_expense.values()
        )
        node = FlowNode(
            id=f"expense_{cat_key}",
            label=cat.name if cat else "Uncategorized",
            node_type="expense_category",
            total_thb=total,
            color=cat.color if cat else "#ff4d4f",
            icon=cat.icon if cat else None,
        )
        nodes.append(node)

        for account_key, amount in (
            (ak, flows[cat_key])
            for ak, flows in account_to_expense.items()
            if cat_key in flows
        ):
            edges.append(FlowEdge(
                source_id=f"account_{account_key}",
                target_id=f"expense_{cat_key}",
                amount_thb=amount,
            ))

    # Transfer edges: account → account (paired transfers only)
    for from_key, to_key, amount in transfer_account_flows:
        edges.append(FlowEdge(
            source_id=f"account_{from_key}",
            target_id=f"account_{to_key}",
            amount_thb=amount,
            label="Transfer",
        ))

    return FlowTree(
        nodes=nodes,
        edges=edges,
        total_income_thb=total_income,
        total_expense_thb=total_expense,
        net_thb=total_income - total_expense,
    )


async def get_category_tree(
    *,
    user_id: UUID,
    repo: ITransactionCategoryRepository,
) -> list[TransactionCategory]:
    """Return flat list of categories; caller organizes into tree."""
    return await repo.list_tree_by_user(user_id)
