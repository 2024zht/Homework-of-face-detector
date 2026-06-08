"""Location service: distance calculation and Gaode API integration"""
import math
import hashlib
import time
from typing import Optional, Tuple
import httpx
from config import AMAP_KEY, AMAP_SECURITY_KEY


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate the great-circle distance between two points (in meters).
    Uses the Haversine formula. Works with GCJ-02 coordinates for short distances.
    """
    R = 6371000  # Earth radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)

    a = (math.sin(delta_phi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def is_within_range(
    user_lat: float, user_lng: float,
    target_lat: float, target_lng: float,
    radius_meters: float = 100
) -> Tuple[bool, float]:
    """
    Check if user is within the target location's radius.
    Returns (is_within, distance_meters).
    """
    distance = haversine_distance(user_lat, user_lng, target_lat, target_lng)
    return distance <= radius_meters, distance


def _amap_sig(params: dict) -> str:
    """Generate Gaode API signature using security key."""
    # Sort params alphabetically
    sorted_items = sorted(params.items(), key=lambda x: x[0])
    param_str = "&".join(f"{k}={v}" for k, v in sorted_items if v is not None)
    # Append security key
    sig_str = param_str + AMAP_SECURITY_KEY
    return hashlib.md5(sig_str.encode()).hexdigest()


async def reverse_geocode(lat: float, lng: float) -> Optional[str]:
    """Get human-readable address from Gaode reverse geocoding API."""
    try:
        params = {
            "key": AMAP_KEY,
            "location": f"{lng},{lat}",
        }
        sig = _amap_sig(params)
        params["sig"] = sig

        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                "https://restapi.amap.com/v3/geocode/regeo",
                params=params,
            )
            data = resp.json()
            if data.get("status") == "1" and data.get("regeocode"):
                return data["regeocode"].get("formatted_address", None)
    except Exception:
        pass
    return None
