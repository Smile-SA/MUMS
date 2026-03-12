# Reproducibility Note

The current setup downloads Helm charts locally (see `chart-repository/`)
which ensures chart reproducibility. However, container images referenced
in these charts are still pulled from remote registries (quay.io, gcr.io,
etc.) at deploy time. This means:

- Images may change or be deleted by the upstream registry
- Tests may not be fully reproducible over time

**Planned solution:** a stateless local Docker registry backed by Zenodo,
where images are stored as immutable artifacts with DOIs. This would
allow full offline reproducibility and scientific citability.

See: https://github.com/pauleve/donodo for inspiration.