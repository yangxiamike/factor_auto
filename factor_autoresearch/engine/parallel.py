"""Ordered parallel helpers for compute execution."""

from __future__ import annotations

import os
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class OrderedResult:
    """Stable output slot for ordered parallel execution."""

    item: Any
    value: Any = None
    error: Exception | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def parse_jobs(jobs: str | int, candidate_count: int) -> int:
    """Normalize jobs to a usable worker count."""
    if candidate_count < 0:
        raise ValueError("candidate_count must be >= 0.")
    if candidate_count == 0:
        return 1
    if jobs == "auto":
        detected = os.cpu_count() or 1
        return max(1, min(detected, candidate_count))
    if isinstance(jobs, bool) or not isinstance(jobs, int):
        raise ValueError("jobs must be 'auto' or a positive integer.")
    if jobs <= 0:
        raise ValueError("jobs must be 'auto' or a positive integer.")
    return min(jobs, candidate_count)


def run_ordered(items: list[T] | tuple[T, ...], worker: Any, jobs: str | int) -> list[OrderedResult]:
    """Run work in parallel while returning results in input order."""
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
    try:
        return OrderedResult(item=item, value=worker(item))
    except Exception as exc:  # noqa: BLE001
        return OrderedResult(item=item, error=exc)
