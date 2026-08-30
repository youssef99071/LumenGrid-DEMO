"""Nokia NaC / CAMARA API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.models.schemas import (
    CapabilitiesResponse,
    DeviceStatusResponse,
    LocationVerifyRequest,
    LocationVerifyResponse,
    NaCStatusResponse,
    QoSRequest,
    QoSResponse,
)
from app.services.nokia_nac import NokiaNaCService, get_nac_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/nac", tags=["nokia-nac"])


@router.get("/status", response_model=NaCStatusResponse)
def nac_status(nac: NokiaNaCService = Depends(get_nac_service)) -> NaCStatusResponse:
    """Check NaC connection status."""
    return NaCStatusResponse(**nac.get_status())


@router.get("/capabilities", response_model=CapabilitiesResponse)
def nac_capabilities(
    nac: NokiaNaCService = Depends(get_nac_service),
) -> CapabilitiesResponse:
    """List available CAMARA APIs."""
    return CapabilitiesResponse(**nac.list_capabilities())


@router.post("/verify-location", response_model=LocationVerifyResponse)
def verify_location(
    body: LocationVerifyRequest,
    nac: NokiaNaCService = Depends(get_nac_service),
) -> LocationVerifyResponse:
    """Simulate / invoke CAMARA location verification."""
    try:
        result = nac.verify_location(
            body.device_id, body.latitude, body.longitude, body.radius
        )
        return LocationVerifyResponse(**result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("verify_location failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/device-status/{device_id}", response_model=DeviceStatusResponse)
def device_status(
    device_id: str,
    nac: NokiaNaCService = Depends(get_nac_service),
) -> DeviceStatusResponse:
    """Get device online/offline/roaming status."""
    try:
        result = nac.get_device_status(device_id)
        return DeviceStatusResponse(**result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("get_device_status failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/qos", response_model=QoSResponse)
def request_qos(
    body: QoSRequest,
    nac: NokiaNaCService = Depends(get_nac_service),
) -> QoSResponse:
    """Request a Quality-on-Demand session for a device."""
    try:
        result = nac.request_qos(body.device_id, body.bandwidth, body.latency)
        return QoSResponse(**result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("request_qos failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
