"""Application configuration — secrets via environment variables."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

# Database
DATABASE_URL = f"sqlite+aiosqlite:///{os.path.join(PROJECT_DIR, 'database', 'checkin.db')}"
SYNC_DATABASE_URL = f"sqlite:///{os.path.join(PROJECT_DIR, 'database', 'checkin.db')}"

# JWT
SECRET_KEY = os.getenv("CHECKIN_SECRET_KEY", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Gaode (AMap) API
AMAP_KEY = os.getenv("AMAP_KEY", "")
AMAP_SECURITY_KEY = os.getenv("AMAP_SECURITY_KEY", "")

# Check-in settings
CHECKIN_RADIUS_METERS = 100  # max distance from location
QR_EXPIRE_MINUTES = 5  # QR code valid duration
AUTO_CHECKOUT_HOURS = 4  # auto sign-out after this many hours

# Face recognition
FACE_SIMILARITY_THRESHOLD = 0.25  # cosine similarity threshold
INSIGHTFACE_MODEL = "buffalo_l"

# File storage
STATIC_DIR = os.path.join(PROJECT_DIR, "static")
PHOTO_DIR = os.path.join(STATIC_DIR, "photos")
QRCODE_DIR = os.path.join(STATIC_DIR, "qrcodes")

# Server
HOST = "0.0.0.0"
PORT = 8080
BASE_URL = os.getenv("CHECKIN_BASE_URL", "https://375eace6.r6.cpolar.top")

# Default lab location (for QR code display)
DEFAULT_LAB_LAT = float(os.getenv("LAB_LAT", "36.547308"))
DEFAULT_LAB_LNG = float(os.getenv("LAB_LNG", "116.83223"))
DEFAULT_LAB_NAME = os.getenv("LAB_NAME", "实验室")

for d in [PHOTO_DIR, QRCODE_DIR]:
    os.makedirs(d, exist_ok=True)
