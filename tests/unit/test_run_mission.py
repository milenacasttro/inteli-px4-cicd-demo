"""Testes unit para tools.run_mission (parte testável sem MAVSDK rodando)."""

from pathlib import Path

from libs.drone_modeling.mission import load_mission
from tools.run_mission import _build_mission_items


def test_build_mission_items_skips_rtl() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    m = load_mission(repo_root / "missions" / "square_50m.yaml")
    # Missão tem takeoff + 4 wp + rtl. RTL é excluído.
    items = _build_mission_items(m)
    assert len(items) == 5  # takeoff + 4 waypoints (RTL drop)


def test_build_mission_items_uses_acceptance_radius() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    m = load_mission(repo_root / "missions" / "square_50m.yaml")
    items = _build_mission_items(m)
    for item in items:
        assert item.acceptance_radius_m == m.acceptance_radius_m
        assert item.speed_m_s == m.cruise_speed_m_s


def test_build_mission_items_carries_altitude() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    m = load_mission(repo_root / "missions" / "square_50m.yaml")
    items = _build_mission_items(m)
    for item in items:
        assert item.relative_altitude_m == 10.0


def test_build_mission_items_only_rtl_returns_empty(tmp_path: Path) -> None:
    yaml = tmp_path / "bad.yaml"
    yaml.write_text(
        """
name: x
takeoff_altitude_m: 10
cruise_speed_m_s: 5
acceptance_radius_m: 2
home: {latitude: 0, longitude: 0}
waypoints:
  - {name: rtl_only, type: rtl}
limits: {max_duration_s: 60, max_altitude_m: 30, geofence_radius_m: 100}
"""
    )
    m = load_mission(yaml)
    assert _build_mission_items(m) == []
