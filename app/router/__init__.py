from fastapi import APIRouter

from app.router.test import router

router_all = APIRouter()

router_all.include_router(router)

