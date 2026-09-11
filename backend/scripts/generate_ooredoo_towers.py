#!/usr/bin/env python3
"""Generate a dense synthetic Ooredoo Tunisia (MCC 605 / MNC 03) tower layer for the map.

Replace the output with a real OpenCelliD export filtered to mcc=605, net=3:
  radio,mcc,net,area,cell,unit,lon,lat,range,samples,...

Usage:
  PYTHONPATH=.vendor python scripts/generate_ooredoo_towers.py
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "ooredoo_towers.json"

# Urban / corridor seeds (lat, lon, weight, radio mix bias toward LTE in cities)
HUBS = [
    (36.8065, 10.1815, 140, "Tunis"),
    (36.8450, 10.2200, 90, "Ariana/Carthage"),
    (36.7500, 10.2000, 70, "Ben Arous"),
    (36.8600, 10.3000, 55, "La Marsa"),
    (35.8256, 10.6411, 80, "Sousse"),
    (35.6781, 10.0963, 50, "Monastir"),
    (34.7406, 10.7603, 95, "Sfax"),
    (33.8869, 10.0982, 40, "Gabès"),
    (36.4513, 10.7350, 35, "Nabeul"),
    (36.7256, 9.1817, 30, "Béja"),
    (35.6784, 10.0969, 25, "Moknine"),
    (37.2744, 9.8739, 45, "Bizerte"),
    (35.7830, 10.8330, 28, "Mahdia"),
    (33.7070, 8.9710, 22, "Tozeur"),
    (32.9290, 10.4510, 20, "Medenine"),
    (36.1750, 8.7100, 25, "Le Kef"),
    (35.6710, 8.7140, 18, "Kasserine"),
    (35.0380, 9.4850, 22, "Sidi Bouzid"),
    (35.7836, 9.7739, 24, "Kairouan"),
    (36.9680, 8.7570, 18, "Jendouba"),
]

# Simplified Tunisia land polygon (lat, lon) — clockwise coastal outline.
# This keeps towers on land and off the sea / Gulf of Tunis / Gulf of Hammamet.
TUNISIA_POLYGON = [
    # North coast (Cape Blanc to Cape Bon peninsula)
    (37.55, 9.05),
    (37.35, 9.70),
    (37.28, 9.87), # Bizerte
    (37.22, 10.00),
    (37.16, 10.19), # Ghar el Melh
    (37.06, 10.12), # Kalaat el Andalous
    (36.94, 10.20), # Raoued
    (36.85, 10.34), # Carthage
    (36.81, 10.32), # La Goulette
    (36.73, 10.33), # Hammam Lif
    (36.70, 10.49), # Soliman (bottom of Gulf of Tunis)
    (36.81, 10.57), # Korbous
    (37.01, 10.90), # Sidi Daoud
    (37.08, 11.04), # El Haouaria (Tip of Cape Bon)
    (36.85, 11.10), # Kelibia
    (36.60, 10.95),
    # Gulf of Hammamet coast going south
    (36.45, 10.74), # Nabeul
    (36.40, 10.61), # Hammamet
    (36.15, 10.60),
    (35.82, 10.64), # Sousse
    (35.77, 10.83), # Monastir/Mahdia
    (35.52, 10.98),
    (35.23, 11.08),
    (34.73, 10.80),
    (34.34, 10.72),
    # Gulf of Gabès turning SW
    (33.88, 10.10),
    (33.56, 10.85),
    (33.10, 11.05),
    (32.95, 11.58),
    # Southern tip / Libya border
    (32.50, 11.58),
    (32.10, 11.50),
    # Sahara southern border going west
    (30.25, 9.55),
    (30.25, 8.00),
    # Western / Algerian border going north
    (31.50, 7.52),
    (33.00, 8.15),
    (33.90, 8.35),
    (34.70, 8.30),
    (35.10, 8.15),
    (35.80, 8.35),
    (36.45, 8.48),
    (36.75, 8.36),
    (37.10, 8.50),
    (37.35, 8.75),
    (37.55, 9.05),  # back to start
]


def _point_in_polygon(lat: float, lon: float, polygon: list[tuple[float, float]]) -> bool:
    """Ray-casting algorithm: returns True if (lat, lon) is inside the polygon."""
    n = len(polygon)
    inside = False
    px, py = lon, lat
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i][1], polygon[i][0]
        xj, yj = polygon[j][1], polygon[j][0]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def is_on_land(lat: float, lon: float) -> bool:
    """Return True only if the point is inside Tunisia's land boundary."""
    # Quick outer bounding box first for speed
    if not (30.2 <= lat <= 37.6 and 7.5 <= lon <= 11.6):
        return False
    return _point_in_polygon(lat, lon, TUNISIA_POLYGON)


def main() -> None:
    rng = random.Random(60503)
    towers = []
    cell_id = 1

    for lat0, lon0, weight, _name in HUBS:
        count = weight * 45  # ~ dense urban cells
        placed = 0
        attempts = 0
        while placed < count and attempts < count * 8:
            attempts += 1
            # Gaussian around hub; tighter for higher weight
            sigma = 0.08 + 0.12 * (1.0 / math.sqrt(weight))
            lat = lat0 + rng.gauss(0, sigma)
            lon = lon0 + rng.gauss(0, sigma * 1.15)
            if not is_on_land(lat, lon):
                continue
            radio = rng.choices(["LTE", "UMTS", "GSM", "NR"], weights=[0.55, 0.25, 0.12, 0.08])[0]
            towers.append(
                {
                    "lat": round(lat, 5),
                    "lon": round(lon, 5),
                    "radio": radio,
                    "mcc": 605,
                    "mnc": 3,
                    "cell": cell_id,
                }
            )
            cell_id += 1
            placed += 1

    # Rural fill along inland areas only
    placed = 0
    attempts = 0
    target_rural = 3500
    while placed < target_rural and attempts < target_rural * 6:
        attempts += 1
        lat = rng.uniform(30.5, 37.3)
        lon = rng.uniform(7.6, 11.4)
        if not is_on_land(lat, lon):
            continue
        radio = rng.choices(["LTE", "UMTS", "GSM"], weights=[0.35, 0.35, 0.30])[0]
        towers.append(
            {
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "radio": radio,
                "mcc": 605,
                "mnc": 3,
                "cell": cell_id,
            }
        )
        cell_id += 1
        placed += 1

    payload = {
        "operator": "Ooredoo Tunisia",
        "mcc": 605,
        "mnc": 3,
        "source": "synthetic_demo",
        "attribution": "Synthetic land-constrained coverage for LumenGrid PoC. Replace with OpenCelliD MCC 605 / MNC 03 CSV for real towers.",
        "count": len(towers),
        "towers": towers,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {len(towers)} towers -> {OUT}")


if __name__ == "__main__":
    main()

