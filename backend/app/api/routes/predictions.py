"""Traffic prediction endpoints."""

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.schemas import PredictRequest, PredictResponse, TrafficPredictionOut
from app.models.traffic_prediction import TrafficPrediction
from app.services.data_generator import create_prediction, run_batch_predictions

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


@router.post("/predict", response_model=PredictResponse)
def predict(body: PredictRequest, db: Session = Depends(get_db)) -> PredictResponse:
    """Run rule-based PoC traffic prediction from radio / CAMARA features."""
    prediction = create_prediction(
        db,
        location_id=body.location_id,
        match_rate=body.match_rate,
        rsrp=body.rsrp,
        rsrq=body.rsrq,
        neighbor_count=body.neighbor_count,
    )
    return PredictResponse(
        prediction=TrafficPredictionOut.model_validate(prediction),
        features_used={
            "match_rate": body.match_rate,
            "rsrp": body.rsrp,
            "rsrq": body.rsrq,
            "neighbor_count": body.neighbor_count,
        },
    )


@router.post("/batch", response_model=List[TrafficPredictionOut])
def batch_predict(
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> List[TrafficPrediction]:
    """Predict traffic for the latest dataset readings."""
    return run_batch_predictions(db, limit=limit)


@router.get("", response_model=List[TrafficPredictionOut])
def list_predictions(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> List[TrafficPrediction]:
    return (
        db.query(TrafficPrediction)
        .order_by(TrafficPrediction.timestamp.desc())
        .limit(limit)
        .all()
    )
