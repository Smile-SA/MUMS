# Known limitations and open questions

Points to investigate or improve in future iterations of the observability pipeline.

## Image pull metrics

`kubelet_image_pull_duration_seconds` is recorded per node and per size bucket,
not per pod. Useful for diagnosing long `ready_time` values caused by slow pulls.
Currently left in the raw `metrics.om` file for on-demand querying.

Open question: add a ninth output file `image_pull_timeseries.csv` if this becomes
a recurring analysis need?

## Image layers

An image is composed of layers; a layer can be shared across multiple images.
Desired data:
- `image_layer_metadata`    : (image, layer)           → list of layers in an image
- `layer_metadata`          : (layer)                  → layer size and other metadata
- `layer_node_timeseries`   : (timestamp, layer, node) → layer presence on the node,
                               or download progress if accessible

Open questions:
- Does Prometheus/kubelet expose per-node layer presence? Lead: kubelet exposes
  `/images` on its endpoint, which lists present layers. Not certain this is scraped
  by default in our Prometheus config.
- If not accessible via Prometheus, consider direct scraping of the kubelet API or
  the Kubernetes API: `GET /api/v1/nodes/{node}/proxy/images`.

## Migration / rescheduling detection

A pod killed and recreated by its controller appears as two distinct entries in
`pod_metadata` (different UIDs, same `controller_name`).
This is the mechanism for detecting a migration after the fact.

Edge case: pod killed and recreated on the **same node** — not a migration, but
produces the same signature. Verify this is distinguishable in practice.

## Static pods

`kube_pod_owner` empty or `owner_kind="Node"`: no controller, no recreation.
Present mainly in `kube-system` (etcd, kube-scheduler, …).
Stored as `controller_kind=''` and `controller_name=''` in `pod_metadata`.

Open question: verify that this does not break joins with
`controller_timeseries` / `controller_metadata`.

## Node disappearance

When a node disappears, its metrics vanish from the scrape. `up=0` is the only
signal in `node_timeseries`. Orphaned pods transition to Unknown and are
eventually recreated elsewhere by their controllers.

Open questions:
- Verify that disappearing metrics do not create silent gaps in the CSVs.
- `up=0` then total absence of the series are two distinct cases; distinguish them
  in downstream analysis.

## Inter-node network

`container_timeseries` contains pod-level network traffic, not link saturation
between nodes. Consider adding `node_network_receive_bytes_total` /
`node_network_transmit_bytes_total` to `node_timeseries` to detect saturation
caused by migrations.

## succeeded_time and failed_time precision

These timestamps are approximated by the first scrape where the phase is
observed (value=1), because `kube_pod_completion_time` is not present in the
current scrape config.

Open question: check whether `kube_pod_completion_time` can be enabled in
kube-state-metrics. Maximum precision is ± scrape frequency (currently 15 s).
