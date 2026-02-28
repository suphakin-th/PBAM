"""Aggregate all v1 routers."""
from fastapi import APIRouter

from .routers.accounts import router as accounts_router
from .routers.auth import router as auth_router
from .routers.categories import router as categories_router
from .routers.groups import router as groups_router
from .routers.ocr import router as ocr_router
from .routers.transactions import router as transactions_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_router)
v1_router.include_router(accounts_router)
v1_router.include_router(categories_router)
v1_router.include_router(transactions_router)
v1_router.include_router(groups_router)
v1_router.include_router(ocr_router)
