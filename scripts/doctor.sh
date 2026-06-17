#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "${ROOT_DIR}"

echo "=== Benchmark platform doctor ==="
echo "Repository: ${ROOT_DIR}"
echo

./scripts/check_prereqs.sh

echo
echo "=== Git state ==="
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Commit: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
    echo "[WARN] Working tree contains uncommitted changes."
  else
    echo "[OK] Working tree is clean."
  fi
else
  echo "[WARN] Current directory is not a Git working tree."
fi

echo
echo "=== Existing Kind clusters ==="
if command -v kind >/dev/null 2>&1; then
  KIND_CLUSTERS="$(kind get clusters 2>/dev/null || true)"
  if [[ -n "${KIND_CLUSTERS}" ]]; then
    printf '%s\n' "${KIND_CLUSTERS}"
  else
    echo "No Kind clusters currently detected."
  fi
fi

echo
echo "=== Kind Docker network ==="
if docker network inspect kind >/dev/null 2>&1; then
  docker network inspect kind \
    --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' \
    | sed 's/^/Subnet: /'
else
  echo "No Docker network named 'kind' currently exists. It is normally created when the first Kind cluster is created."
fi

echo
echo "Doctor check complete."