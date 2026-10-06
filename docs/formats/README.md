# Data formats

Modules exchange data only through **formats**: agreements between the modules
that produce data and those that read it. Each format has its own directory in
the run's data directory, `<data_dir>/<format>/`, whoever produces it. A module
writes only the formats it produces, reads those it needs, and knows nothing of
who produced them.

This is not a closed list: **a module may create a new format** whenever it needs
one (see [New formats](#new-formats)).

| Format | Content | Typical producer | Typical consumers |
|---|---|---|---|
| [`openmetrics`](openmetrics.md) | raw metrics of the cluster | observability | post-processing |
| [`http-requests`](http-requests.md) | every request sent to the application | traffic | post-processing |
| [`run-window`](run-window.md) | the measured period | the platform | post-processing |
| [`essential-tables`](essential-tables.md) | tables on the cluster's objects and their use | post-processing | post-processing |
| [`summary`](summary.md) | a run's indicators | post-processing | comparison |
| [`comparison`](comparison.md) | a run's indicators against a reference run | post-processing | people |

## Common rules

- **Times** are Unix seconds (decimals allowed), **durations** seconds.
- **CSV** files have a header row, comma-separated.
- **Large outputs** are split into numbered files (`000001.csv`, `000002.csv`...),
  each with its header; read them in order.
- **Units** follow the [`summary`](summary.md) units when they apply: `seconds`,
  `bytes`, `ratio`, `count`, `count/second`.

## New formats

A module that needs to exchange data no format covers creates its own:

1. it writes it in `<data_dir>/<name>/`, under a name that says what it holds;
2. it describes it in its README, as precisely as a format of this directory:
   files, columns, units, rules;
3. once another module uses it, or if it is meant to be shared, its description
   moves here, as `<name>.md`, and the producer's README links to it.

A format described here belongs to no module: any module may produce it, and must
then follow its description exactly. A change to a format is agreed with the
modules that use it.
