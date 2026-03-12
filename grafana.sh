#!/bin/bash
# Ouvre le port-forward vers Prometheus et provisionne la datasource + dashboard dans Grafana.
# Usage: ./grafana.sh <seed>

SEED=$1

if [ -z "$SEED" ]; then
    echo "Usage: $0 <seed>" >&2
    exit 1
fi

KUBECONFIG="/tmp/kubeconfig-kind-test-${SEED}"

if [ ! -f "$KUBECONFIG" ]; then
    echo "ERREUR: kubeconfig '$KUBECONFIG' introuvable — cluster démarré ?" >&2
    exit 1
fi

# Lance le port-forward en arrière-plan
kubectl --kubeconfig "$KUBECONFIG" \
    port-forward -n monitoring svc/prometheus-server 9090:80 &
PF_PID=$!
trap "kill $PF_PID 2>/dev/null" EXIT

# Attend que le port soit prêt
echo "=== Attente du port-forward..." >&2
for i in $(seq 1 10); do
    if curl -s http://localhost:9090/-/healthy > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

# Provisionne la datasource Prometheus
echo "=== Provisionnement datasource Prometheus..." >&2
curl -s -X POST http://admin:admin@localhost:3000/api/datasources \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Prometheus",
        "type": "prometheus",
        "url": "http://127.0.0.1:9090",
        "access": "proxy",
        "isDefault": true
    }' > /dev/null

echo ""
echo "=== Prêt ==="
echo "    Grafana UI : http://localhost:3000"
echo "    Dashboard  : Dashboards → Kubernetes cluster monitoring"
echo ""
echo "    Ctrl+C pour fermer le tunnel"
echo ""

wait $PF_PID
