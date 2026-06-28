from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from factor_autoresearch.factor_asset_values import load_library_factor_values, save_factor_values
from factor_autoresearch.factor_assets import (
    AssetCandidateRecord,
    get_factor_record,
    ingest_block3_batch,
    register_factor_value_scope,
)


def _series_from_fixture(sample_dataset_dir: Path, column: str, *, scale: float = 1.0) -> pd.Series:
    frame = pd.read_parquet(sample_dataset_dir / "panel.parquet")
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    series = frame.set_index(["trade_date", "ts_code"])[column].astype(float) * scale
    return series.sort_index()


def _admit_factor(asset_dir: Path, factor_id: str) -> None:
    ingest_block3_batch(
        asset_dir,
        records=[
            AssetCandidateRecord(
                decision="admitted",
                candidate_payload={
                    "candidate_id": factor_id,
                    "expression": f"cs_rank({factor_id})",
                    "category": "intraday",
                    "economic_rationale": factor_id,
                    "metrics": {"directional_rankic_mean": 0.12},
                },
                run_payload={
                    "run_id": "run_001",
                    "source_universe_key": "univ_trade_zz500",
                    "forward_return_definition": "next_open_to_open_v1",
                    "sample_protocol_hash": "sha256:sample",
                    "preprocess_config_hash": "sha256:prep",
                    "engine_version": "compute_v1",
                    "created_at": "2026-06-28T10:00:00+08:00",
                },
            )
        ],
    )


def test_save_factor_values_writes_raw_preprocessed_and_manifest(sample_dataset_dir: Path, tmp_path: Path) -> None:
    asset_dir = tmp_path / "factor_assets"
    _admit_factor(asset_dir, "fa_001")
    raw_factor = _series_from_fixture(sample_dataset_dir, "close_hfq")
    preprocessed = _series_from_fixture(sample_dataset_dir, "open_hfq", scale=0.1)

    result = save_factor_values(
        asset_dir,
        factor_id="fa_001",
        expression_hash="sha256:expr",
        source_run_id="run_001",
        source_universe_key="univ_trade_zz500",
        forward_return_definition="next_open_to_open_v1",
        sample_protocol_hash="sha256:sample",
        preprocess_config_hash="sha256:prep",
        raw_factor=raw_factor,
        preprocessed_factor=preprocessed,
        created_at="2026-06-28T10:00:00+08:00",
    )
    register_factor_value_scope(asset_dir, factor_id="fa_001", value_scope_hash=result["value_scope_hash"])

    manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
    assert Path(result["raw_path"]).exists()
    assert Path(result["preprocessed_path"]).exists()
    assert manifest["factor_id"] == "fa_001"
    assert manifest["row_count"] == len(preprocessed)
    assert manifest["value_scope_hash"] == result["value_scope_hash"]
    assert get_factor_record(asset_dir, "fa_001")["value_scopes"] == [result["value_scope_hash"]]


def test_save_factor_values_keeps_multiple_value_scopes_without_override(sample_dataset_dir: Path, tmp_path: Path) -> None:
    asset_dir = tmp_path / "factor_assets"
    _admit_factor(asset_dir, "fa_001")
    raw_factor = _series_from_fixture(sample_dataset_dir, "close_hfq")
    preprocessed = _series_from_fixture(sample_dataset_dir, "open_hfq", scale=0.1)

    first = save_factor_values(
        asset_dir,
        factor_id="fa_001",
        expression_hash="sha256:expr",
        source_run_id="run_001",
        source_universe_key="univ_trade_zz500",
        forward_return_definition="next_open_to_open_v1",
        sample_protocol_hash="sha256:sample",
        preprocess_config_hash="sha256:prep",
        raw_factor=raw_factor,
        preprocessed_factor=preprocessed,
        created_at="2026-06-28T10:00:00+08:00",
    )
    second = save_factor_values(
        asset_dir,
        factor_id="fa_001",
        expression_hash="sha256:expr",
        source_run_id="run_002",
        source_universe_key="univ_trade_zz500",
        forward_return_definition="next_open_to_open_v1",
        sample_protocol_hash="sha256:sample_alt",
        preprocess_config_hash="sha256:prep",
        raw_factor=raw_factor,
        preprocessed_factor=preprocessed,
        created_at="2026-06-28T10:10:00+08:00",
    )

    assert first["value_scope_hash"] != second["value_scope_hash"]
    assert Path(first["manifest_path"]).exists()
    assert Path(second["manifest_path"]).exists()


def test_load_library_factor_values_returns_only_matching_active_values(sample_dataset_dir: Path, tmp_path: Path) -> None:
    asset_dir = tmp_path / "factor_assets"
    _admit_factor(asset_dir, "fa_active")
    _admit_factor(asset_dir, "fa_mismatch")
    raw_factor = _series_from_fixture(sample_dataset_dir, "close_hfq")
    preprocessed = _series_from_fixture(sample_dataset_dir, "open_hfq", scale=0.1)

    active_result = save_factor_values(
        asset_dir,
        factor_id="fa_active",
        expression_hash="sha256:expr",
        source_run_id="run_001",
        source_universe_key="univ_trade_zz500",
        forward_return_definition="next_open_to_open_v1",
        sample_protocol_hash="sha256:sample",
        preprocess_config_hash="sha256:prep",
        raw_factor=raw_factor,
        preprocessed_factor=preprocessed,
        created_at="2026-06-28T10:00:00+08:00",
    )
    register_factor_value_scope(asset_dir, factor_id="fa_active", value_scope_hash=active_result["value_scope_hash"])
    mismatch_result = save_factor_values(
        asset_dir,
        factor_id="fa_mismatch",
        expression_hash="sha256:expr",
        source_run_id="run_001",
        source_universe_key="univ_trade_zz500",
        forward_return_definition="next_open_to_open_v1",
        sample_protocol_hash="sha256:other",
        preprocess_config_hash="sha256:prep",
        raw_factor=raw_factor,
        preprocessed_factor=preprocessed,
        created_at="2026-06-28T10:00:00+08:00",
    )
    register_factor_value_scope(asset_dir, factor_id="fa_mismatch", value_scope_hash=mismatch_result["value_scope_hash"])

    loaded = load_library_factor_values(
        asset_dir,
        source_universe_key="univ_trade_zz500",
        forward_return_definition="next_open_to_open_v1",
        sample_protocol_hash="sha256:sample",
        preprocess_config_hash="sha256:prep",
        date_start="2024-01-02",
        date_end="2024-01-11",
    )

    assert loaded.loaded_factor_ids == ("fa_active",)
    assert list(loaded.values) == ["fa_active"]
    assert loaded.values["fa_active"].name == "fa_active"


def test_load_library_factor_values_reports_skip_reason_on_scope_mismatch(sample_dataset_dir: Path, tmp_path: Path) -> None:
    asset_dir = tmp_path / "factor_assets"
    _admit_factor(asset_dir, "fa_001")
    raw_factor = _series_from_fixture(sample_dataset_dir, "close_hfq")
    preprocessed = _series_from_fixture(sample_dataset_dir, "open_hfq", scale=0.1)
    result = save_factor_values(
        asset_dir,
        factor_id="fa_001",
        expression_hash="sha256:expr",
        source_run_id="run_001",
        source_universe_key="univ_trade_zz500",
        forward_return_definition="next_open_to_open_v1",
        sample_protocol_hash="sha256:sample",
        preprocess_config_hash="sha256:prep",
        raw_factor=raw_factor,
        preprocessed_factor=preprocessed,
        created_at="2026-06-28T10:00:00+08:00",
    )
    register_factor_value_scope(asset_dir, factor_id="fa_001", value_scope_hash=result["value_scope_hash"])

    loaded = load_library_factor_values(
        asset_dir,
        source_universe_key="univ_trade_zz500",
        forward_return_definition="next_open_to_open_v1",
        sample_protocol_hash="sha256:unexpected",
        preprocess_config_hash="sha256:prep",
        date_start="2024-01-02",
        date_end="2024-01-11",
    )

    assert loaded.loaded_factor_ids == ()
    assert loaded.skipped[0]["factor_id"] == "fa_001"
    assert loaded.skipped[0]["reason"] == "sample_protocol_hash_mismatch"
