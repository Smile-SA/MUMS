#!/bin/bash
# Usage: ./kind.sh <action> <seed> [options]
# Actions: create, destroy
#
# Options:
#   --workers="<list>"    Worker node configuration
#
# --workers format: "count=N,cpu=X,memory=YGi;count=M,cpu=A,memory=BGi;..."
#   cpu/memory set what the worker exposes in the Allocatable field (visible to
#   the scheduler); Capacity remains the host value. Implemented via
#   system-reserved kubelet config — works on cgroup v1, no Docker limits needed.
#
#   Alternative (cgroup v2 only): apply constraints via `docker update --cpus /
#   --memory` after cluster creation, which reduces the real Capacity instead of
#   Allocatable. Useful when schedulers read Capacity directly (e.g. Koordinator).
#   See kind_v2.sh in git history for a reference implementation.
#
# Prints the kubeconfig path to stdout.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
UTILS_DIR="$SCRIPT_DIR/../utils"

ACTION=$1
SEED=$2
shift 2

CLUSTER_NAME="kind-test-${SEED}"
KUBECONFIG_PATH="/tmp/kubeconfig-${CLUSTER_NAME}"
KIND_NODE_IMAGE="${KIND_NODE_IMAGE:-kindest/node:v1.34.0}"
METALLB_IP_RANGE="${METALLB_IP_RANGE:-auto}"
METALLB_POOL_SIZE="${METALLB_POOL_SIZE:-50}"

WORKERS_PARAM=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
       --workers=*) WORKERS_PARAM="${1#--workers=}" ; shift ;;
        *)         shift ;;
    esac
done

# ─── Resource helpers ─────────────────────────────────────────────────────────

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
        echo "ERROR: unrecognized CPU format: '$1' (expected: integer or millicores e.g. 2 or 500m)" >&2
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
        echo "ERROR: unrecognized memory format: '$1' (expected: Gi, Mi, G, M)" >&2
        exit 1
    fi
}

# ─── Kind cluster YAML generation ────────────────────────────────────────────

generate_kind_yaml() {
    local yaml
    yaml="kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  ipFamily: dual
nodes:
  - role: control-plane
    kubeadmConfigPatches:
    - |
      kind: InitConfiguration
      nodeRegistration:
        taints:
          - key: \"node-role.kubernetes.io/control-plane\"
            effect: \"NoSchedule\"
    - |
      # cgroupRoot: / is required by some optimizers (e.g. Koordinator)
      kind: KubeletConfiguration
      cgroupRoot: /
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
                echo "ERROR: cpu=$CPU requested but host only has ${HOST_CPU_MILLI}m CPUs" >&2
                exit 1
            fi
            reserved_parts+=("cpu=${reserved_milli}m")
        fi
        if [ -n "$MEM" ]; then
            local desired_mi
            desired_mi=$(mem_to_mi "$MEM")
            local reserved_mi=$(( HOST_MEM_MI - desired_mi ))
            if [ "$reserved_mi" -lt 0 ]; then
                echo "ERROR: memory=$MEM requested but host only has ${HOST_MEM_MI}Mi" >&2
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
        DOCKER_NETWORK="$CLUSTER_NAME"

        if docker network inspect "$DOCKER_NETWORK" >/dev/null 2>&1; then
            echo "ERROR: Docker network '$DOCKER_NETWORK' already exists." >&2
            echo "       Cluster already created with this seed, or previous destroy incomplete?" >&2
            exit 1
        fi

        echo "=== Creating Kind cluster: $CLUSTER_NAME ===" >&2
        echo "    Host: ${HOST_CPU} CPUs (${HOST_CPU_MILLI}m), ${HOST_MEM_MI}Mi RAM" >&2

        TEMP_YAML=$(mktemp)
        generate_kind_yaml > "$TEMP_YAML"

        if [ "${VERBOSE:-0}" = "1" ]; then
            echo "--- Kind config ---" >&2
            cat "$TEMP_YAML" >&2
            echo "-------------------" >&2
        fi

        KIND_NODE_IMAGE="$(
        KIND_NODE_IMAGE="${KIND_NODE_IMAGE}" \
            "${REPO_ROOT}/utils/kind/validate_node_image.sh"
        )"

        echo "    Kind node image: ${KIND_NODE_IMAGE}" >&2
        # WARNING: KIND_EXPERIMENTAL_DOCKER_NETWORK is an experimental Kind feature.
        # (cf. https://github.com/kubernetes-sigs/kind/issues/273)
        export KIND_EXPERIMENTAL_DOCKER_NETWORK="$DOCKER_NETWORK"

        kind create cluster \
            --name "$CLUSTER_NAME" \
            --kubeconfig "$KUBECONFIG_PATH" \
            --config "$TEMP_YAML" \
            --image "${KIND_NODE_IMAGE}"
        rm "$TEMP_YAML"

        # Dedicated Docker network for this cluster: derive the MetalLB pool
        # from the subnet assigned to this cluster network.
        IPAM_JSON=$(docker network inspect "$DOCKER_NETWORK" -f '{{json .IPAM.Config}}')

        # IPv4: use most of the /16, but skip the low range where Docker gateway
        # and Kind node addresses are usually allocated.
        CIDR4=$(echo "$IPAM_JSON" | grep -oE '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/[0-9]{1,2}' | head -n 1)

        if [[ ! "$CIDR4" =~ ^([0-9]+)\.([0-9]+)\.0\.0/16$ ]]; then
            echo "ERROR: unexpected IPv4 subnet for Docker network '$DOCKER_NETWORK': $CIDR4 (expected a /16)" >&2
            exit 1
        fi

        RANGE4="${BASH_REMATCH[1]}.${BASH_REMATCH[2]}.1.0-${BASH_REMATCH[1]}.${BASH_REMATCH[2]}.255.254"

        # IPv6 is optional. If the Docker network has an IPv6 /64, add an IPv6
        # MetalLB range too. If not, keep IPv4-only behavior.
        CIDR6=$(echo "$IPAM_JSON" | grep -oE '[0-9a-fA-F:]+::/64' | head -n 1 || true)

        if [ -n "$CIDR6" ]; then
            if [[ ! "$CIDR6" =~ ^([0-9a-fA-F:]+)::/64$ ]]; then
                echo "ERROR: unexpected IPv6 subnet for Docker network '$DOCKER_NETWORK': $CIDR6 (expected a /64)" >&2
                exit 1
            fi

            RANGE6="${BASH_REMATCH[1]}:1::/80"

            echo "    MetalLB address ranges: ${RANGE4}, ${RANGE6}" >&2
            "$UTILS_DIR/metallb/deploy.sh" "$KUBECONFIG_PATH" "$RANGE4" "$RANGE6" >&2
        else
            echo "    MetalLB address range: ${RANGE4}" >&2
            "$UTILS_DIR/metallb/deploy.sh" "$KUBECONFIG_PATH" "$RANGE4" >&2
        fi
        "$UTILS_DIR/prometheus/deploy.sh" "$KUBECONFIG_PATH" >&2

        echo "$KUBECONFIG_PATH"
        ;;

    destroy)
        echo "=== Destroying Kind cluster: $CLUSTER_NAME ===" >&2
        kind delete cluster --name "$CLUSTER_NAME"
        docker network rm "$CLUSTER_NAME" >/dev/null 2>&1 || true
        [ -f "$KUBECONFIG_PATH" ] && rm "$KUBECONFIG_PATH"
        ;;

    *)
        echo "Usage: $0 <create|destroy> <seed> [--workers \"count=N,cpu=X,memory=YGi;...\"]" >&2
        exit 1
        ;;
esac
