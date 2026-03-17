"""Finance use-case queries, including the flow-tree aggregation."""
from __future__ import annotations

import re
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
    # Aggregate: unpaired transfers grouped by counterparty ref
    # key: (counterparty_label, account_key, is_inbound)  value: amount
    unpaired_transfer_flows: dict[tuple[str, str, bool], Decimal] = {}

    total_income = Decimal("0")
    total_expense = Decimal("0")

    tx_by_id = {tx.id: tx for tx in transactions if not tx.is_deleted}
    seen_transfer_pairs: set[frozenset] = set()

    _INBOUND_RE = re.compile(r"รับโอน|รับเงิน|เงินเข้าจาก", re.I)

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

        elif tx.transaction_type == TransactionType.TRANSFER:
            if tx.transfer_pair_id:
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
            else:
                # Unpaired transfer — group by counterparty label so we aggregate
                # multiple transactions to the same counterparty into one edge.
                cp = tx.counterparty_ref or "External"
                is_inbound = bool(_INBOUND_RE.search(tx.description or ""))
                key = (cp, account_key, is_inbound)
                unpaired_transfer_flows[key] = (
                    unpaired_transfer_flows.get(key, Decimal("0")) + tx.money.amount_thb
                )

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

    # Account nodes (include accounts that appear in any flow type)
    all_account_keys = set(
        k for flows in income_to_account.values() for k in flows
    ) | set(account_to_expense.keys())
    for from_key, to_key, _ in transfer_account_flows:
        all_account_keys.add(from_key)
        all_account_keys.add(to_key)
    for (_cp, acct_key, _dir) in unpaired_transfer_flows:
        all_account_keys.add(acct_key)

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

    # Transfer edges: account → account (paired transfers)
    for from_key, to_key, amount in transfer_account_flows:
        edges.append(FlowEdge(
            source_id=f"account_{from_key}",
            target_id=f"account_{to_key}",
            amount_thb=amount,
            label="Transfer",
        ))

    # Unpaired transfers: create counterparty pseudo-nodes + edges
    # Group nodes by counterparty label (avoid duplicates)
    seen_cp_nodes: set[str] = set()
    for (cp_label, account_key, is_inbound), amount in unpaired_transfer_flows.items():
        cp_node_id = f"transfer_{cp_label.replace(' ', '_')}"
        if cp_node_id not in seen_cp_nodes:
            seen_cp_nodes.add(cp_node_id)
            nodes.append(FlowNode(
                id=cp_node_id,
                label=cp_label,
                node_type="transfer",
                total_thb=Decimal("0"),  # pseudo-node, no standalone total
                color="#9254de",
            ))
        if is_inbound:
            # Money came IN: counterparty → account
            edges.append(FlowEdge(
                source_id=cp_node_id,
                target_id=f"account_{account_key}",
                amount_thb=amount,
                label="Transfer",
            ))
        else:
            # Money went OUT: account → counterparty
            edges.append(FlowEdge(
                source_id=f"account_{account_key}",
                target_id=cp_node_id,
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


# ── Summary data structures ────────────────────────────────────────────────────

@dataclass
class CategoryStat:
    category_id: str
    name: str
    color: str | None
    icon: str | None
    total_thb: Decimal
    count: int
    percentage: float


@dataclass
class MonthlyPoint:
    month: str          # "YYYY-MM"
    income_thb: Decimal
    expense_thb: Decimal
    net_thb: Decimal
    count: int


@dataclass
class AccountStat:
    account_id: str
    name: str
    account_type: str
    currency: str
    balance_thb: Decimal        # initial_balance + all-time net
    period_income_thb: Decimal
    period_expense_thb: Decimal


@dataclass
class PaymentMethodStat:
    method: str
    total_thb: Decimal
    count: int
    percentage: float


@dataclass
class Summary:
    date_from: date | None
    date_to: date | None
    total_income_thb: Decimal
    total_expense_thb: Decimal
    net_thb: Decimal
    transaction_count: int
    uncategorized_count: int
    recurring_count: int
    monthly_trend: list[MonthlyPoint]
    top_expense_categories: list[CategoryStat]
    top_income_categories: list[CategoryStat]
    accounts: list[AccountStat]
    payment_methods: list[PaymentMethodStat]


def _resolve_cat(cat_key: str, categories: dict, field: str, default):
    """Safe category field lookup."""
    if cat_key == "uncategorized":
        return default
    try:
        cat = categories.get(UUID(cat_key))
        return getattr(cat, field, default) if cat else default
    except (ValueError, AttributeError):
        return default


async def get_summary(
    *,
    user_id: UUID,
    date_from: date | None = None,
    date_to: date | None = None,
    account_repo: IAccountRepository,
    category_repo: ITransactionCategoryRepository,
    transaction_repo: ITransactionRepository,
) -> Summary:
    """Aggregate summary statistics for the given period."""
    period_txs = await transaction_repo.list_by_user(
        user_id, date_from=date_from, date_to=date_to, limit=10000
    )
    all_txs = await transaction_repo.list_by_user(user_id, limit=50000)
    accounts = {a.id: a for a in await account_repo.list_by_user(user_id)}
    categories = {c.id: c for c in await category_repo.list_tree_by_user(user_id)}

    total_income = Decimal("0")
    total_expense = Decimal("0")
    uncategorized_count = 0
    recurring_count = 0
    transaction_count = 0
    monthly: dict[str, dict] = {}
    expense_by_cat: dict[str, Decimal] = {}
    expense_count_by_cat: dict[str, int] = {}
    income_by_cat: dict[str, Decimal] = {}
    income_count_by_cat: dict[str, int] = {}
    payment_by_method: dict[str, Decimal] = {}
    payment_count_by_method: dict[str, int] = {}
    account_period_income: dict[str, Decimal] = {}
    account_period_expense: dict[str, Decimal] = {}

    for tx in period_txs:
        if tx.is_deleted:
            continue
        transaction_count += 1
        month_key = tx.transaction_date.strftime("%Y-%m")
        if month_key not in monthly:
            monthly[month_key] = {"income_thb": Decimal("0"), "expense_thb": Decimal("0"), "count": 0}
        monthly[month_key]["count"] += 1

        cat_key = str(tx.category_id) if tx.category_id else "uncategorized"
        if not tx.category_id:
            uncategorized_count += 1
        if tx.is_recurring:
            recurring_count += 1

        ak = str(tx.account_id)
        if tx.transaction_type == TransactionType.INCOME:
            total_income += tx.money.amount_thb
            monthly[month_key]["income_thb"] += tx.money.amount_thb
            income_by_cat[cat_key] = income_by_cat.get(cat_key, Decimal("0")) + tx.money.amount_thb
            income_count_by_cat[cat_key] = income_count_by_cat.get(cat_key, 0) + 1
            account_period_income[ak] = account_period_income.get(ak, Decimal("0")) + tx.money.amount_thb
        elif tx.transaction_type == TransactionType.EXPENSE:
            total_expense += tx.money.amount_thb
            monthly[month_key]["expense_thb"] += tx.money.amount_thb
            expense_by_cat[cat_key] = expense_by_cat.get(cat_key, Decimal("0")) + tx.money.amount_thb
            expense_count_by_cat[cat_key] = expense_count_by_cat.get(cat_key, 0) + 1
            account_period_expense[ak] = account_period_expense.get(ak, Decimal("0")) + tx.money.amount_thb

        if tx.transaction_type in (TransactionType.INCOME, TransactionType.EXPENSE):
            method = tx.payment_method or "unknown"
            payment_by_method[method] = payment_by_method.get(method, Decimal("0")) + tx.money.amount_thb
            payment_count_by_method[method] = payment_count_by_method.get(method, 0) + 1

    # All-time account balances
    account_all_income: dict[str, Decimal] = {}
    account_all_expense: dict[str, Decimal] = {}
    for tx in all_txs:
        if tx.is_deleted:
            continue
        ak = str(tx.account_id)
        if tx.transaction_type == TransactionType.INCOME:
            account_all_income[ak] = account_all_income.get(ak, Decimal("0")) + tx.money.amount_thb
        elif tx.transaction_type == TransactionType.EXPENSE:
            account_all_expense[ak] = account_all_expense.get(ak, Decimal("0")) + tx.money.amount_thb

    monthly_trend = sorted(
        [
            MonthlyPoint(
                month=k,
                income_thb=v["income_thb"],
                expense_thb=v["expense_thb"],
                net_thb=v["income_thb"] - v["expense_thb"],
                count=v["count"],
            )
            for k, v in monthly.items()
        ],
        key=lambda x: x.month,
    )

    top_expense_cats = [
        CategoryStat(
            category_id=cat_key,
            name=_resolve_cat(cat_key, categories, "name", "Uncategorized"),
            color=_resolve_cat(cat_key, categories, "color", "#ff4d4f"),
            icon=_resolve_cat(cat_key, categories, "icon", None),
            total_thb=total,
            count=expense_count_by_cat.get(cat_key, 0),
            percentage=round(float(total / total_expense * 100), 1) if total_expense > 0 else 0.0,
        )
        for cat_key, total in sorted(expense_by_cat.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    top_income_cats = [
        CategoryStat(
            category_id=cat_key,
            name=_resolve_cat(cat_key, categories, "name", "Uncategorized"),
            color=_resolve_cat(cat_key, categories, "color", "#52c41a"),
            icon=_resolve_cat(cat_key, categories, "icon", None),
            total_thb=total,
            count=income_count_by_cat.get(cat_key, 0),
            percentage=round(float(total / total_income * 100), 1) if total_income > 0 else 0.0,
        )
        for cat_key, total in sorted(income_by_cat.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    account_stats = [
        AccountStat(
            account_id=str(account.id),
            name=account.name,
            account_type=str(account.account_type),
            currency=account.currency,
            balance_thb=(
                account.initial_balance.amount_thb
                + account_all_income.get(str(account.id), Decimal("0"))
                - account_all_expense.get(str(account.id), Decimal("0"))
            ),
            period_income_thb=account_period_income.get(str(account.id), Decimal("0")),
            period_expense_thb=account_period_expense.get(str(account.id), Decimal("0")),
        )
        for account in accounts.values()
    ]

    total_payment = sum(payment_by_method.values()) or Decimal("1")
    payment_stats = sorted(
        [
            PaymentMethodStat(
                method=method,
                total_thb=total,
                count=payment_count_by_method[method],
                percentage=round(float(total / total_payment * 100), 1),
            )
            for method, total in payment_by_method.items()
        ],
        key=lambda x: x.total_thb,
        reverse=True,
    )

    return Summary(
        date_from=date_from,
        date_to=date_to,
        total_income_thb=total_income,
        total_expense_thb=total_expense,
        net_thb=total_income - total_expense,
        transaction_count=transaction_count,
        uncategorized_count=uncategorized_count,
        recurring_count=recurring_count,
        monthly_trend=monthly_trend,
        top_expense_categories=top_expense_cats,
        top_income_categories=top_income_cats,
        accounts=account_stats,
        payment_methods=payment_stats,
    )
