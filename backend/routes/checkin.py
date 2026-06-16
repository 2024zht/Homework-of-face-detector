"""Check-in / Check-out routes"""
import uuid, os, tempfile
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from database import get_db
from models import User, CheckIn, QRSession, Location, CheckInSession
from schemas import CheckInRequest, CheckOutRequest, CheckInResponse, CheckStatusResponse, ActiveSessionResponse
from services.face_service import extract_embedding_from_base64, match_face, save_checkin_photo, embedding_to_bytes
from services.location_service import is_within_range, reverse_geocode
from services.qr_service import validate_qr_token, mark_qr_used
from config import AUTO_CHECKOUT_HOURS
from utils.time_utils import beijing_now_naive
from routes.admin import is_session_time_valid, _session_to_response

router = APIRouter(prefix="/api/check", tags=["check"])


async def _verify_location(lat: float, lng: float, location_id: int, db: AsyncSession, source: Optional[str] = None):
    """Check if coordinates are within location's allowed range."""
    stmt = select(Location).where(Location.id == location_id, Location.is_active == True)
    result = await db.execute(stmt)
    location = result.scalar_one_or_none()
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found")

    within, distance = is_within_range(lat, lng, location.latitude, location.longitude, location.radius_meters, source)
    if not within:
        raise HTTPException(
            status_code=400,
            detail=f"Out of range: {distance:.0f}m from {location.name} (max: {location.radius_meters}m)"
        )
    return location, distance


async def _get_active_sessions(db: AsyncSession, user_id: int = None) -> list[CheckInSession]:
    """Return all active sessions. If user_id given, filter by target_user_ids."""
    stmt = (select(CheckInSession).where(CheckInSession.status == "active")
            .options(selectinload(CheckInSession.location), selectinload(CheckInSession.creator))
            .order_by(CheckInSession.created_at.desc()))
    result = await db.execute(stmt)
    sessions = result.scalars().all()
    if user_id is not None:
        sessions = [s for s in sessions if (
            not s.target_user_ids or str(user_id) in s.target_user_ids.split(",")
        )]
    return sessions


async def _get_any_valid_session(db: AsyncSession) -> Optional[CheckInSession]:
    """Get any active+time_valid session (no user filter)."""
    stmt = (select(CheckInSession).where(CheckInSession.status == "active")
            .options(selectinload(CheckInSession.location), selectinload(CheckInSession.creator)))
    result = await db.execute(stmt)
    for s in result.scalars().all():
        if is_session_time_valid(s):
            return s
    return None


async def _get_best_session(db: AsyncSession, user_id: int) -> Optional[CheckInSession]:
    """Get the first active+time_valid session matching this user."""
    sessions = await _get_active_sessions(db, user_id=user_id)
    for s in sessions:
        if is_session_time_valid(s):
            return s
    return None


@router.get("/session/active", response_model=ActiveSessionResponse)
async def get_active_session_for_student(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get all active sessions visible to this student."""
    from utils.security import decode_access_token
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401)
    payload = decode_access_token(auth[7:])
    if payload is None:
        raise HTTPException(status_code=401)

    user_id = int(payload["sub"])
    sessions = await _get_active_sessions(db, user_id=user_id)
    return {
        "has_active_session": len(sessions) > 0,
        "sessions": [_session_to_response(s) for s in sessions],
    }


@router.post("/in", response_model=CheckInResponse)
async def check_in(req: CheckInRequest, db: AsyncSession = Depends(get_db)):
    # 1. Validate QR token (or allow camera-direct with active session)
    # For target-user validation after identification
    _matched_session = None

    if req.token == "camera-direct":
        # Check if any active+time_valid session exists
        _matched_session = await _get_any_valid_session(db)
        if not _matched_session:
            stmt = select(CheckInSession).where(CheckInSession.status == "active")
            result = await db.execute(stmt)
            if result.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="不在签到时间段内")
            raise HTTPException(status_code=400, detail="暂无签到任务，请等待教师发布签到")
        location = _matched_session.location
        if location is None:
            raise HTTPException(status_code=400, detail="签到任务地点不存在")
        if req.latitude and req.longitude:
            within, distance = is_within_range(req.latitude, req.longitude, location.latitude, location.longitude, location.radius_meters, req.source)
            if not within:
                raise HTTPException(status_code=400, detail=f"Out of range: {distance:.0f}m from {location.name}")
        else:
            distance = 0
        location_name = await reverse_geocode(req.latitude, req.longitude) if req.latitude else location.name
    else:
        qr = await validate_qr_token(db, req.token)
        if qr is None:
            raise HTTPException(status_code=400, detail="QR code expired or invalid")
        if qr.type != "checkin":
            raise HTTPException(status_code=400, detail="This QR code is for check-out, not check-in")
        # Also verify an active session exists and time is valid (QR flow)
        _matched_session = await _get_any_valid_session(db)
        if not _matched_session:
            stmt = select(CheckInSession).where(CheckInSession.status == "active")
            result = await db.execute(stmt)
            if result.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="不在签到时间段内")
            raise HTTPException(status_code=400, detail="暂无签到任务，请等待教师发布签到")
        location, distance = await _verify_location(req.latitude, req.longitude, qr.location_id, db, req.source)
        location_name = await reverse_geocode(req.latitude, req.longitude)
        await mark_qr_used(db, req.token)

    # 3. Identify user — name-verified face recognition (priority order)
    user_id = None
    embedding = None
    user_name = getattr(req, 'user_name', None)
    user_name = user_name.strip() if user_name else None

    if user_name and req.face_image_base64 and req.face_image_base64.strip():
        # Priority 1: name + face → 1:1 verification (most secure)
        embedding = extract_embedding_from_base64(req.face_image_base64)
        if embedding is None:
            raise HTTPException(status_code=400, detail="未检测到人脸，请重新拍照")
        # Find user by exact name
        name_stmt = select(User).where(User.name == user_name, User.is_active == True)
        name_result = await db.execute(name_stmt)
        user = name_result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=400, detail="用户未找到，请检查姓名是否正确")
        if user.face_embedding is not None:
            # 1:1 face verification — must match the claimed user
            matched_id = match_face(embedding, [(user.id, user.face_embedding)])
            if matched_id is None:
                raise HTTPException(status_code=401, detail="人脸验证失败，不是本人")
        user_id = user.id
    elif req.face_image_base64 and req.face_image_base64.strip():
        # Priority 2: face only → open-set matching (no name provided)
        embedding = extract_embedding_from_base64(req.face_image_base64)
        if embedding is not None:
            user_stmt = select(User.id, User.face_embedding).where(
                User.face_embedding.isnot(None),
                User.is_active == True,
            )
            user_result = await db.execute(user_stmt)
            candidates = [(row[0], row[1]) for row in user_result.fetchall()]
            user_id = match_face(embedding, candidates)
    elif user_name:
        # Priority 3: name only → exact name lookup
        name_stmt = select(User.id).where(User.name == user_name, User.is_active == True)
        name_result = await db.execute(name_stmt)
        user_row = name_result.fetchone()
        if user_row:
            user_id = user_row[0]
    else:
        raise HTTPException(status_code=400, detail="请提供人脸照片或姓名")

    if user_id is None:
        raise HTTPException(status_code=400, detail="用户未找到，请检查姓名是否正确")

    # 3.5 Verify user is targeted by the session (if session has target list)
    if _matched_session and _matched_session.target_user_ids:
        target_ids = [int(x) for x in _matched_session.target_user_ids.split(",") if x.strip()]
        if user_id not in target_ids:
            raise HTTPException(status_code=400, detail="您不在本次签到的目标用户中")

    # 4. Check if user already has an active check-in
    active_stmt = select(CheckIn).where(
        CheckIn.user_id == user_id,
        CheckIn.status == "active",
    )
    active_result = await db.execute(active_stmt)
    active_checkin = active_result.scalar_one_or_none()
    if active_checkin is not None:
        raise HTTPException(status_code=400, detail="Already checked in. Please check out first.")

    # 5. Save check-in photo (if provided)
    photo_path = None
    if req.face_image_base64 and req.face_image_base64.strip():
        photo_filename = f"checkin_{user_id}_{uuid.uuid4().hex[:8]}.jpg"
        photo_path = save_checkin_photo(req.face_image_base64, photo_filename)

    # 6. Record check-in
    checkin = CheckIn(
        user_id=user_id,
        location_id=location.id,
        lat=req.latitude,
        lng=req.longitude,
        location_name=location_name or location.name,
        check_in_photo=photo_path,
        status="active",
    )
    db.add(checkin)

    # 7. Self-learning: if face matched, blend new embedding into stored one
    if embedding is not None and user_id is not None:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
        if user.face_embedding is not None:
            from services.face_service import update_embedding
            user.face_embedding = update_embedding(user.face_embedding, embedding)

    # 8. Mark QR as used (skip for camera-direct)
    if req.token != "camera-direct":
        await mark_qr_used(db, req.token)

    # 9. Get user info for response
    user_stmt = select(User).where(User.id == user_id)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one()

    await db.commit()
    await db.refresh(checkin)

    return {
        "id": checkin.id,
        "user_name": user.name,
        "check_in_time": checkin.check_in_time.isoformat(),
        "check_out_time": None,
        "status": "active",
        "location_name": location.name,
        "distance_meters": round(distance, 1),
    }


@router.post("/out", response_model=CheckInResponse)
async def check_out(req: CheckOutRequest, db: AsyncSession = Depends(get_db)):
    # Determine user — name-verified face recognition (priority order)
    user_id = None
    user_name = req.user_name.strip() if req.user_name else None

    if user_name and req.face_image_base64 and req.face_image_base64.strip():
        # Priority 1: name + face → 1:1 verification (most secure)
        embedding = extract_embedding_from_base64(req.face_image_base64)
        if embedding is None:
            raise HTTPException(status_code=400, detail="未检测到人脸，请重新拍照")
        name_stmt = select(User).where(User.name == user_name, User.is_active == True)
        name_result = await db.execute(name_stmt)
        user = name_result.scalar_one_or_none()
        if user is None:
            raise HTTPException(status_code=400, detail="用户未找到，请检查姓名是否正确")
        if user.face_embedding is not None:
            matched_id = match_face(embedding, [(user.id, user.face_embedding)])
            if matched_id is None:
                raise HTTPException(status_code=401, detail="人脸验证失败，不是本人")
        user_id = user.id
    elif req.face_image_base64 and req.face_image_base64.strip():
        # Priority 2: face only → open-set matching
        embedding = extract_embedding_from_base64(req.face_image_base64)
        if embedding is not None:
            user_stmt = select(User.id, User.face_embedding).where(
                User.face_embedding.isnot(None),
                User.is_active == True,
            )
            user_result = await db.execute(user_stmt)
            candidates = [(row[0], row[1]) for row in user_result.fetchall()]
            user_id = match_face(embedding, candidates)
    elif user_name:
        # Priority 3: name only
        name_stmt = select(User.id).where(User.name == user_name, User.is_active == True)
        name_result = await db.execute(name_stmt)
        user_row = name_result.fetchone()
        if user_row:
            user_id = user_row[0]

    if user_id is None:
        raise HTTPException(status_code=400, detail="签退失败，人脸未识别且未提供姓名")

    # Find active check-in
    active_stmt = select(CheckIn).where(
        CheckIn.user_id == user_id,
        CheckIn.status == "active",
    )
    active_result = await db.execute(active_stmt)
    checkin = active_result.scalar_one_or_none()

    if checkin is None:
        raise HTTPException(status_code=400, detail="No active check-in found")

    # Verify location if provided
    if req.latitude and req.longitude:
        location, _ = await _verify_location(req.latitude, req.longitude, checkin.location_id, db)

    # Save check-out photo if provided
    if req.face_image_base64:
        photo_filename = f"checkout_{user_id}_{uuid.uuid4().hex[:8]}.jpg"
        checkin.check_out_photo = save_checkin_photo(req.face_image_base64, photo_filename)

    checkin.check_out_time = beijing_now_naive()
    checkin.status = "completed"
    checkin.is_auto_checkout = False

    if req.token:
        await mark_qr_used(db, req.token)

    await db.commit()
    await db.refresh(checkin)

    user_stmt = select(User).where(User.id == user_id)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one()

    return CheckInResponse(
        id=checkin.id,
        user_name=user.name,
        check_in_time=checkin.check_in_time,
        check_out_time=checkin.check_out_time,
        status="completed",
        location_name=checkin.location_name,
    )


@router.get("/status", response_model=CheckStatusResponse)
async def check_status(user_id: int, db: AsyncSession = Depends(get_db)):
    active_stmt = select(CheckIn).where(
        CheckIn.user_id == user_id,
        CheckIn.status == "active",
    )
    active_result = await db.execute(active_stmt)
    checkin = active_result.scalar_one_or_none()

    if checkin is None:
        return CheckStatusResponse(is_checked_in=False)

    auto_checkout_at = checkin.check_in_time + timedelta(hours=AUTO_CHECKOUT_HOURS)

    return CheckStatusResponse(
        is_checked_in=True,
        check_in_time=checkin.check_in_time,
        location_name=checkin.location_name,
        auto_checkout_at=auto_checkout_at,
    )


@router.post("/batch-video")
async def batch_checkin_video(
    file: UploadFile = File(...),
    token: str = Form(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a video, detect all faces, match against registered users,
    and batch check-in everyone found.
    """
    # 1. Validate QR token
    qr = await validate_qr_token(db, token)
    if qr is None:
        raise HTTPException(status_code=400, detail="QR code expired or invalid")
    if qr.type != "checkin":
        raise HTTPException(status_code=400, detail="This QR is for check-out, not check-in")

    # 1.5 Require active session with valid time window
    _matched_session = await _get_any_valid_session(db)
    if not _matched_session:
        stmt = select(CheckInSession).where(CheckInSession.status == "active")
        result = await db.execute(stmt)
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="不在签到时间段内")
        raise HTTPException(status_code=400, detail="暂无签到任务，请等待教师发布签到")

    # 2. Verify location
    if latitude and longitude:
        location, _ = await _verify_location(latitude, longitude, qr.location_id, db)
        location_name = await reverse_geocode(latitude, longitude)
    else:
        stmt = select(Location).where(Location.id == qr.location_id)
        result = await db.execute(stmt)
        location = result.scalar_one_or_none()
        location_name = location.name if location else None

    # 3. Save uploaded video to temp file
    suffix = os.path.splitext(file.filename or "video.mp4")[1] or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        video_path = tmp.name

    # 4. Get all registered users with face embeddings
    user_stmt = select(User.id, User.name, User.face_embedding).where(
        User.face_embedding.isnot(None), User.is_active == True
    )
    user_result = await db.execute(user_stmt)
    all_users = user_result.fetchall()
    user_map = {row[0]: row[1] for row in all_users}  # id -> name
    candidates = [(row[0], row[2]) for row in all_users]  # row[2] = face_embedding bytes

    if not candidates:
        os.unlink(video_path)
        raise HTTPException(status_code=400, detail="No registered faces in database")

    # 5. Process video (run sync in thread to avoid blocking event loop)
    try:
        import asyncio
        from services.video_service import process_video
        result = await asyncio.to_thread(
            process_video,
            video_path=video_path,
            user_embeddings=candidates,
            location_id=qr.location_id,
            lat=latitude,
            lng=longitude,
            location_name=location_name,
        )
    finally:
        os.unlink(video_path)  # clean up temp file

    # 6. Batch check-in matched users
    checked_in = []
    skipped = []
    now = beijing_now_naive()

    for match in result["matched_users"]:
        uid = match["user_id"]
        # Check if already checked in
        active_stmt = select(CheckIn).where(
            CheckIn.user_id == uid, CheckIn.status == "active"
        )
        active_r = await db.execute(active_stmt)
        if active_r.scalar_one_or_none():
            skipped.append({
                "user_id": uid,
                "user_name": user_map.get(uid, f"User#{uid}"),
                "reason": "Already checked in",
            })
            continue

        # Save face photo
        from services.face_service import save_checkin_photo
        img_data = match["face_img_b64"]
        photo_path = save_checkin_photo(img_data, f"video_checkin_{uid}_{uuid.uuid4().hex[:8]}.jpg")

        # Record check-in
        checkin = CheckIn(
            user_id=uid,
            location_id=qr.location_id,
            lat=latitude,
            lng=longitude,
            location_name=location_name,
            check_in_photo=photo_path,
            status="active",
        )
        db.add(checkin)
        checked_in.append({
            "user_id": uid,
            "user_name": user_map.get(uid, f"User#{uid}"),
            "confidence": match["confidence"],
        })

    if checked_in:
        await mark_qr_used(db, token)
        await db.commit()

    return {
        "video_info": {
            "filename": file.filename,
            "frames_processed": result["total_frames"],
            "unique_faces_found": result["unique_faces"],
        },
        "checked_in": checked_in,
        "skipped": skipped,
        "unmatched_faces": result["unmatched_faces"],
        "processing_time_seconds": result["processing_time_seconds"],
        "total_checked_in": len(checked_in),
    }


@router.post("/self-out")
async def self_checkout(request: Request, db: AsyncSession = Depends(get_db)):
    """Any authenticated user can sign themselves out."""
    from utils.security import decode_access_token
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401)
    payload = decode_access_token(auth[7:])
    if payload is None:
        raise HTTPException(status_code=401)
    user_id = int(payload["sub"])

    active_stmt = select(CheckIn).where(CheckIn.user_id == user_id, CheckIn.status == "active")
    active_result = await db.execute(active_stmt)
    checkin = active_result.scalar_one_or_none()
    if checkin is None:
        raise HTTPException(status_code=400, detail="No active check-in")

    checkin.check_out_time = beijing_now_naive()
    checkin.status = "completed"
    checkin.is_auto_checkout = False
    await db.commit()
    await db.refresh(checkin)
    return {"id": checkin.id, "status": "completed", "check_out_time": checkin.check_out_time.isoformat()}


async def auto_checkout_expired(db: AsyncSession):
    """Called by background task: auto sign-out expired check-ins."""
    cutoff = beijing_now_naive() - timedelta(hours=AUTO_CHECKOUT_HOURS)
    stmt = select(CheckIn).where(
        CheckIn.status == "active",
        CheckIn.check_in_time <= cutoff,
    )
    result = await db.execute(stmt)
    expired = result.scalars().all()

    for c in expired:
        c.check_out_time = c.check_in_time + timedelta(hours=AUTO_CHECKOUT_HOURS)
        c.status = "completed"
        c.is_auto_checkout = True

    if expired:
        await db.commit()

    return len(expired)
