"""Pydantic schemas for API request/response bodies."""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ── Nokia NaC / CAMARA ──────────────────────────────────────────────


class LocationVerifyRequest(BaseModel):
    device_id: str = Field(..., description="Device / MSISDN identifier")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius: float = Field(..., gt=0, description="Verification radius in meters")


class LocationVerifyResponse(BaseModel):
    device_id: str
    verification_result: Literal["TRUE", "FALSE", "PARTIAL", "UNKNOWN"]
    match_rate: int = Field(..., ge=0, le=100)
    sandbox: bool


class DeviceStatusResponse(BaseModel):
    device_id: str
    status: Literal["ONLINE", "OFFLINE", "ROAMING"]
    last_seen: Optional[datetime] = None
    sandbox: bool


class QoSRequest(BaseModel):
    device_id: str
    bandwidth: int = Field(..., gt=0, description="Requested bandwidth in kbps")
    latency: int = Field(..., gt=0, description="Target latency in ms")


class QoSResponse(BaseModel):
    device_id: str
    qos_session_id: str
    status: Literal["AVAILABLE", "UNAVAILABLE", "PENDING"]
    confirmed_bandwidth: int
    confirmed_latency: int
    sandbox: bool


class NaCStatusResponse(BaseModel):
    connected: bool
    sandbox_mode: bool
    api_url: str
    message: str


class CapabilityItem(BaseModel):
    name: str
    description: str
    endpoint: str
    status: Literal["available", "simulated"]


class CapabilitiesResponse(BaseModel):
    capabilities: List[CapabilityItem]
    sandbox_mode: bool


# ── Anchor readings / dataset ───────────────────────────────────────


class AnchorReadingOut(BaseModel):
    id: str
    timestamp: datetime
    anchor_id: str
    latitude: float
    longitude: float
    match_rate: int
    rsrp: int
    rsrq: int
    neighbor_count: int
    traffic_label: str
    annotation_source: str = "GOOGLE_MAPS"

    model_config = {"from_attributes": True}


class GenerateDatasetRequest(BaseModel):
    num_anchors: int = Field(5, ge=1, le=50)
    duration_minutes: int = Field(60, ge=1, le=1440)
    sample_interval_seconds: int = Field(60, ge=10, le=300)
    clear_existing: bool = True


class GenerateDatasetResponse(BaseModel):
    readings_created: int
    clips_created: int = 0
    anchors: List[str]
    start_time: datetime
    end_time: datetime
    clip_duration_seconds: int = 60


class DatasetStatsResponse(BaseModel):
    total_readings: int
    clip_count: int = 0
    clip_duration_seconds: int = 60
    anchor_count: int
    label_distribution: dict[str, int]
    annotation_sources: dict[str, int] = {}
    time_range: Optional[dict[str, Optional[datetime]]]


# ── Traffic predictions ─────────────────────────────────────────────


class TrafficPredictionOut(BaseModel):
    id: str
    timestamp: datetime
    location_id: str
    predicted_state: str
    confidence: float
    model_version: str

    model_config = {"from_attributes": True}


class PredictRequest(BaseModel):
    location_id: str
    match_rate: int = Field(..., ge=0, le=100)
    rsrp: int = Field(..., ge=-140, le=-44)
    rsrq: int = Field(..., ge=-19, le=-3)
    neighbor_count: int = Field(..., ge=0, le=20)


class PredictResponse(BaseModel):
    prediction: TrafficPredictionOut
    features_used: dict
