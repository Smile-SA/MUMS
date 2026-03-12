#!/bin/bash
# Usage: ./kind.sh <action> <seed> [--workers "<list>"]
# Actions: create, destroy, collect_logs
#
# --workers format : "count=N,cpu=X,memory=YGi;count=M,cpu=A,memory=BGi;..."
#   Les ressources cpu/memory définissent ce que le worker expose dans le champ
#   Allocatable (visible par le scheduler). La Capacity reste celle du host.
#   Implémenté via system-reserved kubelet (compatible cgroup v1, pas besoin de Docker limits).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UTILS_DIR="$SCRIPT_DIR/../utils"

ACTION=$1
SEED=$2
shift 2

CLUSTER_NAME="kind-test-${SEED}"
KUBECONFIG_PATH="/tmp/kubeconfig-${CLUSTER_NAME}"
METALLB_IP_RANGE="172.18.240.0-172.18.255.254"
WORKERS_PARAM=""

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

# ─── Helpers ressources ───────────────────────────────────────────────────────

HOST_CPU=$(nproc)
HOST_CPU_MILLI=$(( HOST_CPU * 1000 ))
HOST_MEM_MI=$(( $(grep MemTotal /proc/meminfo | awk '{print $2}') / 1024 ))

cpu_to_milli() {
    local cpu=${1,,}
    if [[ $cpu =~ ^([0-9]+)m$ ]]; then
        echo "${BASH_REMATCH[1]}"
    elif [[ $cpu =~ ^([0-9]+)$ ]]; then
        echo $(( ${BASH_REMATCH[1]} * 1000 ))
    else
        echo "ERREUR: format CPU non reconnu: '$1' (attendu: entier ou millicores ex: 2 ou 500m)" >&2
        exit 1
    fi
}

mem_to_mi() {
    local mem=${1^^}
    if [[ $mem =~ ^([0-9]+)GI$ ]]; then
        echo $(( ${BASH_REMATCH[1]} * 1024 ))
    elif [[ $mem =~ ^([0-9]+)MI$ ]]; then
        echo "${BASH_REMATCH[1]}"
    elif [[ $mem =~ ^([0-9]+)G$ ]]; then
        echo $(( ${BASH_REMATCH[1]} * 1000 ))
    elif [[ $mem =~ ^([0-9]+)M$ ]]; then
        echo "${BASH_REMATCH[1]}"
    else
        echo "ERREUR: format mémoire non reconnu: '$1' (attendu: Gi, Mi, G, M)" >&2
        exit 1
    fi
}

# ─── Génération du YAML Kind ──────────────────────────────────────────────────

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

        local reserved_parts=()
        if [ -n "$CPU" ]; then
            local desired_milli
            desired_milli=$(cpu_to_milli "$CPU")
            local reserved_milli=$(( HOST_CPU_MILLI - desired_milli ))
            if [ "$reserved_milli" -lt 0 ]; then
                echo "ERREUR: cpu=$CPU demandé mais le host n'a que ${HOST_CPU_MILLI}m CPUs" >&2
                exit 1
            fi
            reserved_parts+=("cpu=${reserved_milli}m")
        fi
        if [ -n "$MEM" ]; then
            local desired_mi
            desired_mi=$(mem_to_mi "$MEM")
            local reserved_mi=$(( HOST_MEM_MI - desired_mi ))
            if [ "$reserved_mi" -lt 0 ]; then
                echo "ERREUR: memory=$MEM demandé mais le host n'a que ${HOST_MEM_MI}Mi" >&2
                exit 1
            fi
            reserved_parts+=("memory=${reserved_mi}Mi")
        fi

        for ((i=1; i<=COUNT; i++)); do
            yaml+="  - role: worker\n"
            if [ "${#reserved_parts[@]}" -gt 0 ]; then
                local reserved_str
                reserved_str=$(IFS=','; echo "${reserved_parts[*]}")
                yaml+="    kubeadmConfigPatches:\n"
                yaml+="    - |\n"
                yaml+="      kind: JoinConfiguration\n"
                yaml+="      nodeRegistration:\n"
                yaml+="        kubeletExtraArgs:\n"
                yaml+="          system-reserved: \"${reserved_str}\"\n"
            fi
        done
    done

    echo -e "$yaml"
}

# ─── Actions ──────────────────────────────────────────────────────────────────

case "$ACTION" in
    create)
        echo "=== Création du cluster Kind: $CLUSTER_NAME ===" >&2
        echo "    Host: ${HOST_CPU} CPUs (${HOST_CPU_MILLI}m), ${HOST_MEM_MI}Mi RAM" >&2

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

        "$UTILS_DIR/metallb/deploy.sh" "$KUBECONFIG_PATH" "$METALLB_IP_RANGE"
        "$UTILS_DIR/prometheus/deploy.sh" "$KUBECONFIG_PATH" 

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
