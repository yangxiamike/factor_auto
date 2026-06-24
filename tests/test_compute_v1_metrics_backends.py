from __future__ import annotations

import builtins
import importlib
import importlib.util
import re
import sys

import pandas as pd
import pytest

from factor_autoresearch.calculator import FactorCalc
from factor_autoresearch.candidates import Candidate
from factor_autoresearch.compute_v1.panel import PanelStore
from factor_autoresearch.data_loader import DataLoader
from factor_autoresearch.metrics import compute_candidate_metrics as compute_legacy_metrics
from factor_autoresearch.preprocess import preprocess_factor

HAS_NUMBA = importlib.util.find_spec("numba") is not None


def _build_candidate() -> Candidate:
    return Candidate(
        candidate_id="fa_metric_backend_v1",
        name="metric_backend_v1",
        expression="cs_rank((close_hfq - open_hfq) / open_hfq)",
        expected_direction="positive",
        hypothesis="metric_backend_v1",
        category="intraday",
        lookback_days=1,
        created_at="2026-06-24",
        notes="metric_backend_v1",
    )


def _load_fixture_inputs(sample_dataset_dir, test_config):
    dataset = DataLoader(config=test_config, dataset_path=sample_dataset_dir).load()
    candidate = _build_candidate()
    calc = FactorCalc(test_config)
    raw_factor = calc.calculate(candidate, dataset)
    processed_factor = preprocess_factor(raw_factor, dataset, test_config)
    complexity_score = calc.complexity_score(candidate)
    return dataset, candidate, processed_factor, complexity_score


def _load_metrics_module():
    return importlib.import_module("factor_autoresearch.compute_v1.metrics")


def _reload_metrics_module_without_numba(monkeypatch: pytest.MonkeyPatch):
    original_import = builtins.__import__

    def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "numba" or name.startswith("numba."):
            raise ModuleNotFoundError("simulated missing optional dependency: numba")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _guarded_import)
    for module_name in list(sys.modules):
        if module_name == "numba" or module_name.startswith("numba."):
            monkeypatch.delitem(sys.modules, module_name, raising=False)
    for module_name in (
        "factor_autoresearch.compute_v1.metrics_kernels_numba",
        "factor_autoresearch.compute_v1.metrics_kernels",
        "factor_autoresearch.compute_v1.metrics",
    ):
        monkeypatch.delitem(sys.modules, module_name, raising=False)

    import factor_autoresearch.compute_v1.metrics as metrics_module

    return importlib.reload(metrics_module)


def _assert_metrics_close(left, right) -> None:
    pd.testing.assert_frame_equal(
        left.horizon_rows.sort_values("horizon").reset_index(drop=True),
        right.horizon_rows.sort_values("horizon").reset_index(drop=True),
        check_exact=False,
        atol=1e-12,
        rtol=1e-9,
    )
    pd.testing.assert_frame_equal(
        left.ic_series.sort_values(["horizon", "trade_date"]).reset_index(drop=True),
        right.ic_series.sort_values(["horizon", "trade_date"]).reset_index(drop=True),
        check_exact=False,
        atol=1e-12,
        rtol=1e-9,
    )
    assert left.aggregate["candidate_id"] == right.aggregate["candidate_id"]
    assert left.aggregate["effective_trade_days"] == right.aggregate["effective_trade_days"]
    assert left.aggregate["complexity_score"] == right.aggregate["complexity_score"]
    assert left.aggregate["coverage_mean"] == pytest.approx(
        right.aggregate["coverage_mean"],
        abs=1e-12,
        rel=1e-9,
    )


def test_resolve_metrics_backend_auto_falls_back_to_numpy_when_numba_unavailable(
    monkeypatch: pytest.MonkeyPatch,
    sample_dataset_dir,
    test_config,
) -> None:
    metrics_module = _reload_metrics_module_without_numba(monkeypatch)
    dataset, candidate, processed_factor, complexity_score = _load_fixture_inputs(
        sample_dataset_dir,
        test_config,
    )

    resolved = metrics_module.resolve_metrics_backend("auto")
    assert resolved.name == "numpy"

    auto_result = metrics_module.compute_candidate_metrics(
        candidate_id=candidate.candidate_id,
        factor=processed_factor,
        dataset=dataset,
        config=test_config,
        complexity_score=complexity_score,
        backend="auto",
    )
    numpy_result = metrics_module.compute_candidate_metrics(
        candidate_id=candidate.candidate_id,
        factor=processed_factor,
        dataset=dataset,
        config=test_config,
        complexity_score=complexity_score,
        backend="numpy",
    )

    _assert_metrics_close(auto_result, numpy_result)


def test_compute_candidate_metrics_numpy_backend_matches_legacy_within_tolerance(
    sample_dataset_dir,
    test_config,
) -> None:
    metrics_module = _load_metrics_module()
    dataset, candidate, processed_factor, complexity_score = _load_fixture_inputs(
        sample_dataset_dir,
        test_config,
    )

    legacy = compute_legacy_metrics(
        candidate_id=candidate.candidate_id,
        factor=processed_factor,
        dataset=dataset,
        config=test_config,
        complexity_score=complexity_score,
    )
    numpy_result = metrics_module.compute_candidate_metrics(
        candidate_id=candidate.candidate_id,
        factor=processed_factor,
        dataset=dataset,
        config=test_config,
        complexity_score=complexity_score,
        backend="numpy",
    )

    _assert_metrics_close(numpy_result, legacy)


@pytest.mark.skipif(not HAS_NUMBA, reason="numba is not installed in this environment")
def test_compute_candidate_metrics_from_matrix_numba_backend_matches_numpy(
    sample_dataset_dir,
    test_config,
) -> None:
    metrics_module = _load_metrics_module()
    dataset, candidate, processed_factor, complexity_score = _load_fixture_inputs(
        sample_dataset_dir,
        test_config,
    )
    panel_store = PanelStore.from_dataset(dataset)
    panel_store, returns_cube = metrics_module.build_returns_cube(dataset, test_config, panel_store)
    factor_matrix = processed_factor.reindex(panel_store.long_index).to_numpy(dtype=float).reshape(
        len(panel_store.date_index),
        len(panel_store.asset_index),
    )

    numpy_backend = metrics_module.resolve_metrics_backend("numpy")
    numba_backend = metrics_module.resolve_metrics_backend("numba")
    assert numpy_backend.name == "numpy"
    assert numba_backend.name == "numba"

    numpy_result = metrics_module.compute_candidate_metrics_from_matrix(
        candidate_id=candidate.candidate_id,
        factor_matrix=factor_matrix,
        panel_store=panel_store,
        returns_cube=returns_cube,
        config=test_config,
        complexity_score=complexity_score,
        backend="numpy",
    )
    numba_result = metrics_module.compute_candidate_metrics_from_matrix(
        candidate_id=candidate.candidate_id,
        factor_matrix=factor_matrix,
        panel_store=panel_store,
        returns_cube=returns_cube,
        config=test_config,
        complexity_score=complexity_score,
        backend="numba",
    )

    assert list(numba_result.horizon_rows.columns) == list(numpy_result.horizon_rows.columns)
    assert list(numba_result.ic_series.columns) == list(numpy_result.ic_series.columns)
    _assert_metrics_close(numba_result, numpy_result)


def test_resolve_metrics_backend_numba_raises_clear_error_when_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metrics_module = _reload_metrics_module_without_numba(monkeypatch)

    with pytest.raises(Exception, match=re.compile(r"numba.*(available|install|installed)", re.IGNORECASE)):
        metrics_module.resolve_metrics_backend("numba")
