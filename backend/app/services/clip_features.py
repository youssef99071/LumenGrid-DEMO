"""Sequence feature extraction for 60s clips (wander + jitter)."""

from __future__ import annotations

from typing import Dict, Iterable, List, Mapping, Optional, Sequence

import numpy as np

CLIP_LEN = 60

CHANNEL_KEYS = ("match_rate", "rsrp", "rsrq", "neighbor_count")
GPS_KEYS = ("latitude", "longitude")

# Channels used per modality (GPS / cell / CAMARA match_rate)
MODALITY_CHANNELS: Dict[str, List[str]] = {
    "full": ["match_rate", "rsrp", "rsrq", "neighbor_count", "latitude", "longitude"],
    "gps_cell_camara": ["match_rate", "rsrp", "rsrq", "neighbor_count", "latitude", "longitude"],
    "gps_camara": ["match_rate", "latitude", "longitude"],
    "cell_camara": ["match_rate", "rsrp", "rsrq", "neighbor_count"],
}


def _as_array(values: Sequence[float], length: int = CLIP_LEN) -> np.ndarray:
    arr = np.asarray(list(values), dtype=float)
    if len(arr) == 0:
        return np.zeros(length, dtype=float)
    if len(arr) >= length:
        return arr[:length]
    # Pad short clips by repeating last value (still-forming recording)
    pad = np.full(length - len(arr), arr[-1], dtype=float)
    return np.concatenate([arr, pad])


def _channel_stats(series: np.ndarray, prefix: str) -> Dict[str, float]:
    """Mean/std/min/max + wander (range) + jitter (std of 1st difference)."""
    diff = np.diff(series) if len(series) > 1 else np.array([0.0])
    # Linear slope over the window (wander trend)
    x = np.arange(len(series), dtype=float)
    slope = float(np.polyfit(x, series, 1)[0]) if len(series) > 1 else 0.0
    return {
        f"{prefix}_mean": float(np.mean(series)),
        f"{prefix}_std": float(np.std(series)),
        f"{prefix}_min": float(np.min(series)),
        f"{prefix}_max": float(np.max(series)),
        f"{prefix}_wander": float(np.max(series) - np.min(series)),
        f"{prefix}_jitter": float(np.std(diff)),
        f"{prefix}_slope": slope,
    }


def extract_clip_features(
    samples: Sequence[Mapping[str, float]],
    *,
    modality: str = "full",
) -> Dict[str, float]:
    """Build a fixed feature vector from a 60s sample sequence."""
    modality = modality if modality in MODALITY_CHANNELS else "full"
    channels = MODALITY_CHANNELS[modality]
    feats: Dict[str, float] = {}

    for key in CHANNEL_KEYS:
        if key not in channels:
            continue
        series = _as_array([float(s.get(key, 0)) for s in samples])
        feats.update(_channel_stats(series, key))

    if "latitude" in channels and "longitude" in channels:
        lats = _as_array([float(s.get("latitude", 0)) for s in samples])
        lons = _as_array([float(s.get("longitude", 0)) for s in samples])
        feats["lat_mean"] = float(np.mean(lats))
        feats["lon_mean"] = float(np.mean(lons))
        # Spatial wander (meters-ish proxy using degree std)
        feats["gps_wander"] = float(np.sqrt(np.std(lats) ** 2 + np.std(lons) ** 2) * 111_000)
        feats["gps_jitter"] = float(
            np.std(
                np.sqrt(np.diff(lats, prepend=lats[0]) ** 2 + np.diff(lons, prepend=lons[0]) ** 2)
            )
            * 111_000
        )

    feats["sample_count"] = float(min(len(samples), CLIP_LEN))
    return feats


def feature_names(modality: str = "full") -> List[str]:
    """Stable ordered feature names for a modality (empty clip → schema only)."""
    dummy = [{k: 0.0 for k in (*CHANNEL_KEYS, *GPS_KEYS)} for _ in range(CLIP_LEN)]
    return list(extract_clip_features(dummy, modality=modality).keys())


def samples_from_readings(readings: Iterable) -> List[Dict[str, float]]:
    """ORM AnchorReading rows → dict samples ordered by seq_index."""
    rows = sorted(list(readings), key=lambda r: getattr(r, "seq_index", 0))
    return [
        {
            "match_rate": float(r.match_rate),
            "rsrp": float(r.rsrp),
            "rsrq": float(r.rsrq),
            "neighbor_count": float(r.neighbor_count),
            "latitude": float(r.latitude),
            "longitude": float(r.longitude),
        }
        for r in rows
    ]


def synthesize_clip_samples(
    *,
    label_metrics_fn,
    label,
    rng,
    lat: float,
    lon: float,
    duration: int = CLIP_LEN,
) -> List[Dict[str, float]]:
    """Generate a 60s wander/jitter sequence around a class band."""
    samples: List[Dict[str, float]] = []
    base = label_metrics_fn(label, rng)
    # Temporal structure: slow wander + high-freq jitter (stronger in jam)
    jam_factor = {
        "EMPTY": 0.3,
        "LOW_OCCUPANCY": 0.5,
        "NORMAL": 0.8,
        "SLOW": 1.2,
        "TRAFFIC_JAM": 1.8,
    }.get(getattr(label, "value", str(label)), 1.0)

    phase = rng.random() * 2 * np.pi
    for i in range(duration):
        t = i / max(1, duration - 1)
        wander = jam_factor * 4 * np.sin(2 * np.pi * t + phase)
        jitter_mr = rng.gauss(0, 1.2 * jam_factor)
        jitter_rsrp = rng.gauss(0, 1.5 * jam_factor)
        samples.append(
            {
                "match_rate": int(
                    np.clip(base["match_rate"] + wander + jitter_mr, 0, 100)
                ),
                "rsrp": int(np.clip(base["rsrp"] + wander * 0.8 + jitter_rsrp, -140, -44)),
                "rsrq": int(
                    np.clip(base["rsrq"] + rng.gauss(0, 0.4 * jam_factor), -19, -3)
                ),
                "neighbor_count": int(
                    np.clip(base["neighbor_count"] + rng.randint(-1, 2), 0, 20)
                ),
                "latitude": lat + rng.gauss(0, 0.00003 * jam_factor),
                "longitude": lon + rng.gauss(0, 0.00003 * jam_factor),
            }
        )
    return samples
