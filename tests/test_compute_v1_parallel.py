import time

import pytest

from factor_autoresearch.engine.parallel import parse_jobs, run_ordered
from factor_autoresearch.engine.routing import get_engine_module, normalize_engine_name, validate_engine_name


def test_parse_jobs_auto_caps_to_candidate_count(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("factor_autoresearch.engine.parallel.os.cpu_count", lambda: 8)
    assert parse_jobs("auto", candidate_count=3) == 3


def test_parse_jobs_positive_integer_caps_to_candidate_count() -> None:
    assert parse_jobs(10, candidate_count=4) == 4
    assert parse_jobs(2, candidate_count=4) == 2


@pytest.mark.parametrize("jobs", [0, -1, 1.5, "AUTO", "two", True])
def test_parse_jobs_rejects_invalid_values(jobs: object) -> None:
    with pytest.raises(ValueError):
        parse_jobs(jobs=jobs, candidate_count=3)  # type: ignore[arg-type]


def test_run_ordered_preserves_input_order_with_parallel_completion() -> None:
    items = [0, 1, 2, 3]

    def worker(value: int) -> int:
        time.sleep(0.02 * (len(items) - value))
        return value * 10

    results = run_ordered(items, worker, jobs=4)

    assert [result.item for result in results] == items
    assert [result.value for result in results] == [0, 10, 20, 30]
    assert all(result.ok for result in results)


def test_run_ordered_keeps_exception_in_original_slot() -> None:
    items = ["a", "boom", "c"]

    def worker(value: str) -> str:
        if value == "boom":
            time.sleep(0.01)
            raise RuntimeError("expected failure")
        time.sleep(0.02 if value == "a" else 0.0)
        return value.upper()

    results = run_ordered(items, worker, jobs="auto")

    assert [result.item for result in results] == items
    assert results[0].value == "A"
    assert results[0].error is None
    assert results[1].value is None
    assert isinstance(results[1].error, RuntimeError)
    assert str(results[1].error) == "expected failure"
    assert results[2].value == "C"
    assert results[2].error is None


def test_validate_engine_name_accepts_supported_values() -> None:
    assert validate_engine_name("legacy") == "legacy"
    assert validate_engine_name(" V1 ") == "v1"
    assert normalize_engine_name(None) == "legacy"


def test_validate_engine_name_rejects_unsupported_values() -> None:
    with pytest.raises(ValueError, match="Unsupported engine"):
        validate_engine_name("gpu")


def test_get_engine_module_returns_expected_module() -> None:
    module = get_engine_module("v1")
    assert module.ENGINE_NAME == "v1"
