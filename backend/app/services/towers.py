"""Load OpenCelliD Ooredoo cells for Greater Tunis (MCC 605 / MNC 03)."""

from __future__ import annotations

import csv
import logging
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
CSV_PATH = DATA_DIR / "ooredoo_towers.csv"  # Greater Tunis OpenCelliD export

OPERATORS = {
    1: "Orange Tunisia",
    2: "Tunisie Telecom",
    3: "Ooredoo Tunisia",
}


def _parse_opencellid_csv(path: Path) -> Dict[str, Any]:
    towers: List[Dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as f:
        sample = f.readline()
        f.seek(0)
        has_header = sample.lower().startswith("radio,") or sample.lower().startswith("mcc,")
        fieldnames = [
            "radio",
            "mcc",
            "net",
            "area",
            "cell",
            "unit",
            "lon",
            "lat",
            "range",
            "samples",
            "changeable",
            "created",
            "updated",
            "averageSignal",
        ]
        reader = csv.DictReader(f) if has_header else csv.DictReader(f, fieldnames=fieldnames)
        for row in reader:
            try:
                mcc = int(row.get("mcc") or row.get("MCC") or 0)
                mnc = int(row.get("net") or row.get("mnc") or row.get("MNC") or -1)
                if mcc != 605 or mnc != 3:
                    continue
                lat = float(row.get("lat") or row.get("latitude") or 0)
                lon = float(row.get("lon") or row.get("longitude") or 0)
                if not (36.76 <= lat <= 36.90 and 10.12 <= lon <= 10.33):
                    continue
                towers.append(
                    {
                        "lat": round(lat, 5),
                        "lon": round(lon, 5),
                        "radio": row.get("radio") or row.get("RAT") or "LTE",
                        "mcc": 605,
                        "mnc": mnc,
                        "operator": OPERATORS.get(mnc, f"MCC 605 / MNC {mnc}"),
                        "cell": int(float(row.get("cell") or row.get("cellid") or 0)),
                    }
                )
            except (TypeError, ValueError):
                continue
    return {
        "operator": "Ooredoo Tunisia",
        "mcc": 605,
        "mnc": 3,
        "source": "opencellid_tunis_area",
        "attribution": "OpenCelliD — https://opencellid.org/ (CC BY-SA 4.0)",
        "count": len(towers),
        "towers": towers,
    }


@lru_cache(maxsize=1)
def load_towers() -> Dict[str, Any]:
    """Load OpenCelliD Ooredoo Greater Tunis cells (MCC 605 / MNC 03)."""
    if CSV_PATH.exists():
        logger.info("Loading Ooredoo towers from OpenCelliD CSV %s", CSV_PATH)
        return _parse_opencellid_csv(CSV_PATH)
    return {
        "operator": "Ooredoo Tunisia",
        "mcc": 605,
        "mnc": 3,
        "source": "empty",
        "attribution": "No OpenCelliD CSV — run python3 scripts/download_ooredoo_towers.py",
        "count": 0,
        "towers": [],
    }


def towers_payload(
    *,
    bbox: Optional[tuple[float, float, float, float]] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    data = load_towers()
    towers: List[Dict[str, Any]] = data["towers"]
    if bbox:
        min_lat, min_lon, max_lat, max_lon = bbox
        towers = [
            t
            for t in towers
            if min_lat <= t["lat"] <= max_lat and min_lon <= t["lon"] <= max_lon
        ]
    if limit is not None and limit > 0:
        towers = towers[:limit]
    return {
        "operator": data.get("operator"),
        "mcc": data.get("mcc"),
        "mnc": data.get("mnc"),
        "source": data.get("source"),
        "attribution": data.get("attribution"),
        "count": len(towers),
        "total": data.get("count", len(towers)),
        "towers": towers,
    }


def clear_tower_cache() -> None:
    load_towers.cache_clear()


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def nearest_ooredoo(
    lat: float, lon: float, n: int = 3
) -> List[Tuple[Dict[str, Any], float]]:
    towers = [t for t in load_towers().get("towers", []) if int(t.get("mnc") or 0) == 3]
    ranked = sorted(towers, key=lambda t: haversine_m(lat, lon, t["lat"], t["lon"]))
    unique: List[Tuple[Dict[str, Any], float]] = []
    seen: set[str] = set()
    for tower in ranked:
        site = f"{round(tower['lat'], 4)},{round(tower['lon'], 4)}"
        if site in seen:
            continue
        seen.add(site)
        unique.append((tower, round(haversine_m(lat, lon, tower["lat"], tower["lon"]), 1)))
        if len(unique) == n:
            break
    return unique


def rssi_from_rsrp(rsrp: float) -> int:
    """LTE RSSI ≈ RSRP + 10·log10(12·N_RB); 10 MHz → N_RB=50."""
    return int(round(rsrp + 10 * math.log10(12 * 50)))


def camara_distance_m(
    real_m: float,
    match_rate: Optional[float],
    rsrp: Optional[float],
) -> float:
    """Network-estimated range: CAMARA is coarser than GPS, worse when match/RSRP drop."""
    mr = 70.0 if match_rate is None else float(match_rate)
    rp = -90.0 if rsrp is None else float(rsrp)
    match_bias = 1.0 + (100.0 - mr) / 70.0
    rsrp_bias = 1.0 + max(0.0, -90.0 - rp) / 80.0
    return round(max(25.0, real_m * match_bias * rsrp_bias), 1)


def rssi_at_distance(serving_rssi: int, serving_m: float, target_m: float) -> int:
    """Farther neighbor cells are weaker by free-space path-loss vs the serving site."""
    d0 = max(serving_m, 1.0)
    d1 = max(target_m, 1.0)
    return int(round(max(-120.0, min(-40.0, serving_rssi - 20.0 * math.log10(d1 / d0)))))


def radio_overlay(
    lat: float,
    lon: float,
    *,
    match_rate: Optional[float] = None,
    rsrp: Optional[float] = None,
) -> Dict[str, Any]:
    neighbors = nearest_ooredoo(lat, lon, n=3)
    if not neighbors:
        return {
            "real_distance_m": [],
            "camara_distance_m": [],
            "rssi_dbm": [],
            "rsrp": int(round(rsrp)) if rsrp is not None else None,
        }
    serving_m = neighbors[0][1]
    serving_rssi = rssi_from_rsrp(rsrp if rsrp is not None else -90.0)
    reals = [dist for _tower, dist in neighbors]
    camaras = [camara_distance_m(dist, match_rate, rsrp) for dist in reals]
    rssis = [rssi_at_distance(serving_rssi, serving_m, dist) for dist in reals]
    return {
        "real_distance_m": reals,
        "camara_distance_m": camaras,
        "rssi_dbm": rssis,
        "rsrp": int(round(rsrp)) if rsrp is not None else None,
    }
