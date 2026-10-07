# Format `http-requests`

Every request sent to the application under test, as seen by the client.

`<data_dir>/http-requests/<index>.csv` (`000001.csv`, `000002.csv`...): one row per
request, a new file every 100,000 rows.

| Column | Content |
|---|---|
| `timestamp` | request start, Unix seconds |
| `method` | HTTP method, e.g. `GET` |
| `endpoint` | requested path, e.g. `/product/OLJCESPC7Z` |
| `status_code` | HTTP status, when a response was received (an HTTP error such as 500 included) |
| `response_time_seconds` | latency seen by the client |
| `no_response_reason` | only when no response was received: `timeout` (no answer in time, e.g. overloaded service), `connection_refused` (nothing listening, e.g. pod stopped), `connection_reset` (connection cut mid-request, e.g. pod evicted) or `other`; empty otherwise |

Rows are written as responses arrive: they are not strictly sorted by `timestamp`.
