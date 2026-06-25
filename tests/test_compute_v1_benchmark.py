from __future__ import annotations

import pytest

from factor_autoresearch.compute_v1.benchmark import (
    BenchmarkComparison,
    BenchmarkResult,
    BenchmarkTimer,
    EvaluationBenchmark,
    compare_legacy_vs_v1,
)


def _fake_clock(*values: float):
    timeline = iter(values)
    return lambda: next(timeline)


def test_benchmark_timer_records_elapsed_seconds() -> None:
    timer = BenchmarkTimer("legacy", clock=_fake_clock(10.0, 10.25), metadata={"candidate_id": "fa_001"})

    with timer:
        pass

    assert timer.result == BenchmarkResult(
        name="legacy",
        elapsed_seconds=0.25,
        metadata={"candidate_id": "fa_001"},
    )
    assert timer.result.elapsed_ms == 250.0


def test_compare_legacy_vs_v1_calculates_speedup() -> None:
    comparison = compare_legacy_vs_v1(
        legacy_runner=lambda: None,
        v1_runner=lambda: None,
        clock=_fake_clock(0.0, 1.2, 2.0, 2.4),
        metadata={"candidate_id": "fa_speed"},
    )

    assert comparison.legacy.elapsed_seconds == pytest.approx(1.2)
    assert comparison.v1.elapsed_seconds == pytest.approx(0.4)
    assert comparison.speedup == pytest.approx(3.0)
    assert comparison.delta_seconds == pytest.approx(0.8)
    assert comparison.faster_engine == "v1"
    assert comparison.to_summary_dict() == {
        "legacy": {
            "name": "legacy",
            "elapsed_seconds": 1.2,
            "elapsed_ms": 1200.0,
            "metadata": {"candidate_id": "fa_speed"},
        },
        "v1": {
            "name": "v1",
            "elapsed_seconds": 0.4,
            "elapsed_ms": 400.0,
            "metadata": {"candidate_id": "fa_speed"},
        },
        "speedup": 3.0,
        "delta_seconds": 0.8,
        "faster_engine": "v1",
    }


def test_comparison_markdown_render_is_compact() -> None:
    comparison = BenchmarkComparison(
        legacy=BenchmarkResult(name="legacy", elapsed_seconds=0.8),
        v1=BenchmarkResult(name="v1", elapsed_seconds=0.5),
    )

    assert comparison.to_markdown() == "\n".join(
        [
            "## Compute v1 Benchmark",
            "",
            "- legacy: 800.00 ms",
            "- v1: 500.00 ms",
            "- speedup: 1.60x",
            "- faster: v1",
        ]
    )


def test_evaluation_benchmark_serializes_run_summary() -> None:
    summary = EvaluationBenchmark(
        engine="v1",
        jobs=4,
        candidate_count=12,
        trade_days=30,
        panel_rows=1200,
        universe_daily_mean=40.0,
        total_seconds=3.4567891,
        calculate_seconds=1.1,
        preprocess_seconds=0.9,
        metrics_seconds=1.2,
        artifact_seconds=0.2,
    )

    assert summary.to_dict() == {
        "engine": "v1",
        "jobs": 4,
        "candidate_count": 12,
        "trade_days": 30,
        "panel_rows": 1200,
        "universe_daily_mean": 40.0,
        "total_seconds": 3.456789,
        "calculate_seconds": 1.1,
        "preprocess_seconds": 0.9,
        "metrics_seconds": 1.2,
        "artifact_seconds": 0.2,
    }
