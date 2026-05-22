"""Teste SITL do PR #2: executa missão square_50m e valida métricas.

Pressupõe:
- PX4 SITL com Gazebo gz_x500 rodando (compose service 'sitl')
- mavsdk_server rodando em background (entrypoint do tester)
- tester e sitl compartilham network namespace (network_mode service:sitl)
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.sitl


REPO_ROOT = Path(__file__).resolve().parents[2]
MISSION_YAML = REPO_ROOT / "missions" / "square_50m.yaml"
REPORTS_DIR = REPO_ROOT / "reports"


def test_square_50m_mission_executes() -> None:
    """Executa run_mission.py CLI e valida exit code 0."""
    cmd = [
        "python",
        "-m",
        "tools.run_mission",
        "--mission",
        str(MISSION_YAML),
        "--mavsdk-server",
        os.environ.get("MAVSDK_SERVER_HOST", "127.0.0.1"),
        "--mavsdk-port",
        os.environ.get("MAVSDK_SERVER_PORT", "50051"),
        "--system-address",
        os.environ.get("MAVLINK_URL", "udpin://0.0.0.0:14540"),
    ]
    result = subprocess.run(cmd, cwd=REPO_ROOT, timeout=300, capture_output=True, text=True)
    if result.returncode != 0:
        pytest.fail(
            f"run_mission falhou (exit={result.returncode}).\n"
            f"stdout:\n{result.stdout[-2000:]}\n"
            f"stderr:\n{result.stderr[-2000:]}"
        )


def test_metrics_within_baseline_thresholds() -> None:
    """Extrai métricas do .ulog mais recente e valida thresholds soft.

    Estes thresholds são baseline pré-Aula 10 (que vai apertar). Servem
    como sanity check: se algo estiver muito fora, é erro real (não cabe
    em variabilidade normal do simulador).
    """
    # PX4 SITL escreve ULogs em build/px4_sitl_default/rootfs/log/<date>/<time>.ulg
    # dentro do container sitl. Esse path está mapeado em $ULOG_DIR no tester via
    # named volume `ulogs` (vide docker-compose.ci.yml). Default /ulogs.
    ulog_dir = Path(os.environ.get("ULOG_DIR", "/ulogs"))
    if not ulog_dir.is_dir():
        pytest.skip(f"ULOG_DIR não existe: {ulog_dir}")
    candidates = sorted(
        ulog_dir.rglob("*.ulg"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        pytest.skip(f"nenhum .ulg encontrado em {ulog_dir}")
    latest = candidates[0]

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output = REPORTS_DIR / "metrics.json"
    result = subprocess.run(
        [
            "python",
            "-m",
            "tools.extract_metrics",
            "--ulog",
            str(latest),
            "--output",
            str(output),
        ],
        cwd=REPO_ROOT,
        timeout=60,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"extract_metrics falhou: {result.stderr}"

    metrics = json.loads(output.read_text())
    # Thresholds baseline frouxos (Aula 10 apertará via quality_gates.yaml)
    assert (
        30 <= metrics["mission_duration_s"] <= 240
    ), f"duração fora do baseline (30-240s): {metrics['mission_duration_s']}"
    assert (
        5 <= metrics["max_altitude_m"] <= 30
    ), f"max_altitude fora (5-30m): {metrics['max_altitude_m']}"
    assert (
        metrics["max_acceleration_m_s2"] < 50
    ), f"max_accel impossível: {metrics['max_acceleration_m_s2']}"
