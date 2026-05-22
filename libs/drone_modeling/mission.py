"""Carregamento e validação de missões em YAML."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from libs.drone_modeling.geometry import ned_to_lat_lon

VALID_TYPES = {"takeoff", "waypoint", "rtl"}


@dataclass(frozen=True)
class Waypoint:
    name: str
    type: str
    lat: float | None = None
    lon: float | None = None
    alt_m: float | None = None


@dataclass(frozen=True)
class Mission:
    name: str
    description: str
    takeoff_altitude_m: float
    cruise_speed_m_s: float
    acceptance_radius_m: float
    home_lat: float
    home_lon: float
    max_duration_s: int
    max_altitude_m: float
    geofence_radius_m: float
    waypoints: tuple[Waypoint, ...] = field(default_factory=tuple)


def _build_waypoint(
    raw: dict[str, Any], home_lat: float, home_lon: float, takeoff_alt: float
) -> Waypoint:
    wp_type = raw["type"]
    if wp_type not in VALID_TYPES:
        raise ValueError(
            f"tipo de waypoint desconhecido: '{wp_type}' (válidos: {sorted(VALID_TYPES)})"
        )
    name = raw.get("name", wp_type)
    if wp_type == "takeoff":
        return Waypoint(
            name=name,
            type=wp_type,
            lat=home_lat,
            lon=home_lon,
            alt_m=raw.get("altitude_m", takeoff_alt),
        )
    if wp_type == "rtl":
        return Waypoint(name=name, type=wp_type)
    # waypoint NED → lat/lon
    lat, lon = ned_to_lat_lon(raw["north_m"], raw["east_m"], home_lat, home_lon)
    return Waypoint(name=name, type=wp_type, lat=lat, lon=lon, alt_m=raw["altitude_m"])


def load_mission(yaml_path: str | Path) -> Mission:
    """Lê YAML de missão e retorna Mission imutável com waypoints em lat/lon."""
    data = yaml.safe_load(Path(yaml_path).read_text())
    home = data["home"]
    limits = data["limits"]
    takeoff_alt = float(data["takeoff_altitude_m"])
    waypoints = tuple(
        _build_waypoint(raw, home["latitude"], home["longitude"], takeoff_alt)
        for raw in data["waypoints"]
    )
    return Mission(
        name=data["name"],
        description=data.get("description", ""),
        takeoff_altitude_m=takeoff_alt,
        cruise_speed_m_s=float(data["cruise_speed_m_s"]),
        acceptance_radius_m=float(data["acceptance_radius_m"]),
        home_lat=float(home["latitude"]),
        home_lon=float(home["longitude"]),
        max_duration_s=int(limits["max_duration_s"]),
        max_altitude_m=float(limits["max_altitude_m"]),
        geofence_radius_m=float(limits["geofence_radius_m"]),
        waypoints=waypoints,
    )
