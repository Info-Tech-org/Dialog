"""
Device management API — bind / unbind / list devices for a user
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlmodel import Session as DBSession, select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from models import Device, get_session
from models.user_model import User
from api.auth import get_current_user
from config import settings

router = APIRouter()


# ---------- request / response schemas ----------

class DeviceCreateRequest(BaseModel):
    device_id: str
    name: str = ""
    device_token: Optional[str] = None  # fallback if X-Device-Token header not set


class DeviceUpdateRequest(BaseModel):
    name: str


class DeviceResponse(BaseModel):
    id: int
    device_id: str
    user_id: Optional[int]
    name: str
    is_online: bool
    last_seen: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- endpoints ----------

@router.get("", response_model=list[DeviceResponse])
async def list_devices(
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_session),
):
    """获取当前用户绑定的设备列表（admin 可看全部含未绑定设备）"""
    if getattr(user, 'is_admin', False):
        statement = select(Device).order_by(Device.created_at.desc())
    else:
        statement = select(Device).where(Device.user_id == user.id).order_by(Device.created_at.desc())
    devices = db.exec(statement).all()
    return devices


@router.get("/unclaimed", response_model=list[DeviceResponse])
async def list_unclaimed_devices(
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_session),
):
    """返回当前在线且未绑定用户的设备（任意已登录用户可认领）"""
    statement = (
        select(Device)
        .where(Device.user_id == None, Device.is_online == True)
        .order_by(Device.last_seen.desc())
    )
    return db.exec(statement).all()


@router.post("", response_model=DeviceResponse, status_code=201)
async def bind_device(
    req: DeviceCreateRequest,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_session),
    x_device_token: Optional[str] = Header(default=None),
):
    """绑定新设备到当前用户（认领未绑定设备须提供 X-Device-Token）"""
    # 检查 device_id 是否已存在
    existing = db.exec(select(Device).where(Device.device_id == req.device_id)).first()
    if existing:
        if existing.user_id is None:
            # Claiming an unbound device requires device token verification
            token = x_device_token or req.device_token
            if not token:
                raise HTTPException(
                    status_code=401,
                    detail="认领未绑定设备需提供设备 Token（Header: X-Device-Token 或 body.device_token）",
                )
            if settings.device_ingest_token and token != settings.device_ingest_token:
                raise HTTPException(status_code=403, detail="设备 Token 错误，认领失败")
            existing.user_id = user.id
            existing.name = req.name or existing.name
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing
        if existing.user_id == user.id:
            raise HTTPException(status_code=409, detail="该设备已绑定到你的账号")
        raise HTTPException(status_code=409, detail="该设备已被其他用户绑定")

    device = Device(
        device_id=req.device_id,
        user_id=user.id,
        name=req.name,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.patch("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: str,
    req: DeviceUpdateRequest,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_session),
):
    """更新设备名称"""
    device = db.exec(select(Device).where(Device.device_id == device_id)).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    if device.user_id != user.id and not getattr(user, 'is_admin', False):
        raise HTTPException(status_code=403, detail="无权操作该设备")

    device.name = req.name
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.delete("/{device_id}", status_code=204)
async def unbind_device(
    device_id: str,
    user: User = Depends(get_current_user),
    db: DBSession = Depends(get_session),
):
    """解绑设备"""
    device = db.exec(select(Device).where(Device.device_id == device_id)).first()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")
    if device.user_id != user.id and not getattr(user, 'is_admin', False):
        raise HTTPException(status_code=403, detail="无权操作该设备")

    db.delete(device)
    db.commit()
