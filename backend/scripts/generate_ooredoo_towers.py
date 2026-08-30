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


def clamp_tunisia(lat: float, lon: float) -> bool:
    return 30.2 <= lat <= 37.6 and 7.5 <= lon <= 11.6


def main() -> None:
    rng = random.Random(60503)
    towers = []
    cell_id = 1

    for lat0, lon0, weight, _name in HUBS:
        count = weight * 45  # ~ dense urban cells
        for _ in range(count):
            # Gaussian around hub; tighter for higher weight
            sigma = 0.08 + 0.12 * (1.0 / math.sqrt(weight))
            lat = lat0 + rng.gauss(0, sigma)
            lon = lon0 + rng.gauss(0, sigma * 1.15)
            if not clamp_tunisia(lat, lon):
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

    # Rural fill along coast / inland
    for _ in range(3500):
        lat = rng.uniform(32.5, 37.3)
        lon = rng.uniform(8.0, 11.3)
        if not clamp_tunisia(lat, lon):
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

    payload = {
        "operator": "Ooredoo Tunisia",
        "mcc": 605,
        "mnc": 3,
        "source": "synthetic_demo",
        "attribution": "Synthetic densified coverage for LumenGrid PoC. Replace with OpenCelliD MCC 605 / MNC 03 CSV for real towers.",
        "count": len(towers),
        "towers": towers,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {len(towers)} towers → {OUT}")


if __name__ == "__main__":
    main()
