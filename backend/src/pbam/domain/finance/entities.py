"""Domain entities for the Finance bounded context."""
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from .value_objects import Money


class AccountType(StrEnum):
    BANK = "bank"
    CASH = "cash"
    CREDIT_CARD = "credit_card"
    SAVINGS = "savings"
    INVESTMENT = "investment"


class TransactionType(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"


class PaymentMethod(StrEnum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    QR_CODE = "qr_code"
    PROMPTPAY = "promptpay"
    BANK_TRANSFER = "bank_transfer"
    DIGITAL_WALLET = "digital_wallet"
    ATM = "atm"
    CASH = "cash"
    ONLINE = "online"
    SUBSCRIPTION = "subscription"
    UNKNOWN = "unknown"


class CategoryType(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"


@dataclass
class Account:
    id: UUID
    user_id: UUID
    name: str
    account_type: AccountType
    currency: str
    initial_balance: Money
    is_active: bool = True
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    deleted_at: datetime | None = None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        self.deleted_at = datetime.utcnow()
        self.is_active = False


@dataclass
class TransactionCategory:
    """Forms the tree structure for the flow visualization."""
    id: UUID
    user_id: UUID
    name: str
    category_type: CategoryType
    parent_id: UUID | None = None
    color: str | None = None
    icon: str | None = None
    sort_order: int = 0
    is_system: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    deleted_at: datetime | None = None

    @property
    def is_root(self) -> bool:
        return self.parent_id is None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


@dataclass
class Transaction:
    """Leaf node in the money flow tree."""
    id: UUID
    user_id: UUID
    account_id: UUID
    money: Money
    transaction_type: TransactionType
    description: str
    transaction_date: date
    category_id: UUID | None = None
    payment_method: str | None = None
    transfer_pair_id: UUID | None = None
    tags: list[str] = field(default_factory=list)
    source_document_id: UUID | None = None
    is_recurring: bool = False
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    deleted_at: datetime | None = None

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        self.deleted_at = datetime.utcnow()


@dataclass
class TransactionComment:
    id: UUID
    transaction_id: UUID
    user_id: UUID
    content: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    deleted_at: datetime | None = None

    def soft_delete(self) -> None:
        self.deleted_at = datetime.utcnow()


@dataclass
class TransactionGroup:
    id: UUID
    user_id: UUID
    name: str
    description: str | None = None
    color: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    deleted_at: datetime | None = None

    def soft_delete(self) -> None:
        self.deleted_at = datetime.utcnow()
