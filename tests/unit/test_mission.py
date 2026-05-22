"""Testes para libs.drone_modeling.mission."""

from pathlib import Path

import pytest

from libs.drone_modeling.mission import (
    Mission,
    Waypoint,
    load_mission,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _make_mission_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "mission.yaml"
    p.write_text(
        """
name: test_square
description: teste
takeoff_altitude_m: 10.0
cruise_speed_m_s: 5.0
acceptance_radius_m: 2.0
home:
  latitude: 47.397742
  longitude: 8.545594
waypoints:
  - name: takeoff
    type: takeoff
    altitude_m: 10.0
  - name: wp1
    type: waypoint
    north_m: 50.0
    east_m: 0.0
    altitude_m: 10.0
  - name: rtl
    type: rtl
limits:
  max_duration_s: 180
  max_altitude_m: 30.0
  geofence_radius_m: 100.0
"""
    )
    return p


class TestLoadMission:
    def test_loads_basic_fields(self, tmp_path: Path) -> None:
        m = load_mission(_make_mission_yaml(tmp_path))
        assert m.name == "test_square"
        assert m.takeoff_altitude_m == 10.0
        assert m.cruise_speed_m_s == 5.0
        assert m.acceptance_radius_m == 2.0
        assert m.home_lat == 47.397742
        assert m.home_lon == 8.545594
        assert m.max_duration_s == 180
        assert m.max_altitude_m == 30.0
        assert m.geofence_radius_m == 100.0

    def test_takeoff_waypoint(self, tmp_path: Path) -> None:
        m = load_mission(_make_mission_yaml(tmp_path))
        assert m.waypoints[0].name == "takeoff"
        assert m.waypoints[0].type == "takeoff"
        # takeoff usa lat/lon do home
        assert m.waypoints[0].lat == m.home_lat
        assert m.waypoints[0].lon == m.home_lon
        assert m.waypoints[0].alt_m == 10.0

    def test_ned_waypoint_converts_to_lat_lon(self, tmp_path: Path) -> None:
        m = load_mission(_make_mission_yaml(tmp_path))
        wp1 = m.waypoints[1]
        assert wp1.name == "wp1"
        # 50m ao norte de (47.397742, 8.545594) → lat aumenta ~0.000449°
        assert wp1.lat is not None
        assert wp1.lat == pytest.approx(47.397742 + 50 / 111320.0, abs=1e-5)
        assert wp1.lon == pytest.approx(8.545594, abs=1e-5)
        assert wp1.alt_m == 10.0

    def test_rtl_waypoint(self, tmp_path: Path) -> None:
        m = load_mission(_make_mission_yaml(tmp_path))
        rtl = m.waypoints[-1]
        assert rtl.type == "rtl"
        # RTL não precisa de lat/lon
        assert rtl.lat is None and rtl.lon is None

    def test_rejects_unknown_waypoint_type(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text(
            """
name: bad
takeoff_altitude_m: 10.0
cruise_speed_m_s: 5.0
acceptance_radius_m: 2.0
home: {latitude: 0, longitude: 0}
waypoints:
  - name: w
    type: orbital
limits: {max_duration_s: 100, max_altitude_m: 30, geofence_radius_m: 100}
"""
        )
        with pytest.raises(ValueError, match="tipo de waypoint desconhecido"):
            load_mission(bad)


class TestMissionDataclass:
    def test_waypoints_immutable_after_load(self, tmp_path: Path) -> None:
        m = load_mission(_make_mission_yaml(tmp_path))
        # Mission é frozen — mutação levanta
        with pytest.raises((AttributeError, TypeError)):
            m.name = "novo"  # type: ignore[misc]

    def test_waypoint_immutable(self) -> None:
        wp = Waypoint(name="x", type="takeoff", lat=0.0, lon=0.0, alt_m=10.0)
        with pytest.raises((AttributeError, TypeError)):
            wp.name = "y"  # type: ignore[misc]


class TestMissionReferenceFile:
    """Smoke check no missions/square_50m.yaml do repo."""

    def test_real_square_50m_loads(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        m = load_mission(repo_root / "missions" / "square_50m.yaml")
        assert m.name == "square_50m"
        # takeoff + 4 waypoints quadrados + rtl
        assert len(m.waypoints) == 6
        assert m.waypoints[0].type == "takeoff"
        assert m.waypoints[-1].type == "rtl"
        assert isinstance(m, Mission)
