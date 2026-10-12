from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_session
from app.models import Workspace
from sqlalchemy import select, update

workspaces_router = APIRouter(prefix="/workspaces", tags=["workspaces"])

@workspaces_router.get("/")
async def list_workspaces(session: AsyncSession = Depends(get_async_session)):
    """列出所有未删除的工作空间。"""
    result = await session.execute(
        select(Workspace).where(Workspace.deleted_at.is_(None)).order_by(Workspace.created_at.desc())
    )
    items = result.scalars().all()
    return [
        {"id": w.id, "name": w.name, "created_at": w.created_at.isoformat()}
        for w in items
    ]

@workspaces_router.post("/")
async def create_workspace(body:dict, session: AsyncSession = Depends(get_async_session)):
    """创建工作空间"""
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400,detail="没输入名字")
    ws = Workspace(name=name)
    session.add(ws)
    await session.commit()
    await session.refresh(ws)
    return {"id": ws.id, "name": ws.name, "created_at": ws.created_at.isoformat()}

@workspaces_router.post("/{workspace_id}/delete")
async def delete_workspace(workspace_id: int, session: AsyncSession = Depends(get_async_session)):
    """软删除工作空间"""
    ws = await session.get(Workspace,workspace_id)
    if not ws or ws.is_deleted:
        raise HTTPException(status_code=404, detail="工作空间不存在")
    await session.execute(
        update(Workspace).where(Workspace.id == workspace_id).values(deleted_at=datetime.utcnow())
    )
    await session.commit()
    return {"ok": True}


