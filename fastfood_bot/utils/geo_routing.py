"""
utils/geo_routing.py
====================
Darxan Burger — Geosamoviy (Geospatial) Hisob-kitoblar va
"Eng Yaqin Filialni Avtomatik Aniqlash" (Nearest Branch Routing) moduli.

Arxitektura va imkoniyatlar:
  1. `branches` jadvalidan barcha faol (`is_active = TRUE`) filiallarni olish.
  2. Mijozning GPS koordinatalari (`client_lat`, `client_lon`) va barcha faol filiallar
     orasidagi masofani `asyncio.gather` yordamida PARALLEL ravishda (OSRM + Haversine) hisoblash.
  3. Eng qisqa masofadagi filialni (`find_nearest_branch`) tanlash va yetkazib berish
     zonasini (standart `MAX_DELIVERY_RADIUS_KM = 15.0` km) tekshirish.
  4. Buyurtmani avtomatik ravishda eng yaqin filialning `admin_chat_id` (Telegram guruhi/kanali)ga
     yo'naltirish (`route_order_to_nearest_branch`).
  5. Ham joriy aiohttp/aiogram 2.x tizimi bilan to'liq integratsiya, ham FastAPI + SQLAlchemy 2.0 + aiogram 3
     endpointlar arxitekturasi.
"""

import asyncio
import logging
import math
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from config import (
    ADMIN_CHANNEL_ID,
    BRANCH_1_CHANNEL_ID,
    BRANCH_2_CHANNEL_ID,
    DELIVERY_BASE_FEE,
    DELIVERY_CHANNEL_ID,
    DELIVERY_EXTRA_PER_KM,
    DELIVERY_FEE,
    DELIVERY_FREE_KM,
)
from database.crud import get_active_branches

log = logging.getLogger(__name__)

# Maksimal yetkazib berish radiusi (km)
MAX_DELIVERY_RADIUS_KM: float = float(os.getenv("MAX_DELIVERY_RADIUS_KM", "15.0"))

OUT_OF_ZONE_MESSAGE_UZ = "Afsuski, bu manzil bizning yetkazib berish zonamizdan tashqarida"
OUT_OF_ZONE_MESSAGE_RU = "К сожалению, этот адрес находится вне зоны нашей доставки"
OUT_OF_ZONE_MESSAGE_EN = "Unfortunately, this address is outside our delivery zone"

# OSRM masofa keshi (15 daqiqa)
_ROUTE_CACHE: Dict[str, Tuple[float, float]] = {}
_ROUTE_CACHE_TTL = 15 * 60

OSRM_ROUTE_URL = (
    "http://router.project-osrm.org/route/v1/driving/"
    "{lon1},{lat1};{lon2},{lat2}?overview=false"
)

# Darxan Burger Buxoro shahridagi 2 ta haqiqiy filiali (2GIS ma'lumotlari asosida)
DEFAULT_FALLBACK_BRANCHES: List[Dict[str, Any]] = [
    {
        "id": 1,
        "name": "Darxan Burger - Abu Ali ibn Sino",
        "address": "Buxoro sh., Abu Ali ibn Sino ko'chasi",
        "latitude": 39.783420,
        "longitude": 64.422526,
        "admin_chat_id": BRANCH_1_CHANNEL_ID or "-1003885234768",
        "delivery_channel_id": DELIVERY_CHANNEL_ID or "-1003943860489",
        "max_delivery_km": MAX_DELIVERY_RADIUS_KM,
        "is_active": True,
    },
    {
        "id": 2,
        "name": "Darxan Burger - 5-mikrorayon",
        "address": "Buxoro sh., 5-mikrorayon",
        "latitude": 39.748796,
        "longitude": 64.414346,
        "admin_chat_id": BRANCH_2_CHANNEL_ID or "-1003631903801",
        "delivery_channel_id": DELIVERY_CHANNEL_ID or "-1003943860489",
        "max_delivery_km": MAX_DELIVERY_RADIUS_KM,
        "is_active": True,
    },
]


# ══════════════════════════════════════════════════════════════════════
# 1. GEOSAMOVIY (HAVERSINE & OSRM) MASOFA HISOBLASH FUNKSIYALARI
# ══════════════════════════════════════════════════════════════════════

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Yer shari egriligini hisobga olgan holda ikki GPS koordinata orasidagi
    masofani Haversine formulasi bo'yicha kilometrda hisoblaydi.
    """
    earth_radius_km = 6371.0
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    delta_phi = math.radians(float(lat2) - float(lat1))
    delta_lambda = math.radians(float(lon2) - float(lon1))

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(earth_radius_km * c, 2)


async def get_driving_or_haversine_km(
    client_lat: float,
    client_lon: float,
    branch_lat: float,
    branch_lon: float,
    use_osrm: bool = True,
) -> float:
    """
    Avval tezkor Haversine masofani tekshiradi:
    - Agar to'g'ri chiziq masofasi > 30 km bo'lsa (boshqa shahar), OSRM ga so'rov yubormaydi.
    - Yaqin filiallar uchun OSRM orqali haqiqiy avtomobil yo'li masofasini oladi,
      OSRM javob bermasa Haversine masofasini qaytaradi.
    """
    straight_km = haversine_distance_km(client_lat, client_lon, branch_lat, branch_lon)
    if not use_osrm or straight_km > 30.0:
        return round(straight_km, 2)

    cache_key = f"{client_lat:.4f},{client_lon:.4f}->{branch_lat:.4f},{branch_lon:.4f}"
    now = time.time()
    if cache_key in _ROUTE_CACHE:
        cached_km, ts = _ROUTE_CACHE[cache_key]
        if now - ts < _ROUTE_CACHE_TTL:
            return cached_km

    url = OSRM_ROUTE_URL.format(
        lon1=client_lon,
        lat1=client_lat,
        lon2=branch_lon,
        lat2=branch_lat,
    )
    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=2.5),
                headers={"User-Agent": "DarxanBurgerGeoRouter/3.0"},
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    routes = data.get("routes") or []
                    if routes and "distance" in routes[0]:
                        road_km = round(float(routes[0]["distance"]) / 1000.0, 2)
                        _ROUTE_CACHE[cache_key] = (road_km, now)
                        return road_km
    except Exception as e:
        log.debug(f"OSRM fallback to Haversine ({e})")

    _ROUTE_CACHE[cache_key] = (straight_km, now)
    return round(straight_km, 2)


def compute_fee_for_distance(distance_km: float) -> int:
    """Masofaga qarab yetkazib berish narxini (1000 so'mga yaxlitlangan holda) hisoblaydi."""
    if distance_km <= DELIVERY_FREE_KM:
        raw_fee = DELIVERY_BASE_FEE
    else:
        extra_km = max(0.0, distance_km - DELIVERY_FREE_KM)
        raw_fee = DELIVERY_BASE_FEE + int(extra_km * DELIVERY_EXTRA_PER_KM)

    remainder = raw_fee % 1000
    if remainder <= 500:
        raw_fee -= remainder
    else:
        raw_fee += 1000 - remainder
    return max(DELIVERY_BASE_FEE, raw_fee)


# ══════════════════════════════════════════════════════════════════════
# 2. PARALLEL RAVISHDA ENG YAQIN FILIALNI TOPISH (find_nearest_branch)
# ══════════════════════════════════════════════════════════════════════

async def _evaluate_single_branch(
    client_lat: float,
    client_lon: float,
    branch: Dict[str, Any],
    use_osrm: bool = True,
) -> Dict[str, Any]:
    """Bitta filialgacha bo'lgan masofa va yetkazib berish narxini hisoblaydi."""
    b_id = int(branch["id"])
    b_lat = float(branch["latitude"])
    b_lon = float(branch["longitude"])
    dist_km = await get_driving_or_haversine_km(
        client_lat, client_lon, b_lat, b_lon, use_osrm=use_osrm
    )
    max_km = float(branch.get("max_delivery_km") or MAX_DELIVERY_RADIUS_KM)
    fee = compute_fee_for_distance(dist_km)

    # 1-filial -> -1003885234768, 2-filial -> -1003631903801
    default_ch = (
        (BRANCH_2_CHANNEL_ID or "-1003631903801")
        if b_id == 2
        else (BRANCH_1_CHANNEL_ID or "-1003885234768")
    )
    admin_ch = str(branch.get("admin_chat_id") or default_ch)

    return {
        "id": b_id,
        "name": str(branch["name"]),
        "address": str(branch.get("address") or ""),
        "latitude": b_lat,
        "longitude": b_lon,
        "admin_chat_id": admin_ch,
        "delivery_channel_id": str(
            branch.get("delivery_channel_id") or DELIVERY_CHANNEL_ID or "-1003943860489"
        ),
        "distance_km": round(dist_km, 1),
        "max_delivery_km": max_km,
        "in_delivery_zone": dist_km <= max_km,
        "delivery_fee": fee,
    }


def _get_clean_bukhara_branches(db_rows: Any) -> List[Dict[str, Any]]:
    """
    Bazadan olingan filiallarni tekshiradi. Agar bazada eski (>2 ta yoki Toshkent)
    filiallar qolgan bo'lsa, faqat Buxorodagi 2 ta haqiqiy filialni qaytaradi.
    """
    if not db_rows:
        return [dict(b) for b in DEFAULT_FALLBACK_BRANCHES]
    rows = [dict(r) for r in db_rows]
    if len(rows) != 2:
        return [dict(b) for b in DEFAULT_FALLBACK_BRANCHES]
    # Kanal ID larini 1-filial va 2-filial uchun aniq kafolatlash
    for r in rows:
        if int(r.get("id", 0)) == 1:
            r["admin_chat_id"] = BRANCH_1_CHANNEL_ID or "-1003885234768"
        elif int(r.get("id", 0)) == 2:
            r["admin_chat_id"] = BRANCH_2_CHANNEL_ID or "-1003631903801"
    return rows


async def find_nearest_branch(
    client_lat: float,
    client_lon: float,
    max_radius_km: Optional[float] = None,
    use_osrm: bool = True,
) -> Dict[str, Any]:
    """
    Mijoz koordinatalariga (`client_lat`, `client_lon`) asoslanib:
      1. Barcha faol filiallargacha bo'lgan masofani `asyncio.gather` yordamida PARALLEL hisoblaydi.
      2. Eng qisqa masofadagi filialni (`nearest_branch`) tanlaydi.
      3. Yetkazib berish radiusidan (`max_radius_km`, standart 15 km) uzoq bo'lsa,
         `in_delivery_zone = False` va ogohlantirish xabarini qaytaradi.
    """
    try:
        db_rows = await get_active_branches()
        branches = _get_clean_bukhara_branches(db_rows)
    except Exception as e:
        log.warning(f"Bazadan filiallarni olishda xato ({e}), fallback ishlatiladi.")
        branches = [dict(b) for b in DEFAULT_FALLBACK_BRANCHES]

    # Parallel ravishda barcha faol filiallargacha masofani hisoblash
    tasks = [
        _evaluate_single_branch(float(client_lat), float(client_lon), b, use_osrm=use_osrm)
        for b in branches
    ]
    evaluated: List[Dict[str, Any]] = await asyncio.gather(*tasks)
    evaluated.sort(key=lambda item: item["distance_km"])

    nearest = evaluated[0]
    effective_limit = (
        float(max_radius_km)
        if max_radius_km is not None
        else float(nearest.get("max_delivery_km") or MAX_DELIVERY_RADIUS_KM)
    )
    in_zone = nearest["distance_km"] <= effective_limit
    nearest["in_delivery_zone"] = in_zone

    if in_zone:
        msg_uz = f"Sizga eng yaqin filial: {nearest['name']} ({nearest['distance_km']} km)"
        return {
            "success": True,
            "in_delivery_zone": True,
            "nearest_branch": nearest,
            "all_branches": evaluated,
            "distance_km": nearest["distance_km"],
            "delivery_fee": nearest["delivery_fee"],
            "message": msg_uz,
            "error": None,
        }
    else:
        return {
            "success": False,
            "in_delivery_zone": False,
            "nearest_branch": nearest,
            "all_branches": evaluated,
            "distance_km": nearest["distance_km"],
            "delivery_fee": nearest["delivery_fee"],
            "message": OUT_OF_ZONE_MESSAGE_UZ,
            "error": OUT_OF_ZONE_MESSAGE_UZ,
        }


async def resolve_branch_for_order(
    client_lat: Optional[float] = None,
    client_lon: Optional[float] = None,
    address: Optional[str] = None,
    branch_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Mijoz buyurtmasi uchun filialni aniqlaydi:
      1. Agar `branch_id` (1 yoki 2) berilgan bo'lsa — o'sha filialni tanlaydi.
      2. Agar `client_lat` va `client_lon` berilgan bo'lsa — `find_nearest_branch` orqali
         eng yaqin filialni aniqlaydi.
      3. Agar faqat matnli `address` berilgan bo'lsa — matn ichidagi kalit so'zlar
         (masalan, '5-mikrorayon' -> 2-filial, 'ibn sino' -> 1-filial) yoki Nominatim
         orqali Buxoro bo'yicha koordinatasini topib, eng yaqin filialni qaytaradi.
    """
    try:
        db_rows = await get_active_branches()
        branches = _get_clean_bukhara_branches(db_rows)
    except Exception:
        branches = [dict(b) for b in DEFAULT_FALLBACK_BRANCHES]

    by_id = {int(b["id"]): dict(b) for b in branches}

    # 1. Agar aniq branch_id tanlangan bo'lsa (masalan "Shu yerda" bo'limida)
    if branch_id and int(branch_id) in by_id:
        chosen = by_id[int(branch_id)]
        if client_lat is not None and client_lon is not None:
            return await _evaluate_single_branch(float(client_lat), float(client_lon), chosen)
        chosen.setdefault("distance_km", 0.0)
        chosen.setdefault("in_delivery_zone", True)
        chosen.setdefault("delivery_fee", DELIVERY_FEE)
        return chosen

    # 2. Agar GPS koordinatalar mavjud bo'lsa — eng yaqin filialni hisoblaymiz
    if client_lat is not None and client_lon is not None:
        geo_res = await find_nearest_branch(float(client_lat), float(client_lon))
        if geo_res.get("nearest_branch"):
            return geo_res["nearest_branch"]

    # 3. Matnli manzil orqali aniqlash (agar GPS berilmagan bo'lsa)
    addr_low = (address or "").lower()
    if addr_low:
        branch2_keywords = (
            "5-mikr", "5 mikr", "5-mkr", "5 mkr", "5-микр", "5 микр",
            "5-kichik", "5 kichik", "mikrarayon", "mikrorayon", "микрорайон",
            "elit max", "2-filial", "2 filial", "piridastgir", "murtazoyev",
            "6-mikr", "4-mikr", "3-mikr", "karvon", "avtovokzal", "sharq",
        )
        branch1_keywords = (
            "ibn sino", "abu ali", "ибн сино", "абу али", "samarqand",
            "самарканд", "1-filial", "1 filial", "gijduvon", "g'ijduvon",
            "markaziy bozor", "kolxoz", "ark", "kalon",
        )
        if any(k in addr_low for k in branch2_keywords) and 2 in by_id:
            b2 = by_id[2]
            b2.setdefault("distance_km", None)
            b2.setdefault("in_delivery_zone", True)
            b2.setdefault("delivery_fee", DELIVERY_FEE)
            return b2
        if any(k in addr_low for k in branch1_keywords) and 1 in by_id:
            b1 = by_id[1]
            b1.setdefault("distance_km", None)
            b1.setdefault("in_delivery_zone", True)
            b1.setdefault("delivery_fee", DELIVERY_FEE)
            return b1

        # Nominatim orqali Buxoro shahrida qidirib ko'rish
        if "stol" not in addr_low and len(addr_low) >= 4:
            try:
                q = address if ("buxoro" in addr_low or "бухар" in addr_low) else f"Buxoro, {address}"
                async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
                    async with session.get(
                        "https://nominatim.openstreetmap.org/search",
                        params={"format": "json", "q": q, "limit": "1"},
                        headers={"User-Agent": "DarxanBurgerGeoRouter/3.0"},
                        timeout=aiohttp.ClientTimeout(total=2.5),
                    ) as resp:
                        if resp.status == 200:
                            sdata = await resp.json()
                            if sdata and isinstance(sdata, list):
                                slat = float(sdata[0]["lat"])
                                slon = float(sdata[0]["lon"])
                                geo_res = await find_nearest_branch(slat, slon)
                                if geo_res.get("nearest_branch"):
                                    return geo_res["nearest_branch"]
            except Exception as e:
                log.debug(f"Address forward geocode fallback: {e}")

    # Default: 1-filial (Abu Ali ibn Sino ko'chasi)
    fallback = by_id.get(1) or dict(DEFAULT_FALLBACK_BRANCHES[0])
    fallback.setdefault("distance_km", None)
    fallback.setdefault("in_delivery_zone", True)
    fallback.setdefault("delivery_fee", DELIVERY_FEE)
    return fallback


# ══════════════════════════════════════════════════════════════════════
# 3. BUYURTMANI ENG YAQIN FILIALGA YO'NALTIRISH (route_order_to_nearest_branch)
# ══════════════════════════════════════════════════════════════════════

async def route_order_to_nearest_branch(
    bot,
    order_id: int,
    total_amount: int,
    user,
    items: list,
    phone: str,
    address: str,
    client_lat: Optional[float] = None,
    client_lon: Optional[float] = None,
    note: Optional[str] = None,
    delivery_type: str = "delivery",
    payment_method: str = "Naqd (Yetkazib berilganda)",
    promo_code: Optional[str] = None,
    discount_pct: int = 0,
    discount_amt: int = 0,
    precomputed_branch: Optional[Dict[str, Any]] = None,
    branch_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Buyurtmani avtomatik ravishda eng yaqin filialning `admin_chat_id`
    (1-filial: -1003885234768 yoki 2-filial: -1003631903801) kanaliga yuboradi.
    Barcha xabarlar bir xil ko'rinishda yuboriladi, faqat filialga qarab
    tegishli kanalga yo'naltiriladi.
    """
    from utils.helpers import notify_admins_new_order

    branch_info = precomputed_branch
    if branch_info is None:
        branch_info = await resolve_branch_for_order(
            client_lat=client_lat,
            client_lon=client_lon,
            address=address,
            branch_id=branch_id,
        )

    target_admin_chat_id = (
        branch_info.get("admin_chat_id") if branch_info else None
    ) or BRANCH_1_CHANNEL_ID or ADMIN_CHANNEL_ID
    branch_name = branch_info.get("name") if branch_info else "Darxan Burger - Abu Ali ibn Sino"
    distance_km = branch_info.get("distance_km") if branch_info else None

    await notify_admins_new_order(
        bot=bot,
        order_id=order_id,
        total_amount=total_amount,
        user=user,
        items=items,
        phone=phone,
        address=address,
        location={"lat": client_lat, "lon": client_lon} if (client_lat and client_lon) else None,
        note=note,
        delivery_type=delivery_type,
        payment_method=payment_method,
        promo_code=promo_code,
        discount_pct=discount_pct,
        discount_amt=discount_amt,
        branch_name=branch_name,
        distance_km=distance_km,
        target_channel_id=target_admin_chat_id,
    )

    return {
        "routed": True,
        "order_id": order_id,
        "branch": branch_info,
        "target_admin_chat_id": target_admin_chat_id,
    }


# ══════════════════════════════════════════════════════════════════════
# 4. FASTAPI + AIOGRAM 3 STANDALONE ROUTER (Arxitektura namunasi)
# ══════════════════════════════════════════════════════════════════════
try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field

    fastapi_geo_router = APIRouter(prefix="/api/v1/geo", tags=["Geo-Routing & Branches"])

    class NearestBranchRequest(BaseModel):
        client_lat: float = Field(..., ge=-90.0, le=90.0, description="Mijoz GPS kengligi (latitude)")
        client_lon: float = Field(..., ge=-180.0, le=180.0, description="Mijoz GPS uzunligi (longitude)")

    @fastapi_geo_router.post("/nearest-branch")
    async def fastapi_get_nearest_branch(payload: NearestBranchRequest):
        """
        Mijoz koordinatalariga ko'ra eng yaqin faol filialni Haversine/OSRM orqali
        parallel ravishda aniqlaydi va 15 km yetkazib berish zonasini tekshiradi.
        """
        result = await find_nearest_branch(payload.client_lat, payload.client_lon)
        if not result["in_delivery_zone"]:
            raise HTTPException(
                status_code=400,
                detail=OUT_OF_ZONE_MESSAGE_UZ,
            )
        return result

except ImportError:
    fastapi_geo_router = None

