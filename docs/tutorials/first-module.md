# Your first module

This tutorial writes a module from scratch, on an example: **`request-count`**, a
small post-processing module that counts the requests sent during a run (or only
those that failed), and writes the result as a run indicator. Once written, its
count appears in every comparison of runs, like any other indicator.

The example is deliberately simple, but it shows everything a module needs: a
descriptor, an action, an argument with its default, standard data in and out,
and a README. You will test it on an existing run, then use it in a scenario.

You need a run from [the first tutorial](first-benchmark.md) (the smoke test is
enough).

## 1. Create the module

A module can live anywhere: in the platform's own `modules/` directory, or in a
directory of your own, kept apart from the platform. This tutorial uses a
directory of your own, `~/my-modules`:

```bash
mkdir -p ~/my-modules/post-processing/request-count
cd ~/my-modules/post-processing/request-count
```

Then tell the platform to look there too, besides its own modules:

```bash
mums config add module_paths ~/my-modules
mums config get module_paths            # its directories, and yours
```

(`mums config remove module_paths ~/my-modules` undoes it.)

## 2. The descriptor

`module.yaml` says what the module is, what it implements, what it accepts and
what it needs:

```yaml
name: request-count
type: post-processing
contract: 1
entrypoint: run.sh

lifecycle:
  run: "<data_dir>"

args:
  errors_only:
    required: false
    type: bool
    description: "Count only the requests that failed: a 5xx status, or no response (default: false)."

dependencies:
  commands:
    - python3
```

A post-processing module has a single action, `run`, which receives the run's data
directory. The [module contract](../reference/module-contract.md) gives the actions
of every type.

## 3. The action

`run.sh` is called as `run.sh run <data_dir> [--errors_only true|false]`. It sets
the argument's default, reads the options, and hands over to Python:

```bash
#!/usr/bin/env bash
# request-count: counts the requests of a run (see README.md).
# Usage: run.sh run <data_dir> [--errors_only true|false]
set -euo pipefail

usage() { echo "Usage: $0 run <data_dir> [--errors_only true|false]" >&2; exit 1; }
[ "${1:-}" = "run" ] && [ "$#" -ge 2 ] || usage
DATA_DIR="$2"
shift 2

ERRORS_ONLY=false                       # the default, stated in module.yaml
while [ "$#" -gt 0 ]; do
    case "$1" in
        --errors_only) ERRORS_ONLY="$2"; shift 2 ;;
        *) echo "ERROR: unknown option '$1'" >&2; usage ;;
    esac
done

python3 count.py "$DATA_DIR" "$ERRORS_ONLY"
```

`count.py` reads the standard format `http-requests` and writes the standard format
`summary` (see [the data formats](../formats/README.md)):

```python
"""Counts the requests of a run: <data_dir>/http-requests -> <data_dir>/summary/request-count.csv."""

import csv
import sys
from pathlib import Path

data_dir, errors_only = Path(sys.argv[1]), sys.argv[2] == "true"

requests_dir = data_dir / "http-requests"
if not requests_dir.is_dir():
    sys.exit(f"ERROR: no http-requests data in {data_dir}: the run needs a traffic module.")

count = 0
for path in sorted(requests_dir.glob("*.csv")):
    with path.open(newline="") as stream:
        for row in csv.DictReader(stream):
            failed = bool(row["no_response_reason"]) or row["status_code"].startswith("5")
            if failed or not errors_only:
                count += 1

summary_dir = data_dir / "summary"
summary_dir.mkdir(exist_ok=True)
with (summary_dir / "request-count.csv").open("w", newline="") as stream:
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["metric", "value", "unit", "goal", "description"])
    if errors_only:
        writer.writerow(["failed_requests", count, "count", "minimize", "requests that failed"])
    else:
        writer.writerow(["requests", count, "count", "none", "requests sent"])
```

Make the entrypoint executable:

```bash
chmod +x run.sh
```

## 4. Check it

The platform must find it and accept its descriptor:

```bash
mums deps check request-count
```

## 5. Test it on an existing run

A post-processing module only reads and writes data: test it directly on the data
of the smoke test, without a new run.

```bash
RUN=$(ls -td ~/mums/output/smoke-test-* | head -1)
./run.sh run $RUN/data
cat $RUN/data/summary/request-count.csv
./run.sh run $RUN/data --errors_only true
cat $RUN/data/summary/request-count.csv
```

## 6. Use it in a scenario

Copy the smoke test, and add the module after the others:

```bash
cd ~/mums
cp configs/smoke-test.yaml configs/my-test.yaml
```

```yaml
post-processing:
  - module: essential-tables
  - module: request-count
    errors_only: true
```

```bash
mums validate configs/my-test.yaml
mums run configs/my-test.yaml
```

The new run has its `summary/request-count.csv`, and `mums compare`
now compares it like any other indicator.

## 7. Document it

Write its `README.md`, following [the model](../reference/module-contract.md#readme):

```markdown
# request-count

Post-processing module: counts the requests of a run.

## Actions

- `run <data_dir>`: writes `<data_dir>/summary/request-count.csv`.

## Arguments

| Argument | Default | Description |
|---|---|---|
| `errors_only` | `false` | Count only the requests that failed: a 5xx status, or no response. |

## Data consumed

`http-requests`.

## Data produced

`summary`: `requests` (or `failed_requests` with `errors_only`).

## Dependencies

python3.

## Files

`run.sh` (action), `count.py`, `module.yaml`.
```

## Next

[Writing modules](../guides/writing-modules.md) covers what a longer-running module
needs: dependencies to install, processes in the background, robust stops, utils.
