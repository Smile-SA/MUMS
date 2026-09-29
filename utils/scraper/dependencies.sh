#!/usr/bin/env bash
# Python packages of the scraper (requirements.txt), installed with the
# platform's interpreter (first on PATH).
# Usage: ./dependencies.sh install|check
set -euo pipefail

case "${1:-}" in
    install) python3 -m pip install -r requirements.txt ;;
    check)   python3 -c "import requests" ;;
    *) echo "Usage: $0 install|check" >&2; exit 2 ;;
esac
