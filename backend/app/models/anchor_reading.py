"""Recording models: 60-second clips + per-second samples for wander/jitter learning."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class TrafficLabel(str, enum.Enum):
    EMPTY = "EMPTY"
    LOW_OCCUPANCY = "LOW_OCCUPANCY"
    NORMAL = "NORMAL"
    SLOW = "SLOW"
    TRAFFIC_JAM = "TRAFFIC_JAM"


class AnnotationSource(str, enum.Enum):
    GOOGLE_MAPS = "GOOGLE_MAPS"
    USER = "USER"
    SYNTHETIC = "SYNTHETIC"


OCCUPANCY_ORDER = [
    TrafficLabel.EMPTY,
    TrafficLabel.LOW_OCCUPANCY,
    TrafficLabel.NORMAL,
    TrafficLabel.SLOW,
    TrafficLabel.TRAFFIC_JAM,
]

CLIP_DURATION_SECONDS = 60


class RecordingClip(Base):
    """One labeled 60s window used for learning and matching."""

    __tablename__ = "recording_clips"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    anchor_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    traffic_label: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    annotation_source: Mapped[str] = mapped_column(
        String(32), nullable=False, default=AnnotationSource.GOOGLE_MAPS.value
    )

    samples: Mapped[list["AnchorReading"]] = relationship(
        "AnchorReading", back_populates="clip", cascade="all, delete-orphan"
    )


class AnchorReading(Base):
    """One second (or tick) inside a 60s clip — captures wander/jitter over time."""

    __tablename__ = "anchor_readings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    clip_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("recording_clips.id"), nullable=False, index=True
    )
    seq_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    anchor_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    match_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    rsrp: Mapped[int] = mapped_column(Integer, nullable=False)
    rsrq: Mapped[int] = mapped_column(Integer, nullable=False)
    neighbor_count: Mapped[int] = mapped_column(Integer, nullable=False)
    traffic_label: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    annotation_source: Mapped[str] = mapped_column(
        String(32), nullable=False, default=AnnotationSource.GOOGLE_MAPS.value
    )

    clip: Mapped["RecordingClip"] = relationship("RecordingClip", back_populates="samples")
