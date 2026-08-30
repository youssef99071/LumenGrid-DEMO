"""Live AI simulation: record a 60s clip, then match occupancy on the full sequence."""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional

from sqlalchemy.orm import Session, joinedload

from app.db.session import SessionLocal
from app.models.anchor_reading import AnchorReading, RecordingClip, TrafficLabel
from app.models.traffic_prediction import TrafficPrediction
from app.services.clip_features import extract_clip_features, samples_from_readings
from app.services.data_generator import MODEL_VERSION, explain_prediction, _metrics_for_label
from app.services.locations import LOCATION_BY_ID, get_location
from app.services.ml_model import predict_clip
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
    tick_rows: List[Dict[str, float]] = []
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

            tick_rows.append(
                {
                    "match_rate": float(metrics["match_rate"]),
                    "rsrp": float(metrics["rsrp"]),
                    "rsrq": float(metrics["rsrq"]),
                    "neighbor_count": float(metrics["neighbor_count"]),
                    "latitude": lat,
                    "longitude": lon,
                }
            )

            # Live tick for the chart — class match waits until clip is complete
            await hub.broadcast(
                {
                    "type": "prediction_update",
                    "location_id": location_id,
                    "latitude": lat,
                    "longitude": lon,
                    "prediction": clip_label.value,  # provisional ground-truth band
                    "confidence": 0.0,
                    "match_rate": metrics["match_rate"],
                    "rsrp": metrics["rsrp"],
                    "rsrq": metrics["rsrq"],
                    "neighbor_count": metrics["neighbor_count"],
                    "actual_traffic": clip_label.value,
                    "correct": False,
                    "probabilities": {},
                    "reading_id": reading.id,
                    "clip_id": clip_id,
                    "timestamp": ts.isoformat(),
                    "model_version": MODEL_VERSION,
                    "progress": round((i + 1) / n * 100, 1),
                    "sample_index": i + 1,
                    "total_samples": n,
                    "scenario": scenario,
                    "interim": True,
                }
            )
            await asyncio.sleep(interval)

        # ── Clip-level match (learning & inference unit) ──────────────
        state, confidence, probs = predict_clip(tick_rows, modality="full")
        feats = extract_clip_features(tick_rows, modality="full")
        pred = TrafficPrediction(
            timestamp=start_ts + timedelta(seconds=n - 1),
            location_id=location_id,
            predicted_state=state,
            confidence=confidence,
            model_version=MODEL_VERSION,
        )
        db.add(pred)
        db.commit()
        db.refresh(pred)

        explanation = explain_prediction(
            predicted_state=state,
            confidence=confidence,
            match_rate=int(round(feats.get("match_rate_mean", 0))),
            rsrp=int(round(feats.get("rsrp_mean", 0))),
            rsrq=int(round(feats.get("rsrq_mean", 0))),
            neighbor_count=int(round(feats.get("neighbor_count_mean", 0))),
            location_name=loc["name"],
            wander=feats.get("match_rate_wander"),
            jitter=feats.get("match_rate_jitter"),
        )
        await hub.broadcast(
            {
                "type": "simulation_complete",
                "location_id": location_id,
                "location_name": loc["name"],
                "samples": n,
                "scenario": scenario,
                "clip_id": clip_id,
                "unit": "60s_clip",
                "final_prediction": {
                    "prediction": state,
                    "confidence": confidence,
                    "match_rate": int(round(feats.get("match_rate_mean", 0))),
                    "rsrp": int(round(feats.get("rsrp_mean", 0))),
                    "rsrq": int(round(feats.get("rsrq_mean", 0))),
                    "neighbor_count": int(round(feats.get("neighbor_count_mean", 0))),
                    "wander": round(feats.get("match_rate_wander", 0), 2),
                    "jitter": round(feats.get("match_rate_jitter", 0), 2),
                    "actual_traffic": clip_label.value,
                    "probabilities": probs,
                    "explanation": explanation,
                    "timestamp": pred.timestamp.isoformat(),
                    "correct": state == clip_label.value,
                },
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
    anchors = db.query(func.count(func.distinct(RecordingClip.anchor_id))).scalar() or 0
    latest_pred = (
        db.query(TrafficPrediction).order_by(TrafficPrediction.timestamp.desc()).first()
    )

    recent_preds: List[TrafficPrediction] = (
        db.query(TrafficPrediction).order_by(TrafficPrediction.timestamp.desc()).limit(200).all()
    )
    correct = 0
    compared = 0
    for pred in recent_preds:
        clip = (
            db.query(RecordingClip)
            .filter(
                RecordingClip.anchor_id == pred.location_id,
                RecordingClip.end_time == pred.timestamp,
            )
            .first()
        )
        if clip is None:
            continue
        compared += 1
        if clip.traffic_label == pred.predicted_state:
            correct += 1
    accuracy = (correct / compared) if compared else None

    markers = []
    for loc_id, loc in LOCATION_BY_ID.items():
        pred = (
            db.query(TrafficPrediction)
            .filter(TrafficPrediction.location_id == loc_id)
            .order_by(TrafficPrediction.timestamp.desc())
            .first()
        )
        clip = (
            db.query(RecordingClip)
            .options(joinedload(RecordingClip.samples))
            .filter(RecordingClip.anchor_id == loc_id)
            .order_by(RecordingClip.start_time.desc())
            .first()
        )
        state = pred.predicted_state if pred else "NORMAL"
        conf = pred.confidence if pred else 0.0
        match_rate = None
        if clip and clip.samples:
            feats = extract_clip_features(samples_from_readings(clip.samples))
            match_rate = int(round(feats.get("match_rate_mean", 0)))
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
            }
        )

    total_readings = db.query(func.count(AnchorReading.id)).scalar() or 0
    return {
        "traffic_health_pct": round((normalish / total_clips) * 100, 1) if total_clips else 100.0,
        "active_anchors": anchors or len(LOCATION_BY_ID),
        "model_accuracy": round(accuracy * 100, 1) if accuracy is not None else None,
        "latest_confidence": latest_pred.confidence if latest_pred else None,
        "total_readings": total_readings,
        "total_clips": total_clips,
        "total_predictions": db.query(func.count(TrafficPrediction.id)).scalar() or 0,
        "markers": markers,
    }
