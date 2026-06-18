# Testing

## Local fast checks

```bash
make check
make lint
make test
```

## Full standalone smoke test

The smoke test requires Docker, Kind, kubectl and Helm.

```bash
make doctor
make smoke
```

The smoke test creates a real local Kind environment and may take several minutes.

## CI

GitLab CI runs lightweight lint and unit tests. Full Kind-based smoke testing is kept local/manual unless a runner with suitable Docker support is available.
