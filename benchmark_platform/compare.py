"""Compare two benchmark runs (typically baseline vs. optimized): Locust
latency/error deltas during peak traffic, node resource balance, and
optimizer migration count -- joined into a single report.

This module has no hardcoded knowledge of any specific optimizer module.
Migration counts come from a generic, optional artifact contract: any
optimizer module MAY write `artifacts/<module-name>/moves.jsonl` (one JSON
object per line, `{"old_host": ..., "new_host": ..., "time": ...}`,
`old_host: null` for an initial placement rather than a migration) -- see
"Optional artifact conventions" in docs/output-format.md. The module name is
read from the run's own manifest.yaml (`modules.optimizer.name`), not
hardcoded here.

Pure stdlib (csv/json/statistics/yaml), consistent with the rest of the
platform (see benchmark_platform/datasets/metadata.py,
observability/analysis/*.py) -- no pandas dependency.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

OVERLOAD_THRESHOLD = 0.9


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _read_csv_glob(dir_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not dir_path.is_dir():
        return rows
    for path in sorted(dir_path.glob("*.csv")):
        rows.extend(_read_csv(path))
    return rows


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if not value or value.upper() == "N/A":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


@dataclass
class LatencySummary:
    sample_count: int
    p50_ms: float | None
    p95_ms: float | None
    p99_ms: float | None
    requests_per_s: float | None
    failures_per_s: float | None


@dataclass
class ResourceSummary:
    mean_node_imbalance: float | None  # average stdev of cpu_usage_ratio across nodes, per tick
    overload_episodes: int
    overload_ticks: int


@dataclass
class MigrationSummary:
    migration_count: int
    first_move_time: float | None
    last_move_time: float | None


@dataclass
class RunSummary:
    run_dir: str
    latency_overall: LatencySummary
    latency_peak: LatencySummary
    resources: ResourceSummary
    migrations: MigrationSummary


def _aggregated_traffic_rows(run_dir: Path) -> list[dict[str, str]]:
    rows = _read_csv(run_dir / "traffic" / "locust_stats_history.csv")
    return [r for r in rows if r.get("Name") == "Aggregated"]


def _peak_window(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Rows in the top quartile of concurrent User Count -- the day-profile
    shape's actual peak, not the whole (mostly ramping) run."""
    users = [u for u in (_to_float(r.get("User Count")) for r in rows) if u is not None]
    if not users:
        return rows
    sorted_users = sorted(users)
    threshold = sorted_users[int(len(sorted_users) * 0.75)]
    peak = [r for r in rows if (_to_float(r.get("User Count")) or 0) >= threshold]
    return peak or rows


def _summarize_latency(rows: list[dict[str, str]]) -> LatencySummary:
    def col(name: str) -> list[float]:
        return [v for v in (_to_float(r.get(name)) for r in rows) if v is not None]

    return LatencySummary(
        sample_count=len(rows),
        p50_ms=_mean(col("50%")),
        p95_ms=_mean(col("95%")),
        p99_ms=_mean(col("99%")),
        requests_per_s=_mean(col("Requests/s")),
        failures_per_s=_mean(col("Failures/s")),
    )


def _summarize_resources(
    run_dir: Path, *, threshold: float = OVERLOAD_THRESHOLD
) -> ResourceSummary:
    rows = _read_csv_glob(run_dir / "datasets" / "node_timeseries")

    by_tick: dict[int, list[float]] = {}
    all_ticks: set[int] = set()
    overloaded_ticks: set[int] = set()
    for row in rows:
        ts = _to_float(row.get("timestamp"))
        if ts is None:
            continue
        tick = int(ts)
        all_ticks.add(tick)
        ratio = _to_float(row.get("cpu_usage_ratio"))
        if ratio is None:
            continue
        by_tick.setdefault(tick, []).append(ratio)
        if ratio > threshold:
            overloaded_ticks.add(tick)

    stdevs = [statistics.pstdev(v) for v in by_tick.values() if len(v) > 1]

    sorted_all = sorted(all_ticks)
    gaps = [b - a for a, b in zip(sorted_all, sorted_all[1:], strict=False) if b > a]
    tick_span = statistics.median(gaps) if gaps else 1

    sorted_overloaded = sorted(overloaded_ticks)
    episodes = 0
    prev: int | None = None
    for tick in sorted_overloaded:
        if prev is None or (tick - prev) > tick_span * 1.5:
            episodes += 1
        prev = tick

    return ResourceSummary(
        mean_node_imbalance=_mean(stdevs),
        overload_episodes=episodes,
        overload_ticks=len(overloaded_ticks),
    )


def _optimizer_moves_path(run_dir: Path) -> Path | None:
    """<run_dir>/artifacts/<optimizer-module-name>/moves.jsonl, with the
    module name read from this run's own manifest.yaml -- not hardcoded to
    any specific optimizer (see module docstring)."""
    manifest_path = run_dir / "manifest.yaml"
    if not manifest_path.exists():
        return None
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None
    if not isinstance(manifest, dict):
        return None

    name = manifest.get("modules", {}).get("optimizer", {}).get("name")
    if not name:
        return None
    return run_dir / "artifacts" / str(name) / "moves.jsonl"


def _summarize_migrations(run_dir: Path) -> MigrationSummary:
    """Reads the optimizer module's moves.jsonl, if it wrote one (a generic,
    optional contract -- see module docstring). Empty summary if the run's
    optimizer didn't produce one."""
    moves_path = _optimizer_moves_path(run_dir)
    if moves_path is None or not moves_path.exists():
        return MigrationSummary(migration_count=0, first_move_time=None, last_move_time=None)

    count = 0
    times: list[float] = []
    with moves_path.open(encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                move = json.loads(line)
            except json.JSONDecodeError:
                continue
            if move.get("old_host") is None:
                continue  # initial placement, not a migration
            count += 1
            t = _to_float(str(move.get("time"))) or _to_float(str(move.get("recorded_at")))
            if t is not None:
                times.append(t)

    return MigrationSummary(
        migration_count=count,
        first_move_time=min(times) if times else None,
        last_move_time=max(times) if times else None,
    )


def summarize_run(run_dir: Path) -> RunSummary:
    rows = _aggregated_traffic_rows(run_dir)
    return RunSummary(
        run_dir=str(run_dir),
        latency_overall=_summarize_latency(rows),
        latency_peak=_summarize_latency(_peak_window(rows)),
        resources=_summarize_resources(run_dir),
        migrations=_summarize_migrations(run_dir),
    )


def _pct_change(baseline: float | None, optimized: float | None) -> float | None:
    if baseline is None or optimized is None or baseline == 0:
        return None
    return (optimized - baseline) / baseline * 100.0


def _headline(baseline: RunSummary, optimized: RunSummary) -> str:
    b_p95 = baseline.latency_peak.p95_ms
    o_p95 = optimized.latency_peak.p95_ms
    pct = _pct_change(b_p95, o_p95)
    migrations = optimized.migrations.migration_count

    if pct is None or b_p95 is None or o_p95 is None:
        return (
            "Not enough peak-traffic latency data in one of the two runs "
            "to compute a p95 delta."
        )

    direction = "improved" if pct < 0 else "regressed"
    return (
        f"Optimized {direction} p95 latency by {pct:+.1f}% "
        f"({b_p95:.0f}ms -> {o_p95:.0f}ms) during peak traffic, "
        f"at the cost of {migrations} migration(s)."
    )


def compare_runs(baseline_dir: Path, optimized_dir: Path) -> dict[str, Any]:
    baseline = summarize_run(baseline_dir)
    optimized = summarize_run(optimized_dir)

    return {
        "baseline": asdict(baseline),
        "optimized": asdict(optimized),
        "deltas": {
            "p50_ms_peak_pct": _pct_change(
                baseline.latency_peak.p50_ms, optimized.latency_peak.p50_ms
            ),
            "p95_ms_peak_pct": _pct_change(
                baseline.latency_peak.p95_ms, optimized.latency_peak.p95_ms
            ),
            "p99_ms_peak_pct": _pct_change(
                baseline.latency_peak.p99_ms, optimized.latency_peak.p99_ms
            ),
            "failures_per_s_peak_pct": _pct_change(
                baseline.latency_peak.failures_per_s, optimized.latency_peak.failures_per_s
            ),
            "mean_node_imbalance_pct": _pct_change(
                baseline.resources.mean_node_imbalance, optimized.resources.mean_node_imbalance
            ),
        },
        "headline": _headline(baseline, optimized),
    }


def _fmt(value: float | None, suffix: str = "", digits: int = 1) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}{suffix}"


def render_markdown(result: dict[str, Any]) -> str:
    baseline = result["baseline"]
    optimized = result["optimized"]
    deltas = result["deltas"]

    lines = [
        "# Benchmark comparison",
        "",
        f"- Baseline:  `{baseline['run_dir']}`",
        f"- Optimized: `{optimized['run_dir']}`",
        "",
        f"**{result['headline']}**",
        "",
        "## Latency during peak traffic (top quartile of concurrent users)",
        "",
        "| Metric | Baseline | Optimized | Delta |",
        "|---|---:|---:|---:|",
        f"| p50 (ms) | {_fmt(baseline['latency_peak']['p50_ms'])} "
        f"| {_fmt(optimized['latency_peak']['p50_ms'])} "
        f"| {_fmt(deltas['p50_ms_peak_pct'], '%')} |",
        f"| p95 (ms) | {_fmt(baseline['latency_peak']['p95_ms'])} "
        f"| {_fmt(optimized['latency_peak']['p95_ms'])} "
        f"| {_fmt(deltas['p95_ms_peak_pct'], '%')} |",
        f"| p99 (ms) | {_fmt(baseline['latency_peak']['p99_ms'])} "
        f"| {_fmt(optimized['latency_peak']['p99_ms'])} "
        f"| {_fmt(deltas['p99_ms_peak_pct'], '%')} |",
        f"| failures/s | {_fmt(baseline['latency_peak']['failures_per_s'], digits=3)} "
        f"| {_fmt(optimized['latency_peak']['failures_per_s'], digits=3)} "
        f"| {_fmt(deltas['failures_per_s_peak_pct'], '%')} |",
        "",
        "## Node resource balance",
        "",
        "| Metric | Baseline | Optimized | Delta |",
        "|---|---:|---:|---:|",
        f"| Mean node CPU-ratio stdev "
        f"| {_fmt(baseline['resources']['mean_node_imbalance'], digits=3)} "
        f"| {_fmt(optimized['resources']['mean_node_imbalance'], digits=3)} "
        f"| {_fmt(deltas['mean_node_imbalance_pct'], '%')} |",
        f"| Overload episodes (>{OVERLOAD_THRESHOLD:.0%} CPU) "
        f"| {baseline['resources']['overload_episodes']} "
        f"| {optimized['resources']['overload_episodes']} | |",
        "",
        "## Migrations (from the optimizer module's moves.jsonl, if any)",
        "",
        f"- Baseline:  {baseline['migrations']['migration_count']}",
        f"- Optimized: {optimized['migrations']['migration_count']}",
        "",
    ]
    return "\n".join(lines)


def default_output_dir(baseline_run_dir: Path, optimized_run_dir: Path) -> Path:
    pair = f"{baseline_run_dir.name}__vs__{optimized_run_dir.name}"
    return optimized_run_dir.parent / "comparisons" / pair


def write_report(result: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "comparison.json"
    md_path = output_dir / "comparison.md"

    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(result), encoding="utf-8")

    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline_run_dir", type=Path)
    parser.add_argument("optimized_run_dir", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Output directory. Default: "
            "<optimized_run_dir>/../comparisons/<baseline>__vs__<optimized>/"
        ),
    )
    args = parser.parse_args(argv)

    output_dir = args.output or default_output_dir(args.baseline_run_dir, args.optimized_run_dir)

    result = compare_runs(args.baseline_run_dir, args.optimized_run_dir)
    json_path, md_path = write_report(result, output_dir)

    print(result["headline"])
    print(json_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
