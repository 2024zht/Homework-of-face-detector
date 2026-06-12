"""SQLAlchemy ORM models"""
import uuid
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, LargeBinary
from sqlalchemy.orm import relationship
from database import Base
from utils.time_utils import beijing_now_naive


def gen_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False, default="student")  # admin, instructor, student
    face_embedding = Column(LargeBinary, nullable=True)  # numpy float32 array as bytes
    face_photo_path = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=beijing_now_naive)

    checkins = relationship("CheckIn", back_populates="user")
    qr_sessions = relationship("QRSession", back_populates="generator")


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    latitude = Column(Float, nullable=False)  # GCJ-02
    longitude = Column(Float, nullable=False)  # GCJ-02
    radius_meters = Column(Integer, default=100)
    created_by = Column(Integer, ForeignKey("users.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=beijing_now_naive)

    creator = relationship("User")


class CheckIn(Base):
    __tablename__ = "checkins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    check_in_time = Column(DateTime, default=beijing_now_naive, index=True)
    check_out_time = Column(DateTime, nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    lat = Column(Float, nullable=True)  # actual position at check-in
    lng = Column(Float, nullable=True)
    location_name = Column(String(500), nullable=True)
    check_in_photo = Column(String(500), nullable=True)
    check_out_photo = Column(String(500), nullable=True)
    is_auto_checkout = Column(Boolean, default=False)
    status = Column(String(20), default="active")  # active, completed
    # Correction tracking: admin can reassign misidentified checkins
    original_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    corrected_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    corrected_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="checkins", foreign_keys=[user_id])
    location = relationship("Location")


class QRSession(Base):
    __tablename__ = "qr_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(64), unique=True, nullable=False, default=gen_uuid, index=True)
    type = Column(String(10), nullable=False)  # checkin, checkout
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    generated_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=beijing_now_naive)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)

    generator = relationship("User", back_populates="qr_sessions")
    location = relationship("Location")

    def is_expired(self) -> bool:
        return beijing_now_naive() > self.expires_at
