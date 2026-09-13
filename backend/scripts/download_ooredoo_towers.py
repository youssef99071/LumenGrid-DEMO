#!/usr/bin/env python3
"""Download OpenCelliD cells for Greater Tunis (MCC 605).

Uses tiled getInArea calls (historical API, not the 18-month country dump).
OpenCelliD rejects boxes larger than 4 km² and returns at most 50 cells
per request, so this walks a small grid and paginates.

Reads OPENCELLID_API_KEY from the environment or backend/.env.
Writes data/ooredoo_towers.csv for the map layer.

Usage:
  cd backend && PYTHONPATH=.vendor python3 scripts/download_ooredoo_towers.py
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import os
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_CSV = DATA_DIR / "ooredoo_towers.csv"

# Covers Tunis + Ariana / La Marsa / inner Ben Arous (demo map anchors).
TUNIS_BBOX = {
    "min_lat": 36.76,
    "max_lat": 36.90,
    "min_lon": 10.12,
    "max_lon": 10.33,
}
# ~1.3 km × 1.1 km ≈ 1.4 km², under the 4 km² getInArea limit.
TILE_DEG = 0.012
MCC = 605
PAGE_SIZE = 50
AREA_URL = "https://opencellid.org/cell/getInArea"
SIZE_URL = "https://opencellid.org/cell/getInAreaSize"
COUNTRY_URLS = [
    "https://opencellid.org/ocid/downloads?token={token}&type=mcc&file=605.csv.gz",
    "https://download.unwiredlabs.com/ocid/downloads?token={token}&type=mcc&file=605.csv.gz",
]
PROGRESS_PATH = DATA_DIR / "_ocid_tunis_progress.txt"

OCID_FIELDS = [
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


def _load_key() -> str:
    key = os.environ.get("OPENCELLID_API_KEY", "").strip()
    if key:
        return key
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("OPENCELLID_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _tiles() -> list[tuple[float, float, float, float]]:
    tiles = []
    lat = TUNIS_BBOX["min_lat"]
    while lat < TUNIS_BBOX["max_lat"] - 1e-9:
        lon = TUNIS_BBOX["min_lon"]
        lat2 = min(lat + TILE_DEG, TUNIS_BBOX["max_lat"])
        while lon < TUNIS_BBOX["max_lon"] - 1e-9:
            lon2 = min(lon + TILE_DEG, TUNIS_BBOX["max_lon"])
            tiles.append((lat, lon, lat2, lon2))
            lon = lon2
        lat = lat2
    return tiles


def _bbox_param(bbox: tuple[float, float, float, float]) -> str:
    lat1, lon1, lat2, lon2 = bbox
    return f"{lat1:.5f},{lon1:.5f},{lat2:.5f},{lon2:.5f}"


def _cell_row(cell: dict) -> dict[str, str] | None:
    try:
        if int(cell.get("mcc") or 0) != MCC:
            return None
        lat = float(cell.get("lat") or 0)
        lon = float(cell.get("lon") or 0)
    except (TypeError, ValueError):
        return None
    if not (
        TUNIS_BBOX["min_lat"] - 0.01 <= lat <= TUNIS_BBOX["max_lat"] + 0.01
        and TUNIS_BBOX["min_lon"] - 0.01 <= lon <= TUNIS_BBOX["max_lon"] + 0.01
    ):
        return None
    return {
        "radio": str(cell.get("radio") or "LTE"),
        "mcc": str(cell.get("mcc") or MCC),
        "net": str(cell.get("mnc") or cell.get("net") or ""),
        "area": str(cell.get("lac") or cell.get("area") or 0),
        "cell": str(cell.get("cellid") or cell.get("cell") or 0),
        "unit": "0",
        "lon": str(lon),
        "lat": str(lat),
        "range": str(cell.get("range") or 0),
        "samples": str(cell.get("samples") or 0),
        "changeable": str(cell.get("changeable") or 1),
        "created": str(cell.get("created") or ""),
        "updated": str(cell.get("updated") or ""),
        "averageSignal": str(cell.get("averageSignalStrength") or cell.get("averageSignal") or 0),
    }


def _row_key(row: dict[str, str]) -> tuple:
    return (row.get("radio"), row.get("mcc"), row.get("net"), row.get("area"), row.get("cell"))


def _load_existing() -> dict[tuple, dict[str, str]]:
    if not OUT_CSV.exists():
        return {}
    seen: dict[tuple, dict[str, str]] = {}
    with OUT_CSV.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            mapped = _cell_row(row)
            if mapped:
                seen[_row_key(mapped)] = mapped
    return seen


def _write_csv(rows: list[dict[str, str]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=OCID_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _merge_country_dump(client: httpx.Client, token: str, seen: dict[tuple, dict[str, str]]) -> int:
    """Fill gaps from the 18-month MCC 605 export (separate download quota)."""
    added = 0
    for template in COUNTRY_URLS:
        response = client.get(template.format(token=token))
        ctype = response.headers.get("content-type", "")
        if response.status_code != 200 or "text/html" in ctype or response.content[:1] == b"<":
            print(f"  country dump HTTP {response.status_code} — skipped")
            continue
        raw = gzip.decompress(response.content) if response.content[:2] == b"\x1f\x8b" else response.content
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8", errors="replace")))
        for row in reader:
            mapped = _cell_row(row)
            if not mapped:
                continue
            key = _row_key(mapped)
            if key not in seen:
                seen[key] = mapped
                added += 1
        print(f"  merged {added} extra cells from 18-month country dump")
        return added
    return 0


def _read_progress() -> int:
    if not PROGRESS_PATH.exists():
        return 0
    try:
        return int(PROGRESS_PATH.read_text(encoding="utf-8").strip() or 0)
    except ValueError:
        return 0


def _write_progress(tile_index: int) -> None:
    PROGRESS_PATH.write_text(str(tile_index), encoding="utf-8")


def main() -> int:
    token = _load_key()
    if not token:
        print("Set OPENCELLID_API_KEY in backend/.env", file=sys.stderr)
        return 1

    tiles = _tiles()
    seen = _load_existing()
    start_at = _read_progress()
    print(f"Downloading Greater Tunis cells in {len(tiles)} OpenCelliD tiles…")
    if seen:
        print(f"  resuming with {len(seen)} cells already saved (next tile {start_at + 1})")
    requests_made = 0
    headers = {"User-Agent": "LumenGrid/0.1 (OpenCelliD Tunis import)"}
    with httpx.Client(timeout=120.0, follow_redirects=True, headers=headers) as client:
        for i, tile in enumerate(tiles, start=1):
            if i <= start_at:
                continue
            size_resp = client.get(
                SIZE_URL,
                params={"key": token, "BBOX": _bbox_param(tile), "mcc": MCC, "format": "json"},
            )
            requests_made += 1
            expected = 0
            if size_resp.status_code == 200:
                try:
                    expected = int(size_resp.json().get("count") or 0)
                except (ValueError, TypeError, json.JSONDecodeError):
                    expected = 0
            elif size_resp.status_code in (429, 403):
                print(f"  stopped at tile {i}: HTTP {size_resp.status_code} (API limit)")
                break
            else:
                print(f"  tile {i} size HTTP {size_resp.status_code}")

            if expected == 0:
                _write_progress(i)
                print(f"  tile {i}/{len(tiles)} empty (total {len(seen)}, req {requests_made})")
                time.sleep(0.08)
                continue

            added = 0
            offset = 0
            limited = False
            while True:
                response = client.get(
                    AREA_URL,
                    params={
                        "key": token,
                        "BBOX": _bbox_param(tile),
                        "mcc": MCC,
                        "format": "json",
                        "limit": PAGE_SIZE,
                        "offset": offset,
                    },
                )
                requests_made += 1
                if response.status_code in (429, 403):
                    print(f"  stopped at tile {i}: HTTP {response.status_code} (API limit)")
                    limited = True
                    break
                if response.status_code != 200:
                    print(f"  tile {i} page offset={offset} HTTP {response.status_code}")
                    break
                try:
                    payload = response.json()
                except json.JSONDecodeError:
                    print(f"  tile {i} returned non-JSON")
                    break
                cells = payload.get("cells") or []
                for cell in cells:
                    row = _cell_row(cell)
                    if not row:
                        continue
                    key = _row_key(row)
                    if key not in seen:
                        added += 1
                    seen[key] = row
                if len(cells) < PAGE_SIZE:
                    break
                offset += PAGE_SIZE
                if offset > 20_000:
                    break
                time.sleep(0.12)

            if limited:
                break
            _write_progress(i)
            print(
                f"  tile {i}/{len(tiles)} expected {expected} → +{added} unique "
                f"(total {len(seen)}, req {requests_made})"
            )
            if i % 10 == 0:
                _write_csv(list(seen.values()))
            time.sleep(0.12)

        print("Merging 18-month MCC 605 country dump for any remaining Tunis cells…")
        _merge_country_dump(client, token, seen)

    if not seen:
        print("No Tunis cells returned from OpenCelliD.", file=sys.stderr)
        return 2

    rows = list(seen.values())
    _write_csv(rows)
    by_net: dict[str, int] = {}
    for row in rows:
        net = str(row.get("net") or "?")
        by_net[net] = by_net.get(net, 0) + 1
    print(f"Wrote {len(rows)} Tunis cells → {OUT_CSV}")
    print("By MNC:", ", ".join(f"{k}={v}" for k, v in sorted(by_net.items())))
    print(f"API requests used this run: {requests_made}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
