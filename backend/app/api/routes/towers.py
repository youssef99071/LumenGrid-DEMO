"""Ooredoo Tunisia (MCC 605 / MNC 03) tower map endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from app.services.towers import clear_tower_cache, towers_payload

router = APIRouter(prefix="/api/towers", tags=["towers"])


@router.get("/ooredoo")
def get_ooredoo_towers(
    min_lat: Optional[float] = None,
    min_lon: Optional[float] = None,
    max_lat: Optional[float] = None,
    max_lon: Optional[float] = None,
    limit: Optional[int] = Query(None, ge=1, le=100_000),
) -> dict:
    """Return Ooredoo (605/03) tower points for the Leaflet layer."""
    bbox = None
    if None not in (min_lat, min_lon, max_lat, max_lon):
        bbox = (min_lat, min_lon, max_lat, max_lon)  # type: ignore[arg-type]
    return towers_payload(bbox=bbox, limit=limit)


@router.post("/reload")
def reload_towers() -> dict:
    clear_tower_cache()
    data = towers_payload()
    return {"reloaded": True, "count": data["count"], "source": data["source"]}
