"""
compute engine 并发辅助: 提供有序、可降级的候选计算执行器。
本模块只调度任务和收集结果，不理解候选因子或指标含义。
"""

from __future__ import annotations

import os
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, TypeVar

T = TypeVar("T")
AUTO_MAX_WORKERS = 3
AUTO_SERIAL_THRESHOLD = 32


# ============== 并发结果结构 ==============
@dataclass(frozen=True)
class OrderedResult:
    """有序结果: 保留输入项、返回值和异常信息。"""

    item: Any
    value: Any = None
    error: Exception | None = None

    @property
    def ok(self) -> bool:
        """是否成功: 没有异常时视为成功。"""
        return self.error is None


# ============== worker 数量解析 ==============
def parse_jobs(jobs: str | int, candidate_count: int) -> int:
    """解析 jobs: 把配置值转成实际 worker 数量。"""
    if candidate_count < 0:
        raise ValueError("candidate_count must be >= 0.")
    if candidate_count == 0:
        return 1
    if jobs == "auto":
        if candidate_count <= AUTO_SERIAL_THRESHOLD:
            return 1
        detected = os.cpu_count() or 1
        return max(1, min(detected, candidate_count, AUTO_MAX_WORKERS))
    if isinstance(jobs, bool) or not isinstance(jobs, int):
        raise ValueError("jobs must be 'auto' or a positive integer.")
    if jobs <= 0:
        raise ValueError("jobs must be 'auto' or a positive integer.")
    return min(jobs, candidate_count)


# ============== 有序执行 ==============
def run_ordered(items: list[T] | tuple[T, ...], worker: Any, jobs: str | int) -> list[OrderedResult]:
    """有序执行: 可并发处理输入项，并按原输入顺序返回结果。"""
    sequence = list(items)
    if not sequence:
        return []

    worker_count = parse_jobs(jobs, len(sequence))
    if worker_count == 1:
        return [_run_one(item, worker) for item in sequence]

    ordered_results: list[OrderedResult | None] = [None] * len(sequence)
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_map: dict[Future[Any], int] = {
            executor.submit(worker, item): index for index, item in enumerate(sequence)
        }
        for future in as_completed(future_map):
            index = future_map[future]
            item = sequence[index]
            try:
                ordered_results[index] = OrderedResult(item=item, value=future.result())
            except Exception as exc:  # noqa: BLE001
                ordered_results[index] = OrderedResult(item=item, error=exc)

    return [result for result in ordered_results if result is not None]


def _run_one(item: T, worker: Any) -> OrderedResult:
    """单项执行: 串行路径复用和并发路径一致的结果结构。"""
    try:
        return OrderedResult(item=item, value=worker(item))
    except Exception as exc:  # noqa: BLE001
        return OrderedResult(item=item, error=exc)
