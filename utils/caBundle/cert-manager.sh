#!/usr/bin/env bash
# cert-manager.sh — Manages the TLS certificate for a MutatingWebhook
#
# Usage:
#   ./cert-manager.sh check  --service <name> --namespace <ns>
#   ./cert-manager.sh create --service <name> --namespace <ns> --secret <secret-name>
#   ./cert-manager.sh delete --service <name> --namespace <ns> --secret <secret-name>
#
# Example:
#   ./cert-manager.sh create --service basic-rescheduler --namespace rescheduler-system --secret rescheduler-tls

set -euo pipefail

# ── Helpers ────────────────────────────────────────────────────────────────────

usage() {
    grep '^#' "$0" | grep -v '#!/' | sed 's/^# \{0,1\}//'
    exit 1
}

log()  { echo "[cert-manager] $*"; }
err()  { echo "[cert-manager] ERROR: $*" >&2; exit 1; }

require() {
    for cmd in "$@"; do
        command -v "$cmd" &>/dev/null || err "Required command not found: $cmd"
    done
}

# ── Parse arguments ─────────────────────────────────────────────────────────────

COMMAND=""
SERVICE=""
NAMESPACE=""
SECRET=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        check|create|delete) COMMAND="$1" ;;
        --service)    SERVICE="$2";    shift ;;
        --namespace)  NAMESPACE="$2";  shift ;;
        --secret)     SECRET="$2";     shift ;;
        -h|--help)    usage ;;
        *) err "Unknown argument: $1" ;;
    esac
    shift
done

[[ -z "$COMMAND" ]]   && usage
[[ -z "$SERVICE" ]]   && err "--service is required"
[[ -z "$NAMESPACE" ]] && err "--namespace is required"

# Full DNS name of the service — used as the certificate CN.
# Format: <service>.<namespace>.svc
# Kubernetes resolves this DNS name to the Service ClusterIP.
DNS_NAME="${SERVICE}.${NAMESPACE}.svc"
CSR_NAME="${SERVICE}-tls-csr"

# ── Command: check ─────────────────────────────────────────────────────────────
# Checks whether an approved CSR and a TLS Secret already exist.

cmd_check() {
    log "Checking certificate for $DNS_NAME..."

    local ok=true

    # Check the Kubernetes CSR.
    if kubectl get csr "$CSR_NAME" &>/dev/null; then
        local condition
        condition=$(kubectl get csr "$CSR_NAME" -o jsonpath='{.status.conditions[0].type}' 2>/dev/null || echo "")
        if [[ "$condition" == "Approved" ]]; then
            log "✓ CSR '$CSR_NAME' exists and is approved"
        else
            log "✗ CSR '$CSR_NAME' exists but is not approved (state: ${condition:-unknown})"
            ok=false
        fi
    else
        log "✗ CSR '$CSR_NAME' does not exist"
        ok=false
    fi

    # Check the TLS Secret (only when --secret is provided).
    if [[ -n "$SECRET" ]]; then
        if kubectl get secret "$SECRET" -n "$NAMESPACE" &>/dev/null; then
            log "✓ Secret '$SECRET' exists in namespace '$NAMESPACE'"
        else
            log "✗ Secret '$SECRET' not found in namespace '$NAMESPACE'"
            ok=false
        fi
    fi

    if $ok; then
        log "✓ All good"
        return 0
    else
        log "✗ Certificate incomplete or missing — run 'create'"
        return 1
    fi
}

# ── Command: create ────────────────────────────────────────────────────────────
# Generates a private key, submits a CSR, approves it, retrieves the cert,
# and creates the TLS Secret.

cmd_create() {
    [[ -z "$SECRET" ]] && err "--secret is required for create"

    require openssl kubectl

    local tmpdir
    tmpdir=$(mktemp -d)
    trap "rm -rf $tmpdir" EXIT

    log "Generating RSA 2048 private key..."
    # tls.key: private key — never leaves the Secret, never committed.
    openssl genrsa -out "$tmpdir/tls.key" 2048 2>/dev/null

    log "Generating CSR (CN=$DNS_NAME)..."
    # The CN must match the Service DNS name exactly.
    # kube-apiserver validates this CN when calling the webhook.
    openssl req -new \
        -key "$tmpdir/tls.key" \
        -out "$tmpdir/tls.csr" \
        -subj "/CN=${DNS_NAME}" \
        -addext "subjectAltName=DNS:${DNS_NAME},DNS:${DNS_NAME}.cluster.local" \
        2>/dev/null

    log "Submitting CSR to the Kubernetes API..."
    # The CSR is base64-encoded and submitted as a CertificateSigningRequest object.
    # Kubernetes signs it with its own CA — that CA goes into caBundle.
    local csr_b64
    csr_b64=$(base64 < "$tmpdir/tls.csr" | tr -d '\n')

    kubectl apply -f - <<EOF
apiVersion: certificates.k8s.io/v1
kind: CertificateSigningRequest
metadata:
  name: ${CSR_NAME}
spec:
  request: ${csr_b64}
  signerName: kubernetes.io/kube-apiserver-client
  usages:
    - digital signature
    - key encipherment
    - server auth
EOF

    log "Approving CSR..."
    # In production this step may be delegated to a human or an approval controller.
    kubectl certificate approve "$CSR_NAME"

    log "Waiting for signed certificate..."
    local retries=10
    while [[ $retries -gt 0 ]]; do
        local cert
        cert=$(kubectl get csr "$CSR_NAME" -o jsonpath='{.status.certificate}' 2>/dev/null || echo "")
        if [[ -n "$cert" ]]; then
            echo "$cert" | base64 --decode > "$tmpdir/tls.crt"
            log "✓ Certificate received"
            break
        fi
        sleep 2
        ((retries--))
    done
    [[ $retries -eq 0 ]] && err "Timeout: certificate was not issued"

    log "Creating TLS Secret '$SECRET' in '$NAMESPACE'..."
    # tls.crt = certificate signed by the cluster CA
    # tls.key = locally generated private key
    kubectl create secret tls "$SECRET" \
        --cert="$tmpdir/tls.crt" \
        --key="$tmpdir/tls.key" \
        --namespace="$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -

    log "Retrieving caBundle (cluster CA)..."
    # The caBundle is the cluster's public CA.
    # Pass it to kube-apiserver in the MutatingWebhookConfiguration
    # so it can verify the certificate presented by the webhook pod.
    local ca_bundle
    ca_bundle=$(kubectl get configmap kube-root-ca.crt \
        -n "$NAMESPACE" \
        -o jsonpath='{.data.ca\.crt}' | base64 | tr -d '\n')

    log ""
    log "✓ Certificate created successfully"
    log ""
    log "Use in your MutatingWebhookConfiguration:"
    log ""
    echo "  caBundle: ${ca_bundle}"
    log ""
    log "Mount the Secret in your Deployment:"
    log ""
    cat <<EOF
  volumes:
    - name: tls
      secret:
        secretName: ${SECRET}
  containers:
    - volumeMounts:
        - name: tls
          mountPath: /tls
          readOnly: true
EOF
}

# ── Command: delete ────────────────────────────────────────────────────────────

cmd_delete() {
    [[ -z "$SECRET" ]] && err "--secret is required for delete"

    log "Deleting CSR '$CSR_NAME'..."
    kubectl delete csr "$CSR_NAME" --ignore-not-found

    log "Deleting Secret '$SECRET' in '$NAMESPACE'..."
    kubectl delete secret "$SECRET" -n "$NAMESPACE" --ignore-not-found

    log "✓ Cleaned up"
}

# ── Dispatch ────────────────────────────────────────────────────────────────────

case "$COMMAND" in
    check)  cmd_check ;;
    create) cmd_create ;;
    delete) cmd_delete ;;
esac
