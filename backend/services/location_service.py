"""Location service: distance calculation and Gaode API integration"""
import math
import hashlib
import time
from typing import Optional, Tuple
import httpx
from config import AMAP_KEY, AMAP_SECURITY_KEY


# ── WGS-84 to GCJ-02 conversion ──────────────────────────
# Phone GPS returns WGS-84. Gaode maps use GCJ-02. Offset = 100-500m.
PI = math.pi
_A = 6378245.0
_EE = 0.00669342162296594323


def _tx(x, y):
    r = -100 + 2*x + 3*y + 0.2*y*y + 0.1*x*y + 0.2*math.sqrt(abs(x))
    r += (20*math.sin(6*x*PI) + 20*math.sin(2*x*PI))*2/3
    r += (20*math.sin(y*PI) + 40*math.sin(y/3*PI))*2/3
    r += (160*math.sin(y/12*PI) + 320*math.sin(y*PI/30))*2/3
    return r


def _ty(x, y):
    r = 300 + x + 2*y + 0.1*x*x + 0.1*x*y + 0.1*math.sqrt(abs(x))
    r += (20*math.sin(6*x*PI) + 20*math.sin(2*x*PI))*2/3
    r += (20*math.sin(x*PI) + 40*math.sin(x/3*PI))*2/3
    r += (150*math.sin(x/12*PI) + 300*math.sin(x/30*PI))*2/3
    return r


def wgs84_to_gcj02(lat, lng):
    """Convert WGS-84 (phone GPS) to GCJ-02 (Gaode coordinate system)."""
    if lng < 72.004 or lng > 137.8347 or lat < 0.8293 or lat > 55.8271:
        return lat, lng
    dlat = _tx(lng - 105, lat - 35)
    dlng = _ty(lng - 105, lat - 35)
    rlat = lat / 180 * PI
    m = 1 - _EE * math.sin(rlat)**2
    sm = math.sqrt(m)
    dlat = (dlat*180) / ((_A*(1-_EE))/(m*sm)*PI)
    dlng = (dlng*180) / (_A/sm*math.cos(rlat)*PI)
    return lat + dlat, lng + dlng


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
    Phone GPS (WGS-84) is converted to GCJ-02 to match Gaode coordinates.
    Returns (is_within, distance_meters).
    """
    # Convert phone GPS WGS-84 → GCJ-02 to match lab coordinates from Gaode
    user_gcj_lat, user_gcj_lng = wgs84_to_gcj02(user_lat, user_lng)
    distance = haversine_distance(user_gcj_lat, user_gcj_lng, target_lat, target_lng)
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
    """Get human-readable address from Gaode reverse geocoding API.
    Input coords are WGS-84 from phone GPS; converts to GCJ-02 for Gaode."""
    try:
        gcj_lat, gcj_lng = wgs84_to_gcj02(lat, lng)
        params = {
            "key": AMAP_KEY,
            "location": f"{gcj_lng},{gcj_lat}",
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
