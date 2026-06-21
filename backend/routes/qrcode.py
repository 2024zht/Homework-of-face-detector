"""QR code routes"""
import urllib.parse
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from dataclasses import dataclass

from database import get_db
from models import QRSession, Location, CheckInSession
from schemas import QRGenerateRequest, QRValidateResponse
from services.qr_service import generate_qr_session, validate_qr_token
from utils.security import decode_access_token

router = APIRouter(prefix="/api/qr", tags=["qr"])


async def get_current_admin(request: Request, db: AsyncSession = Depends(get_db)):
    """Simple admin auth via Bearer token."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth[7:]
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("role") not in ("admin", "instructor"):
        raise HTTPException(status_code=403, detail="Admin or instructor required")
    return payload


@router.post("/generate")
async def generate_qr(
    req: QRGenerateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    # 如果提供了 session_id，查找任务并获取其 location_id
    location_id = req.location_id
    session_id = req.session_id

    if session_id is not None:
        sess_stmt = (select(CheckInSession).where(CheckInSession.id == session_id)
                     .options(selectinload(CheckInSession.location)))
        sess_result = await db.execute(sess_stmt)
        qr_session = sess_result.scalar_one_or_none()
        if qr_session is None:
            raise HTTPException(status_code=404, detail="签到任务不存在")
        if qr_session.status != "active":
            raise HTTPException(status_code=400, detail="该签到任务已结束")
        # 使用任务的 location_id（若未冲突）
        location_id = qr_session.location_id

    # Validate location exists
    loc_stmt = select(Location).where(Location.id == location_id, Location.is_active == True)
    loc_result = await db.execute(loc_stmt)
    location = loc_result.scalar_one_or_none()
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")

    # Use the configured public base URL (cpolar tunnel), not localhost
    from config import BASE_URL
    base_url = BASE_URL.rstrip("/")

    session, filename = await generate_qr_session(
        db=db,
        qr_type=req.type,
        location_id=location_id,
        generated_by=int(_admin["sub"]),
        base_url=base_url,
        session_id=session_id,
    )

    checkin_url = f"{base_url}/checkin.html?token={session.token}&type={session.type}&location_id={location_id}"
    if session_id is not None:
        checkin_url += f"&session_id={session_id}"
        if qr_session.name:
            checkin_url += f"&session_name={urllib.parse.quote(qr_session.name)}"

    return {
        "token": session.token,
        "type": session.type,
        "qr_url": f"{base_url}/static/qrcodes/{filename}",
        "checkin_url": checkin_url,
        "expires_at": session.expires_at.isoformat(),
    }


@router.get("/validate/{token}", response_model=QRValidateResponse)
async def validate_qr(token: str, db: AsyncSession = Depends(get_db)):
    qr = await validate_qr_token(db, token)
    if qr is None:
        return QRValidateResponse(valid=False, message="QR code expired or invalid")

    # Eager-load location name to avoid lazy-load MissingGreenlet error
    from models import Location
    from sqlalchemy import select as sa_select
    loc_result = await db.execute(sa_select(Location.name).where(Location.id == qr.location_id))
    loc_name = loc_result.scalar_one_or_none()

    return QRValidateResponse(
        valid=True,
        type=qr.type,
        location_name=loc_name,
        expires_at=qr.expires_at,
        message="Valid",
    )


@router.post("/self")
async def self_qr(request: Request, db: AsyncSession = Depends(get_db)):
    """Any authenticated user can get a personal check-in QR code."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401)
    payload = decode_access_token(auth[7:])
    if payload is None:
        raise HTTPException(status_code=401)
    loc_stmt = select(Location).where(Location.is_active == True).limit(1)
    loc_result = await db.execute(loc_stmt)
    location = loc_result.scalar_one_or_none()
    if location is None:
        raise HTTPException(status_code=404, detail="No active location")
    from config import BASE_URL
    base_url = BASE_URL.rstrip("/")
    session, filename = await generate_qr_session(
        db=db, qr_type="checkin", location_id=location.id,
        generated_by=int(payload["sub"]), base_url=base_url,
    )
    return {
        "token": session.token,
        "qr_url": f"{base_url}/static/qrcodes/{filename}",
        "checkin_url": f"{base_url}/checkin.html?token={session.token}&type=checkin&location_id={location.id}",
        "expires_at": session.expires_at.isoformat(),
    }


@router.get("/image/{filename}")
async def get_qr_image(filename: str):
    """Serve QR code image."""
    from fastapi.responses import FileResponse
    import os
    from config import QRCODE_DIR
    path = os.path.join(QRCODE_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="QR image not found")
    return FileResponse(path)
