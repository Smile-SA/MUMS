# compare

Compares benchmark runs from their summaries (`<data_dir>/summary/*.csv`, the
standard summary format: `metric, value, unit, goal, description`), outside any
run. The first run is the reference.

## Usage

```bash
# single runs: the first one is the reference
python3 utils/compare/compare.py <reference_data_dir> <data_dir> [<data_dir> ...] [-v] [-m [FILE]] [-c [FILE]]
# groups of repetitions: the first group is the reference
python3 utils/compare/compare.py -g NAME <data_dir>... -g NAME <data_dir>... [--alpha A] [-v] [-m [FILE]] [-c [FILE]]
```

Each `<data_dir>` is the data directory of a run. Glob patterns are accepted,
expanded by the shell or, if quoted, by the tool; order is kept. A directory given
twice is compared once; one without summary is left out, with a warning.
Indicators are matched by summary file and metric name; the tool knows nothing
about them: any module adding a summary file is compared too.

**Single runs.** Each run is named after its path, without the parts all paths
share. For each indicator: the reference's value, each run's value, its change
(relative, or absolute when the reference is 0), and ✓ / ✗ when better / worse
according to the indicator's `goal`. No significance test: two runs of the same
scenario already differ by a few %.

**Groups** (`-g NAME DIRS...`, repeated). For each indicator: each group's median,
interquartile range and number of runs, the change of medians against the reference
group, and a verdict only when the difference is significant: a two-sided
Mann-Whitney U test (exact, by permutation; on 20,000 random permutations beyond
that many), p < `--alpha` (default 0.05). `~` means no significant difference. With 3
runs per group nothing can be significant (smallest p: 0.1); with 5, the smallest p
is 0.008.

## Outputs

At least one, any combination:

| Option | Output |
|---|---|
| `-v`, `--verbose` | aligned report on the console |
| `-m`, `--markdown [FILE]` | Markdown report (default file: `comparison.md`) |
| `-c`, `--csv [FILE]` | every value in long form (default file: `comparison.csv`). Single runs: `run, source, metric, unit, goal, value, reference, change, verdict`. Groups: `group, source, metric, unit, goal, runs, median, q1, q3, reference_runs, reference_median, change, p_value, verdict` |

## Dependencies

python3.

## Files

`compare.py`, `util.yaml`.

## Known limitations

- The test compares each group with the reference, one indicator at a time: with
  many indicators, a few "significant" differences are expected by chance at
  p < 0.05. Decide beforehand which indicators answer the question.
- Relative changes on near-zero values are misleading (one error in 2,000
  requests going to none: −100 %).
- Maximum latencies depend on a single request: prefer high percentiles (p99).
