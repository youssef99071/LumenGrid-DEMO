"""Simulation + dashboard + WebSocket routes."""

from __future__ import annotations

import logging
from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.locations import list_locations
from app.services.simulation import (
    dashboard_snapshot,
    simulation_busy,
    start_simulation_task,
)
from app.services.ws_hub import hub

logger = logging.getLogger(__name__)

router = APIRouter(tags=["simulation"])


class SimulationRunRequest(BaseModel):
    traffic_intensity: int = Field(50, ge=0, le=100)
    location_id: str
    time_of_day: Literal["morning", "afternoon", "evening", "night"] = "morning"
    speed: Literal[1, 5, 10] = 5
    duration_seconds: int = Field(60, ge=5, le=120)
    scenario: Literal[
        "CUSTOM", "EMPTY", "LOW_OCCUPANCY", "NORMAL", "SLOW", "TRAFFIC_JAM"
    ] = "CUSTOM"


class LocationOut(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    district: str


class MarkerOut(BaseModel):
    location_id: str
    name: str
    district: str
    latitude: float
    longitude: float
    prediction: str
    confidence: float
    match_rate: int | None = None
    rsrp: int | None = None
    rssi_dbm: List[int] | None = None
    real_distance_m: List[float] | None = None
    camara_distance_m: List[float] | None = None
    updated_at: str | None = None


class DashboardStatsOut(BaseModel):
    traffic_health_pct: float
    active_anchors: int
    model_accuracy: float | None
    latest_confidence: float | None
    total_readings: int
    total_clips: int = 0
    total_predictions: int
    markers: List[MarkerOut]


@router.get("/api/locations", response_model=List[LocationOut])
def get_locations(response: Response) -> List[LocationOut]:
    response.headers["Cache-Control"] = "public, max-age=3600"
    return [LocationOut(**loc) for loc in list_locations()]


@router.get("/api/dashboard/stats", response_model=DashboardStatsOut)
def get_dashboard_stats(db: Session = Depends(get_db)) -> DashboardStatsOut:
    return DashboardStatsOut(**dashboard_snapshot(db))


@router.post("/api/simulation/run")
async def run_simulation_endpoint(body: SimulationRunRequest) -> dict:
    if simulation_busy():
        raise HTTPException(status_code=409, detail="A simulation is already running")
    started = start_simulation_task(
        traffic_intensity=body.traffic_intensity,
        location_id=body.location_id,
        time_of_day=body.time_of_day,
        speed=body.speed,
        duration_seconds=body.duration_seconds,
        scenario=body.scenario,
    )
    if not started:
        raise HTTPException(status_code=409, detail="A simulation is already running")
    return {"status": "started", **body.model_dump()}


@router.get("/api/simulation/status")
def simulation_status() -> dict:
    return {"running": simulation_busy()}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await hub.connect(websocket)
    try:
        while True:
            # Keep connection alive; clients may send pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(websocket)
    except Exception:  # noqa: BLE001
        await hub.disconnect(websocket)
        logger.exception("WebSocket error")
