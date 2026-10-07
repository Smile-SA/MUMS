# no-optimization

Optimizer module that does nothing: the reference point. Pods are placed by the
default Kubernetes scheduler and never moved. Running the same scenario with
another optimizer and comparing the results shows what that optimizer changes.

## Actions

- `start <kubeconfig>`: does nothing.
- No `stop`: there is nothing to stop.

## Arguments

None.

## Data produced

None.

## Dependencies

None.

## Files

`run.sh` (the entrypoint), `module.yaml`.
