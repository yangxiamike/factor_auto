from __future__ import annotations

import json

import pandas as pd
import pytest

from factor_autoresearch.data_loader import DataLoader


def test_data_loader_loads_fixture(sample_dataset_dir, test_config) -> None:
    dataset = DataLoader(config=test_config, dataset_path=sample_dataset_dir).load()
    assert list(dataset.panel.index.names) == ["trade_date", "ts_code"]
    assert dataset.manifest["dataset_id"] == test_config.dataset_id


def test_data_loader_raises_on_manifest_mismatch(sample_dataset_dir, test_config) -> None:
    manifest_path = sample_dataset_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["dataset_id"] = "unexpected_dataset"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="dataset_id mismatch between manifest and config"):
        DataLoader(config=test_config, dataset_path=sample_dataset_dir).load()


@pytest.mark.parametrize(
    ("filename", "column_to_drop", "expected_message"),
    [
        ("panel.parquet", "industry", "panel.parquet missing columns: industry"),
        ("forward_returns.parquet", "fwd_ret_5d", "forward_returns.parquet missing columns: fwd_ret_5d"),
    ],
)
def test_data_loader_raises_on_missing_required_columns(
    sample_dataset_dir,
    test_config,
    filename: str,
    column_to_drop: str,
    expected_message: str,
) -> None:
    file_path = sample_dataset_dir / filename
    frame = pd.read_parquet(file_path).drop(columns=[column_to_drop])
    frame.to_parquet(file_path, index=False)

    with pytest.raises(ValueError, match=expected_message):
        DataLoader(config=test_config, dataset_path=sample_dataset_dir).load()


@pytest.mark.parametrize(
    ("filename", "expected_message"),
    [
        ("panel.parquet", "panel.parquet contains duplicate \\(trade_date, ts_code\\)"),
        ("forward_returns.parquet", "forward_returns.parquet contains duplicate \\(trade_date, ts_code\\)"),
    ],
)
def test_data_loader_raises_on_duplicate_primary_keys(
    sample_dataset_dir,
    test_config,
    filename: str,
    expected_message: str,
) -> None:
    file_path = sample_dataset_dir / filename
    frame = pd.read_parquet(file_path)
    duplicated = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    duplicated.to_parquet(file_path, index=False)

    with pytest.raises(ValueError, match=expected_message):
        DataLoader(config=test_config, dataset_path=sample_dataset_dir).load()
