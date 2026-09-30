# observability.prometheus

Observability module: installs Prometheus in the cluster (optional) and scrapes
it for the whole run. It does nothing else: all processing of the scraped data
is done by post-processing modules.

## Actions

- `start <kubeconfig> <data_dir>`: installs Prometheus (Helm chart, namespace
  `monitoring`) unless `install_prometheus` is false, opens a port-forward to it,
  then starts the scraper in the background. Fails right away if the scraper dies.
- `stop <kubeconfig>`: stops the scraper and the port-forward. Succeeds whatever
  is running (a `start` that failed half-way included).

## Arguments

| Argument | Default | Description |
|---|---|---|
| `install_prometheus` | `true` | Install Prometheus. Set it to `false` when the cluster already has one (e.g. a managed cloud cluster). |
| `frequency_seconds` | `15` | Time between two scrapes. Scrapes start at a fixed rate: the period does not drift. |
| `local_port` | `9090` | Local port of the port-forward. Must be free. |
| `timeout_seconds` | `10` | Timeout of each scrape request. |

## Data produced

`<data_dir>/openmetrics/<index>.om` (`000001.om`, `000002.om`...): one file per
scrape, a valid OpenMetrics exposition exactly as returned by Prometheus's
`/federate` endpoint (all series, ending with `# EOF`). A file appears only once
complete. Read all scrapes in order with `cat <data_dir>/openmetrics/*.om`.

## Extras, logs

- `extras/…/scrapes.csv`: journal of every scrape attempt (start and end time,
  success, HTTP status, bytes, error). For debugging: which scrapes failed, and why.
- `extras/…/*.pid`: internal state (scraper and port-forward processes).
- `logs/…/scraper.log`, `logs/…/port-forward.log`.

## Dependencies

kubectl, curl, python3, and `utils.helm`. The dependency script installs the
scraper's Python package (`requests`) and fetches the Prometheus chart (pinned
version, see `dependencies.sh`).

## Files

`run.sh` (actions), `scraper.py` (the scraper), `deploy.sh` (Helm install),
`port-forward.sh` / `port-forward-stop.sh`, `check_local_port.sh`,
`dependencies.sh`, `requirements.txt`.

## Known limitations

- With `install_prometheus: false`, the existing Prometheus must be the service
  `prometheus-server` in the namespace `monitoring` (hard-coded in the port-forward).
- Metric timestamps are Prometheus's own (when it scraped each target), not the
  time of our scrape; targets are scraped at their own rate (e.g. cAdvisor every
  minute), so consecutive files can repeat the same values.
