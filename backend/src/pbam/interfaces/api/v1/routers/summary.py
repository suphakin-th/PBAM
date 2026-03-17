"""Summary router: aggregated analytics for the given date range."""
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from pbam.interfaces.api.v1.schemas.finance import (
    AccountStatResponse,
    CategoryStatResponse,
    MonthlyPointResponse,
    PaymentMethodStatResponse,
    SummaryResponse,
)
from pbam.interfaces.dependencies import CurrentUserId, Facade

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("", response_model=SummaryResponse)
async def get_summary(
    facade: Facade,
    current_user_id: CurrentUserId,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
):
    s = await facade.get_summary(current_user_id, date_from, date_to)
    return SummaryResponse(
        date_from=s.date_from,
        date_to=s.date_to,
        total_income_thb=s.total_income_thb,
        total_expense_thb=s.total_expense_thb,
        net_thb=s.net_thb,
        transaction_count=s.transaction_count,
        uncategorized_count=s.uncategorized_count,
        recurring_count=s.recurring_count,
        monthly_trend=[
            MonthlyPointResponse(
                month=p.month,
                income_thb=p.income_thb,
                expense_thb=p.expense_thb,
                net_thb=p.net_thb,
                count=p.count,
            )
            for p in s.monthly_trend
        ],
        top_expense_categories=[
            CategoryStatResponse(
                category_id=c.category_id,
                name=c.name,
                color=c.color,
                icon=c.icon,
                total_thb=c.total_thb,
                count=c.count,
                percentage=c.percentage,
            )
            for c in s.top_expense_categories
        ],
        top_income_categories=[
            CategoryStatResponse(
                category_id=c.category_id,
                name=c.name,
                color=c.color,
                icon=c.icon,
                total_thb=c.total_thb,
                count=c.count,
                percentage=c.percentage,
            )
            for c in s.top_income_categories
        ],
        accounts=[
            AccountStatResponse(
                account_id=a.account_id,
                name=a.name,
                account_type=a.account_type,
                currency=a.currency,
                balance_thb=a.balance_thb,
                period_income_thb=a.period_income_thb,
                period_expense_thb=a.period_expense_thb,
            )
            for a in s.accounts
        ],
        payment_methods=[
            PaymentMethodStatResponse(
                method=p.method,
                total_thb=p.total_thb,
                count=p.count,
                percentage=p.percentage,
            )
            for p in s.payment_methods
        ],
    )
