# Format `openmetrics`

Raw metrics of the cluster, as collected while the run lasts.

`<data_dir>/openmetrics/<index>.om` (`000001.om`, `000002.om`...): one file per
collection of the metrics, in order. A file appears only once complete. Each file
is a valid [OpenMetrics](https://openmetrics.io) exposition, ending with `# EOF`.

All collections, in order: `cat <data_dir>/openmetrics/*.om`.

Metric timestamps are those of the metrics' source (when it measured them), not
the time of the collection.
