from __future__ import annotations

from pathlib import Path

from benchmark_platform.compare import compare_runs, write_report

FIXTURES = Path(__file__).parent / "fixtures"
BASELINE_DIR = FIXTURES / "compare_baseline"
OPTIMIZED_DIR = FIXTURES / "compare_optimized"


def test_compare_runs_computes_peak_latency_deltas() -> None:
    result = compare_runs(BASELINE_DIR, OPTIMIZED_DIR)

    baseline_peak = result["baseline"]["latency_peak"]
    optimized_peak = result["optimized"]["latency_peak"]

    # Peak window is the top quartile of User Count (10 in both fixtures);
    # baseline's 95% column there is (700, 720), optimized's is (500, 480).
    assert baseline_peak["p95_ms"] == 710.0
    assert optimized_peak["p95_ms"] == 490.0

    assert result["deltas"]["p95_ms_peak_pct"] < 0  # optimized improved latency


def test_compare_runs_counts_migrations_and_ignores_initial_placement() -> None:
    result = compare_runs(BASELINE_DIR, OPTIMIZED_DIR)

    # Baseline's optimizer module has no moves.jsonl at all.
    assert result["baseline"]["migrations"]["migration_count"] == 0
    # Optimized has 3 move entries, one of which is an initial placement
    # (old_host=null) and must not be counted as a migration.
    assert result["optimized"]["migrations"]["migration_count"] == 2


def test_compare_reads_moves_jsonl_from_any_optimizer_module_name(tmp_path: Path) -> None:
    """The migration count must come from whatever optimizer module name is
    recorded in *this run's* manifest.yaml, not a hardcoded module name."""
    run_dir = tmp_path / "some-run"
    artifacts_dir = run_dir / "artifacts" / "optimizers.made-up-name"
    artifacts_dir.mkdir(parents=True)
    (artifacts_dir / "moves.jsonl").write_text(
        '{"old_host": null, "new_host": "n1", "time": 1}\n'
        '{"old_host": "n1", "new_host": "n2", "time": 2}\n',
        encoding="utf-8",
    )
    (run_dir / "manifest.yaml").write_text(
        "modules:\n  optimizer:\n    name: optimizers.made-up-name\n", encoding="utf-8"
    )

    result = compare_runs(BASELINE_DIR, run_dir)
    assert result["optimized"]["migrations"]["migration_count"] == 1


def test_compare_runs_detects_resource_imbalance_improvement() -> None:
    result = compare_runs(BASELINE_DIR, OPTIMIZED_DIR)

    assert result["baseline"]["resources"]["overload_episodes"] == 1
    assert result["optimized"]["resources"]["overload_episodes"] == 0
    assert (
        result["optimized"]["resources"]["mean_node_imbalance"]
        < result["baseline"]["resources"]["mean_node_imbalance"]
    )


def test_headline_mentions_direction_and_migrations() -> None:
    result = compare_runs(BASELINE_DIR, OPTIMIZED_DIR)
    assert "improved" in result["headline"]
    assert "2 migration" in result["headline"]


def test_write_report_creates_json_and_markdown(tmp_path: Path) -> None:
    result = compare_runs(BASELINE_DIR, OPTIMIZED_DIR)
    json_path, md_path = write_report(result, tmp_path / "out")

    assert json_path.exists()
    assert md_path.exists()
    assert "Benchmark comparison" in md_path.read_text(encoding="utf-8")
