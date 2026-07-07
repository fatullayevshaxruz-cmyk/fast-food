"""
utils/delivery_fee.py
======================
Masofaga qarab yetkazib berish narxini hisoblash.

OSRM (Open Source Routing Machine) API — bepul, ro'yxatdan o'tish shart emas.
Agar API ishlamasa → haversine formula bilan to'g'ri chiziq masofa (fallback).

Formula:
  - Birinchi FREE_KM km   → BASE_FEE
  - Qo'shimcha har km     → EXTRA_PER_KM so'm
  - API ishlamasa         → DELIVERY_FEE (tekis narx, fallback)
"""

import math
import time
import logging
import aiohttp

log = logging.getLogger(__name__)

# Natijalarni 15 daqiqa keshlaymiz
_CACHE: dict = {}
_CACHE_TTL = 15 * 60

OSRM_URL = (
    "http://router.project-osrm.org/route/v1/driving/"
    "{lon1},{lat1};{lon2},{lat2}?overview=false"
)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """To'g'ri chiziq masofa (Haversine) — OSRM ishlamasa fallback."""
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def _get_route_km(
    user_lat: float, user_lon: float,
    rest_lat: float,  rest_lon: float,
) -> float:
    """OSRM API orqali yo'l masofasini olish (km). Kesh: 15 daqiqa."""
    cache_key = f"{user_lat:.4f},{user_lon:.4f}"
    now = time.time()

    if cache_key in _CACHE:
        val, ts = _CACHE[cache_key]
        if now - ts < _CACHE_TTL:
            log.debug(f"Delivery fee keshdan: {val:.1f} km")
            return val

    # OSRM API urinish
    url = OSRM_URL.format(
        lon1=user_lon, lat1=user_lat,
        lon2=rest_lon, lat2=rest_lat,
    )
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=5),
                headers={"User-Agent": "FastFoodBot/2.0"},
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    routes = data.get("routes", [])
                    if routes:
                        km = routes[0]["distance"] / 1000.0
                        _CACHE[cache_key] = (km, now)
                        log.info(f"OSRM masofa: {km:.1f} km")
                        return km
    except Exception as e:
        log.warning(f"OSRM API xatosi ({e}), haversine ishlatiladi")

    # Fallback: to'g'ri chiziq
    km = _haversine_km(user_lat, user_lon, rest_lat, rest_lon)
    _CACHE[cache_key] = (km, now)
    log.info(f"Haversine masofa: {km:.1f} km")
    return km


async def calculate_delivery_fee(
    user_lat: float,
    user_lon: float,
    restaurant_lat: float,
    restaurant_lon: float,
    base_fee: int,
    extra_per_km: int,
    free_km: float,
    fallback_fee: int,
) -> tuple:
    """
    Yetkazib berish narxini hisoblaydi.

    Returns: (fee: int, distance_km: float)
      - fee          — to'lash kerak bo'lgan narx (so'mda)
      - distance_km  — yo'l masofasi (km)
    """
    try:
        km = await _get_route_km(user_lat, user_lon, restaurant_lat, restaurant_lon)

        if km <= free_km:
            fee = base_fee
        else:
            extra = km - free_km
            fee = base_fee + int(extra * extra_per_km)

        return fee, round(km, 1)

    except Exception as e:
        log.error(f"Delivery fee hisoblanmadi: {e}")
        return fallback_fee, 0.0
