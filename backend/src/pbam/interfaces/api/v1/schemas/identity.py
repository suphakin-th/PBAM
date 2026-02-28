"""Pydantic v2 schemas for identity endpoints."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        import re
        if not re.match(r"^[a-zA-Z0-9_\-]{3,50}$", v):
            raise ValueError("Username must be 3-50 chars: letters, numbers, _ or -")
        return v

    @field_validator("password")
    @classmethod
    def password_strong(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    username_or_email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class UserResponse(BaseModel):
    id: UUID
    email: str
    username: str
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}
