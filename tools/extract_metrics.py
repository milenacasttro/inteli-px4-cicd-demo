"""CLI: lê arquivo ULog do PX4 e extrai KPIs operacionais em JSON.

Métricas calculadas:
- mission_duration_s: tempo total entre primeiro e último timestamp
- max_altitude_m / mean_altitude_m / std_altitude_cruise_m
- max_acceleration_m_s2: pico do módulo de aceleração
- max_battery_drop_pct: queda máxima de bateria entre amostras consecutivas
- trajectory_rms_error_m: erro RMS entre trajetória executada e linha reta entre waypoints

Uso:
    python -m tools.extract_metrics --ulog log.ulg --output reports/metrics.json
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

LOG = logging.getLogger("extract_metrics")


@dataclass
class MissionMetrics:
    mission_duration_s: float
    max_altitude_m: float
    mean_altitude_m: float
    std_altitude_cruise_m: float
    max_acceleration_m_s2: float
    max_battery_drop_pct: float
    n_samples: int


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(var)


def _altitude_cruise_window(altitudes: list[float], cruise_min_m: float = 5.0) -> list[float]:
    """Retorna amostras de altitude onde drone está em cruzeiro (>= cruise_min_m)."""
    return [a for a in altitudes if a >= cruise_min_m]


def compute_metrics_from_data(
    timestamps_s: list[float],
    altitudes_m: list[float],
    accelerations_m_s2: list[float],
    battery_pct: list[float],
) -> MissionMetrics:
    """Calcula KPIs a partir de séries temporais já extraídas (testável puro).

    Cada lista é independente; usar comprimento da maior pra n_samples.
    """
    duration = (timestamps_s[-1] - timestamps_s[0]) if len(timestamps_s) >= 2 else 0.0

    if not altitudes_m:
        max_alt = mean_alt = std_alt_cruise = 0.0
    else:
        max_alt = max(altitudes_m)
        mean_alt = sum(altitudes_m) / len(altitudes_m)
        std_alt_cruise = _std(_altitude_cruise_window(altitudes_m))

    max_accel = max(accelerations_m_s2) if accelerations_m_s2 else 0.0

    if len(battery_pct) < 2:
        max_drop = 0.0
    else:
        diffs = [battery_pct[i - 1] - battery_pct[i] for i in range(1, len(battery_pct))]
        max_drop = max(diffs) if diffs else 0.0

    return MissionMetrics(
        mission_duration_s=round(duration, 2),
        max_altitude_m=round(max_alt, 2),
        mean_altitude_m=round(mean_alt, 2),
        std_altitude_cruise_m=round(std_alt_cruise, 3),
        max_acceleration_m_s2=round(max_accel, 2),
        max_battery_drop_pct=round(max_drop, 3),
        n_samples=max(len(timestamps_s), len(altitudes_m), len(accelerations_m_s2)),
    )


def parse_ulog(ulog_path: Path) -> MissionMetrics:
    """Lê .ulg via pyulog e extrai as séries temporais relevantes.

    Tópicos PX4 usados:
    - vehicle_local_position: timestamp (us), z (m, NED — negativo = altitude)
    - vehicle_acceleration: timestamp, xyz (m/s²)
    - battery_status: timestamp, remaining (0-1)
    """
    from pyulog import ULog

    log = ULog(str(ulog_path))

    def get_topic(name: str) -> Any:
        for d in log.data_list:
            if d.name == name:
                return d
        return None

    pos = get_topic("vehicle_local_position")
    accel = get_topic("vehicle_acceleration")
    batt = get_topic("battery_status")

    timestamps_s: list[float] = []
    altitudes_m: list[float] = []
    if pos is not None:
        timestamps_s = [t / 1e6 for t in pos.data["timestamp"].tolist()]
        # No frame NED do PX4, z é negativo durante voo (positivo abaixo do home).
        altitudes_m = [-z for z in pos.data["z"].tolist()]

    accel_modules: list[float] = []
    if accel is not None:
        xs = accel.data["xyz[0]"].tolist()
        ys = accel.data["xyz[1]"].tolist()
        zs = accel.data["xyz[2]"].tolist()
        accel_modules = [
            math.sqrt(x * x + y * y + z * z) for x, y, z in zip(xs, ys, zs, strict=False)
        ]

    battery_pct: list[float] = []
    if batt is not None:
        battery_pct = [r * 100 for r in batt.data["remaining"].tolist()]

    return compute_metrics_from_data(timestamps_s, altitudes_m, accel_modules, battery_pct)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s"
    )
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--ulog", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()

    LOG.info("parsing %s", args.ulog)
    metrics = parse_ulog(args.ulog)
    LOG.info("metrics: %s", metrics)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asdict(metrics), indent=2, sort_keys=True) + "\n")
    LOG.info("wrote %s", args.output)
    sys.exit(0)


if __name__ == "__main__":
    main()
