"""Demo anchors inside a 250,000 m² footprint around Avenue Habib Bourguiba."""

from __future__ import annotations

from typing import Dict, List, TypedDict


class LocationDef(TypedDict):
    id: str
    name: str
    latitude: float
    longitude: float
    district: str


# ~490 m × 490 m box (≈ 240,000 m²) centered on 36.79920, 10.18020.
TUNIS_LOCATIONS: List[LocationDef] = [
    {
        "id": "TUNIS-AVE-BOURGUIBA",
        "name": "Bourguiba center",
        "latitude": 36.79920,
        "longitude": 10.18020,
        "district": "Avenue Habib Bourguiba",
    },
    {
        "id": "TUNIS-CARTHAGE-HWY",
        "name": "Avenue de Paris",
        "latitude": 36.80140,
        "longitude": 10.18030,
        "district": "Avenue Habib Bourguiba",
    },
    {
        "id": "TUNIS-ROUTE-MARSA",
        "name": "Place Barcelone",
        "latitude": 36.79700,
        "longitude": 10.18050,
        "district": "Avenue Habib Bourguiba",
    },
    {
        "id": "TUNIS-PLACE-BARCELONE",
        "name": "Place de l'Indépendance",
        "latitude": 36.79910,
        "longitude": 10.17745,
        "district": "Avenue Habib Bourguiba",
    },
    {
        "id": "TUNIS-BAB-SOUIKA",
        "name": "Avenue Mohammed V",
        "latitude": 36.79940,
        "longitude": 10.18295,
        "district": "Avenue Habib Bourguiba",
    },
    {
        "id": "TUNIS-THEATRE",
        "name": "Théâtre Municipal",
        "latitude": 36.80040,
        "longitude": 10.18180,
        "district": "Avenue Habib Bourguiba",
    },
    {
        "id": "TUNIS-CATHEDRAL",
        "name": "Cathedral Saint-Vincent",
        "latitude": 36.79800,
        "longitude": 10.17860,
        "district": "Avenue Habib Bourguiba",
    },
    {
        "id": "TUNIS-RUE-ROME",
        "name": "Rue de Rome",
        "latitude": 36.79780,
        "longitude": 10.18220,
        "district": "Avenue Habib Bourguiba",
    },
    {
        "id": "TUNIS-AVE-CARTHAGE",
        "name": "Avenue de Carthage",
        "latitude": 36.80070,
        "longitude": 10.17850,
        "district": "Avenue Habib Bourguiba",
    },
    {
        "id": "TUNIS-RUE-ESPAGNE",
        "name": "Rue d'Espagne",
        "latitude": 36.79850,
        "longitude": 10.18140,
        "district": "Avenue Habib Bourguiba",
    },
]

LOCATION_BY_ID: Dict[str, LocationDef] = {loc["id"]: loc for loc in TUNIS_LOCATIONS}


def list_locations() -> List[LocationDef]:
    return list(TUNIS_LOCATIONS)


def get_location(location_id: str) -> LocationDef | None:
    return LOCATION_BY_ID.get(location_id)
