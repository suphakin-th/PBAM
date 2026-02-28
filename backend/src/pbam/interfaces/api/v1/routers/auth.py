"""Auth router: register, login, logout, me."""
from fastapi import APIRouter, HTTPException, Request, status

from pbam.application.identity.commands import InvalidCredentialsError, UserAlreadyExistsError
from pbam.interfaces.api.v1.schemas.identity import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from pbam.interfaces.dependencies import CurrentUserId, Facade

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, request: Request, facade: Facade):
    try:
        result = await facade.register(
            email=body.email,
            username=body.username,
            password=body.password,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except UserAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return TokenResponse(access_token=result.token, expires_at=result.expires_at)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, facade: Facade):
    try:
        result = await facade.login(
            username_or_email=body.username_or_email,
            password=body.password,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except InvalidCredentialsError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(access_token=result.token, expires_at=result.expires_at)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(facade: Facade, current_user_id: CurrentUserId, request: Request):
    auth_header = request.headers.get("authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    await facade.logout(token)


@router.get("/me", response_model=UserResponse)
async def me(facade: Facade, current_user_id: CurrentUserId):
    user = await facade.get_current_user(current_user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse(
        id=user.id,
        email=str(user.email),
        username=str(user.username),
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
    )
