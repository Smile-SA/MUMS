#!/usr/bin/env bash
# Basic-evaluation post-processing module (contract 1): summarizes one run from
# standard data into <data_dir>/summary/post-processing.basic-evaluation.csv
# (see README.md).
#
# Usage:
#   run.sh run <data_dir> [--run_window true|false]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

usage() {
    echo "Usage: $0 run <data_dir> [--run_window true|false]" >&2
    exit 1
}

ACTION="${1:-}"
if [ "$ACTION" != "run" ]; then
    [ -n "$ACTION" ] && echo "ERROR: unknown action '$ACTION'" >&2
    usage
fi
shift
[ "$#" -ge 1 ] || usage
DATA_DIR="$1"
shift

RUN_WINDOW=true
while [ "$#" -gt 0 ]; do
    case "$1" in
        --run_window) RUN_WINDOW="$2"; shift 2 ;;
        *) echo "ERROR: unknown option '$1'" >&2; usage ;;
    esac
done

python3 "${SCRIPT_DIR}/evaluate.py" "$DATA_DIR" --run-window "$RUN_WINDOW"
