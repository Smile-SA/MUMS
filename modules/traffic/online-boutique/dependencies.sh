#!/usr/bin/env bash
# Python packages of the Locust traffic (requirements.txt: locust, Faker),
# installed with the platform's interpreter (first on PATH).
# Usage: ./dependencies.sh install|check
set -euo pipefail

case "${1:-}" in
    install) python3 -m pip install -r requirements.txt ;;
    check)
        command -v locust >/dev/null 2>&1 || { echo "locust command not found"; exit 1; }
        python3 -c "import locust, faker"
        ;;
    *) echo "Usage: $0 install|check" >&2; exit 2 ;;
esac
