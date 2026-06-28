from __future__ import annotations

from pathlib import Path

from factor_autoresearch.factor_asset_benchmark import (
    AssetAdmissionBenchmark,
    benchmark_admission_round,
    build_test_library,
    classify_benchmark,
)
from factor_autoresearch.factor_asset_values import load_library_factor_values


def test_classify_benchmark_follows_plan_thresholds() -> None:
    assert classify_benchmark(240.0) == ("strong_pass", False)
    assert classify_benchmark(480.0) == ("pass", False)
    assert classify_benchmark(900.0) == ("needs_optimization", True)
    assert classify_benchmark(1500.0) == ("fail", True)


def test_build_test_library_creates_active_values_loadable_by_scope(tmp_path: Path) -> None:
    asset_dir = tmp_path / "factor_assets"

    summary = build_test_library(asset_dir, library_size=3)
    loaded = load_library_factor_values(
        asset_dir,
        source_universe_key="univ_trade_zz500",
        forward_return_definition="next_open_to_open_v1",
        sample_protocol_hash="sha256:test_library_sample",
        preprocess_config_hash="sha256:test_library_preprocess",
        date_start="2024-01-02",
        date_end="2024-02-26",
    )

    assert summary.library_size == 3
    assert len(summary.factor_ids) == 3
    assert loaded.loaded_factor_ids == summary.factor_ids


def test_build_test_library_can_align_to_benchmark_scope(monkeypatch, tmp_path: Path) -> None:
    asset_dir = tmp_path / "factor_assets"
    scope = {
        "source_universe_key": "mainboard_fixture",
        "forward_return_definition": "next_open_to_open_v1",
        "sample_protocol_hash": "sha256:aligned_scope",
        "preprocess_config_hash": "sha256:aligned_preprocess",
        "date_start": "2024-03-01",
        "date_end": "2024-03-29",
    }
    monkeypatch.setattr(
        "factor_autoresearch.factor_asset_benchmark._benchmark_scope",
        lambda **kwargs: scope,
    )

    summary = build_test_library(
        asset_dir,
        library_size=2,
        config_path=tmp_path / "experiment.toml",
        dataset_path=tmp_path / "dataset",
        screening_gate_config_path=tmp_path / "screening.toml",
    )
    loaded = load_library_factor_values(
        asset_dir,
        source_universe_key="mainboard_fixture",
        forward_return_definition="next_open_to_open_v1",
        sample_protocol_hash="sha256:aligned_scope",
        preprocess_config_hash="sha256:aligned_preprocess",
        date_start="2024-03-01",
        date_end="2024-03-29",
    )

    assert summary.library_size == 2
    assert loaded.loaded_factor_ids == summary.factor_ids




def test_benchmark_scope_prefers_observed_trade_dates(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "factor_autoresearch.factor_asset_benchmark.load_experiment_config",
        lambda path: type(
            "ExperimentConfig",
            (),
            {
                "source_universe_key": "univ_trade_mainboard",
                "forward_return_definition": "next_open_to_open_v1",
                "date_start": "2014-01-01",
                "date_end": "2026-05-31",
            },
        )(),
    )
    monkeypatch.setattr(
        "factor_autoresearch.factor_asset_benchmark.load_block3_screening_config",
        lambda path: type("ScreeningConfig", (), {"screening_sample_roles": ["walk_forward_test"]})(),
    )
    monkeypatch.setattr(
        "factor_autoresearch.factor_asset_benchmark._hash_preprocess_config",
        lambda config: "sha256:preprocess_scope",
    )
    monkeypatch.setattr(
        "factor_autoresearch.factor_asset_benchmark.build_screening_sample_view",
        lambda **kwargs: type(
            "SampleView",
            (),
            {
                "dataset": type("Dataset", (), {"manifest": {"date_start": "2014-01-01", "date_end": "2026-05-31"}})(),
                "source_universe_key": "univ_trade_mainboard",
                "forward_return_definition": {"name": "next_open_to_open_v1", "available_horizons": ["1d", "5d", "20d"]},
                "sample_protocol_hash": "sha256:mainboard_scope",
                "evaluated_date_start": "2014-01-02",
                "evaluated_date_end": "2026-05-29",
            },
        )(),
    )

    from factor_autoresearch.factor_asset_benchmark import _benchmark_scope

    scope = _benchmark_scope(
        config_path=tmp_path / "experiment.toml",
        dataset_path=tmp_path / "dataset",
        screening_gate_config_path=tmp_path / "screening.toml",
    )

    assert scope["date_start"] == "2014-01-02"
    assert scope["date_end"] == "2026-05-29"
def test_benchmark_admission_round_returns_required_fields(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "factor_autoresearch.factor_asset_benchmark.load_library_factor_values",
        lambda *args, **kwargs: type("LoadResult", (), {"loaded_factor_ids": ("fa_001",), "values": {"fa_001": "stub"}})(),
    )
    monkeypatch.setattr(
        "factor_autoresearch.factor_asset_benchmark.run_block3_screening",
        lambda **kwargs: type("Summary", (), {"total_candidates": 5})(),
    )
    monkeypatch.setattr(
        "factor_autoresearch.factor_asset_benchmark._benchmark_scope",
        lambda **kwargs: {
            "source_universe_key": "univ_trade_zz500",
            "forward_return_definition": "next_open_to_open_v1",
            "sample_protocol_hash": "sha256:test_library_sample",
            "preprocess_config_hash": "sha256:test_library_preprocess",
            "date_start": "2024-01-02",
            "date_end": "2024-02-26",
        },
    )

    benchmark = benchmark_admission_round(
        config_path=tmp_path / "experiment.toml",
        candidates_path=tmp_path / "candidates.jsonl",
        dataset_path=tmp_path / "dataset",
        output_dir=tmp_path / "outputs",
        screening_gate_config_path=tmp_path / "screening.toml",
        asset_store_dir=tmp_path / "factor_assets",
    )

    assert isinstance(benchmark, AssetAdmissionBenchmark)
    payload = benchmark.as_dict()
    assert payload["total_candidates"] == 5
    assert payload["active_library_factors"] == 1
    assert "classification" in payload
    assert "should_trigger_optimization_loop" in payload

