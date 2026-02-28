"""Immutable value objects for the Identity bounded context."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, self.value):
            raise ValueError(f"Invalid email address: {self.value}")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Username:
    value: str

    def __post_init__(self) -> None:
        if len(self.value) < 3 or len(self.value) > 50:
            raise ValueError("Username must be between 3 and 50 characters")
        if not re.match(r"^[a-zA-Z0-9_\-]+$", self.value):
            raise ValueError("Username may only contain letters, numbers, underscores, and hyphens")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class PasswordHash:
    """Opaque wrapper for the hashed password string — never the raw password."""
    value: str

    def __str__(self) -> str:
        return self.value
