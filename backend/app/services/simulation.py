"""Live What-If recorder: generate a 60s clip. Prediction is a separate ML step."""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Literal, Optional

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.anchor_reading import AnchorReading, RecordingClip, TrafficLabel
from app.models.traffic_prediction import TrafficPrediction
from app.services.data_generator import _metrics_for_label
from app.services.locations import LOCATION_BY_ID, get_location
from app.services.towers import radio_overlay
from app.services.ws_hub import hub

logger = logging.getLogger(__name__)

TimeOfDay = Literal["morning", "afternoon", "evening", "night"]
SimSpeed = Literal[1, 5, 10]
WhatIfScenario = Literal[
    "CUSTOM", "EMPTY", "LOW_OCCUPANCY", "NORMAL", "SLOW", "TRAFFIC_JAM"
]

_running: Optional[asyncio.Task] = None

SCENARIO_INTENSITY = {
    "EMPTY": 5,
    "LOW_OCCUPANCY": 20,
    "NORMAL": 40,
    "SLOW": 62,
    "TRAFFIC_JAM": 85,
}


def intensity_to_label(intensity: int, time_of_day: TimeOfDay, rng: random.Random) -> TrafficLabel:
    bias = {"morning": 8, "afternoon": 0, "evening": 12, "night": -20}[time_of_day]
    effective = max(0, min(100, intensity + bias + rng.randint(-4, 4)))
    if effective < 12:
        return TrafficLabel.EMPTY
    if effective < 28:
        return TrafficLabel.LOW_OCCUPANCY
    if effective < 50:
        return TrafficLabel.NORMAL
    if effective < 72:
        return TrafficLabel.SLOW
    return TrafficLabel.TRAFFIC_JAM


def metrics_from_intensity(intensity: int, rng: random.Random) -> Dict[str, int]:
    label = intensity_to_label(intensity, "afternoon", rng)
    return _metrics_for_label(label, rng)


def metrics_for_scenario(scenario: WhatIfScenario, rng: random.Random) -> tuple[TrafficLabel, Dict[str, int]]:
    label = TrafficLabel[scenario] if scenario != "CUSTOM" else TrafficLabel.NORMAL
    return label, _metrics_for_label(label, rng)


async def run_simulation(
    *,
    traffic_intensity: int,
    location_id: str,
    time_of_day: TimeOfDay,
    speed: SimSpeed,
    duration_seconds: int = 60,
    scenario: WhatIfScenario = "CUSTOM",
) -> None:
    loc = get_location(location_id)
    if loc is None:
        await hub.broadcast({"type": "error", "message": f"Unknown location {location_id}"})
        return

    rng = random.Random()
    n = duration_seconds
    interval = 1.0 / float(speed)
    if scenario != "CUSTOM":
        traffic_intensity = SCENARIO_INTENSITY[scenario]
        clip_label, _ = metrics_for_scenario(scenario, rng)
    else:
        clip_label = intensity_to_label(traffic_intensity, time_of_day, rng)

    clip_id = str(uuid.uuid4())
    start_ts = datetime.utcnow()

    await hub.broadcast(
        {
            "type": "simulation_started",
            "location_id": location_id,
            "location_name": loc["name"],
            "traffic_intensity": traffic_intensity,
            "time_of_day": time_of_day,
            "speed": speed,
            "duration_seconds": duration_seconds,
            "scenario": scenario,
            "clip_id": clip_id,
            "unit": "60s_clip",
        }
    )

    db = SessionLocal()
    try:
        clip = RecordingClip(
            id=clip_id,
            anchor_id=location_id,
            start_time=start_ts,
            end_time=start_ts + timedelta(seconds=n - 1),
            duration_seconds=n,
            sample_count=n,
            latitude=loc["latitude"],
            longitude=loc["longitude"],
            traffic_label=clip_label.value,
            annotation_source="SYNTHETIC",
        )
        db.add(clip)
        db.commit()

        for i in range(n):
            if scenario != "CUSTOM":
                label, base = metrics_for_scenario(scenario, rng)
            else:
                drift = int(8 * (i / max(1, n - 1)) * (1 if traffic_intensity >= 50 else -1))
                tick_intensity = max(0, min(100, traffic_intensity + drift + rng.randint(-3, 3)))
                label = intensity_to_label(tick_intensity, time_of_day, rng)
                base = metrics_from_intensity(tick_intensity, rng)

            # Per-tick wander/jitter around class band
            jam_factor = 1.0 + (0.8 if label == TrafficLabel.TRAFFIC_JAM else 0.0)
            metrics = {
                "match_rate": int(max(0, min(100, base["match_rate"] + rng.gauss(0, 1.5 * jam_factor)))),
                "rsrp": int(max(-140, min(-44, base["rsrp"] + rng.gauss(0, 1.2 * jam_factor)))),
                "rsrq": int(max(-19, min(-3, base["rsrq"] + rng.gauss(0, 0.4 * jam_factor)))),
                "neighbor_count": int(max(0, min(20, base["neighbor_count"] + rng.randint(-1, 1)))),
            }
            lat = loc["latitude"] + rng.gauss(0, 0.00003 * jam_factor)
            lon = loc["longitude"] + rng.gauss(0, 0.00003 * jam_factor)
            ts = start_ts + timedelta(seconds=i)

            reading = AnchorReading(
                clip_id=clip_id,
                seq_index=i,
                timestamp=ts,
                anchor_id=location_id,
                latitude=lat,
                longitude=lon,
                traffic_label=clip_label.value,
                annotation_source="SYNTHETIC",
                **metrics,
            )
            db.add(reading)
            db.commit()

            # Live tick for the recording chart — prediction is a separate step
            await hub.broadcast(
                {
                    "type": "recording_update",
                    "location_id": location_id,
                    "latitude": lat,
                    "longitude": lon,
                    "match_rate": metrics["match_rate"],
                    "rsrp": metrics["rsrp"],
                    "rsrq": metrics["rsrq"],
                    "neighbor_count": metrics["neighbor_count"],
                    "actual_traffic": clip_label.value,
                    "reading_id": reading.id,
                    "clip_id": clip_id,
                    "timestamp": ts.isoformat(),
                    "progress": round((i + 1) / n * 100, 1),
                    "sample_index": i + 1,
                    "total_samples": n,
                    "scenario": scenario,
                }
            )
            await asyncio.sleep(interval)

        await hub.broadcast(
            {
                "type": "simulation_complete",
                "location_id": location_id,
                "location_name": loc["name"],
                "samples": n,
                "scenario": scenario,
                "clip_id": clip_id,
                "unit": "60s_clip",
                "actual_traffic": clip_label.value,
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Simulation failed")
        await hub.broadcast({"type": "error", "message": str(exc)})
    finally:
        db.close()


def simulation_busy() -> bool:
    return _running is not None and not _running.done()


def start_simulation_task(**kwargs: Any) -> bool:
    global _running
    if simulation_busy():
        return False
    _running = asyncio.create_task(run_simulation(**kwargs))
    return True


def dashboard_snapshot(db: Session) -> Dict[str, Any]:
    """Aggregate stats for dashboard cards + map markers (clip-based)."""
    from sqlalchemy import func

    from app.services.ml_model import model_status

    total_clips = db.query(func.count(RecordingClip.id)).scalar() or 0
    normalish = (
        db.query(func.count(RecordingClip.id))
        .filter(
            RecordingClip.traffic_label.in_(
                [
                    TrafficLabel.EMPTY.value,
                    TrafficLabel.LOW_OCCUPANCY.value,
                    TrafficLabel.NORMAL.value,
                ]
            )
        )
        .scalar()
        or 0
    )
    latest_pred = (
        db.query(TrafficPrediction).order_by(TrafficPrediction.timestamp.desc()).first()
    )
    recent_preds = (
        db.query(TrafficPrediction)
        .order_by(TrafficPrediction.timestamp.desc())
        .limit(80)
        .all()
    )
    latest_by_loc: Dict[str, TrafficPrediction] = {}
    for pred in recent_preds:
        if pred.location_id not in latest_by_loc:
            latest_by_loc[pred.location_id] = pred

    trained = model_status()
    accuracy = trained.get("accuracy")

    markers = []
    for loc_id, loc in LOCATION_BY_ID.items():
        pred = latest_by_loc.get(loc_id)
        clip = (
            db.query(RecordingClip)
            .filter(RecordingClip.anchor_id == loc_id)
            .order_by(RecordingClip.start_time.desc())
            .first()
        )
        sample = None
        if clip is not None:
            sample = (
                db.query(AnchorReading)
                .filter(AnchorReading.clip_id == clip.id, AnchorReading.seq_index == 0)
                .first()
            )
        state = pred.predicted_state if pred else "NORMAL"
        conf = pred.confidence if pred else 0.0
        match_rate = int(sample.match_rate) if sample is not None else None
        rsrp = int(sample.rsrp) if sample is not None else None
        radio = radio_overlay(loc["latitude"], loc["longitude"], match_rate=match_rate, rsrp=rsrp)
        markers.append(
            {
                "location_id": loc_id,
                "name": loc["name"],
                "district": loc["district"],
                "latitude": loc["latitude"],
                "longitude": loc["longitude"],
                "prediction": state,
                "confidence": conf,
                "match_rate": match_rate,
                "updated_at": (pred.timestamp.isoformat() if pred else None),
                **radio,
            }
        )

    return {
        "traffic_health_pct": round((normalish / total_clips) * 100, 1) if total_clips else 100.0,
        "active_anchors": len(LOCATION_BY_ID),
        "model_accuracy": float(accuracy) if accuracy is not None else None,
        "latest_confidence": latest_pred.confidence if latest_pred else None,
        "total_readings": total_clips * 60,
        "total_clips": total_clips,
        "total_predictions": db.query(func.count(TrafficPrediction.id)).scalar() or 0,
        "markers": markers,
    }
