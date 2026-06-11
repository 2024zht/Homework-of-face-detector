"""JWT token utilities"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from config import SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_MINUTES
from utils.time_utils import beijing_now_naive


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = beijing_now_naive() + (expires_delta or timedelta(minutes=JWT_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
