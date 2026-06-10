#!/usr/bin/env bash
set -euo pipefail

# Print a MetalLB address range on stdout.
# Diagnostic messages are written to stderr so callers may capture the range.
#
# Override behavior:
#   METALLB_IP_RANGE=172.18.255.205-172.18.255.254 ./utils/metallb/select_ip_range.sh
#
# Automatic behavior:
#   METALLB_IP_RANGE=auto ./utils/metallb/select_ip_range.sh

METALLB_IP_RANGE="${METALLB_IP_RANGE:-auto}"
KIND_NETWORK_NAME="${KIND_NETWORK_NAME:-kind}"
METALLB_POOL_SIZE="${METALLB_POOL_SIZE:-50}"

if [[ "${METALLB_IP_RANGE}" != "auto" ]]; then
  echo "[INFO] Using explicitly configured MetalLB range: ${METALLB_IP_RANGE}" >&2
  printf '%s\n' "${METALLB_IP_RANGE}"
  exit 0
fi

if ! docker network inspect "${KIND_NETWORK_NAME}" >/dev/null 2>&1; then
  echo "[ERROR] Docker network '${KIND_NETWORK_NAME}' does not exist. Create the Kind cluster before selecting an automatic MetalLB range." >&2
  exit 1
fi

SUBNET="$(
  docker network inspect "${KIND_NETWORK_NAME}" \
    --format '{{range .IPAM.Config}}{{if .Subnet}}{{.Subnet}}{{"\n"}}{{end}}{{end}}' \
    | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/[0-9]+$' \
    | head -n 1
)"

if [[ -z "${SUBNET}" ]]; then
  echo "[ERROR] Could not determine an IPv4 subnet for Docker network '${KIND_NETWORK_NAME}'." >&2
  exit 1
fi

RANGE="$(
  python3 - "${SUBNET}" "${METALLB_POOL_SIZE}" <<'PY'
import ipaddress
import sys

subnet_text = sys.argv[1]
pool_size = int(sys.argv[2])

if pool_size < 2:
    raise SystemExit("METALLB_POOL_SIZE must be at least 2.")

network = ipaddress.ip_network(subnet_text, strict=False)

if network.version != 4:
    raise SystemExit(f"Only IPv4 Kind networks are currently supported; got {network}.")

usable_count = max(0, network.num_addresses - 2)
if usable_count < pool_size:
    raise SystemExit(
        f"Kind network {network} has only {usable_count} usable IPv4 addresses, "
        f"which is insufficient for a requested MetalLB pool of {pool_size}."
    )

# Use a compact high-address range. Kind node containers are normally allocated
# from the low part of the Docker subnet, while the high range avoids overlap and
# follows conventional MetalLB local-cluster configurations.
end = int(network.broadcast_address) - 1
start = end - pool_size + 1

# Never emit an endpoint whose final octet is .0 as the first automatically
# allocated service IP. It may be valid in a larger parent subnet, but avoiding
# it reduces ambiguity in local routing/debugging and prevents repeating the
# endpoint shape observed during the failed manual test.
if int(ipaddress.ip_address(start).packed[-1]) == 0:
    start += 1

if start > end:
    raise SystemExit("Failed to derive a non-empty MetalLB address range.")

print(f"{ipaddress.ip_address(start)}-{ipaddress.ip_address(end)}")
PY
)"

echo "[INFO] Kind Docker subnet: ${SUBNET}" >&2
echo "[INFO] Automatically selected MetalLB range: ${RANGE}" >&2
printf '%s\n' "${RANGE}"