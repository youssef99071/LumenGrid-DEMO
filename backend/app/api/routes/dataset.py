"""Learning dataset generation and query endpoints."""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.anchor_reading import AnchorReading
from app.models.schemas import (
    AnchorReadingOut,
    DatasetStatsResponse,
    GenerateDatasetRequest,
    GenerateDatasetResponse,
)
from app.services.data_generator import generate_dataset, get_dataset_stats, seed_demo_dataset

router = APIRouter(prefix="/api/dataset", tags=["dataset"])


@router.post("/generate", response_model=GenerateDatasetResponse)
def generate(
    body: GenerateDatasetRequest,
    db: Session = Depends(get_db),
) -> GenerateDatasetResponse:
    """Generate synthetic 1-minute anchor recordings for the learning database."""
    result = generate_dataset(
        db,
        num_anchors=body.num_anchors,
        duration_minutes=body.duration_minutes,
        sample_interval_seconds=body.sample_interval_seconds,
        clear_existing=body.clear_existing,
    )
    return GenerateDatasetResponse(**result)


@router.post("/seed-demo")
def seed_demo(force: bool = False, db: Session = Depends(get_db)) -> dict:
    """Pre-load 7 days of demo data for the 3 Tunis corridor locations."""
    return seed_demo_dataset(db, force=force)


@router.get("/stats", response_model=DatasetStatsResponse)
def stats(db: Session = Depends(get_db)) -> DatasetStatsResponse:
    return DatasetStatsResponse(**get_dataset_stats(db))


@router.get("/readings", response_model=List[AnchorReadingOut])
def list_readings(
    anchor_id: Optional[str] = None,
    traffic_label: Optional[str] = None,
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[AnchorReading]:
    q = db.query(AnchorReading).order_by(AnchorReading.timestamp.desc())
    if anchor_id:
        q = q.filter(AnchorReading.anchor_id == anchor_id)
    if traffic_label:
        q = q.filter(AnchorReading.traffic_label == traffic_label)
    return q.offset(offset).limit(limit).all()
