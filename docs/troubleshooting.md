# Troubleshooting the Standalone Benchmark

## Kind cluster creation fails while starting the control plane

### Symptom

Cluster creation fails during `kubeadm init` or while waiting for the kubelet, and the output includes both:

```text
cgroup v1 is deprecated in Kubernetes
```

and a Kind node image at Kubernetes `v1.35.x` or newer.

### Cause

Kubernetes v1.35 and newer do not start kubelet on cgroup v1 hosts by default. The benchmark platform therefore exposes the Kind node image explicitly instead of depending on Kind's current default image.

### Check the host cgroup mode

```bash
stat -fc %T /sys/fs/cgroup/
```

Interpretation:

```text
cgroup2fs  → cgroup v2
tmpfs      → cgroup v1
```

### Supported immediate workaround for a cgroup v1 host

Use the documented compatible image:

```bash
export KIND_NODE_IMAGE=kindest/node:v1.34.0
```

Then create the environment again.

The longer-term host-side improvement is to move the system to cgroup v2.

---

## Online Boutique receives an external IP but `curl` cannot reach it

### Symptom

The service shows an external IP, but:

```bash
curl "http://<frontend-ip>"
```

fails with a routing or connection error.

### Checks

Verify application readiness:

```bash
kubectl --kubeconfig "$KUBECONFIG" -n online-boutique get pods -o wide
kubectl --kubeconfig "$KUBECONFIG" -n online-boutique get svc -o wide
```

Verify MetalLB resources:

```bash
kubectl --kubeconfig "$KUBECONFIG" -n metallb-system get pods -o wide
kubectl --kubeconfig "$KUBECONFIG" -n metallb-system get ipaddresspool,l2advertisement -o yaml
```

Verify the Docker network used by Kind:

```bash
docker network inspect kind \
  --format '{{range .IPAM.Config}}{{.Subnet}}{{"\n"}}{{end}}'
```

### Platform behavior after the fix

The environment script derives a small high-address MetalLB pool from the actual Kind Docker IPv4 subnet unless an explicit range is provided.

The stack and traffic scripts then wait for:

1. Ready application pods.
2. An allocated frontend endpoint.
3. A successful HTTP connection to that endpoint.

The earlier observed address ending in `.0` was associated with a failed reachability test, but the address alone is not definitive proof of the failure cause when the Docker network uses a larger parent prefix. Endpoint validation remains mandatory.

### Explicit MetalLB override

When needed, select a known free range inside the actual Kind Docker subnet:

```bash
export METALLB_IP_RANGE=172.18.255.220-172.18.255.230
```

Do not configure a range outside the Kind Docker network.

---

## Prometheus port forwarding fails because port 9090 is in use

### Symptom

Starting observability fails because another process already uses local port `9090`.

### Check

```bash
ss -ltnp | grep ':9090'
```

### Override

Select a different local port:

```bash
export PROMETHEUS_LOCAL_PORT=19090
```

Use the same port for any local Prometheus/scraper URL configured by the observability script.
