"""Admin management routes"""
import base64
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload
from typing import Optional

from database import get_db
from models import User, CheckIn, Location
from schemas import (
    UserCreate, UserResponse, LocationCreate, LocationResponse,
    CheckInRecord, StatisticsResponse, LocationValidateRequest,
)
from services.face_service import (
    extract_embedding, embedding_to_bytes,
    extract_embedding_from_base64,
)
from services.location_service import is_within_range, reverse_geocode
from utils.security import decode_access_token

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def get_current_admin(request: Request):
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


# ── Users ────────────────────────────────────────────────
@router.get("/users", response_model=list[UserResponse])
async def list_users(
    role: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    stmt = select(User).where(User.is_active == True)
    if role:
        stmt = stmt.where(User.role == role)
    stmt = stmt.order_by(User.created_at.desc())
    result = await db.execute(stmt)
    users = result.scalars().all()

    return [
        UserResponse(
            id=u.id,
            username=u.username,
            name=u.name,
            role=u.role,
            has_face=u.face_embedding is not None,
            is_active=u.is_active,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.post("/users", response_model=UserResponse)
async def create_user(
    req: UserCreate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    import bcrypt

    stmt = select(User).where(User.username == req.username)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(
        username=req.username,
        password_hash=bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode(),
        name=req.name,
        role=req.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserResponse(
        id=user.id,
        username=user.username,
        name=user.name,
        role=user.role,
        has_face=False,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("/users/{user_id}/face")
async def register_face(
    user_id: int,
    face_image_base64: str,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Register a face for a user. Body: {"face_image_base64": "..."}"""
    from pydantic import BaseModel

    class FaceReg(BaseModel):
        face_image_base64: str

    # Handle both form and JSON
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    embedding = extract_embedding_from_base64(face_image_base64)
    if embedding is None:
        raise HTTPException(status_code=400, detail="No face detected in image")

    user.face_embedding = embedding_to_bytes(embedding)

    # Save photo
    from services.face_service import save_checkin_photo
    photo_path = save_checkin_photo(face_image_base64, f"face_user_{user_id}.jpg")
    user.face_photo_path = photo_path

    await db.commit()

    return {"success": True, "message": f"Face registered for {user.name}"}


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    await db.commit()
    return {"success": True}


# ── Locations ────────────────────────────────────────────
@router.get("/locations", response_model=list[LocationResponse])
async def list_locations(
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    stmt = select(Location).where(Location.is_active == True)
    result = await db.execute(stmt)
    locations = result.scalars().all()
    return [
        LocationResponse(
            id=l.id, name=l.name, latitude=l.latitude,
            longitude=l.longitude, radius_meters=l.radius_meters,
            is_active=l.is_active,
        )
        for l in locations
    ]


@router.post("/locations", response_model=LocationResponse)
async def create_location(
    req: LocationCreate,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    location = Location(
        name=req.name,
        latitude=req.latitude,
        longitude=req.longitude,
        radius_meters=req.radius_meters,
        created_by=int(_admin["sub"]),
    )
    db.add(location)
    await db.commit()
    await db.refresh(location)
    return LocationResponse(
        id=location.id, name=location.name,
        latitude=location.latitude, longitude=location.longitude,
        radius_meters=location.radius_meters, is_active=location.is_active,
    )


# ── Statistics ───────────────────────────────────────────
@router.get("/statistics", response_model=StatisticsResponse)
async def get_statistics(
    date: Optional[str] = None,
    location_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Get daily attendance statistics. date format: YYYY-MM-DD (default: today)"""
    if date:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    else:
        target_date = datetime.utcnow().date()

    day_start = datetime(target_date.year, target_date.month, target_date.day)
    day_end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59)

    # Total users
    total_stmt = select(func.count(User.id)).where(User.is_active == True, User.role == "student")
    total_result = await db.execute(total_stmt)
    total_users = total_result.scalar() or 0

    # Today's check-ins
    ci_stmt = select(CheckIn).options(selectinload(CheckIn.user)).where(
        CheckIn.check_in_time >= day_start,
        CheckIn.check_in_time <= day_end,
    )
    if location_id:
        ci_stmt = ci_stmt.where(CheckIn.location_id == location_id)
    ci_result = await db.execute(ci_stmt.order_by(CheckIn.check_in_time.desc()))
    all_checkins = ci_result.scalars().all()

    checked_in_user_ids = set(c.user_id for c in all_checkins)
    checked_in_today = len(checked_in_user_ids)
    not_checked_in = max(0, total_users - checked_in_today)

    # Average duration for completed ones
    completed = [c for c in all_checkins if c.check_out_time is not None]
    if completed:
        durations = [(c.check_out_time - c.check_in_time).total_seconds() / 60 for c in completed]
        avg_duration = sum(durations) / len(durations)
    else:
        avg_duration = None

    records = []
    for c in all_checkins[:50]:  # limit to 50
        records.append(CheckInRecord(
            id=c.id, user_id=c.user_id,
            user_name=c.user.name if c.user else f"User#{c.user_id}",
            role=c.user.role if c.user else "student",
            check_in_time=c.check_in_time,
            check_out_time=c.check_out_time,
            location_name=c.location_name,
            status=c.status,
            is_auto_checkout=c.is_auto_checkout,
        ))

    return StatisticsResponse(
        total_users=total_users,
        checked_in_today=checked_in_today,
        not_checked_in=not_checked_in,
        total_checkins_today=len(all_checkins),
        avg_duration_minutes=round(avg_duration, 1) if avg_duration else None,
        records=records,
    )


async def _get_current_user(request: Request):
    """Auth that accepts any valid logged-in user."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_access_token(auth[7:])
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


@router.get("/checkins", response_model=list[CheckInRecord])
async def list_checkins(
    date: Optional[str] = None,
    user_id: Optional[int] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _user=Depends(_get_current_user),
):
    # Students can only see their own records
    if _user.get("role") == "student":
        user_id = int(_user["sub"])
    stmt = select(CheckIn).options(selectinload(CheckIn.user))
    if date:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
        day_start = datetime(target_date.year, target_date.month, target_date.day)
        day_end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59)
        stmt = stmt.where(CheckIn.check_in_time >= day_start, CheckIn.check_in_time <= day_end)
    if user_id:
        stmt = stmt.where(CheckIn.user_id == user_id)
    if status:
        stmt = stmt.where(CheckIn.status == status)

    stmt = stmt.order_by(CheckIn.check_in_time.desc()).limit(100)
    result = await db.execute(stmt)
    checkins = result.scalars().all()

    return [
        CheckInRecord(
            id=c.id, user_id=c.user_id,
            user_name=c.user.name if c.user else f"User#{c.user_id}",
            role=c.user.role if c.user else "student",
            check_in_time=c.check_in_time,
            check_out_time=c.check_out_time,
            location_name=c.location_name,
            status=c.status,
            is_auto_checkout=c.is_auto_checkout,
        )
        for c in checkins
    ]


# ── Location validation ──────────────────────────────────
@router.post("/validate-location")
async def validate_location(
    req: LocationValidateRequest,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Location).where(Location.id == req.location_id, Location.is_active == True)
    result = await db.execute(stmt)
    location = result.scalar_one_or_none()
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")

    within, distance = is_within_range(
        req.lat, req.lng,
        location.latitude, location.longitude,
        location.radius_meters,
    )
    addr = await reverse_geocode(req.lat, req.lng)

    return {
        "within_range": within,
        "distance_meters": round(distance, 1),
        "max_meters": location.radius_meters,
        "location_name": location.name,
        "address": addr,
    }
