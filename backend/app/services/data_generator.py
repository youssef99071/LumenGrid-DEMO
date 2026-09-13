"""Learning-phase generator: labeled 60-second clips with wander/jitter."""

from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.anchor_reading import (
    OCCUPANCY_ORDER,
    AnnotationSource,
    AnchorReading,
    RecordingClip,
    TrafficLabel,
)
from app.models.traffic_prediction import TrafficPrediction
from app.services.clip_features import CLIP_LEN, samples_from_readings, synthesize_clip_samples
from app.services.locations import TUNIS_LOCATIONS

logger = logging.getLogger(__name__)

DEFAULT_ANCHORS: List[Tuple[str, float, float]] = [
    (loc["id"], loc["latitude"], loc["longitude"]) for loc in TUNIS_LOCATIONS
]

MODEL_VERSION = "clip-rf-v1"


def _traffic_profile(minute_of_day: int, rng: random.Random) -> TrafficLabel:
    hour = (minute_of_day // 60) % 24
    labels = list(OCCUPANCY_ORDER)
    if 7 <= hour <= 9 or 16 <= hour <= 18:
        weights = [0.02, 0.08, 0.20, 0.35, 0.35]
    elif 11 <= hour <= 14:
        weights = [0.05, 0.15, 0.40, 0.30, 0.10]
    elif 22 <= hour or hour <= 5:
        weights = [0.45, 0.30, 0.18, 0.05, 0.02]
    else:
        weights = [0.10, 0.20, 0.40, 0.20, 0.10]
    return rng.choices(labels, weights=weights, k=1)[0]


def _metrics_for_label(label: TrafficLabel, rng: random.Random) -> dict:
    bands = {
        TrafficLabel.EMPTY: (90, 99, -75, -50, -7, -3, 0, 3),
        TrafficLabel.LOW_OCCUPANCY: (80, 92, -90, -70, -10, -5, 2, 6),
        TrafficLabel.NORMAL: (68, 82, -100, -82, -12, -7, 5, 10),
        TrafficLabel.SLOW: (52, 68, -115, -95, -15, -10, 9, 14),
        TrafficLabel.TRAFFIC_JAM: (35, 55, -135, -110, -19, -14, 13, 20),
    }
    mr_lo, mr_hi, rsrp_lo, rsrp_hi, rsrq_lo, rsrq_hi, n_lo, n_hi = bands[label]
    return {
        "match_rate": rng.randint(mr_lo, mr_hi),
        "rsrp": rng.randint(rsrp_lo, rsrp_hi),
        "rsrq": rng.randint(rsrq_lo, rsrq_hi),
        "neighbor_count": rng.randint(n_lo, n_hi),
    }


def _annotation_source(rng: random.Random) -> str:
    return rng.choices(
        [
            AnnotationSource.GOOGLE_MAPS.value,
            AnnotationSource.USER.value,
            AnnotationSource.SYNTHETIC.value,
        ],
        weights=[0.70, 0.20, 0.10],
        k=1,
    )[0]


def generate_dataset(
    db: Session,
    *,
    num_anchors: int = 10,
    duration_minutes: int = 60,
    sample_interval_seconds: int = 60,
    clear_existing: bool = True,
    start_time: Optional[datetime] = None,
    seed: int = 42,
    zones: Optional[List[dict]] = None,
) -> dict:
    """Generate labeled 60s clips (one clip every ``sample_interval_seconds``).

    ``sample_interval_seconds`` is the spacing between clip starts (default 60 →
    contiguous 60s windows). Each clip contains ``CLIP_LEN`` 1 Hz samples.
    """
    rng = random.Random(seed)

    if clear_existing:
        db.query(TrafficPrediction).delete()
        db.query(AnchorReading).delete()
        db.query(RecordingClip).delete()
        db.commit()
        logger.info("Cleared existing clips and readings")

    forced_labels: Dict[str, TrafficLabel] = {}
    if zones:
        anchors = []
        for i, zone in enumerate(zones):
            raw = zone.get("label", TrafficLabel.NORMAL)
            label = raw if isinstance(raw, TrafficLabel) else TrafficLabel[str(raw)]
            aid = str(zone.get("id") or f"ZONE-{label.value}-{i + 1}")
            anchors.append((aid, float(zone["latitude"]), float(zone["longitude"])))
            forced_labels[aid] = label
    else:
        anchors = DEFAULT_ANCHORS[:num_anchors]
        while len(anchors) < num_anchors:
            idx = len(anchors) + 1
            base_lat, base_lon = DEFAULT_ANCHORS[0][1], DEFAULT_ANCHORS[0][2]
            anchors.append(
                (
                    f"ANCHOR-X{idx}",
                    base_lat + rng.uniform(-0.01, 0.01),
                    base_lon + rng.uniform(-0.01, 0.01),
                )
            )

    start = start_time or datetime.utcnow().replace(
        hour=6, minute=0, second=0, microsecond=0
    )
    if start.tzinfo is not None:
        start = start.replace(tzinfo=None)

    clip_stride = max(CLIP_LEN, sample_interval_seconds)
    clips_per_anchor = max(1, (duration_minutes * 60) // clip_stride)

    total_samples = 0
    clip_ids: List[str] = []

    for anchor_id, lat, lon in anchors:
        for i in range(clips_per_anchor):
            clip_start = start + timedelta(seconds=clip_stride * i)
            minute_of_day = clip_start.hour * 60 + clip_start.minute
            label = forced_labels.get(anchor_id) or _traffic_profile(minute_of_day, rng)
            source = _annotation_source(rng)
            samples = synthesize_clip_samples(
                label_metrics_fn=_metrics_for_label,
                label=label,
                rng=rng,
                lat=lat,
                lon=lon,
                duration=CLIP_LEN,
            )
            clip = RecordingClip(
                id=str(uuid.uuid4()),
                anchor_id=anchor_id,
                start_time=clip_start,
                end_time=clip_start + timedelta(seconds=CLIP_LEN - 1),
                duration_seconds=CLIP_LEN,
                sample_count=CLIP_LEN,
                latitude=lat,
                longitude=lon,
                traffic_label=label.value,
                annotation_source=source,
            )
            db.add(clip)
            for idx, s in enumerate(samples):
                db.add(
                    AnchorReading(
                        clip_id=clip.id,
                        seq_index=idx,
                        timestamp=clip_start + timedelta(seconds=idx),
                        anchor_id=anchor_id,
                        latitude=s["latitude"],
                        longitude=s["longitude"],
                        match_rate=int(s["match_rate"]),
                        rsrp=int(s["rsrp"]),
                        rsrq=int(s["rsrq"]),
                        neighbor_count=int(s["neighbor_count"]),
                        traffic_label=label.value,
                        annotation_source=source,
                    )
                )
            total_samples += CLIP_LEN
            clip_ids.append(clip.id)

    db.commit()
    end_time = start + timedelta(seconds=clip_stride * (clips_per_anchor - 1) + CLIP_LEN - 1)
    logger.info(
        "Generated %s clips (%s samples) across %s anchors",
        len(clip_ids),
        total_samples,
        len(anchors),
    )
    return {
        "readings_created": total_samples,
        "clips_created": len(clip_ids),
        "anchors": [a[0] for a in anchors],
        "start_time": start,
        "end_time": end_time,
        "clip_duration_seconds": CLIP_LEN,
    }


def get_dataset_stats(db: Session) -> dict:
    total = db.query(func.count(AnchorReading.id)).scalar() or 0
    clip_count = db.query(func.count(RecordingClip.id)).scalar() or 0
    anchor_count = db.query(func.count(func.distinct(RecordingClip.anchor_id))).scalar() or 0
    label_rows = (
        db.query(RecordingClip.traffic_label, func.count(RecordingClip.id))
        .group_by(RecordingClip.traffic_label)
        .all()
    )
    label_distribution = {str(label): count for label, count in label_rows}
    source_rows = (
        db.query(RecordingClip.annotation_source, func.count(RecordingClip.id))
        .group_by(RecordingClip.annotation_source)
        .all()
    )
    annotation_sources = {str(src): count for src, count in source_rows}
    min_ts, max_ts = db.query(
        func.min(RecordingClip.start_time), func.max(RecordingClip.end_time)
    ).one()
    return {
        "total_readings": total,
        "clip_count": clip_count,
        "clip_duration_seconds": CLIP_LEN,
        "anchor_count": anchor_count,
        "label_distribution": label_distribution,
        "annotation_sources": annotation_sources,
        "time_range": {"start": min_ts, "end": max_ts} if clip_count else None,
    }


def explain_prediction(
    *,
    predicted_state: str,
    confidence: float,
    match_rate: int,
    rsrp: int,
    rsrq: int,
    neighbor_count: int,
    location_name: str = "",
    modality: str = "full",
    wander: float | None = None,
    jitter: float | None = None,
) -> str:
    place = f" at {location_name}" if location_name else ""
    dyn = ""
    if wander is not None and jitter is not None:
        dyn = f" Match-rate wander={wander:.1f}, jitter={jitter:.2f} over the 60s clip."
    mapping = {
        TrafficLabel.EMPTY.value: "near-empty corridor — high match rate, low jitter",
        TrafficLabel.LOW_OCCUPANCY.value: "light traffic — elevated match rate",
        TrafficLabel.NORMAL.value: "typical flow — mid match rate / moderate wander",
        TrafficLabel.SLOW.value: "congested flow — depressed match rate, higher jitter",
        TrafficLabel.TRAFFIC_JAM.value: "jam — 35–55% match band with strong multipath jitter",
    }
    blurb = mapping.get(predicted_state, "occupancy class")
    return (
        f"Predicted {predicted_state.replace('_', ' ')} "
        f"({confidence * 100:.0f}% confidence){place} from a 60s clip. "
        f"{blurb.capitalize()} (modality={modality}, "
        f"mean match_rate≈{match_rate}%, RSRP≈{rsrp}, RSRQ≈{rsrq}, neighbors≈{neighbor_count})."
        f"{dyn}"
    )


def seed_demo_dataset(
    db: Session,
    *,
    force: bool = False,
    zones: Optional[List[dict]] = None,
) -> dict:
    """Generate labeled 60s clips only — training and prediction are separate steps."""
    from app.db.session import init_db

    init_db()

    existing = db.query(func.count(RecordingClip.id)).scalar() or 0
    existing_anchors = db.query(func.count(func.distinct(RecordingClip.anchor_id))).scalar() or 0
    if existing > 0 and not force and existing_anchors >= len(TUNIS_LOCATIONS) and not zones:
        return {
            "seeded": False,
            "reason": "data already present",
            "clips": existing,
        }

    db.query(TrafficPrediction).delete()
    db.query(AnchorReading).delete()
    db.query(RecordingClip).delete()
    db.commit()

    start = datetime.utcnow() - timedelta(days=7)
    start = start.replace(minute=0, second=0, microsecond=0)

    # One 60s clip every 30 minutes → manageable volume, still sequence-based
    result = generate_dataset(
        db,
        num_anchors=len(TUNIS_LOCATIONS),
        duration_minutes=7 * 24 * 60,
        sample_interval_seconds=30 * 60,
        clear_existing=False,
        start_time=start,
        seed=20260829,
        zones=zones,
    )
    logger.info("Generated %s labeled clips (no train / no predict)", result.get("clips_created"))
    return {
        "seeded": True,
        "readings_created": result["readings_created"],
        "clips_created": result.get("clips_created"),
        "anchors": result["anchors"],
        "clip_duration_seconds": CLIP_LEN,
        "start_time": result["start_time"],
        "end_time": result["end_time"],
    }


def predict_traffic(
    match_rate: int,
    rsrp: int,
    rsrq: int,
    neighbor_count: int,
    latitude: float = 0.0,
    longitude: float = 0.0,
    modality: str = "full",
) -> Tuple[str, float]:
    from app.services.ml_model import predict_occupancy

    state, confidence, _ = predict_occupancy(
        match_rate=match_rate,
        rsrp=rsrp,
        rsrq=rsrq,
        neighbor_count=neighbor_count,
        latitude=latitude,
        longitude=longitude,
        modality=modality,
    )
    return state, confidence


def create_prediction(
    db: Session,
    *,
    location_id: str,
    match_rate: int,
    rsrp: int,
    rsrq: int,
    neighbor_count: int,
) -> TrafficPrediction:
    state, confidence = predict_traffic(match_rate, rsrp, rsrq, neighbor_count)
    prediction = TrafficPrediction(
        timestamp=datetime.utcnow(),
        location_id=location_id,
        predicted_state=state,
        confidence=confidence,
        model_version=MODEL_VERSION,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction


def run_batch_predictions(db: Session, limit: int = 100) -> List[TrafficPrediction]:
    from app.services.ml_model import predict_clip

    clips = (
        db.query(RecordingClip)
        .options(joinedload(RecordingClip.samples))
        .order_by(RecordingClip.start_time.desc())
        .limit(limit)
        .all()
    )
    predictions: List[TrafficPrediction] = []
    for clip in clips:
        samples = samples_from_readings(clip.samples)
        state, confidence = predict_clip(samples, modality="full")[:2]
        pred = TrafficPrediction(
            timestamp=clip.end_time,
            location_id=clip.anchor_id,
            predicted_state=state,
            confidence=confidence,
            model_version=MODEL_VERSION,
        )
        db.add(pred)
        predictions.append(pred)
    db.commit()
    for pred in predictions:
        db.refresh(pred)
    return predictions
