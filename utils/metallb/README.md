# metallb

Util: installs [MetalLB](https://metallb.io) in a cluster, so that `LoadBalancer`
services get an external IP where no cloud provider gives one (e.g. local
clusters).

## Scripts

Called by modules as `$MUMS_UTILS_PATH/metallb/<script>`.

- `deploy.sh <kubeconfig> <ip_range> [<ip_range> ...]`: installs the MetalLB chart
  (version in `chart-version`, through the util `helm`; release `metallb`,
  namespace `metallb-system`), waits for its controller and speakers, then
  declares the given IP ranges (an `IPAddressPool` and an `L2Advertisement`,
  layer 2 mode). An IP range is written as MetalLB expects it, e.g.
  `172.18.255.200-172.18.255.250` or a CIDR.

## Dependencies

kubectl, and the util `helm`. The dependency script fetches the chart (version
in `chart-version`) into the `helm` util's local repository.

## Files

`deploy.sh`, `chart-version`, `dependencies.sh`, `util.yaml`.

## Known limitations

- Layer 2 mode only, with one pool (`default-pool`): enough for a local cluster.
- Fixed release name and namespace: one MetalLB per cluster.
