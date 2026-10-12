from fastapi import APIRouter

from app.routers.workspaces import workspaces_router

router_all = APIRouter()

router_all.include_router(workspaces_router)


