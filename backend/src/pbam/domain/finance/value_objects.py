"""Immutable value objects for the Finance bounded context."""
from dataclasses import dataclass
from decimal import Decimal


SUPPORTED_CURRENCIES = frozenset([
    "THB", "USD", "EUR", "GBP", "JPY", "SGD", "CNY", "HKD", "AUD", "CAD",
])

BASE_CURRENCY = "THB"


@dataclass(frozen=True)
class Currency:
    code: str  # ISO 4217

    def __post_init__(self) -> None:
        if self.code not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Unsupported currency: {self.code}. Supported: {SUPPORTED_CURRENCIES}")

    def __str__(self) -> str:
        return self.code

    @classmethod
    def thb(cls) -> "Currency":
        return cls("THB")


@dataclass(frozen=True)
class Money:
    """Represents an amount in a specific currency.

    For THB transactions: original_amount == amount_thb, exchange_rate == 1.0
    For foreign currency: original_amount is in original_currency, amount_thb is converted.
    """
    amount_thb: Decimal          # base amount always in THB
    original_amount: Decimal     # original amount in original_currency
    original_currency: Currency  # the currency of original_amount

    def __post_init__(self) -> None:
        if self.amount_thb < 0:
            raise ValueError("Money amount cannot be negative")
        if self.original_amount < 0:
            raise ValueError("Money original amount cannot be negative")

    @classmethod
    def in_thb(cls, amount: Decimal) -> "Money":
        return cls(
            amount_thb=amount,
            original_amount=amount,
            original_currency=Currency.thb(),
        )

    @classmethod
    def foreign(
        cls,
        original_amount: Decimal,
        original_currency: Currency,
        exchange_rate: Decimal,
    ) -> "Money":
        return cls(
            amount_thb=(original_amount * exchange_rate).quantize(Decimal("0.0001")),
            original_amount=original_amount,
            original_currency=original_currency,
        )

    @property
    def is_foreign_currency(self) -> bool:
        return self.original_currency.code != BASE_CURRENCY

    @property
    def exchange_rate(self) -> Decimal | None:
        if not self.is_foreign_currency:
            return None
        if self.original_amount == 0:
            return Decimal("1")
        return (self.amount_thb / self.original_amount).quantize(Decimal("0.00000001"))

    def __add__(self, other: "Money") -> "Money":
        """Add two THB-base amounts (result is always in THB)."""
        return Money.in_thb(self.amount_thb + other.amount_thb)
