# helm

Util: fetches Helm charts at a given version into a local repository, and
installs them from there. A module that deploys a chart asks for a version,
fetched once, then always installed from the same local copy.

## Scripts

Called by modules as `$MUMS_UTILS_PATH/helm/<script>`.

- `pull.sh <repo_url> <chart> <version>`: fetches the chart into
  `chart-repository/<chart>/<version>/`. Does nothing if that version is already
  there (safe to run again). Needs network access the first time.
  E.g. `pull.sh https://charts.example.org mychart 1.2.3`.
- `install.sh <kubeconfig> <release_name> <chart> <version> [helm options...]`:
  installs that local copy of the chart (`helm install`), with the given
  Helm options (values, namespace...).

## Dependencies

helm (Helm 3) and curl. The dependency script installs Helm with its official
installer script if it is missing.

## Files

`pull.sh`, `install.sh`, `dependencies.sh`, `util.yaml`; `chart-repository/`
(the fetched charts, one directory per chart and version; not versioned).

## Known limitations

- `install.sh` always passes `--create-namespace`, which breaks charts that
  create their own namespace: the modules concerned do not pass `--namespace`.
- Reproducibility: charts are kept locally, but the container images they
  reference are still pulled from their registries (quay.io, gcr.io...) at deploy
  time, so they may change or disappear upstream. A possible solution: a local
  registry backed by an archive of immutable images with DOIs (e.g. Zenodo; see
  https://github.com/pauleve/donodo), for offline reproducibility and citability.
