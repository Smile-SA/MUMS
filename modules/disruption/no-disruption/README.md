# no-disruption

Disruption module that does nothing: the cluster runs undisturbed for the whole
run. It is the usual choice; a scenario takes another disruption module to see how
an optimizer copes with nodes, pods or the network failing.

## Actions

- `start <kubeconfig> <seed>`: does nothing.
- No `stop`: there is nothing to stop.

## Arguments

None.

## Data produced

None.

## Dependencies

None.

## Files

`run.sh` (the entrypoint), `module.yaml`.
