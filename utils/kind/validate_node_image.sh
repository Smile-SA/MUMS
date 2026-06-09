#!/usr/bin/env bash
set -euo pipefail

# This script prints the validated Kind node image on stdout.
# Diagnostics are intentionally written to stderr so callers may safely use:
#   KIND_NODE_IMAGE="$(utils/kind/validate_node_image.sh)"

KIND_NODE_IMAGE="${KIND_NODE_IMAGE:-kindest/node:v1.34.0}"

detect_cgroup_mode() {
  local fs_type
  fs_type="$(stat -fc %T /sys/fs/cgroup 2>/dev/null || true)"

  case "${fs_type}" in
    cgroup2fs)
      printf '%s' "v2"
      ;;
    tmpfs)
      printf '%s' "v1"
      ;;
    *)
      printf '%s' "unknown"
      ;;
  esac
}

extract_kubernetes_major_minor() {
  local image="$1"

  if [[ "${image}" =~ :v([0-9]+)\.([0-9]+)(\.[0-9]+)? ]]; then
    printf '%s %s\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
    return 0
  fi

  return 1
}

CGROUP_MODE="$(detect_cgroup_mode)"

if VERSION_PARTS="$(extract_kubernetes_major_minor "${KIND_NODE_IMAGE}")"; then
  read -r K8S_MAJOR K8S_MINOR <<< "${VERSION_PARTS}"

  if [[ "${CGROUP_MODE}" == "v1" ]] \
    && (( K8S_MAJOR > 1 || (K8S_MAJOR == 1 && K8S_MINOR >= 35) )); then
    cat >&2 <<ERROR
[ERROR] Unsupported Kind node-image selection for this host:
        Host cgroup mode: ${CGROUP_MODE}
        Kind node image:  ${KIND_NODE_IMAGE}

Kubernetes v1.35 and newer do not start kubelet on cgroup v1 by default.
Use a cgroup-v2 host, or select a pre-v1.35 Kind node image.

Verified working selection for the current tested host:
  KIND_NODE_IMAGE=kindest/node:v1.34.0
ERROR
    exit 1
  fi
else
  echo "[WARN] Could not extract a Kubernetes version from KIND_NODE_IMAGE='${KIND_NODE_IMAGE}'. Compatibility cannot be checked automatically." >&2
fi

case "${CGROUP_MODE}" in
  v1)
    echo "[WARN] Host uses cgroup v1; using Kind node image '${KIND_NODE_IMAGE}'." >&2
    ;;
  v2)
    echo "[INFO] Host uses cgroup v2; using Kind node image '${KIND_NODE_IMAGE}'." >&2
    ;;
  *)
    echo "[WARN] Host cgroup mode could not be identified; using Kind node image '${KIND_NODE_IMAGE}'." >&2
    ;;
esac

printf '%s\n' "${KIND_NODE_IMAGE}"
