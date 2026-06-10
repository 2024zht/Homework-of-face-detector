"""InsightFace wrapper service for face detection and recognition"""
import os, sys, time, base64, io
from typing import Optional, Tuple, List
import numpy as np
from PIL import Image

# ── DLL setup for GPU ────────────────────────────────────
_site = os.path.join(os.path.dirname(sys.executable), "lib", "site-packages")
for _pkg in ["nvidia\\cudnn\\bin", "nvidia\\cublas\\bin", "nvidia\\cuda_nvrtc\\bin"]:
    _d = os.path.join(_site, _pkg)
    if os.path.isdir(_d) and hasattr(os, "add_dll_directory"):
        os.add_dll_directory(_d)
    os.environ["PATH"] = _d + ";" + os.environ.get("PATH", "")

import cv2
from insightface.app import FaceAnalysis
from config import INSIGHTFACE_MODEL, FACE_SIMILARITY_THRESHOLD

# Lazy-loaded singleton
_app: Optional[FaceAnalysis] = None
_initialized = False


def _ensure_app():
    global _app, _initialized
    if not _initialized:
        _app = FaceAnalysis(
            name=INSIGHTFACE_MODEL,
            allowed_modules=['detection', 'recognition'],
            providers=['CUDAExecutionProvider', 'CPUExecutionProvider'],
        )
        _app.prepare(ctx_id=0, det_size=(640, 640))
        _initialized = True
    return _app


def extract_embedding(image_data: bytes) -> Optional[np.ndarray]:
    """Extract face embedding from JPEG image bytes. Returns (512,) float32 array or None."""
    try:
        app = _ensure_app()
        # Decode image
        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return None

        faces = app.get(img)
        if len(faces) < 1:
            return None

        # Use the largest face
        best = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        return best.normed_embedding.astype(np.float32)
    except Exception as e:
        print(f"[FaceService] extract_embedding error: {e}")
        return None


def extract_embedding_from_base64(b64_string: str) -> Optional[np.ndarray]:
    """Extract face embedding from base64-encoded JPEG string."""
    try:
        # Strip data URI prefix if present
        if ',' in b64_string:
            b64_string = b64_string.split(',', 1)[1]
        image_data = base64.b64decode(b64_string)
        return extract_embedding(image_data)
    except Exception as e:
        print(f"[FaceService] extract_embedding_from_base64 error: {e}")
        return None


def match_face(embedding: np.ndarray, candidates: List[Tuple[int, bytes]]) -> Optional[int]:
    """
    Find the best matching user from a list of (user_id, face_embedding_bytes).
    Returns user_id or None if no match above threshold.
    """
    if not candidates:
        return None

    best_id = None
    best_sim = -1.0

    for user_id, emb_bytes in candidates:
        try:
            stored_emb = np.frombuffer(emb_bytes, dtype=np.float32)
            if stored_emb.shape[0] != 512:
                continue
            # Cosine similarity (both are already normalized)
            sim = float(np.dot(embedding, stored_emb))
            if sim > best_sim:
                best_sim = sim
                best_id = user_id
        except Exception:
            continue

    if best_sim >= FACE_SIMILARITY_THRESHOLD:
        return best_id
    return None


def embedding_to_bytes(embedding: np.ndarray) -> bytes:
    """Convert numpy embedding to bytes for database storage."""
    return embedding.astype(np.float32).tobytes()


def bytes_to_embedding(data: bytes) -> np.ndarray:
    """Convert stored bytes back to numpy embedding."""
    return np.frombuffer(data, dtype=np.float32)


def save_checkin_photo(image_data: bytes, filename: str) -> str:
    """Save a check-in photo and return the relative path."""
    from config import PHOTO_DIR
    path = os.path.join(PHOTO_DIR, filename)
    # Decode base64 if needed
    if isinstance(image_data, str):
        if ',' in image_data:
            image_data = image_data.split(',', 1)[1]
        image_data = base64.b64decode(image_data)
    with open(path, 'wb') as f:
        f.write(image_data)
    return f"photos/{filename}"


LEARNING_RATE = 0.15  # weight for new embedding in moving average


def update_embedding(old_bytes: bytes, new_embedding: np.ndarray) -> bytes:
    """
    Self-learning: merge new embedding into stored one via moving average.
    Blends old stored embedding (85%) with new one (15%), then re-normalizes.
    Over time, the stored embedding becomes a richer representation of the person.
    """
    old_emb = bytes_to_embedding(old_bytes)
    if old_emb.shape != new_embedding.shape:
        return embedding_to_bytes(new_embedding)
    blended = (1.0 - LEARNING_RATE) * old_emb + LEARNING_RATE * new_embedding
    norm = np.linalg.norm(blended)
    if norm > 0:
        blended = blended / norm
    return embedding_to_bytes(blended.astype(np.float32))
