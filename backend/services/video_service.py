"""
Video processing service: frame extraction + batch face recognition + deduplication.
Processes uploaded video, finds all unique faces, and returns their embeddings.
"""
import os, sys, time, tempfile, uuid
from typing import List, Tuple, Optional
import numpy as np
import cv2

from services.face_service import _ensure_app, match_face
from config import FACE_SIMILARITY_THRESHOLD

# ── Config ───────────────────────────────────────────────
FRAME_INTERVAL_SECONDS = 0.5   # sample one frame every 0.5s
MIN_FACE_SIZE = 50             # minimum face bbox dimension
DEDUP_SIMILARITY = 0.45        # cosine similarity threshold to consider two faces the SAME person
                                # (higher than recognition threshold: we're deduping, not identifying)


class VideoPerson:
    """Represents a unique person found in the video."""
    def __init__(self, track_id: int, best_embedding: np.ndarray, best_face_img: np.ndarray,
                 best_score: float, first_frame: int):
        self.track_id = track_id
        self.best_embedding = best_embedding  # 512-dim normed embedding
        self.best_face_img = best_face_img    # best quality face crop
        self.best_score = best_score          # detection confidence
        self.first_frame = first_frame        # frame where first seen
        self.count = 1                        # number of detections across frames

    def update(self, embedding: np.ndarray, face_img: np.ndarray, score: float, frame_idx: int):
        self.count += 1
        if score > self.best_score:
            self.best_score = score
            self.best_embedding = embedding
            self.best_face_img = face_img


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two normalized embeddings."""
    return float(np.dot(a, b))


def _embedding_to_jpeg_base64(face_img: np.ndarray) -> str:
    """Convert a face crop (BGR numpy) to base64 JPEG string."""
    import base64
    _, buf = cv2.imencode('.jpg', face_img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf).decode()


async def process_video(
    video_path: str,
    user_embeddings: List[Tuple[int, bytes]],  # [(user_id, embedding_bytes), ...]
    location_id: int,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    location_name: Optional[str] = None,
    progress_callback=None,
) -> dict:
    """
    Process a video file, find all unique faces, match against registered users,
    and return check-in results.

    Returns:
        {
            "total_frames": int,
            "unique_faces": int,
            "matched_users": [{"user_id": int, "user_name": str, "confidence": float, "face_img_b64": str}, ...],
            "unmatched_faces": int,
            "processing_time_seconds": float,
        }
    """
    t_start = time.perf_counter()
    app = _ensure_app()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError("Cannot open video file")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30  # fallback

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_skip = max(1, int(fps * FRAME_INTERVAL_SECONDS))

    unique_persons: List[VideoPerson] = []  # deduplicated face tracks
    track_counter = 0

    frame_idx = 0
    processed_frames = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Sample frames at interval
        if frame_idx % frame_skip == 0:
            processed_frames += 1

            # Detect faces in this frame
            faces = app.get(frame)

            for face in faces:
                bbox = face.bbox
                w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                if w < MIN_FACE_SIZE or h < MIN_FACE_SIZE:
                    continue

                emb = face.normed_embedding
                score = face.det_score

                # Check if this face matches any existing track
                matched = False
                for person in unique_persons:
                    sim = _cosine_sim(emb, person.best_embedding)
                    if sim >= DEDUP_SIMILARITY:
                        person.update(emb, _crop_face(frame, face), score, frame_idx)
                        matched = True
                        break

                if not matched:
                    track_counter += 1
                    unique_persons.append(VideoPerson(
                        track_id=track_counter,
                        best_embedding=emb,
                        best_face_img=_crop_face(frame, face),
                        best_score=score,
                        first_frame=frame_idx,
                    ))

        frame_idx += 1

    cap.release()

    # ── Match against registered users ────────────────────
    matched_users = []
    unmatched_count = 0

    for person in unique_persons:
        user_id = match_face(person.best_embedding, user_embeddings)
        if user_id is not None:
            face_b64 = _embedding_to_jpeg_base64(person.best_face_img)
            conf = person.best_score
            matched_users.append({
                "user_id": user_id,
                "confidence": round(float(conf), 4),
                "face_img_b64": face_b64,
                "detections": person.count,
            })
        else:
            unmatched_count += 1

    elapsed = time.perf_counter() - t_start

    return {
        "total_frames": processed_frames,
        "unique_faces": len(unique_persons),
        "matched_users": matched_users,
        "unmatched_faces": unmatched_count,
        "processing_time_seconds": round(elapsed, 1),
    }


def _crop_face(frame: np.ndarray, face) -> np.ndarray:
    """Crop the face region from a frame."""
    bbox = face.bbox.astype(int)
    x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]
    # Add margin
    h, w = frame.shape[:2]
    margin = int(min(x2 - x1, y2 - y1) * 0.2)
    x1 = max(0, x1 - margin)
    y1 = max(0, y1 - margin)
    x2 = min(w, x2 + margin)
    y2 = min(h, y2 + margin)
    return frame[y1:y2, x1:x2].copy()
