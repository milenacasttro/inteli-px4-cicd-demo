"""Geometria de drones: conversões lat/lon ↔ NED e cálculos de erro de trajetória."""

import math

EARTH_RADIUS_M = 6_371_000.0
METERS_PER_DEG_LAT = 111_320.0


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância entre 2 pontos lat/lon (graus decimais) em metros."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def lat_lon_to_ned(lat: float, lon: float, ref_lat: float, ref_lon: float) -> tuple[float, float]:
    """Converte (lat, lon) para coordenadas NED relativas a (ref_lat, ref_lon).

    Aproximação plana — adequada para distâncias <10km (precisão sub-metro).
    Retorna (north_m, east_m).
    """
    north = (lat - ref_lat) * METERS_PER_DEG_LAT
    east = (lon - ref_lon) * METERS_PER_DEG_LAT * math.cos(math.radians(ref_lat))
    return north, east


def ned_to_lat_lon(
    north_m: float, east_m: float, ref_lat: float, ref_lon: float
) -> tuple[float, float]:
    """Inversa de lat_lon_to_ned. Retorna (lat, lon) em graus decimais."""
    lat = ref_lat + (north_m / METERS_PER_DEG_LAT)
    lon = ref_lon + (east_m / (METERS_PER_DEG_LAT * math.cos(math.radians(ref_lat))))
    return lat, lon


def trajectory_rms_error(
    planned: list[tuple[float, float]], actual: list[tuple[float, float]]
) -> float:
    """RMS do erro de posição entre trajetória planejada e real, em metros.

    Cada ponto é uma tupla (north_m, east_m). Compara ponto-a-ponto — pressupõe
    que `planned` e `actual` estão sincronizados (mesma quantidade, mesmos
    instantes de amostragem).

    Raises:
        ValueError: se listas têm tamanhos diferentes ou estão vazias.
    """
    if not planned or not actual:
        raise ValueError("trajetória vazio: planned e actual precisam de pelo menos 1 ponto")
    if len(planned) != len(actual):
        raise ValueError(
            f"trajetórias devem ter mesma quantidade de pontos "
            f"(planned={len(planned)}, actual={len(actual)})"
        )
    squared_errors = [
        (p[0] - a[0]) ** 2 + (p[1] - a[1]) ** 2 for p, a in zip(planned, actual, strict=True)
    ]
    return math.sqrt(sum(squared_errors) / len(squared_errors))
