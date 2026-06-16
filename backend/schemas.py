"""Pydantic request/response schemas"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ── Auth ─────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserCreate(BaseModel):
    username: str
    password: str
    name: str
    role: str = "student"  # admin, instructor, student


class UserResponse(BaseModel):
    id: int
    username: str
    name: str
    role: str
    has_face: bool = False
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Location ─────────────────────────────────────────────
class LocationCreate(BaseModel):
    name: str
    latitude: float
    longitude: float
    radius_meters: int = 100


class LocationResponse(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    radius_meters: int
    is_active: bool

    class Config:
        from_attributes = True


# ── Check-in ─────────────────────────────────────────────
class CheckInRequest(BaseModel):
    token: str
    face_image_base64: str  # base64-encoded JPEG
    latitude: Optional[float] = None  # from Gaode JS API
    longitude: Optional[float] = None
    user_name: Optional[str] = None  # manual name input as fallback
    source: Optional[str] = None  # "amap"=GCJ-02, absent=WGS-84
    session_id: Optional[int] = None  # which session to check in for


class CheckOutRequest(BaseModel):
    token: Optional[str] = None
    face_image_base64: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    user_name: Optional[str] = None  # name for 1:1 face verification


class CheckInResponse(BaseModel):
    id: int
    user_name: str
    check_in_time: datetime
    check_out_time: Optional[datetime] = None
    status: str
    location_name: Optional[str] = None

    class Config:
        from_attributes = True


class CheckStatusResponse(BaseModel):
    is_checked_in: bool
    check_in_time: Optional[datetime] = None
    location_name: Optional[str] = None
    auto_checkout_at: Optional[datetime] = None


# ── QR ───────────────────────────────────────────────────
class QRGenerateRequest(BaseModel):
    type: str = "checkin"  # checkin / checkout
    location_id: int


class QRValidateResponse(BaseModel):
    valid: bool
    type: Optional[str] = None
    location_name: Optional[str] = None
    expires_at: Optional[datetime] = None
    message: str = ""


# ── Stats ────────────────────────────────────────────────
class CheckInRecord(BaseModel):
    id: int
    user_id: int
    user_name: str
    role: str
    check_in_time: datetime
    check_out_time: Optional[datetime] = None
    location_name: Optional[str] = None
    status: str
    is_auto_checkout: bool
    check_in_photo: Optional[str] = None
    check_out_photo: Optional[str] = None
    original_user_id: Optional[int] = None
    corrected_by: Optional[int] = None
    corrected_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StatisticsResponse(BaseModel):
    total_users: int
    checked_in_today: int
    not_checked_in: int
    total_checkins_today: int
    avg_duration_minutes: Optional[float] = None
    records: list[CheckInRecord] = []


class LocationValidateRequest(BaseModel):
    lat: float
    lng: float
    location_id: int
    source: Optional[str] = None  # "amap"=GCJ-02


# ── Check-In Session ──────────────────────────────────────
class SessionCreate(BaseModel):
    location_id: int
    start_date: Optional[str] = None   # "2026-06-16"
    end_date: Optional[str] = None     # "2026-06-20"
    checkin_start_time: Optional[str] = None  # "08:00"
    checkin_end_time: Optional[str] = None    # "20:00"
    recurring_days: Optional[str] = None  # "0,1,2,3,4" Mon=0 Sun=6
    target_user_ids: Optional[str] = None  # "1,3,5" comma-separated, null=all


class SessionResponse(BaseModel):
    id: int
    location_id: int
    location_name: Optional[str] = None
    created_by: int
    creator_name: Optional[str] = None
    status: str
    created_at: datetime
    ended_at: Optional[datetime] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    checkin_start_time: Optional[str] = None
    checkin_end_time: Optional[str] = None
    recurring_days: Optional[str] = None
    target_user_ids: Optional[str] = None
    time_valid: bool = True  # whether current time falls within session window

    class Config:
        from_attributes = True


class ActiveSessionResponse(BaseModel):
    has_active_session: bool
    sessions: list[SessionResponse] = []  # now supports multiple concurrent sessions


# ── Password Reset ─────────────────────────────────────────
class ForgotPasswordRequest(BaseModel):
    """Check if a user can reset password via face verification"""
    username: str


class ForgotPasswordResponse(BaseModel):
    """Tells frontend whether user exists and has face registered"""
    exists: bool
    has_face: bool
    message: str


class ResetPasswordRequest(BaseModel):
    """Face-verified password reset"""
    username: str
    face_image_base64: str
    new_password: str = Field(min_length=4, max_length=128)


class AdminResetPasswordRequest(BaseModel):
    """Admin resets a user's password"""
    new_password: str = Field(default="123456", min_length=4, max_length=128)


# ── Correction ────────────────────────────────────────────
class CorrectionRequest(BaseModel):
    """Admin reassigns a checkin record to the correct user"""
    correct_user_id: int
