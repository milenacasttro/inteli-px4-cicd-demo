"""Testes para libs.drone_modeling.geometry."""

import math

import pytest

from libs.drone_modeling.geometry import (
    haversine_distance,
    lat_lon_to_ned,
    ned_to_lat_lon,
    trajectory_rms_error,
)


class TestHaversineDistance:
    def test_same_point_returns_zero(self) -> None:
        assert haversine_distance(-23.55, -46.63, -23.55, -46.63) == 0.0

    def test_one_degree_latitude_is_about_111km(self) -> None:
        # 1° de latitude ≈ 111.32 km em qualquer longitude.
        d = haversine_distance(0.0, 0.0, 1.0, 0.0)
        assert d == pytest.approx(111195, rel=0.001)

    def test_known_distance_sao_paulo_to_rio(self) -> None:
        # São Paulo (-23.55, -46.63) → Rio (-22.91, -43.20) ≈ 360 km
        d = haversine_distance(-23.55, -46.63, -22.91, -43.20)
        assert d == pytest.approx(360_000, rel=0.02)


class TestLatLonToNed:
    def test_same_point_is_origin(self) -> None:
        ref_lat, ref_lon = -23.55, -46.63
        north, east = lat_lon_to_ned(ref_lat, ref_lon, ref_lat, ref_lon)
        assert north == pytest.approx(0.0, abs=1e-6)
        assert east == pytest.approx(0.0, abs=1e-6)

    def test_50m_north_of_origin(self) -> None:
        # ~50m ao norte: dlat = 50 / 111320 ≈ 0.000449°
        ref_lat, ref_lon = -23.55, -46.63
        target_lat = ref_lat + (50.0 / 111320.0)
        north, east = lat_lon_to_ned(target_lat, ref_lon, ref_lat, ref_lon)
        assert north == pytest.approx(50.0, abs=0.5)
        assert east == pytest.approx(0.0, abs=0.5)

    def test_50m_east_of_origin(self) -> None:
        ref_lat, ref_lon = -23.55, -46.63
        # 1° lon em -23.55° latitude ≈ 111320 * cos(23.55°) ≈ 102050m
        meters_per_deg_lon = 111320.0 * math.cos(math.radians(ref_lat))
        target_lon = ref_lon + (50.0 / meters_per_deg_lon)
        north, east = lat_lon_to_ned(ref_lat, target_lon, ref_lat, ref_lon)
        assert north == pytest.approx(0.0, abs=0.5)
        assert east == pytest.approx(50.0, abs=0.5)


class TestNedToLatLon:
    def test_origin_returns_ref(self) -> None:
        ref_lat, ref_lon = -23.55, -46.63
        lat, lon = ned_to_lat_lon(0.0, 0.0, ref_lat, ref_lon)
        assert lat == pytest.approx(ref_lat)
        assert lon == pytest.approx(ref_lon)

    def test_roundtrip_ned_lat_lon(self) -> None:
        # NED → lat/lon → NED deve recuperar o ponto original
        ref_lat, ref_lon = -23.55, -46.63
        north_in, east_in = 35.5, -27.2
        lat, lon = ned_to_lat_lon(north_in, east_in, ref_lat, ref_lon)
        north_out, east_out = lat_lon_to_ned(lat, lon, ref_lat, ref_lon)
        assert north_out == pytest.approx(north_in, abs=0.01)
        assert east_out == pytest.approx(east_in, abs=0.01)


class TestTrajectoryRmsError:
    def test_perfect_trajectory_returns_zero(self) -> None:
        planned = [(0.0, 0.0), (50.0, 0.0), (50.0, 50.0), (0.0, 50.0)]
        actual = [(0.0, 0.0), (50.0, 0.0), (50.0, 50.0), (0.0, 50.0)]
        assert trajectory_rms_error(planned, actual) == 0.0

    def test_constant_2m_offset(self) -> None:
        # Trajetória real 2m ao norte da planejada em todos os pontos
        planned = [(0.0, 0.0), (50.0, 0.0), (50.0, 50.0)]
        actual = [(2.0, 0.0), (52.0, 0.0), (52.0, 50.0)]
        assert trajectory_rms_error(planned, actual) == pytest.approx(2.0)

    def test_rejects_different_lengths(self) -> None:
        with pytest.raises(ValueError, match="mesma quantidade"):
            trajectory_rms_error([(0.0, 0.0)], [(0.0, 0.0), (1.0, 0.0)])

    def test_rejects_empty(self) -> None:
        with pytest.raises(ValueError, match="vazio"):
            trajectory_rms_error([], [])
