# prometheus-live-scraper

Observability module: installs Prometheus in the cluster (optional) and scrapes
it for the whole run. It does nothing else: all processing of the scraped data
is done by post-processing modules.

## Actions

- `start <kubeconfig> <data_dir>`: unless `install_prometheus` is false, installs
  Prometheus (Helm chart, namespace `monitoring`; see "Measuring under pressure"),
  collecting its targets every `frequency_seconds`. Then opens a port-forward to
  it and starts the scraper in the background. Fails right away if the scraper dies.
- `stop <kubeconfig>`: stops the scraper and the port-forward. Succeeds whatever
  is running (a `start` that failed half-way included).

## Arguments

| Argument | Default | Description |
|---|---|---|
| `install_prometheus` | `true` | Install Prometheus. Set it to `false` when the cluster already has one (e.g. a managed cloud cluster). |
| `chart_version` | `28.13.0` | Version of the Prometheus Helm chart (`prometheus-community/prometheus`) to install, like a node image: fetched at `start` if not downloaded yet. |
| `placement` | `control-plane` | Where the installed Prometheus runs: `control-plane` (away from the measured workload) or `any` (let Kubernetes choose; e.g. when the control-plane is not schedulable, as on managed clusters). |
| `frequency_seconds` | `60` | Time between two scrapes (fixed rate: the period does not drift). The installed Prometheus also collects its targets at this rate, so that each scrape brings new samples; the time Prometheus and the scraper wait for an answer is this value too. |
| `local_port` | `9090` | Local port of the port-forward. Must be free. |

## Measuring under pressure

Losing samples when the cluster is overloaded is exactly what must not happen,
since that is when they matter. The installed Prometheus is therefore set up to
keep measuring under pressure:

- it runs on the control-plane node (with `placement: control-plane`), with
  kube-state-metrics: not competing with the measured workload for resources, and
  out of reach of optimizers that move or evict workload pods;
- it has a high priority (PriorityClass `benchmark-observability`): never evicted
  or preempted before the workload;
- it has reserved resources (requests equal to limits);
- Prometheus and the scraper wait for an answer as long as the scrape interval allows;
- the port-forward is restarted automatically if it drops (e.g. the Prometheus pod
  restarts); the scraper keeps its schedule and logs the scrapes that failed meanwhile;
- Alertmanager and Pushgateway, unused, are not installed.

## Data produced

`<data_dir>/openmetrics/<index>.om` (`000001.om`, `000002.om`...): one file per
scrape, a valid OpenMetrics exposition exactly as returned by Prometheus's
`/federate` endpoint (all series, ending with `# EOF`). A file appears only once
complete. Read all scrapes in order with `cat <data_dir>/openmetrics/*.om`.

## Extras, logs

- `extras/…/scrapes.csv`: journal of every scrape attempt (start and end time,
  success, HTTP status, bytes, error). For debugging: which scrapes failed, and why.
- `extras/…/port-forward.csv`: journal of the port-forward (each start and drop,
  with its time).
- `extras/…/*.pid`: internal state (scraper and port-forward processes).
- `logs/…/scraper.log`, `logs/…/port-forward.log`.

## Dependencies

kubectl, curl, python3, and `helm`. The dependency script installs the
scraper's Python package (`requests`). The Prometheus chart is fetched at `start`
(version `chart_version`), so the first run with a given version needs network
access.

## Files

`run.sh` (actions), `scraper.py` (the scraper), `deploy.sh` (Helm install),
`port-forward.sh` / `port-forward-stop.sh`, `check_local_port.sh`,
`dependencies.sh`, `requirements.txt`.

## Known limitations

- Runs in parallel: `local_port` (9090 by default) must differ between runs that
  execute at the same time, otherwise the second one fails at `start` (port not
  available). Set a different `local_port` in each scenario.
- With `install_prometheus: false`, the existing Prometheus must be the service
  `prometheus-server` in the namespace `monitoring` (hard-coded in the port-forward).
- With `install_prometheus: false`, the module controls neither the real sampling
  rate of the existing Prometheus (if it collects its targets less often than
  `frequency_seconds`, consecutive files repeat the same samples) nor how it holds
  up under pressure.
- Prometheus's reserved resources are fixed (500m CPU, 1Gi memory): enough for the
  clusters tested so far, possibly not for much larger ones.
- Metric timestamps are Prometheus's own (when it collected each target), not the
  time of our scrape. Targets are collected at slightly different moments, so an
  occasional file may repeat or skip a sample.
