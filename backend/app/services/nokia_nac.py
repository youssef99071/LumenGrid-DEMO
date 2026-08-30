"""Nokia Network as Code (NaC) service with CAMARA API sandbox simulation."""

from __future__ import annotations

import hashlib
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

VerificationResult = Literal["TRUE", "FALSE", "PARTIAL", "UNKNOWN"]
DeviceStatus = Literal["ONLINE", "OFFLINE", "ROAMING"]
QoSStatus = Literal["AVAILABLE", "UNAVAILABLE", "PENDING"]


class NokiaNaCService:
    """Handles all Nokia NaC / CAMARA API interactions.

    When ``sandbox_mode`` is True (default), methods return deterministic
    simulated responses without contacting the real NaC platform.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.sandbox = self.settings.sandbox_mode
        self.base_url = self.settings.nac_api_url.rstrip("/")
        self._client: Optional[httpx.Client] = None

    # ── HTTP helpers ────────────────────────────────────────────────

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.base_url,
                timeout=30.0,
                headers={
                    "X-RapidAPI-Key": self.settings.nac_rapidapi_key,
                    "X-RapidAPI-Host": self.base_url.replace("https://", "").replace(
                        "http://", ""
                    ),
                    "Content-Type": "application/json",
                },
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        client = self._get_client()
        logger.info("NaC API request: %s %s json=%s params=%s", method, path, json, params)
        response = client.request(method, path, json=json, params=params)
        logger.info(
            "NaC API response: status=%s body=%s",
            response.status_code,
            response.text[:500],
        )
        response.raise_for_status()
        return response.json()

    # ── Connection status ───────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        if self.sandbox:
            logger.info("NaC status check (sandbox): connected=True")
            return {
                "connected": True,
                "sandbox_mode": True,
                "api_url": self.base_url,
                "message": "Sandbox mode active — using simulated CAMARA responses",
            }

        try:
            # Lightweight connectivity probe; real NaC may use a health endpoint.
            self._request("GET", "/location-verification/v0.3/verify")
            connected = True
            message = "Connected to Nokia NaC platform"
        except Exception as exc:  # noqa: BLE001
            connected = False
            message = f"NaC connection failed: {exc}"
            logger.exception("NaC status check failed")

        return {
            "connected": connected,
            "sandbox_mode": False,
            "api_url": self.base_url,
            "message": message,
        }

    def list_capabilities(self) -> Dict[str, Any]:
        status = "simulated" if self.sandbox else "available"
        return {
            "sandbox_mode": self.sandbox,
            "capabilities": [
                {
                    "name": "location-verification",
                    "description": "Verify whether a device is within a geographic area",
                    "endpoint": "POST /api/nac/verify-location",
                    "status": status,
                },
                {
                    "name": "device-status",
                    "description": "Retrieve device connectivity / roaming status",
                    "endpoint": "GET /api/nac/device-status/{device_id}",
                    "status": status,
                },
                {
                    "name": "quality-on-demand",
                    "description": "Request QoS session for a device",
                    "endpoint": "POST /api/nac/qos",
                    "status": status,
                },
            ],
        }

    # ── CAMARA: Location Verification ───────────────────────────────

    def verify_location(
        self,
        device_id: str,
        latitude: float,
        longitude: float,
        radius: float,
    ) -> Dict[str, Any]:
        """Verify device location via CAMARA Location Verification API.

        Returns ``verification_result`` and ``match_rate`` (0–100).
        """
        if self.sandbox:
            return self._sandbox_verify_location(device_id, latitude, longitude, radius)

        payload = {
            "device": {"phoneNumber": device_id},
            "area": {
                "areaType": "CIRCLE",
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": radius,
            },
        }
        data = self._request("POST", "/location-verification/v0.3/verify", json=payload)
        return {
            "device_id": device_id,
            "verification_result": data.get("verificationResult", "UNKNOWN"),
            "match_rate": int(data.get("matchRate", 0)),
            "sandbox": False,
        }

    def _sandbox_verify_location(
        self,
        device_id: str,
        latitude: float,
        longitude: float,
        radius: float,
    ) -> Dict[str, Any]:
        """Deterministic sandbox simulation based on device_id + coords hash."""
        seed = int(
            hashlib.sha256(
                f"{device_id}:{latitude:.5f}:{longitude:.5f}:{radius}".encode()
            ).hexdigest()[:8],
            16,
        )
        rng = random.Random(seed)
        match_rate = rng.randint(40, 100)

        if match_rate >= 80:
            result: VerificationResult = "TRUE"
        elif match_rate >= 55:
            result = "PARTIAL"
        elif match_rate >= 30:
            result = "FALSE"
        else:
            result = "UNKNOWN"

        logger.info(
            "Sandbox verify_location device=%s match_rate=%s result=%s",
            device_id,
            match_rate,
            result,
        )
        return {
            "device_id": device_id,
            "verification_result": result,
            "match_rate": match_rate,
            "sandbox": True,
        }

    # ── CAMARA: Device Status ───────────────────────────────────────

    def get_device_status(self, device_id: str) -> Dict[str, Any]:
        if self.sandbox:
            return self._sandbox_device_status(device_id)

        data = self._request(
            "GET",
            "/device-status/v0.5/connectivity",
            params={"device[phoneNumber]": device_id},
        )
        return {
            "device_id": device_id,
            "status": data.get("connectivityStatus", "OFFLINE").upper(),
            "last_seen": data.get("lastSeen"),
            "sandbox": False,
        }

    def _sandbox_device_status(self, device_id: str) -> Dict[str, Any]:
        seed = int(hashlib.sha256(device_id.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        statuses: list[DeviceStatus] = ["ONLINE", "ONLINE", "ONLINE", "ROAMING", "OFFLINE"]
        status = rng.choice(statuses)
        logger.info("Sandbox get_device_status device=%s status=%s", device_id, status)
        return {
            "device_id": device_id,
            "status": status,
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "sandbox": True,
        }

    # ── CAMARA: Quality on Demand ───────────────────────────────────

    def request_qos(
        self,
        device_id: str,
        bandwidth: int,
        latency: int,
    ) -> Dict[str, Any]:
        if self.sandbox:
            return self._sandbox_request_qos(device_id, bandwidth, latency)

        payload = {
            "device": {"phoneNumber": device_id},
            "qosProfile": "QOS_L",
            "duration": 3600,
            "qosRequirements": {
                "minDownstreamRate": {"value": bandwidth, "unit": "kbps"},
                "maxDelay": {"value": latency, "unit": "ms"},
            },
        }
        data = self._request("POST", "/qod/v0.10/sessions", json=payload)
        return {
            "device_id": device_id,
            "qos_session_id": data.get("sessionId", str(uuid.uuid4())),
            "status": data.get("qosStatus", "PENDING").upper(),
            "confirmed_bandwidth": bandwidth,
            "confirmed_latency": latency,
            "sandbox": False,
        }

    def _sandbox_request_qos(
        self,
        device_id: str,
        bandwidth: int,
        latency: int,
    ) -> Dict[str, Any]:
        seed = int(hashlib.sha256(f"{device_id}:{bandwidth}:{latency}".encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        available = rng.random() > 0.15
        status: QoSStatus = "AVAILABLE" if available else "UNAVAILABLE"
        session_id = f"qos-sandbox-{uuid.uuid4().hex[:12]}"
        logger.info(
            "Sandbox request_qos device=%s bw=%s lat=%s status=%s",
            device_id,
            bandwidth,
            latency,
            status,
        )
        return {
            "device_id": device_id,
            "qos_session_id": session_id,
            "status": status,
            "confirmed_bandwidth": bandwidth if available else 0,
            "confirmed_latency": latency if available else 0,
            "sandbox": True,
        }


def get_nac_service() -> NokiaNaCService:
    return NokiaNaCService()
