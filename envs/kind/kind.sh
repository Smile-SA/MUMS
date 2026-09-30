#!/usr/bin/env bash
# Kind environment module (contract 1).
#
# Usage:
#   kind.sh create <seed> <id> <output_file> --extras_dir <dir> --node_image <image> [--workers <json>] [--cgroups v1|v2]
#   kind.sh destroy <id> --extras_dir <dir> [...]
#
# <id> names the cluster and its Docker network. `destroy <id>` removes whatever
# exists for that id (cluster complete, partial, or absent): it never fails
# because something is missing.
#
# --workers: JSON mapping {"count": N, "cpu": X, "memory": "YGi"}.
# --cgroups: how cpu/memory are enforced on each worker.
#   v1 (default, works on any host): kubelet system-reserved. Workers expose the
#       requested cpu/memory as Allocatable, but their Capacity stays the HOST's
#       values: tools that read Capacity (e.g. some optimizers such as
#       Koordinator) see wrong node sizes.
#   v2 (cgroup v2 hosts only): Docker limits (docker update --cpus/--memory)
#       after creation. Workers' Capacity is the requested cpu/memory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
UTILS_DIR="${BENCHMARK_UTILS_PATH:?BENCHMARK_UTILS_PATH is not set}"

# kind binary: the system's one (on PATH), or a module-local pinned version (see kind-version).
KIND_VERSION="$(tr -d '[:space:]' < "${SCRIPT_DIR}/kind-version")"
if [ "$KIND_VERSION" = "system" ]; then
    KIND="kind"
else
    KIND="${SCRIPT_DIR}/.bin/kind-${KIND_VERSION}"
fi

usage() {
    echo "Usage:" >&2
    echo "  $0 create <seed> <id> <output_file> --extras_dir <dir> --node_image <image> [--workers <json>] [--cgroups v1|v2]" >&2
    echo "  $0 destroy <id> --extras_dir <dir>" >&2
    exit 1
}

ACTION="${1:-}"
[ -n "$ACTION" ] || usage
shift

case "$ACTION" in
    create)
        [ "$#" -ge 3 ] || usage
        SEED="$1"; ID="$2"; OUTPUT_FILE="$3"
        shift 3
        ;;
    destroy)
        [ "$#" -ge 1 ] || usage
        ID="$1"
        shift
        ;;
    *)
        echo "ERROR: unknown action '$ACTION'" >&2
        usage
        ;;
esac

EXTRAS_DIR=""
NODE_IMAGE=""
WORKERS_JSON='{}'
CGROUPS="v1"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --extras_dir) EXTRAS_DIR="$2";   shift 2 ;;
        --node_image) NODE_IMAGE="$2";   shift 2 ;;
        --workers)    WORKERS_JSON="$2"; shift 2 ;;
        --cgroups)    CGROUPS="$2";      shift 2 ;;
        *)
            echo "ERROR: unknown option '$1'" >&2
            usage
            ;;
    esac
done

CLUSTER_NAME="$ID"
DOCKER_NETWORK="$ID"

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
    local count cpu mem
    count="$(jq -r '.count // 1' <<< "$WORKERS_JSON")"
    cpu="$(jq -r '.cpu // empty' <<< "$WORKERS_JSON")"
    mem="$(jq -r '.memory // empty' <<< "$WORKERS_JSON")"

    cat <<'YAML'
kind: Cluster
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
          - key: "node-role.kubernetes.io/control-plane"
            effect: "NoSchedule"
    - |
      # cgroupRoot: / is required by some optimizers (e.g. Koordinator)
      kind: KubeletConfiguration
      cgroupRoot: /
YAML

    local reserved_parts=()
    if [ "$CGROUPS" = "v2" ]; then
        cpu=""; mem=""   # enforced with Docker limits after creation (apply_docker_limits)
    fi
    if [ -n "$cpu" ]; then
        local desired_milli reserved_milli
        desired_milli=$(cpu_to_milli "$cpu")
        reserved_milli=$(( HOST_CPU_MILLI - desired_milli ))
        if [ "$reserved_milli" -lt 0 ]; then
            echo "ERROR: cpu=$cpu requested but host only has ${HOST_CPU_MILLI}m CPUs" >&2
            exit 1
        fi
        reserved_parts+=("cpu=${reserved_milli}m")
    fi
    if [ -n "$mem" ]; then
        local desired_mi reserved_mi
        desired_mi=$(mem_to_mi "$mem")
        reserved_mi=$(( HOST_MEM_MI - desired_mi ))
        if [ "$reserved_mi" -lt 0 ]; then
            echo "ERROR: memory=$mem requested but host only has ${HOST_MEM_MI}Mi" >&2
            exit 1
        fi
        reserved_parts+=("memory=${reserved_mi}Mi")
    fi

    local i reserved_str
    for ((i = 1; i <= count; i++)); do
        echo "  - role: worker"
        if [ "${#reserved_parts[@]}" -gt 0 ]; then
            reserved_str=$(IFS=','; echo "${reserved_parts[*]}")
            echo "    kubeadmConfigPatches:"
            echo "    - |"
            echo "      kind: JoinConfiguration"
            echo "      nodeRegistration:"
            echo "        kubeletExtraArgs:"
            echo "          system-reserved: \"${reserved_str}\""
        fi
    done
}

# ─── cgroup v2 mode: Docker limits ───────────────────────────────────────────

host_cgroup_mode() {
    case "$(stat -fc %T /sys/fs/cgroup 2>/dev/null || true)" in
        cgroup2fs) echo "v2" ;;
        tmpfs)     echo "v1" ;;
        *)         echo "unknown" ;;
    esac
}

cpu_to_cores() {
    local cpu=${1,,}
    if [[ $cpu =~ ^([0-9]+)m$ ]]; then
        awk -v m="${BASH_REMATCH[1]}" 'BEGIN { printf "%.3f", m / 1000 }'
    elif [[ $cpu =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
        echo "$cpu"
    else
        echo "ERROR: unrecognized CPU format: '$1'" >&2
        exit 1
    fi
}

# Applies the workers' cpu/memory as Docker limits, so that their Capacity is
# the requested value. Requires a cgroup v2 host.
apply_docker_limits() {
    local cpu mem args=() container
    cpu="$(jq -r '.cpu // empty' <<< "$WORKERS_JSON")"
    mem="$(jq -r '.memory // empty' <<< "$WORKERS_JSON")"
    [ -n "$cpu" ] && args+=(--cpus "$(cpu_to_cores "$cpu")")
    if [ -n "$mem" ]; then
        local bytes=$(( $(mem_to_mi "$mem") * 1024 * 1024 ))
        args+=(--memory "$bytes" --memory-swap "$bytes")
    fi
    [ "${#args[@]}" -gt 0 ] || return 0
    while read -r container; do
        echo "    Docker limits on ${container}: ${args[*]}"
        docker update "${args[@]}" "$container" >/dev/null
    done < <(docker ps --format '{{.Names}}' | grep -E "^${CLUSTER_NAME}-worker[0-9]*$" | sort)
}

# ─── Node image check ────────────────────────────────────────────────────────

# The node image comes from --node_image only. This only checks that it can run
# on this host: Kubernetes v1.35+ does not start kubelet on cgroup v1.
check_node_image() {
    local image="$1" cgroup_mode
    cgroup_mode="$(host_cgroup_mode)"

    if [[ "$image" =~ :v([0-9]+)\.([0-9]+) ]]; then
        local major="${BASH_REMATCH[1]}" minor="${BASH_REMATCH[2]}"
        if [ "$cgroup_mode" = "v1" ] && (( major > 1 || (major == 1 && minor >= 35) )); then
            echo "ERROR: node image '$image' (Kubernetes v${major}.${minor}) cannot run on this cgroup v1 host." >&2
            echo "       Kubernetes v1.35+ does not start kubelet on cgroup v1: use a cgroup v2 host," >&2
            echo "       or a pre-v1.35 image (--node_image, e.g. kindest/node:v1.34.0)." >&2
            exit 1
        fi
    else
        echo "[WARN] Could not read a Kubernetes version from node image '$image': compatibility not checked." >&2
    fi

    if [ "$cgroup_mode" = "v1" ]; then
        echo "[WARN] Host uses cgroup v1 (deprecated by Kubernetes and kind)." >&2
    fi
}

# ─── Actions ──────────────────────────────────────────────────────────────────

case "$ACTION" in
    create)
        if [ -z "$EXTRAS_DIR" ]; then
            echo "ERROR: --extras_dir is required for create" >&2
            exit 1
        fi
        if [ -z "$NODE_IMAGE" ]; then
            echo "ERROR: --node_image is required for create" >&2
            exit 1
        fi
        case "$CGROUPS" in
            v1) ;;
            v2)
                if [ "$(host_cgroup_mode)" != "v2" ]; then
                    echo "ERROR: --cgroups v2 requires a cgroup v2 host (this host: $(host_cgroup_mode))." >&2
                    exit 1
                fi
                ;;
            *) echo "ERROR: --cgroups must be v1 or v2 (got '$CGROUPS')" >&2; exit 1 ;;
        esac
        mkdir -p "$EXTRAS_DIR"
        KUBECONFIG_PATH="${EXTRAS_DIR}/kubeconfig"
        KIND_CONFIG="${EXTRAS_DIR}/kind-config.yaml"

        if docker network inspect "$DOCKER_NETWORK" >/dev/null 2>&1; then
            echo "ERROR: environment '$ID' already exists (Docker network '$DOCKER_NETWORK')." >&2
            echo "       Remove it with: $0 destroy $ID" >&2
            exit 1
        fi

        echo "=== Creating Kind cluster: $CLUSTER_NAME (seed $SEED) ==="
        echo "    Host: ${HOST_CPU} CPUs (${HOST_CPU_MILLI}m), ${HOST_MEM_MI}Mi RAM"

        generate_kind_yaml > "$KIND_CONFIG"
        echo "--- Kind config (${KIND_CONFIG}) ---"
        cat "$KIND_CONFIG"
        echo "------------------------------------"

        check_node_image "$NODE_IMAGE"
        echo "    Kind node image: ${NODE_IMAGE}"

        # WARNING: KIND_EXPERIMENTAL_DOCKER_NETWORK is an experimental Kind feature.
        # (cf. https://github.com/kubernetes-sigs/kind/issues/273)
        export KIND_EXPERIMENTAL_DOCKER_NETWORK="$DOCKER_NETWORK"

        "$KIND" create cluster \
            --name "$CLUSTER_NAME" \
            --kubeconfig "$KUBECONFIG_PATH" \
            --config "$KIND_CONFIG" \
            --image "${NODE_IMAGE}"

        if [ "$CGROUPS" = "v2" ]; then
            echo "=== Applying worker Docker limits (cgroups v2) ==="
            apply_docker_limits
        fi

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
            echo "    MetalLB address ranges: ${RANGE4}, ${RANGE6}"
            "${UTILS_DIR}/metallb/deploy.sh" "$KUBECONFIG_PATH" "$RANGE4" "$RANGE6"
        else
            echo "    MetalLB address range: ${RANGE4}"
            "${UTILS_DIR}/metallb/deploy.sh" "$KUBECONFIG_PATH" "$RANGE4"
        fi

        echo "$KUBECONFIG_PATH" > "$OUTPUT_FILE"
        ;;

    destroy)
        # Must succeed whatever exists for this id: complete, partial, or nothing.
        echo "=== Destroying Kind cluster: $CLUSTER_NAME ==="
        "$KIND" delete cluster --name "$CLUSTER_NAME" || true
        docker network rm "$DOCKER_NETWORK" >/dev/null 2>&1 || true
        if [ -n "$EXTRAS_DIR" ]; then
            rm -f "${EXTRAS_DIR}/kubeconfig"
        fi
        ;;
esac
