"""Pydantic v2 schemas for finance endpoints."""
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, field_validator


# ── Accounts ──────────────────────────────────────────────────────────────────

class AccountCreate(BaseModel):
    name: str
    account_type: str
    currency: str = "THB"
    initial_balance: Decimal = Decimal("0")
    metadata: dict[str, Any] = {}


class AccountUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    metadata: dict[str, Any] | None = None


class AccountResponse(BaseModel):
    id: UUID
    name: str
    account_type: str
    currency: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Categories ────────────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    name: str
    category_type: str
    parent_id: UUID | None = None
    color: str | None = None
    icon: str | None = None
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    icon: str | None = None
    sort_order: int | None = None
    parent_id: UUID | None = None


class CategoryResponse(BaseModel):
    id: UUID
    name: str
    category_type: str
    parent_id: UUID | None
    color: str | None
    icon: str | None
    sort_order: int
    is_system: bool
    children: list["CategoryResponse"] = []

    model_config = {"from_attributes": True}


# ── Transactions ──────────────────────────────────────────────────────────────

class TransactionCreate(BaseModel):
    account_id: UUID
    amount: Decimal
    currency: str = "THB"
    exchange_rate: Decimal | None = None
    transaction_type: str
    description: str
    transaction_date: date
    category_id: UUID | None = None
    payment_method: str | None = None
    tags: list[str] = []
    is_recurring: bool = False

    @field_validator("transaction_type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        if v not in ("income", "expense", "transfer"):
            raise ValueError("transaction_type must be income, expense, or transfer")
        return v


class TransactionUpdate(BaseModel):
    description: str | None = None
    category_id: UUID | None = None
    transaction_type: str | None = None
    payment_method: str | None = None
    tags: list[str] | None = None
    transaction_date: date | None = None
    counterparty_name: str | None = None

    @field_validator("transaction_type")
    @classmethod
    def valid_type(cls, v: str | None) -> str | None:
        if v is not None and v not in ("income", "expense", "transfer"):
            raise ValueError("transaction_type must be income, expense, or transfer")
        return v


class TransactionResponse(BaseModel):
    id: UUID
    account_id: UUID
    category_id: UUID | None
    payment_method: str | None
    counterparty_ref: str | None
    counterparty_name: str | None
    transfer_pair_id: UUID | None
    amount_thb: Decimal
    original_amount: Decimal | None
    original_currency: str | None
    transaction_type: str
    description: str
    transaction_date: date
    tags: list[str]
    is_recurring: bool
    metadata: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    items: list[TransactionResponse]
    total: int
    limit: int
    offset: int


# ── Comments ──────────────────────────────────────────────────────────────────

class CommentCreate(BaseModel):
    content: str


class CommentResponse(BaseModel):
    id: UUID
    transaction_id: UUID
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Groups ────────────────────────────────────────────────────────────────────

class GroupCreate(BaseModel):
    name: str
    description: str | None = None
    color: str | None = None


class GroupResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    color: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Flow tree ─────────────────────────────────────────────────────────────────

class FlowNodeResponse(BaseModel):
    id: str
    label: str
    node_type: str
    total_thb: Decimal
    color: str | None
    icon: str | None


class FlowEdgeResponse(BaseModel):
    source_id: str
    target_id: str
    amount_thb: Decimal
    label: str | None


class FlowTreeResponse(BaseModel):
    nodes: list[FlowNodeResponse]
    edges: list[FlowEdgeResponse]
    total_income_thb: Decimal
    total_expense_thb: Decimal
    net_thb: Decimal
