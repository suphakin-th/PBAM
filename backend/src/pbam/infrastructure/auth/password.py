"""Argon2id password hashing using argon2-cffi."""
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from pbam.domain.identity.value_objects import PasswordHash

_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=65536,  # 64 MiB
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


def hash_password(raw_password: str) -> PasswordHash:
    """Hash a raw password using Argon2id. Returns an opaque PasswordHash."""
    return PasswordHash(_hasher.hash(raw_password))


def verify_password(raw_password: str, password_hash: PasswordHash) -> bool:
    """Verify a raw password against a stored Argon2id hash."""
    try:
        return _hasher.verify(str(password_hash), raw_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: PasswordHash) -> bool:
    """True if the hash was created with outdated parameters and should be updated."""
    return _hasher.check_needs_rehash(str(password_hash))
