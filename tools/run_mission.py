"""CLI: executa uma missão YAML no PX4 SITL via MAVSDK.

Pressupõe que o `mavsdk_server` está rodando como processo externo (vide
docker/entrypoint-tester.sh). Conecta no gRPC localhost, faz upload+start+
wait_completion da missão, retorna 0 em sucesso.

Uso:
    python -m tools.run_mission \\
        --mission missions/square_50m.yaml \\
        [--mavsdk-server 127.0.0.1] [--mavsdk-port 50051] \\
        [--system-address udpin://0.0.0.0:14540]
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from libs.drone_modeling.mission import Mission, load_mission

if TYPE_CHECKING:
    from mavsdk import System

LOG = logging.getLogger("run_mission")


async def _wait_connected(drone: System, timeout_s: float = 30.0) -> None:
    """Espera MAVSDK detectar conexão com PX4."""

    async def loop() -> None:
        async for state in drone.core.connection_state():
            if state.is_connected:
                return

    await asyncio.wait_for(loop(), timeout=timeout_s)


async def _wait_armable(drone: System, timeout_s: float = 90.0) -> None:
    """Espera todos os checks de saúde necessários pra armar.

    Inclui: GPS lock, home position, local position (EKF2 convergiu) e
    armable flag. Sem isso o action.arm() levanta COMMAND_DENIED.
    """

    async def loop() -> None:
        async for health in drone.telemetry.health():
            if (
                health.is_global_position_ok
                and health.is_home_position_ok
                and health.is_local_position_ok
                and health.is_armable
            ):
                return

    await asyncio.wait_for(loop(), timeout=timeout_s)


async def _arm_with_retry(drone: System, attempts: int = 5, delay_s: float = 3.0) -> None:
    """Tenta arm() com retry — em SITL com jmavsim, preflight pode reprovar
    transiente nos primeiros segundos mesmo após is_armable=True."""
    from mavsdk.action import ActionError

    last_err: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            await drone.action.arm()
            return
        except ActionError as e:
            last_err = e
            LOG.warning("arm() tentativa %d/%d falhou: %s", i, attempts, e)
            await asyncio.sleep(delay_s)
    raise RuntimeError(f"arm() falhou em {attempts} tentativas: {last_err}")


def _build_mission_items(m: Mission) -> list[Any]:
    """Converte waypoints da Mission em MissionItem do MAVSDK.

    Retorno é list[Any] porque MAVSDK não publica type stubs públicos.
    """
    from mavsdk.mission import MissionItem

    items: list[Any] = []
    for wp in m.waypoints:
        if wp.type == "rtl":
            # RTL não vira MissionItem: setamos return_to_launch_after_mission=True
            continue
        if wp.lat is None or wp.lon is None or wp.alt_m is None:
            raise ValueError(f"waypoint '{wp.name}' sem coordenadas/altitude válidas")
        items.append(
            MissionItem(
                latitude_deg=wp.lat,
                longitude_deg=wp.lon,
                relative_altitude_m=wp.alt_m,
                speed_m_s=m.cruise_speed_m_s,
                is_fly_through=False,
                gimbal_pitch_deg=float("nan"),
                gimbal_yaw_deg=float("nan"),
                camera_action=MissionItem.CameraAction.NONE,
                loiter_time_s=float("nan"),
                camera_photo_interval_s=float("nan"),
                acceptance_radius_m=m.acceptance_radius_m,
                yaw_deg=float("nan"),
                camera_photo_distance_m=float("nan"),
                vehicle_action=MissionItem.VehicleAction.NONE,
            )
        )
    return items


async def _execute_mission(drone: System, m: Mission, timeout_s: float) -> None:
    """Upload + arm + start + wait completion."""
    from mavsdk.mission import MissionPlan

    items = _build_mission_items(m)
    has_rtl = any(wp.type == "rtl" for wp in m.waypoints)
    LOG.info("upload %d itens (RTL=%s)", len(items), has_rtl)

    await drone.mission.set_return_to_launch_after_mission(has_rtl)
    await drone.mission.upload_mission(MissionPlan(items))
    LOG.info("upload OK; arming (com retry)")
    await _arm_with_retry(drone)
    LOG.info("armed; starting mission")
    await drone.mission.start_mission()
    LOG.info("mission started; waiting completion (timeout=%ds)", int(timeout_s))

    async def wait() -> None:
        async for progress in drone.mission.mission_progress():
            LOG.info("progress: %d/%d", progress.current, progress.total)
            if progress.total > 0 and progress.current == progress.total:
                return

    await asyncio.wait_for(wait(), timeout=timeout_s)
    LOG.info("mission completed")


async def run(
    mission_path: Path,
    mavsdk_server: str,
    mavsdk_port: int,
    system_address: str,
) -> int:
    from mavsdk import System

    m = load_mission(mission_path)
    LOG.info("loaded mission '%s' (%d waypoints)", m.name, len(m.waypoints))

    drone = System(mavsdk_server_address=mavsdk_server, port=mavsdk_port)
    LOG.info("connecting MAVSDK to %s", system_address)
    await drone.connect(system_address=system_address)
    await _wait_connected(drone, timeout_s=30)
    LOG.info("MAVLink heartbeat received; waiting for armable health")
    await _wait_armable(drone, timeout_s=90)
    LOG.info("armable: all health checks ok")

    try:
        await _execute_mission(drone, m, timeout_s=m.max_duration_s)
    finally:
        with contextlib.suppress(TimeoutError, Exception):
            await asyncio.wait_for(drone.action.land(), timeout=10)

    return 0


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--mission", required=True, type=Path, help="caminho do YAML")
    p.add_argument("--mavsdk-server", default="127.0.0.1")
    p.add_argument("--mavsdk-port", type=int, default=50051)
    p.add_argument("--system-address", default="udpin://0.0.0.0:14540")
    args = p.parse_args()

    code = asyncio.run(run(args.mission, args.mavsdk_server, args.mavsdk_port, args.system_address))
    sys.exit(code)


if __name__ == "__main__":
    main()
