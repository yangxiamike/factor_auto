"""Lightweight benchmark helpers for compute engine comparisons."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from time import perf_counter
from typing import Any

Clock = Callable[[], float]
SUMMARY_PRECISION = 6


@dataclass(slots=True)
class BenchmarkResult:
    """A single benchmark measurement."""

    name: str
    elapsed_seconds: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def elapsed_ms(self) -> float:
        return self.elapsed_seconds * 1000.0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["elapsed_seconds"] = round(self.elapsed_seconds, SUMMARY_PRECISION)
        payload["elapsed_ms"] = round(self.elapsed_ms, SUMMARY_PRECISION)
        return payload


class BenchmarkTimer:
    """Context manager that records elapsed wall-clock time."""

    def __init__(self, name: str, clock: Clock = perf_counter, metadata: dict[str, Any] | None = None) -> None:
        self.name = name
        self.clock = clock
        self.metadata = dict(metadata or {})
        self._start: float | None = None
        self.result: BenchmarkResult | None = None

    def __enter__(self) -> BenchmarkTimer:
        self._start = self.clock()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._start is None:
            raise RuntimeError("benchmark timer was not started")
        elapsed_seconds = self.clock() - self._start
        self.result = BenchmarkResult(
            name=self.name,
            elapsed_seconds=max(elapsed_seconds, 0.0),
            metadata=self.metadata,
        )


def timed_call(
    name: str,
    func: Callable[..., Any],
    *args: Any,
    clock: Clock = perf_counter,
    metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> BenchmarkResult:
    """Run a callable and return its timing measurement."""

    with BenchmarkTimer(name=name, clock=clock, metadata=metadata) as timer:
        func(*args, **kwargs)
    if timer.result is None:
        raise RuntimeError("benchmark timer did not capture a result")
    return timer.result


@dataclass(slots=True)
class EvaluationBenchmark:
    """Serialized batch benchmark written beside run artifacts."""

    engine: str
    jobs: str | int
    candidate_count: int
    trade_days: int
    panel_rows: int
    universe_daily_mean: float
    total_seconds: float
    calculate_seconds: float
    preprocess_seconds: float
    metrics_seconds: float
    artifact_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "jobs": self.jobs,
            "candidate_count": int(self.candidate_count),
            "trade_days": int(self.trade_days),
            "panel_rows": int(self.panel_rows),
            "universe_daily_mean": round(float(self.universe_daily_mean), SUMMARY_PRECISION),
            "total_seconds": round(float(self.total_seconds), SUMMARY_PRECISION),
            "calculate_seconds": round(float(self.calculate_seconds), SUMMARY_PRECISION),
            "preprocess_seconds": round(float(self.preprocess_seconds), SUMMARY_PRECISION),
            "metrics_seconds": round(float(self.metrics_seconds), SUMMARY_PRECISION),
            "artifact_seconds": round(float(self.artifact_seconds), SUMMARY_PRECISION),
        }


@dataclass(slots=True)
class BenchmarkComparison:
    """A side-by-side runtime comparison between legacy and compute v1."""

    legacy: BenchmarkResult
    v1: BenchmarkResult

    @property
    def speedup(self) -> float:
        if self.v1.elapsed_seconds == 0.0:
            return float("inf")
        return self.legacy.elapsed_seconds / self.v1.elapsed_seconds

    @property
    def delta_seconds(self) -> float:
        return self.legacy.elapsed_seconds - self.v1.elapsed_seconds

    @property
    def faster_engine(self) -> str:
        if self.legacy.elapsed_seconds < self.v1.elapsed_seconds:
            return self.legacy.name
        if self.v1.elapsed_seconds < self.legacy.elapsed_seconds:
            return self.v1.name
        return "tie"

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "legacy": self.legacy.to_dict(),
            "v1": self.v1.to_dict(),
            "speedup": round(self.speedup, SUMMARY_PRECISION),
            "delta_seconds": round(self.delta_seconds, SUMMARY_PRECISION),
            "faster_engine": self.faster_engine,
        }

    def to_markdown(self, title: str = "Compute v1 Benchmark") -> str:
        return "\n".join(
            [
                f"## {title}",
                "",
                f"- legacy: {self.legacy.elapsed_ms:.2f} ms",
                f"- v1: {self.v1.elapsed_ms:.2f} ms",
                f"- speedup: {self.speedup:.2f}x",
                f"- faster: {self.faster_engine}",
            ]
        )


def compare_legacy_vs_v1(
    legacy_runner: Callable[[], Any],
    v1_runner: Callable[[], Any],
    *,
    clock: Clock = perf_counter,
    legacy_name: str = "legacy",
    v1_name: str = "v1",
    metadata: dict[str, Any] | None = None,
) -> BenchmarkComparison:
    """Benchmark two callables and return a compact comparison object."""

    shared_metadata = dict(metadata or {})
    legacy = timed_call(legacy_name, legacy_runner, clock=clock, metadata=shared_metadata)
    v1 = timed_call(v1_name, v1_runner, clock=clock, metadata=shared_metadata)
    return BenchmarkComparison(legacy=legacy, v1=v1)
