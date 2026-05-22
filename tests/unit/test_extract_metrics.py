"""Testes para tools.extract_metrics (parte pura, sem .ulg real)."""

import pytest

from tools.extract_metrics import (
    MissionMetrics,
    _altitude_cruise_window,
    _std,
    compute_metrics_from_data,
)


class TestStd:
    def test_empty_returns_zero(self) -> None:
        assert _std([]) == 0.0

    def test_single_value_returns_zero(self) -> None:
        assert _std([42.0]) == 0.0

    def test_known_std(self) -> None:
        # std de [1,2,3,4,5] (amostral, ddof=1) ≈ 1.5811
        assert _std([1.0, 2.0, 3.0, 4.0, 5.0]) == pytest.approx(1.5811, abs=0.001)


class TestCruiseWindow:
    def test_filters_below_threshold(self) -> None:
        # Default cruise_min_m = 5.0
        assert _altitude_cruise_window([0.0, 1.0, 5.0, 10.0, 3.0]) == [5.0, 10.0]


class TestComputeMetrics:
    def test_basic_60s_flight(self) -> None:
        # 60s, decola até 10m e fica em cruzeiro
        ts = [0.0, 30.0, 60.0]
        alts = [0.0, 10.0, 10.0]
        accel = [9.8, 9.81, 9.8]
        batt = [100.0, 95.0, 90.0]
        m = compute_metrics_from_data(ts, alts, accel, batt)
        assert isinstance(m, MissionMetrics)
        assert m.mission_duration_s == 60.0
        assert m.max_altitude_m == 10.0
        assert m.mean_altitude_m == pytest.approx(6.67, abs=0.01)
        # Cruise window é só [10, 10] → std=0
        assert m.std_altitude_cruise_m == 0.0
        assert m.max_acceleration_m_s2 == 9.81
        # Maior drop entre amostras: 95→90 = 5pct
        assert m.max_battery_drop_pct == 5.0
        assert m.n_samples == 3

    def test_empty_series_returns_zeros(self) -> None:
        m = compute_metrics_from_data([], [], [], [])
        assert m.mission_duration_s == 0.0
        assert m.max_altitude_m == 0.0
        assert m.max_acceleration_m_s2 == 0.0
        assert m.max_battery_drop_pct == 0.0
        assert m.n_samples == 0

    def test_single_battery_sample_no_drop(self) -> None:
        m = compute_metrics_from_data([0.0], [10.0], [9.8], [100.0])
        assert m.max_battery_drop_pct == 0.0

    def test_battery_recovery_does_not_count(self) -> None:
        # Bateria sobe (regen ou ruído) → drop continua sendo do que efetivamente caiu
        m = compute_metrics_from_data(
            [0.0, 1.0, 2.0], [10, 10, 10], [9.8, 9.8, 9.8], [100.0, 90.0, 95.0]
        )
        # diffs = [10, -5] → max = 10
        assert m.max_battery_drop_pct == 10.0

    def test_altitude_std_only_uses_cruise_samples(self) -> None:
        # Decolagem 0→5, cruzeiro com ruído, pouso
        alts = [0.0, 2.0, 5.0, 10.0, 11.0, 9.0, 10.0, 5.0, 0.0]
        m = compute_metrics_from_data([0.0, 1.0, 2.0], alts, [], [])
        # Cruise window = [5, 10, 11, 9, 10, 5] → std não-zero
        assert m.std_altitude_cruise_m > 0
