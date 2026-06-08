"""QR code generation service"""
import os, uuid, qrcode
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from config import QRCODE_DIR, QR_EXPIRE_MINUTES
from models import QRSession


async def generate_qr_session(
    db: AsyncSession,
    qr_type: str,
    location_id: int,
    generated_by: int,
    base_url: str = "",
) -> Tuple[QRSession, str]:
    """
    Create a new QR session and return the session + QR image path.
    """
    token = str(uuid.uuid4())
    session = QRSession(
        token=token,
        type=qr_type,
        location_id=location_id,
        generated_by=generated_by,
        expires_at=datetime.utcnow() + timedelta(minutes=QR_EXPIRE_MINUTES),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    # Build URL that the QR code points to
    url = f"{base_url}/checkin.html?token={token}&type={qr_type}&location_id={location_id}"

    # Generate QR image
    img = qrcode.make(url)
    filename = f"qr_{token[:8]}_{qr_type}.png"
    filepath = os.path.join(QRCODE_DIR, filename)
    img.save(filepath)

    return session, filename


async def validate_qr_token(
    db: AsyncSession, token: str
) -> Optional[QRSession]:
    """Validate a QR token. Returns session if valid, None otherwise."""
    stmt = select(QRSession).where(QRSession.token == token)
    result = await db.execute(stmt)
    qr = result.scalar_one_or_none()

    if qr is None:
        return None
    if qr.is_expired():
        return None
    return qr


async def mark_qr_used(db: AsyncSession, token: str):
    """Mark a QR session as used."""
    stmt = select(QRSession).where(QRSession.token == token)
    result = await db.execute(stmt)
    qr = result.scalar_one_or_none()
    if qr:
        qr.is_used = True
        await db.commit()
