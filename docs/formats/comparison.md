# Format `comparison`

A run's indicators compared with those of a reference run.

`<data_dir>/comparison/<module>.csv`: one row per indicator found in either run's
summaries.

| Column | Content |
|---|---|
| `run` | the run |
| `source` | the summary file the indicator comes from |
| `metric`, `unit`, `goal` | as in [`summary`](summary.md) |
| `value`, `reference` | the run's value and the reference's |
| `change` | the change against the reference: relative (`+5.8%`), or absolute when the reference is 0 |
| `verdict` | `better`, `worse`, `=`, or empty (no goal, or not comparable), from `goal` |
