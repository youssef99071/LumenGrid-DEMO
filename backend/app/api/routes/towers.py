"""Greater Tunis OpenCelliD tower map endpoints."""

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
    """Return Ooredoo Greater Tunis (MCC 605 / MNC 03) cells for the Leaflet layer."""
    bbox = None
    if None not in (min_lat, min_lon, max_lat, max_lon):
        bbox = (min_lat, min_lon, max_lat, max_lon)  # type: ignore[arg-type]
    return towers_payload(bbox=bbox, limit=limit)


@router.post("/reload")
def reload_towers() -> dict:
    clear_tower_cache()
    data = towers_payload()
    return {"reloaded": True, "count": data["count"], "source": data["source"]}


@router.post("/sync")
def sync_from_opencellid() -> dict:
    """Re-download Greater Tunis cells from OpenCelliD using OPENCELLID_API_KEY."""
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parents[3] / "scripts" / "download_ooredoo_towers.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(script.parent.parent),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        from fastapi import HTTPException

        raise HTTPException(status_code=502, detail=result.stderr or result.stdout or "download failed")
    clear_tower_cache()
    data = towers_payload()
    return {"synced": True, "count": data["count"], "source": data["source"], "log": result.stdout.strip()}
