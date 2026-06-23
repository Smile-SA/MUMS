#!/usr/bin/env bash
set -euo pipefail

CONFIG="${1:-configs/basic-online-boutique.yaml}"

echo "=== Running standalone smoke test ==="
echo "Config: ${CONFIG}"

python -m benchmark_platform.cli validate "${CONFIG}"
python -m benchmark_platform.cli run "${CONFIG}"

LATEST_RUN="$(find output/runs -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)"

if [[ -z "${LATEST_RUN}" ]]; then
  echo "[ERROR] No run directory found." >&2
  exit 1
fi

echo "Latest run: ${LATEST_RUN}"

test -f "${LATEST_RUN}/manifest.yaml"
test -f "${LATEST_RUN}/config.yaml"
test -d "${LATEST_RUN}/logs"
test -d "${LATEST_RUN}/metrics"
test -s "${LATEST_RUN}/metrics/metrics.om"
test -s "${LATEST_RUN}/metrics/scrapes.csv"
test -d "${LATEST_RUN}/datasets"
test -f "${LATEST_RUN}/datasets/dataset-metadata.yaml"
test -d "${LATEST_RUN}/datasets/container_timeseries"
test -d "${LATEST_RUN}/datasets/pod_timeseries"
test -d "${LATEST_RUN}/datasets/node_timeseries"
test -d "${LATEST_RUN}/datasets/controller_timeseries"

if [[ ! -s "${LATEST_RUN}/metrics/metrics.om" ]]; then
  echo "[ERROR] Raw metrics file is missing or empty." >&2
  exit 1
fi

if [[ ! -s "${LATEST_RUN}/metrics/scrapes.csv" ]]; then
  echo "[ERROR] Scrape metadata file is missing or empty." >&2
  exit 1
fi

python -m benchmark_platform.datasets.metadata "${LATEST_RUN}"
test -f "${LATEST_RUN}/datasets/dataset-metadata.yaml"

echo "Standalone smoke test succeeded."
