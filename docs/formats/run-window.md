# Format `run-window`

The measured period of a run: the run's wait, while every module was running.
Written by the platform.

`<data_dir>/run-window/run-window.csv`: a header, then one row.

| Column | Content |
|---|---|
| `start` | start of the wait, Unix seconds |
| `end` | end of the wait, Unix seconds |

Evaluations use it to count only what happened during the measured period.
