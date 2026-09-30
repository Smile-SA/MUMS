# traffic.online-boutique

Traffic module: generates load on Online Boutique with [Locust](https://locust.io),
following a load shape (a simulated day by default), and records every request.

## Actions

- `start <kubeconfig> <seed> <data_dir>`: finds the frontend's external URL
  (`check_frontend.sh`: pods ready, `LoadBalancer` IP, HTTP answer), then starts
  Locust in the background. Fails right away if Locust dies.
- `stop <kubeconfig>`: stops Locust (waits for it to flush its files). Succeeds
  if nothing is running.

## Arguments

| Argument | Default | Description |
|---|---|---|
| `shape` | `day_profile` | Load shape: a file `shapes/<shape>.py`. |
| `cycle_minutes` | `60` | Duration of one cycle of the shape (e.g. `day_profile` replays a full day in this time). |
| `requests_per_file` | `100000` | Rows per request file before starting a new one. |

The seed makes Locust's random choices (products, currencies...) reproducible.

## Data produced

`<data_dir>/http-requests/<index>.csv` (`000001.csv`, `000002.csv`...): one row
per request, the platform's standard **http-requests** format. Independent of
Locust: any load generator can produce it. Columns:

| Column | Content |
|---|---|
| `timestamp` | request start, Unix seconds (with decimals) |
| `method` | HTTP method, e.g. `GET` |
| `endpoint` | requested path, e.g. `/product/OLJCESPC7Z` |
| `status_code` | HTTP status, when a response was received (an HTTP error such as 500 included) |
| `response_time_ms` | latency seen by the load generator |
| `no_response_reason` | only when no response was received: `timeout` (no answer in time, e.g. overloaded service), `connection_refused` (nothing listening, e.g. pod stopped), `connection_reset` (connection cut mid-request, e.g. pod evicted) or `other`; empty otherwise |

A new file starts every `requests_per_file` rows, each with its header. Rows are
written as responses arrive, so they are not strictly sorted by `timestamp`.

## Extras, logs

- `extras/…/locust_*.csv`: Locust's own statistics (aggregates, history,
  failures). Not a standard format: for debugging.
- `extras/…/locust.pid`: internal state.
- `logs/…/locust.log`.

## Dependencies

kubectl, curl. The dependency script installs the Python packages
(`requirements.txt`: Locust, Faker) and checks them.

## Files

`run.sh` (actions), `locustfile.py` (user behaviour: Online Boutique's official
locustfile, modifications listed at its top), `request_log.py` (writes the
http-requests files; loaded by Locust next to the locustfile),
`shapes/` (load shapes), `check_frontend.sh`, `dependencies.sh`, `requirements.txt`.

## Known limitations

- Online Boutique only: the user behaviour and the frontend lookup (namespace
  `online-boutique`, service `frontend-external`) are specific to it.
- Shapes live in this module for now; they should be shared by all Locust-based
  traffic modules.
