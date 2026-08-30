"""ML training + 60s-clip inference + map occupancy routes."""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.clip_features import CLIP_LEN, extract_clip_features, synthesize_clip_samples
from app.services.data_generator import _metrics_for_label, explain_prediction
from app.models.anchor_reading import TrafficLabel
from app.services.ml_model import (
    model_status,
    predict_all_anchors,
    predict_clip,
    train_occupancy_model,
)
import random

router = APIRouter(prefix="/api/ml", tags=["ml"])


class TrainResponse(BaseModel):
    trained: bool
    model_version: str = ""
    accuracy: float = 0
    train_size: int = 0
    test_size: int = 0
    classes: List[str] = []
    n_clips: int = 0
    unit: str = "60s_clip"
    clip_len: int = CLIP_LEN


class ClipSample(BaseModel):
    match_rate: int = Field(..., ge=0, le=100)
    rsrp: Optional[int] = Field(None, ge=-140, le=-44)
    rsrq: Optional[int] = Field(None, ge=-19, le=-3)
    neighbor_count: Optional[int] = Field(None, ge=0, le=20)
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class SamplePredictRequest(BaseModel):
    """Infer from an explicit 60s sequence, or synthesize one from a What-If class."""

    modality: Literal["full", "gps_camara", "cell_camara", "gps_cell_camara"] = "full"
    samples: Optional[List[ClipSample]] = None
    # Convenience: generate a synthetic 60s clip for a target class
    scenario: Optional[
        Literal["EMPTY", "LOW_OCCUPANCY", "NORMAL", "SLOW", "TRAFFIC_JAM"]
    ] = None
    latitude: float = 36.7992
    longitude: float = 10.1802
    location_name: str = ""


class SamplePredictResponse(BaseModel):
    prediction: str
    confidence: float
    probabilities: Dict[str, float]
    modality: str
    explanation: str
    unit: str = "60s_clip"
    sample_count: int
    match_rate_mean: float
    wander: float
    jitter: float


@router.get("/status")
def get_model_status() -> dict:
    return model_status()


@router.post("/train", response_model=TrainResponse)
def train_model(db: Session = Depends(get_db)) -> TrainResponse:
    try:
        result = train_occupancy_model(db)
        return TrainResponse(**{k: result[k] for k in TrainResponse.model_fields if k in result})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/predict", response_model=SamplePredictResponse)
def sample_predict(body: SamplePredictRequest) -> SamplePredictResponse:
    if body.samples and len(body.samples) > 0:
        samples = [s.model_dump() for s in body.samples]
    elif body.scenario:
        rng = random.Random()
        label = TrafficLabel[body.scenario]
        samples = synthesize_clip_samples(
            label_metrics_fn=_metrics_for_label,
            label=label,
            rng=rng,
            lat=body.latitude,
            lon=body.longitude,
            duration=CLIP_LEN,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide samples[] (60s clip) or scenario to synthesize a 60s clip",
        )

    state, confidence, probs = predict_clip(samples, modality=body.modality)
    feats = extract_clip_features(samples, modality="full")
    explanation = explain_prediction(
        predicted_state=state,
        confidence=confidence,
        match_rate=int(round(feats.get("match_rate_mean", 0))),
        rsrp=int(round(feats.get("rsrp_mean", 0))),
        rsrq=int(round(feats.get("rsrq_mean", 0))),
        neighbor_count=int(round(feats.get("neighbor_count_mean", 0))),
        location_name=body.location_name,
        modality=body.modality,
        wander=feats.get("match_rate_wander"),
        jitter=feats.get("match_rate_jitter"),
    )
    return SamplePredictResponse(
        prediction=state,
        confidence=confidence,
        probabilities=probs,
        modality=body.modality,
        explanation=explanation,
        sample_count=len(samples),
        match_rate_mean=round(feats.get("match_rate_mean", 0), 2),
        wander=round(feats.get("match_rate_wander", 0), 2),
        jitter=round(feats.get("match_rate_jitter", 0), 2),
    )


@router.post("/predict-anchors")
def predict_anchors(
    modality: Literal["full", "gps_camara", "cell_camara", "gps_cell_camara"] = "full",
    db: Session = Depends(get_db),
) -> dict:
    """Match latest 60s clip per anchor for the map."""
    markers = predict_all_anchors(db, modality=modality)
    return {"modality": modality, "unit": "60s_clip", "markers": markers, "count": len(markers)}
