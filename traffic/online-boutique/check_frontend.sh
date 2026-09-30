#!/usr/bin/env bash
set -euo pipefail

# Usage: ./check_frontend.sh <kubeconfig> <namespace>
# Waits until the frontend answers over HTTP, then prints its URL on stdout.
KUBECONFIG_PATH="${1:?Usage: $0 <kubeconfig> <namespace>}"
NAMESPACE="${2:?Usage: $0 <kubeconfig> <namespace>}"

SERVICE_NAME="frontend-external"
POD_READY_TIMEOUT_SECONDS=300
ENDPOINT_WAIT_TIMEOUT_SECONDS=180
HTTP_WAIT_TIMEOUT_SECONDS=180
HTTP_RETRY_DELAY_SECONDS=5
HTTP_REQUEST_TIMEOUT_SECONDS=5

KUBECTL=(kubectl --kubeconfig "${KUBECONFIG_PATH}")

log() {
  printf '[online-boutique] %s\n' "$*" >&2
}

diagnostics() {
  log "Diagnostics for namespace '${NAMESPACE}':"
  "${KUBECTL[@]}" -n "${NAMESPACE}" get pods -o wide >&2 || true
  "${KUBECTL[@]}" -n "${NAMESPACE}" get svc -o wide >&2 || true
  # Generic, whatever provides load balancers (MetalLB, a cloud provider...):
  # the service's events show why no external address was allocated.
  "${KUBECTL[@]}" -n "${NAMESPACE}" describe service "${SERVICE_NAME}" >&2 || true
  "${KUBECTL[@]}" -n "${NAMESPACE}" get events --sort-by='.lastTimestamp' >&2 || true
}

if ! "${KUBECTL[@]}" -n "${NAMESPACE}" get service "${SERVICE_NAME}" >/dev/null 2>&1; then
  log "Service '${SERVICE_NAME}' does not exist in namespace '${NAMESPACE}'."
  diagnostics
  exit 1
fi

log "Waiting for pods in namespace '${NAMESPACE}' to become ready (timeout: ${POD_READY_TIMEOUT_SECONDS}s)."
if ! "${KUBECTL[@]}" -n "${NAMESPACE}" wait \
  --for=condition=Ready pod \
  --all \
  --timeout="${POD_READY_TIMEOUT_SECONDS}s" >/dev/null; then
  log "Not all Online Boutique pods became ready."
  diagnostics
  exit 1
fi

DEADLINE=$((SECONDS + ENDPOINT_WAIT_TIMEOUT_SECONDS))
ENDPOINT=""

log "Waiting for LoadBalancer endpoint on service '${SERVICE_NAME}' (timeout: ${ENDPOINT_WAIT_TIMEOUT_SECONDS}s)."
while (( SECONDS < DEADLINE )); do
  ENDPOINT="$(
    "${KUBECTL[@]}" -n "${NAMESPACE}" get service "${SERVICE_NAME}" \
      -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true
  )"

  if [[ -z "${ENDPOINT}" ]]; then
    ENDPOINT="$(
      "${KUBECTL[@]}" -n "${NAMESPACE}" get service "${SERVICE_NAME}" \
        -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || true
    )"
  fi

  if [[ -n "${ENDPOINT}" ]]; then
    break
  fi

  sleep "${HTTP_RETRY_DELAY_SECONDS}"
done

if [[ -z "${ENDPOINT}" ]]; then
  log "No external endpoint was allocated to service '${SERVICE_NAME}'."
  diagnostics
  exit 1
fi

TARGET_URL="http://${ENDPOINT}"
log "Allocated frontend endpoint: ${TARGET_URL}"
log "Waiting for an HTTP response from the frontend (timeout: ${HTTP_WAIT_TIMEOUT_SECONDS}s)."
DEADLINE=$((SECONDS + HTTP_WAIT_TIMEOUT_SECONDS))

while (( SECONDS < DEADLINE )); do
  # Any HTTP response proves TCP/HTTP reachability, including redirects or
  # application-level non-2xx responses. Do not require a specific status here.
  if curl --silent --show-error \
    --output /dev/null \
    --max-time "${HTTP_REQUEST_TIMEOUT_SECONDS}" \
    "${TARGET_URL}"; then
    log "Frontend is reachable: ${TARGET_URL}"
    printf '%s\n' "${TARGET_URL}"
    exit 0
  fi

  sleep "${HTTP_RETRY_DELAY_SECONDS}"
done

log "Frontend endpoint was allocated but did not become reachable: ${TARGET_URL}"
diagnostics
exit 1
