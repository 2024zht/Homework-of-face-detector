"""QR code routes"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from dataclasses import dataclass

from database import get_db
from models import QRSession, Location
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
    # Validate location exists
    loc_stmt = select(Location).where(Location.id == req.location_id, Location.is_active == True)
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
        location_id=req.location_id,
        generated_by=int(_admin["sub"]),
        base_url=base_url,
    )

    return {
        "token": session.token,
        "type": session.type,
        "qr_url": f"{base_url}/static/qrcodes/{filename}",
        "checkin_url": f"{base_url}/checkin.html?token={session.token}&type={session.type}&location_id={req.location_id}",
        "expires_at": session.expires_at.isoformat(),
    }


@router.get("/validate/{token}", response_model=QRValidateResponse)
async def validate_qr(token: str, db: AsyncSession = Depends(get_db)):
    qr = await validate_qr_token(db, token)
    if qr is None:
        return QRValidateResponse(valid=False, message="QR code expired or invalid")

    return QRValidateResponse(
        valid=True,
        type=qr.type,
        location_name=qr.location.name if qr.location else None,
        expires_at=qr.expires_at,
        message="Valid",
    )


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
