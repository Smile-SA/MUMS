#!/bin/bash
# Provisions Prometheus datasource in Grafana.
# Usage: ./grafana.sh <prometheus_url> [grafana_url]
#
# Defaults:
#   grafana_url : http://localhost:3000

PROMETHEUS_URL=$1
GRAFANA_URL=${2:-http://localhost:3000}

if [ -z "$PROMETHEUS_URL" ]; then
    echo "Usage: $0 <prometheus_url> [grafana_url]" >&2
    exit 1
fi

echo "=== Provisioning Prometheus datasource..." >&2
curl -s -X POST "${GRAFANA_URL}/api/datasources" \
    -u admin:admin \
    -H "Content-Type: application/json" \
    -d "{
        \"name\": \"Prometheus\",
        \"type\": \"prometheus\",
        \"url\": \"${PROMETHEUS_URL}\",
        \"access\": \"proxy\",
        \"isDefault\": true
    }" > /dev/null

echo "" >&2
echo "=== Ready ===" >&2
echo "    Grafana  : ${GRAFANA_URL}" >&2
echo "    Prometheus datasource : ${PROMETHEUS_URL}" >&2
echo "    Dashboard : Dashboards → Kubernetes cluster monitoring" >&2
