"""Authentication routes"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import bcrypt

from database import get_db
from models import User
from schemas import (
    LoginRequest, LoginResponse, UserCreate, UserResponse,
    ForgotPasswordRequest, ForgotPasswordResponse,
    ResetPasswordRequest,
)
from utils.security import create_access_token
from services.face_service import extract_embedding_from_base64, match_face

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.username == req.username, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None or not bcrypt.checkpw(req.password.encode(), user.password_hash.encode()):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    token = create_access_token(data={"sub": str(user.id), "role": user.role})

    return LoginResponse(
        access_token=token,
        user={
            "id": user.id,
            "username": user.username,
            "name": user.name,
            "role": user.role,
        }
    )


@router.post("/register", response_model=UserResponse)
async def register(req: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if username exists
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
        has_face=user.face_embedding is not None,
        is_active=user.is_active,
        created_at=user.created_at,
    )


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(req: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Check if a user exists and has face registered for password reset."""
    stmt = select(User).where(User.username == req.username, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        return ForgotPasswordResponse(exists=False, has_face=False, message="用户不存在")

    if user.face_embedding is None:
        return ForgotPasswordResponse(
            exists=True, has_face=False,
            message="该用户未注册人脸，请联系管理员重置密码"
        )

    return ForgotPasswordResponse(
        exists=True, has_face=True, message="请进行人脸验证"
    )


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Reset password after face verification."""
    # 1. Find user
    stmt = select(User).where(User.username == req.username, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 2. Must have face registered
    if user.face_embedding is None:
        raise HTTPException(status_code=400, detail="该用户未注册人脸，无法通过人脸验证重置密码")

    # 3. Extract face embedding from submitted photo
    embedding = extract_embedding_from_base64(req.face_image_base64)
    if embedding is None:
        raise HTTPException(status_code=400, detail="未检测到人脸，请重新拍照")

    # 4. Verify face matches this user
    matched_id = match_face(embedding, [(user.id, user.face_embedding)])
    if matched_id is None:
        raise HTTPException(status_code=401, detail="人脸验证失败，不是本人")

    # 5. Update password
    user.password_hash = bcrypt.hashpw(req.new_password.encode(), bcrypt.gensalt()).decode()
    await db.commit()

    return {"success": True, "message": "密码重置成功，请使用新密码登录"}
