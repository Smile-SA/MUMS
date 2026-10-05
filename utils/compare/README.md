# compare

Compares benchmark runs from their summaries (`<run>/data/summary/*.csv`, the
standard summary format: `metric, value, unit, goal, description`), outside any
run. The first run is the reference.

## Usage

```bash
python3 utils/compare/compare.py <reference_run> <run> [<run> ...] [-v] [-m [FILE]] [-c [FILE]]
python3 utils/compare/compare.py output/runs/basic-...-seed42 output/runs/koordinator-* -v
```

`<run>` is a run directory (containing `data/`) or its `data/` directory. Glob
patterns are accepted, expanded by the shell or, if quoted, by the tool; order
is kept. The first run is the reference; a run given twice is compared once; a
run without summary is left out, with a warning (the reference must have one).

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
