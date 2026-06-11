#!/usr/bin/env bash
set -euo pipefail

PORT="${1:?Usage: $0 <local-port>}"

python3 - "${PORT}" <<'PY'
import socket
import sys

port = int(sys.argv[1])

if not (1 <= port <= 65535):
    raise SystemExit(f"Invalid TCP port: {port}")

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    sock.bind(("127.0.0.1", port))
except OSError as exc:
    raise SystemExit(f"Local port 127.0.0.1:{port} is not available: {exc}")
finally:
    sock.close()

print(f"[OK] Local port 127.0.0.1:{port} is available.")
PY
