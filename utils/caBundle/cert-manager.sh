#!/usr/bin/env bash
# cert-manager.sh — Gestion du certificat TLS pour le MutatingWebhook
#
# Usage:
#   ./cert-manager.sh check  --service <name> --namespace <ns>
#   ./cert-manager.sh create --service <name> --namespace <ns> --secret <secret-name>
#   ./cert-manager.sh delete --service <name> --namespace <ns> --secret <secret-name>
#
# Exemple:
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
        command -v "$cmd" &>/dev/null || err "Commande requise manquante: $cmd"
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
        *) err "Argument inconnu: $1" ;;
    esac
    shift
done

[[ -z "$COMMAND" ]]   && usage
[[ -z "$SERVICE" ]]   && err "--service requis"
[[ -z "$NAMESPACE" ]] && err "--namespace requis"

# Le nom DNS complet du service — c'est ce qui ira dans le CN du certificat
# Format: <service>.<namespace>.svc
# Kubernetes résoudra ce nom DNS vers le ClusterIP du Service
DNS_NAME="${SERVICE}.${NAMESPACE}.svc"
CSR_NAME="${SERVICE}-tls-csr"

# ── Commande: check ─────────────────────────────────────────────────────────────
# Vérifie si un CSR approuvé et un Secret TLS existent déjà

cmd_check() {
    log "Vérification du certificat pour $DNS_NAME..."

    local ok=true

    # Vérifier le CSR Kubernetes
    if kubectl get csr "$CSR_NAME" &>/dev/null; then
        local condition
        condition=$(kubectl get csr "$CSR_NAME" -o jsonpath='{.status.conditions[0].type}' 2>/dev/null || echo "")
        if [[ "$condition" == "Approved" ]]; then
            log "✓ CSR '$CSR_NAME' existe et est approuvé"
        else
            log "✗ CSR '$CSR_NAME' existe mais n'est pas approuvé (état: ${condition:-inconnu})"
            ok=false
        fi
    else
        log "✗ CSR '$CSR_NAME' n'existe pas"
        ok=false
    fi

    # Vérifier le Secret TLS (seulement si --secret fourni)
    if [[ -n "$SECRET" ]]; then
        if kubectl get secret "$SECRET" -n "$NAMESPACE" &>/dev/null; then
            log "✓ Secret '$SECRET' existe dans le namespace '$NAMESPACE'"
        else
            log "✗ Secret '$SECRET' absent du namespace '$NAMESPACE'"
            ok=false
        fi
    fi

    if $ok; then
        log "✓ Tout est en ordre"
        return 0
    else
        log "✗ Certificat incomplet ou absent — lancez 'create'"
        return 1
    fi
}

# ── Commande: create ────────────────────────────────────────────────────────────
# Génère la clé privée, soumet le CSR, approuve, récupère le cert, crée le Secret

cmd_create() {
    [[ -z "$SECRET" ]] && err "--secret requis pour create"

    require openssl kubectl

    local tmpdir
    tmpdir=$(mktemp -d)
    trap "rm -rf $tmpdir" EXIT

    log "Génération de la clé privée RSA 2048..."
    # tls.key : clé privée — ne quitte jamais le Secret, jamais commitée
    openssl genrsa -out "$tmpdir/tls.key" 2048 2>/dev/null

    log "Génération du CSR (CN=$DNS_NAME)..."
    # Le CN doit correspondre exactement au nom DNS du Service
    # kube-apiserver vérifie ce CN quand il appelle le webhook
    openssl req -new \
        -key "$tmpdir/tls.key" \
        -out "$tmpdir/tls.csr" \
        -subj "/CN=${DNS_NAME}" \
        -addext "subjectAltName=DNS:${DNS_NAME},DNS:${DNS_NAME}.cluster.local" \
        2>/dev/null

    log "Soumission du CSR à l'API Kubernetes..."
    # On encode le CSR en base64 et on le soumet comme objet CertificateSigningRequest
    # K8s utilise sa propre CA pour signer — c'est cette CA qu'on mettra dans caBundle
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

    log "Approbation du CSR..."
    # En prod, cette étape peut être faite par un humain ou un controller d'approbation
    # Ici on approuve directement pour simplifier
    kubectl certificate approve "$CSR_NAME"

    log "Attente du certificat signé..."
    local retries=10
    while [[ $retries -gt 0 ]]; do
        local cert
        cert=$(kubectl get csr "$CSR_NAME" -o jsonpath='{.status.certificate}' 2>/dev/null || echo "")
        if [[ -n "$cert" ]]; then
            echo "$cert" | base64 --decode > "$tmpdir/tls.crt"
            log "✓ Certificat reçu"
            break
        fi
        sleep 2
        ((retries--))
    done
    [[ $retries -eq 0 ]] && err "Timeout: le certificat n'a pas été émis"

    log "Création du Secret TLS '$SECRET' dans '$NAMESPACE'..."
    # Le pod montera ce Secret pour servir du HTTPS
    # tls.crt = certificat signé par la CA du cluster
    # tls.key = clé privée générée localement
    kubectl create secret tls "$SECRET" \
        --cert="$tmpdir/tls.crt" \
        --key="$tmpdir/tls.key" \
        --namespace="$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -

    log "Récupération du caBundle (CA du cluster)..."
    # Le caBundle est la CA publique du cluster
    # On la donne à kube-apiserver dans le MutatingWebhookConfiguration
    # pour qu'il puisse vérifier le cert de notre pod
    local ca_bundle
    ca_bundle=$(kubectl get configmap kube-root-ca.crt \
        -n "$NAMESPACE" \
        -o jsonpath='{.data.ca\.crt}' | base64 | tr -d '\n')

    log ""
    log "✓ Certificat créé avec succès"
    log ""
    log "À utiliser dans votre MutatingWebhookConfiguration:"
    log ""
    echo "  caBundle: ${ca_bundle}"
    log ""
    log "Et dans votre Deployment, monter le Secret:"
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

# ── Commande: delete ────────────────────────────────────────────────────────────

cmd_delete() {
    [[ -z "$SECRET" ]] && err "--secret requis pour delete"

    log "Suppression du CSR '$CSR_NAME'..."
    kubectl delete csr "$CSR_NAME" --ignore-not-found

    log "Suppression du Secret '$SECRET' dans '$NAMESPACE'..."
    kubectl delete secret "$SECRET" -n "$NAMESPACE" --ignore-not-found

    log "✓ Nettoyé"
}

# ── Dispatch ────────────────────────────────────────────────────────────────────

case "$COMMAND" in
    check)  cmd_check ;;
    create) cmd_create ;;
    delete) cmd_delete ;;
esac
