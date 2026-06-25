"""
Compute v1 benchmark 模块
负责记录 legacy 与 v1 的运行耗时和对比结果。
不参与计算逻辑，只为验收和优化决策提供证据。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from time import perf_counter
from typing import Any

# ============== 常量和类型 ==============
Clock = Callable[[], float]
SUMMARY_PRECISION = 6


# ============== benchmark 结果 ==============
@dataclass(slots=True)
class BenchmarkResult:
    """单次计时: 保存一个阶段或一次调用的耗时。"""

    name: str
    elapsed_seconds: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def elapsed_ms(self) -> float:
        """毫秒耗时: 由秒级耗时换算。"""

        return self.elapsed_seconds * 1000.0

    def to_dict(self) -> dict[str, Any]:
        """序列化: 输出稳定精度的 benchmark 字典。"""

        payload = asdict(self)
        payload["elapsed_seconds"] = round(self.elapsed_seconds, SUMMARY_PRECISION)
        payload["elapsed_ms"] = round(self.elapsed_ms, SUMMARY_PRECISION)
        return payload


# ============== 计时工具 ==============
class BenchmarkTimer:
    """计时器: 用上下文管理器记录 wall-clock 耗时。"""

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
    """函数计时: 执行 callable 并返回计时结果。"""

    with BenchmarkTimer(name=name, clock=clock, metadata=metadata) as timer:
        func(*args, **kwargs)
    if timer.result is None:
        raise RuntimeError("benchmark timer did not capture a result")
    return timer.result


# ============== 评估运行 benchmark ==============
@dataclass(slots=True)
class EvaluationBenchmark:
    """评估 benchmark: 写入 run 目录的批量耗时摘要。"""

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


# ============== 引擎对比 ==============
@dataclass(slots=True)
class BenchmarkComparison:
    """引擎对比: 保存 legacy 与 v1 的并排耗时。"""

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
    """引擎对比: 分别计时 legacy 与 v1 callable。"""

    shared_metadata = dict(metadata or {})
    legacy = timed_call(legacy_name, legacy_runner, clock=clock, metadata=shared_metadata)
    v1 = timed_call(v1_name, v1_runner, clock=clock, metadata=shared_metadata)
    return BenchmarkComparison(legacy=legacy, v1=v1)
