# Format `summary`

A run's indicators, in a form any comparison can use without knowing what they
mean.

`<data_dir>/summary/<module>.csv`: one file per module that summarizes, one row per
indicator.

| Column | Content |
|---|---|
| `metric` | the indicator's name |
| `value` | its value (empty if it could not be computed) |
| `unit` | `seconds`, `bytes`, `ratio`, `count` (anything counted) or `count/second` |
| `goal` | `minimize`, `maximize` or `none`: whether a lower or a higher value is better |
| `description` | what it measures |

`goal` lets a comparison judge an indicator without knowing it. Indicators are
matched across runs by file and `metric`.
