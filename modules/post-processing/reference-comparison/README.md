# reference-comparison

Post-processing module: compares this run's summaries with those of a reference
run (e.g. a baseline), indicator by indicator, and writes the result as standard
data. It relies on the util `compare`.

## Actions

- `run <data_dir>`: compares `<data_dir>/summary/*.csv` with the reference's
  summaries, and writes `<data_dir>/comparison/reference-comparison.csv`. Fails if
  either has no summary: the modules that write summaries must run before this
  one.

## Arguments

| Argument | Default | Description |
|---|---|---|
| `reference` | (required) | Absolute path to the data directory of the reference run (a relative path is refused: the module does not run from the directory the platform was started in). |

## Data consumed

`summary`: this run's and the reference's (`<data_dir>/summary/*.csv`).

## Data produced: `comparison`

`<data_dir>/comparison/reference-comparison.csv`, one row per indicator found in
either run's summaries: `run, source, metric, unit, goal, value, reference,
change, verdict`. `source` is the summary file the indicator comes from, `change`
the change against the reference (relative, or absolute when the reference is 0),
`verdict` `better`, `worse` or empty, from the indicator's `goal`.

## Dependencies

python3, and the util `compare`.

## Files

`run.sh` (action), `module.yaml`.

## Known limitations

- One reference run against one run: the verdicts do not take the variability
  between runs into account (see the util `compare`).
