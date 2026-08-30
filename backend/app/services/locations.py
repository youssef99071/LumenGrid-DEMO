"""Demo corridor: three Tunis locations for the LumenGrid PoC."""

from __future__ import annotations

from typing import Dict, List, TypedDict


class LocationDef(TypedDict):
    id: str
    name: str
    latitude: float
    longitude: float
    district: str


TUNIS_LOCATIONS: List[LocationDef] = [
    {
        "id": "TUNIS-AVE-BOURGUIBA",
        "name": "Avenue Habib Bourguiba",
        "latitude": 36.7992,
        "longitude": 10.1802,
        "district": "City center",
    },
    {
        "id": "TUNIS-CARTHAGE-HWY",
        "name": "Tunis–Carthage Highway",
        "latitude": 36.8478,
        "longitude": 10.2175,
        "district": "North entrance",
    },
    {
        "id": "TUNIS-ROUTE-MARSA",
        "name": "Route de La Marsa",
        "latitude": 36.8620,
        "longitude": 10.2915,
        "district": "Coastal road",
    },
]

LOCATION_BY_ID: Dict[str, LocationDef] = {loc["id"]: loc for loc in TUNIS_LOCATIONS}


def list_locations() -> List[LocationDef]:
    return list(TUNIS_LOCATIONS)


def get_location(location_id: str) -> LocationDef | None:
    return LOCATION_BY_ID.get(location_id)
