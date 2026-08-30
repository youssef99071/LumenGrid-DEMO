"""Load Ooredoo Tunisia (MCC 605 / MNC 03) tower points for map display."""

from __future__ import annotations

import csv
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
JSON_PATH = DATA_DIR / "ooredoo_towers.json"
CSV_PATH = DATA_DIR / "ooredoo_towers.csv"  # OpenCelliD-style export


def _parse_opencellid_csv(path: Path) -> Dict[str, Any]:
    towers: List[Dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                mcc = int(row.get("mcc") or row.get("MCC") or 0)
                mnc = int(row.get("net") or row.get("mnc") or row.get("MNC") or -1)
                if mcc != 605 or mnc != 3:
                    continue
                lat = float(row.get("lat") or row.get("latitude") or 0)
                lon = float(row.get("lon") or row.get("longitude") or 0)
                if not (30.0 <= lat <= 38.0 and 7.0 <= lon <= 12.0):
                    continue
                towers.append(
                    {
                        "lat": round(lat, 5),
                        "lon": round(lon, 5),
                        "radio": row.get("radio") or row.get("RAT") or "LTE",
                        "mcc": 605,
                        "mnc": 3,
                        "cell": int(float(row.get("cell") or row.get("cellid") or 0)),
                    }
                )
            except (TypeError, ValueError):
                continue
    return {
        "operator": "Ooredoo Tunisia",
        "mcc": 605,
        "mnc": 3,
        "source": "opencellid_csv",
        "attribution": "OpenCelliD — https://opencellid.org/ (CC BY-SA 4.0)",
        "count": len(towers),
        "towers": towers,
    }


@lru_cache(maxsize=1)
def load_towers() -> Dict[str, Any]:
    """Prefer real OpenCelliD CSV if present; else synthetic JSON demo layer."""
    if CSV_PATH.exists():
        logger.info("Loading Ooredoo towers from %s", CSV_PATH)
        return _parse_opencellid_csv(CSV_PATH)
    if not JSON_PATH.exists():
        try:
            from scripts.generate_ooredoo_towers import main as gen

            gen()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not auto-generate towers: %s", exc)
    if JSON_PATH.exists():
        data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
        logger.info("Loading %s towers from %s", data.get("count"), JSON_PATH)
        return data
    return {
        "operator": "Ooredoo Tunisia",
        "mcc": 605,
        "mnc": 3,
        "source": "empty",
        "attribution": "No tower file found — run scripts/generate_ooredoo_towers.py",
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
