#!/bin/bash
# Usage: ./kind_v2.sh <action> <seed> [--workers "<list>"]
# Actions: create, destroy, collect_logs
#
# --workers format : "count=N,cpu=X,memory=YGi;count=M,cpu=A,memory=BGi;..."
#   Les ressources cpu/memory sont appliquées via Docker limits après création
#   du cluster. Nécessite cgroup v2 pour que le worker voie les bonnes Capacity.
#
# Différence avec kind_v1.sh :
#   v1 → system-reserved (Allocatable réduit, Capacity = host)  [cgroup v1 OK]
#   v2 → docker limits   (Capacity réduite = valeur réelle)     [cgroup v2 requis]

set -e

ACTION=$1
SEED=$2
shift 2

CLUSTER_NAME="kind-test-${SEED}"
KUBECONFIG_PATH="/tmp/kubeconfig-${CLUSTER_NAME}"
WORKERS_PARAM=""

# Récupérer le paramètre --workers si fourni
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --workers)
            WORKERS_PARAM="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

# ─── Vérification cgroup v2 ───────────────────────────────────────────────────

check_cgroup_v2() {
    local fstype
    fstype=$(stat -fc %T /sys/fs/cgroup/ 2>/dev/null || echo "unknown")
    if [ "$fstype" != "cgroup2fs" ]; then
        echo "ERREUR: cgroup v2 requis (détecté: '$fstype')." >&2
        echo "  Active cgroup v2 via: GRUB_CMDLINE_LINUX=\"systemd.unified_cgroup_hierarchy=1\" puis reboot." >&2
        exit 1
    fi
}

# ─── Helpers ressources ───────────────────────────────────────────────────────

# Convertit une valeur mémoire (ex: "4Gi", "512Mi", "4G", "512M", "4g", "512m")
# en format Docker (bytes entiers)
mem_to_bytes() {
    local mem=${1^^}  # uppercase pour comparaison insensible à la casse
    if [[ $mem =~ ^([0-9]+)GI$ ]]; then
        echo $(( ${BASH_REMATCH[1]} * 1024 * 1024 * 1024 ))
    elif [[ $mem =~ ^([0-9]+)MI$ ]]; then
        echo $(( ${BASH_REMATCH[1]} * 1024 * 1024 ))
    elif [[ $mem =~ ^([0-9]+)G$ ]]; then
        echo $(( ${BASH_REMATCH[1]} * 1000 * 1000 * 1000 ))
    elif [[ $mem =~ ^([0-9]+)M$ ]]; then
        echo $(( ${BASH_REMATCH[1]} * 1000 * 1000 ))
    else
        echo "ERREUR: format mémoire non reconnu: '$1' (attendu: Gi, Mi, G, M)" >&2
        exit 1
    fi
}

# ─── Génération du YAML Kind ──────────────────────────────────────────────────

# Ici le YAML est minimal : pas de kubeadmConfigPatches nécessaire.
# Les limites seront appliquées via docker update après création.
generate_kind_yaml() {
    local yaml
    yaml="kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
"

    if [ -z "$WORKERS_PARAM" ]; then
        echo -e "$yaml"
        return
    fi

    IFS=';' read -ra WORKER_LIST <<< "$WORKERS_PARAM"
    for w in "${WORKER_LIST[@]}"; do
        IFS=',' read -ra PROPS <<< "$w"
        COUNT=1
        for p in "${PROPS[@]}"; do
            key=${p%=*}
            value=${p#*=}
            [ "$key" = "count" ] && COUNT=$value
        done
        for ((i=1; i<=COUNT; i++)); do
            yaml+="  - role: worker\n"
        done
    done

    echo -e "$yaml"
}

# ─── Application des Docker limits ───────────────────────────────────────────

apply_worker_limits() {
    if [ -z "$WORKERS_PARAM" ]; then return; fi

    # Liste ordonnée des conteneurs workers du cluster
    mapfile -t WORKER_CONTAINERS < <(
        docker ps --format '{{.Names}}' \
        | grep "^${CLUSTER_NAME}-worker" \
        | sort
    )

    IFS=';' read -ra WORKER_LIST <<< "$WORKERS_PARAM"
    local idx=0
    for w in "${WORKER_LIST[@]}"; do
        IFS=',' read -ra PROPS <<< "$w"
        COUNT=1
        CPU=""
        MEM=""
        for p in "${PROPS[@]}"; do
            key=${p%=*}
            value=${p#*=}
            case "$key" in
                count)  COUNT=$value ;;
                cpu)    CPU=$value   ;;
                memory) MEM=$value   ;;
            esac
        done

        for ((i=0; i<COUNT; i++)); do
            local container="${WORKER_CONTAINERS[$idx]}"
            if [ -z "$container" ]; then
                echo "ERREUR: pas assez de conteneurs workers (attendu idx=$idx)" >&2
                exit 1
            fi

            echo "  Limites sur $container : cpu=${CPU:-inchangé} memory=${MEM:-inchangé}" >&2

            local docker_args=()
            [ -n "$CPU" ] && docker_args+=("--cpus" "$CPU")
            if [ -n "$MEM" ]; then
                local mem_bytes
                mem_bytes=$(mem_to_bytes "$MEM")
                docker_args+=("--memory" "$mem_bytes" "--memory-swap" "$mem_bytes")
            fi

            [ "${#docker_args[@]}" -gt 0 ] && docker update "${docker_args[@]}" "$container"

            idx=$(( idx + 1 ))
        done
    done
}

# ─── Actions ──────────────────────────────────────────────────────────────────

case "$ACTION" in
    create)
        check_cgroup_v2

        echo "=== Création du cluster Kind: $CLUSTER_NAME ===" >&2

        TEMP_YAML=$(mktemp)
        generate_kind_yaml > "$TEMP_YAML"

        if [ "${VERBOSE:-0}" = "1" ]; then
            echo "--- Kind config ---" >&2
            cat "$TEMP_YAML" >&2
            echo "-------------------" >&2
        fi

        kind create cluster \
            --name "$CLUSTER_NAME" \
            --kubeconfig "$KUBECONFIG_PATH" \
            --config "$TEMP_YAML"

        rm "$TEMP_YAML"

        echo "=== Application des Docker limits ===" >&2
        apply_worker_limits

        echo "$KUBECONFIG_PATH"
        ;;

    destroy)
        echo "=== Destruction du cluster Kind: $CLUSTER_NAME ===" >&2
        kind delete cluster --name "$CLUSTER_NAME"
        [ -f "$KUBECONFIG_PATH" ] && rm "$KUBECONFIG_PATH"
        ;;

    collect_logs)
        echo "Collecte de logs non implémentée." >&2
        ;;

    *)
        echo "Usage: $0 <create|destroy|collect_logs> <seed> [--workers \"count=N,cpu=X,memory=YGi;...\"]" >&2
        exit 1
        ;;
esac
