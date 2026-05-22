#!/bin/bash
# Entrypoint do tester: sobe mavsdk_server em background antes do comando.
#
# Motivo: MAVSDK 2.x Python tem bug de bootstrap do server interno no container
# slim (vide PR #1 docs). Workaround: rodamos o binário standalone e o Python
# client conecta nele via gRPC localhost.
#
# O mavsdk_server vem como parte do package mavsdk-2.8.4. Se MAVSDK_SERVER_DISABLE=1
# pula o startup (usado para testes que só precisam de pymavlink).

set -euo pipefail

if [ "${MAVSDK_SERVER_DISABLE:-0}" != "1" ]; then
  SERVER_BIN=$(python3 -c 'import mavsdk, os; print(os.path.join(os.path.dirname(mavsdk.__file__), "bin", "mavsdk_server"))')
  MAVSDK_PORT="${MAVSDK_SERVER_PORT:-50051}"
  # mavsdk_server v2.12 (embarcado no mavsdk-python 2.8.4) NÃO aceita schema
  # 'udpin://'. Use 'udp://:14540' legacy. Variável separada do MAVLINK_URL
  # (que pode estar em formato 'udpin:127.0.0.1:14540' pra pymavlink).
  MAVLINK_ADDR="${MAVSDK_SERVER_URL:-udp://:14540}"

  echo "[entrypoint] starting mavsdk_server on port ${MAVSDK_PORT} listening ${MAVLINK_ADDR}"
  "${SERVER_BIN}" -p "${MAVSDK_PORT}" "${MAVLINK_ADDR}" >/tmp/mavsdk_server.log 2>&1 &
  SERVER_PID=$!

  # Espera o server ficar listening (até 10s)
  for _ in $(seq 1 20); do
    if pgrep -x mavsdk_server >/dev/null 2>&1; then
      echo "[entrypoint] mavsdk_server PID=${SERVER_PID} ready"
      break
    fi
    sleep 0.5
  done
fi

# Executa o CMD passado ao container
exec "$@"
