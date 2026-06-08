"""Authentication routes"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import bcrypt

from database import get_db
from models import User
from schemas import LoginRequest, LoginResponse, UserCreate, UserResponse
from utils.security import create_access_token

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
