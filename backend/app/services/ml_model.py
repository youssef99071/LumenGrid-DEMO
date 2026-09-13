"""Occupancy ML: train & match on 60-second clips (wander/jitter sequence features)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sqlalchemy.orm import Session, joinedload

from app.models.anchor_reading import OCCUPANCY_ORDER, RecordingClip
from app.models.traffic_prediction import TrafficPrediction
from app.services.towers import radio_overlay
from app.services.clip_features import (
    CLIP_LEN,
    extract_clip_features,
    feature_names,
    samples_from_readings,
)

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "artifacts"
MODEL_PATH = MODEL_DIR / "occupancy_clip_rf.joblib"
META_PATH = MODEL_DIR / "occupancy_clip_rf_meta.json"

_model: Optional[RandomForestClassifier] = None
_meta: Dict[str, Any] = {}


def _ensure_dir() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)


def _clip_vector(samples: Sequence[Mapping[str, float]], modality: str) -> List[float]:
    names = _meta.get("features") or feature_names(modality)
    feats = extract_clip_features(samples, modality=modality)
    # Align to trained feature schema (impute 0 for missing keys)
    return [float(feats.get(n, 0.0)) for n in names]


def train_occupancy_model(db: Session, *, modality: str = "full") -> Dict[str, Any]:
    """Train RandomForest on labeled 60s clips (sequence features)."""
    global _model, _meta

    clips = (
        db.query(RecordingClip)
        .options(joinedload(RecordingClip.samples))
        .all()
    )
    if len(clips) < 30:
        raise ValueError(f"Need at least 30 labeled 60s clips to train (have {len(clips)})")

    names = feature_names(modality)
    X_rows: List[List[float]] = []
    y_rows: List[str] = []
    for clip in clips:
        samples = samples_from_readings(clip.samples)
        if len(samples) < 10:
            continue
        feats = extract_clip_features(samples, modality=modality)
        X_rows.append([float(feats[n]) for n in names])
        y_rows.append(clip.traffic_label)

    if len(X_rows) < 30:
        raise ValueError(f"Not enough valid clips after filtering (have {len(X_rows)})")

    X = np.array(X_rows, dtype=float)
    y = np.array(y_rows)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    clf = RandomForestClassifier(
        n_estimators=160,
        max_depth=14,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced_subsample",
    )
    clf.fit(X_train, y_train)
    y_pred = clf.predict(X_test)
    acc = float(accuracy_score(y_test, y_pred))
    report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)

    _ensure_dir()
    joblib.dump(
        {
            "model": clf,
            "modality": modality,
            "features": names,
            "clip_len": CLIP_LEN,
            "unit": "60s_clip",
        },
        MODEL_PATH,
    )
    _meta = {
        "model_version": "clip-rf-v1",
        "unit": "60s_clip",
        "clip_len": CLIP_LEN,
        "modality": modality,
        "features": names,
        "train_size": int(len(X_train)),
        "test_size": int(len(X_test)),
        "accuracy": round(acc * 100, 2),
        "classes": [str(c) for c in clf.classes_],
        "n_clips": len(X_rows),
        "report": {
            k: v
            for k, v in report.items()
            if k in {c.value for c in OCCUPANCY_ORDER}
            or k in ("accuracy", "macro avg", "weighted avg")
        },
    }
    META_PATH.write_text(json.dumps(_meta, indent=2), encoding="utf-8")
    _model = clf
    logger.info(
        "Trained clip model accuracy=%.2f%% on %s clips (%ss each)",
        acc * 100,
        len(X_rows),
        CLIP_LEN,
    )
    return {"trained": True, **_meta}


def load_model() -> RandomForestClassifier:
    global _model, _meta
    if _model is not None:
        return _model
    if not MODEL_PATH.exists():
        raise FileNotFoundError("No trained clip model — run seed / train first")
    payload = joblib.load(MODEL_PATH)
    _model = payload["model"]
    if META_PATH.exists():
        _meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    else:
        _meta = {
            "model_version": "clip-rf-v1",
            "features": payload.get("features", feature_names("full")),
            "modality": payload.get("modality", "full"),
        }
    return _model


def model_status() -> Dict[str, Any]:
    loaded = _model is not None or MODEL_PATH.exists()
    meta = dict(_meta)
    if not meta and META_PATH.exists():
        meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    return {"ready": loaded, "unit": "60s_clip", **meta}


def predict_clip(
    samples: Sequence[Mapping[str, float]],
    *,
    modality: str = "full",
) -> Tuple[str, float, Dict[str, float]]:
    """Match occupancy class from a 60s sample sequence."""
    if not samples:
        raise ValueError("Clip has no samples")
    try:
        clf = load_model()
    except FileNotFoundError:
        return _rule_fallback_clip(samples)

    vec = np.array([_clip_vector(samples, modality)], dtype=float)
    proba = clf.predict_proba(vec)[0]
    classes = list(clf.classes_)
    idx = int(np.argmax(proba))
    probs = {str(c): round(float(p), 4) for c, p in zip(classes, proba)}
    for label in OCCUPANCY_ORDER:
        probs.setdefault(label.value, 0.0)
    return str(classes[idx]), round(float(proba[idx]), 4), probs


def predict_occupancy(
    *,
    match_rate: Optional[int] = None,
    rsrp: Optional[int] = None,
    rsrq: Optional[int] = None,
    neighbor_count: Optional[int] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    modality: str = "full",
    samples: Optional[Sequence[Mapping[str, float]]] = None,
) -> Tuple[str, float, Dict[str, float]]:
    """Predict from an explicit 60s clip, or synthesize a flat clip from scalars (compat)."""
    if samples is not None and len(samples) > 0:
        return predict_clip(samples, modality=modality)

    # Compat: expand single snapshot into a low-jitter constant clip
    base = {
        "match_rate": float(match_rate if match_rate is not None else 70),
        "rsrp": float(rsrp if rsrp is not None else -90),
        "rsrq": float(rsrq if rsrq is not None else -10),
        "neighbor_count": float(neighbor_count if neighbor_count is not None else 8),
        "latitude": float(latitude if latitude is not None else 36.83),
        "longitude": float(longitude if longitude is not None else 10.22),
    }
    synthetic = [dict(base) for _ in range(CLIP_LEN)]
    return predict_clip(synthetic, modality=modality)


def _rule_fallback_clip(
    samples: Sequence[Mapping[str, float]],
) -> Tuple[str, float, Dict[str, float]]:
    mrs = [float(s.get("match_rate", 70)) for s in samples]
    mean_mr = float(np.mean(mrs))
    jitter = float(np.std(np.diff(mrs))) if len(mrs) > 1 else 0.0
    # High jitter + low mean → jam; high mean + low jitter → empty
    score = (100 - mean_mr) + jitter * 3
    if mean_mr >= 90 and jitter < 2:
        state = "EMPTY"
    elif mean_mr >= 80:
        state = "LOW_OCCUPANCY"
    elif score < 35:
        state = "NORMAL"
    elif score < 55:
        state = "SLOW"
    else:
        state = "TRAFFIC_JAM"
    probs = {c.value: 0.05 for c in OCCUPANCY_ORDER}
    probs[state] = 0.8
    return state, 0.8, probs


def predict_stored_clip(
    db: Session,
    *,
    clip_id: Optional[str] = None,
    location_id: Optional[str] = None,
    modality: str = "full",
) -> Dict[str, Any]:
    """Match occupancy on an already-generated clip. Does not synthesize data."""
    from app.services.data_generator import MODEL_VERSION, explain_prediction
    from app.services.locations import get_location

    query = db.query(RecordingClip).options(joinedload(RecordingClip.samples))
    if clip_id:
        clip = query.filter(RecordingClip.id == clip_id).first()
    elif location_id:
        clip = (
            query.filter(RecordingClip.anchor_id == location_id)
            .order_by(RecordingClip.start_time.desc())
            .first()
        )
    else:
        clip = query.order_by(RecordingClip.start_time.desc()).first()
    if clip is None or not clip.samples:
        raise ValueError("No stored clip to predict — generate data first")

    loc = get_location(clip.anchor_id)
    samples = samples_from_readings(clip.samples)
    state, confidence, probs = predict_clip(samples, modality=modality)
    feats = extract_clip_features(samples, modality="full")
    pred = TrafficPrediction(
        timestamp=clip.end_time,
        location_id=clip.anchor_id,
        predicted_state=state,
        confidence=confidence,
        model_version=_meta.get("model_version", MODEL_VERSION),
    )
    db.add(pred)
    db.commit()
    db.refresh(pred)
    match_rate = int(round(feats.get("match_rate_mean", 0)))
    rsrp = int(round(feats.get("rsrp_mean", 0)))
    rsrq = int(round(feats.get("rsrq_mean", 0)))
    neighbor_count = int(round(feats.get("neighbor_count_mean", 0)))
    explanation = explain_prediction(
        predicted_state=state,
        confidence=confidence,
        match_rate=match_rate,
        rsrp=rsrp,
        rsrq=rsrq,
        neighbor_count=neighbor_count,
        location_name=(loc or {}).get("name", clip.anchor_id),
        modality=modality,
        wander=feats.get("match_rate_wander"),
        jitter=feats.get("match_rate_jitter"),
    )
    return {
        "clip_id": clip.id,
        "location_id": clip.anchor_id,
        "location_name": (loc or {}).get("name", clip.anchor_id),
        "prediction": state,
        "confidence": confidence,
        "probabilities": probs,
        "match_rate": match_rate,
        "rsrp": rsrp,
        "rsrq": rsrq,
        "neighbor_count": neighbor_count,
        "wander": round(feats.get("match_rate_wander", 0), 2),
        "jitter": round(feats.get("match_rate_jitter", 0), 2),
        "actual_traffic": clip.traffic_label,
        "explanation": explanation,
        "timestamp": pred.timestamp.isoformat(),
        "correct": state == clip.traffic_label,
        "sample_count": len(samples),
        "modality": modality,
        "unit": "60s_clip",
    }


def predict_all_anchors(db: Session, *, modality: str = "full") -> List[Dict[str, Any]]:
    """Latest 60s clip per anchor → occupancy prediction for the map."""
    from app.services.locations import LOCATION_BY_ID

    results = []
    for loc_id, loc in LOCATION_BY_ID.items():
        clip = (
            db.query(RecordingClip)
            .options(joinedload(RecordingClip.samples))
            .filter(RecordingClip.anchor_id == loc_id)
            .order_by(RecordingClip.start_time.desc())
            .first()
        )
        if clip is None or not clip.samples:
            state, confidence, probs = predict_occupancy(
                match_rate=85,
                rsrp=-70,
                rsrq=-6,
                neighbor_count=3,
                latitude=loc["latitude"],
                longitude=loc["longitude"],
                modality=modality,
            )
            results.append(
                {
                    "location_id": loc_id,
                    "name": loc["name"],
                    "district": loc["district"],
                    "latitude": loc["latitude"],
                    "longitude": loc["longitude"],
                    "prediction": state,
                    "confidence": confidence,
                    "probabilities": probs,
                    "match_rate": None,
                    "match_rate_mean": None,
                    "wander": None,
                    "jitter": None,
                    "modality": modality,
                    "clip_id": None,
                    "updated_at": None,
                    **radio_overlay(loc["latitude"], loc["longitude"], rsrp=-70, match_rate=85),
                }
            )
            continue

        samples = samples_from_readings(clip.samples)
        state, confidence, probs = predict_clip(samples, modality=modality)
        feats = extract_clip_features(samples, modality="full")
        pred = TrafficPrediction(
            timestamp=clip.end_time,
            location_id=loc_id,
            predicted_state=state,
            confidence=confidence,
            model_version=_meta.get("model_version", "clip-rf-v1"),
        )
        db.add(pred)
        results.append(
            {
                "location_id": loc_id,
                "name": loc["name"],
                "district": loc["district"],
                "latitude": loc["latitude"],
                "longitude": loc["longitude"],
                "prediction": state,
                "confidence": confidence,
                "probabilities": probs,
                "match_rate": int(round(feats.get("match_rate_mean", 0))),
                "match_rate_mean": round(feats.get("match_rate_mean", 0), 1),
                "wander": round(feats.get("match_rate_wander", 0), 2),
                "jitter": round(feats.get("match_rate_jitter", 0), 2),
                "modality": modality,
                "clip_id": clip.id,
                "updated_at": clip.end_time.isoformat(),
                **radio_overlay(
                    loc["latitude"],
                    loc["longitude"],
                    match_rate=feats.get("match_rate_mean"),
                    rsrp=feats.get("rsrp_mean"),
                ),
            }
        )
    db.commit()
    return results
