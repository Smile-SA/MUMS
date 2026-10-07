# compare

Compares benchmark runs from their summaries (`<data_dir>/summary/*.csv`, the
standard summary format: `metric, value, unit, goal, description`), outside any
run. The first run is the reference.

## Usage

```bash
python3 utils/compare/compare.py <reference_data_dir> <data_dir> [<data_dir> ...] [-v] [-m [FILE]] [-c [FILE]]
python3 utils/compare/compare.py path/to/reference/data 'path/to/runs-*/data' -v
```

Each `<data_dir>` is the data directory of a run. Glob patterns are accepted,
expanded by the shell or, if quoted, by the tool; order is kept. The first one is
the reference; a directory given twice is compared once; one without summary is
left out, with a warning (the reference must have one). Each run is named after
its path, without the parts all paths share (a common parent, or a common last
directory such as `data`).

## Outputs

At least one, any combination:

| Option | Output |
|---|---|
| `-v`, `--verbose` | aligned report on the console |
| `-m`, `--markdown [FILE]` | Markdown report (default file: `comparison.md`) |
| `-c`, `--csv [FILE]` | every value in long form, one row per (run, indicator): `run, source, metric, unit, goal, value, reference, change, verdict` (default file: `comparison.csv`) |

The console and Markdown reports give, for each run, how many indicators are
better or worse than the reference, then one table per summary file (i.e. per
module): each indicator's unit, the reference's value, and for each run its
value, its change against the reference (relative, or absolute when the
reference is 0), and ✓ / ✗ when it is better / worse according to the
indicator's `goal`. Run names are given in full, on several lines when long.

It knows nothing about the indicators: any module adding a summary file is
compared too. Indicators are matched by summary file and metric name.

## Dependencies

python3.

## Files

`compare.py`, `util.yaml`.

## Known limitations

- A verdict (✓ / ✗) is given whatever the size of the change: two runs of the
  same scenario already differ by a few %, so small changes are not significant.
  Repeat runs, and compare groups of repetitions rather than single runs (not
  supported yet: means and spread per group, verdict only beyond the spread).
- Relative changes on near-zero values are misleading (one error in 2,000
  requests going to none: −100 %).
- Maximum latencies depend on a single request: prefer high percentiles (p99).
