from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from factor_autoresearch.sample_protocol import (
    build_sample_protocol,
    build_sample_protocol_from_dataset,
    canonical_json,
)


def test_build_sample_protocol_from_dataset_defaults_to_sandbox_protocol(sample_dataset_dir) -> None:
    protocol = build_sample_protocol_from_dataset(sample_dataset_dir)

    assert protocol.sample_protocol_id == "sandbox_v1"
    assert protocol.split_policy == "single_full_sample"
    assert protocol.sample_protocol_hash.startswith("sha256:")
    assert protocol.observed_date_range == {
        "date_start": "2024-01-02",
        "date_end": "2024-01-11",
    }
    assert protocol.as_dict()["slices"] == [
        {
            "slice_id": "full_sample",
            "role": "full_sample",
            "date_start": "2024-01-02",
            "date_end": "2024-01-11",
        }
    ]


def test_build_sample_protocol_from_dataset_builds_fixed_mining_slices(sample_dataset_dir) -> None:
    protocol = build_sample_protocol_from_dataset(sample_dataset_dir, sample_protocol_id="mining_v1")

    assert protocol.trade_date_count == 8
    assert protocol.split_policy == "time_ordered_oos_and_walk_forward"
    assert protocol.rules["date_source"] == "panel_trade_dates"
    assert protocol.rules["main_windows"] == {
        "formation_fraction": "1/2",
        "validation_fraction": "1/4",
        "oos_fraction": "remainder",
        "formation_count": 4,
        "validation_count": 2,
        "oos_count": 2,
    }
    assert protocol.rules["walk_forward"] == {
        "formation_count": 4,
        "validation_count": 1,
        "step_count": 1,
        "generated_pairs": 2,
        "cutoff_before_oos_count": 6,
    }
    assert protocol.as_dict()["slices"] == [
        {
            "slice_id": "formation",
            "role": "in_sample",
            "date_start": "2024-01-02",
            "date_end": "2024-01-05",
        },
        {
            "slice_id": "validation",
            "role": "validation",
            "date_start": "2024-01-08",
            "date_end": "2024-01-09",
        },
        {
            "slice_id": "oos",
            "role": "oos",
            "date_start": "2024-01-10",
            "date_end": "2024-01-11",
        },
        {
            "slice_id": "wf_001_formation",
            "role": "walk_forward_formation",
            "pair_id": "wf_001",
            "date_start": "2024-01-02",
            "date_end": "2024-01-05",
        },
        {
            "slice_id": "wf_001_validation",
            "role": "walk_forward_validation",
            "pair_id": "wf_001",
            "date_start": "2024-01-08",
            "date_end": "2024-01-08",
        },
        {
            "slice_id": "wf_002_formation",
            "role": "walk_forward_formation",
            "pair_id": "wf_002",
            "date_start": "2024-01-03",
            "date_end": "2024-01-08",
        },
        {
            "slice_id": "wf_002_validation",
            "role": "walk_forward_validation",
            "pair_id": "wf_002",
            "date_start": "2024-01-09",
            "date_end": "2024-01-09",
        },
    ]


def test_build_sample_protocol_uses_fixed_draft_when_dates_are_compatible(
    sample_dataset_dir,
    monkeypatch,
    tmp_path: Path,
) -> None:
    draft_path = tmp_path / "mining_v1_sample_protocol_v1.toml"
    draft_path.write_text(
        "\n".join(
            [
                'sample_protocol_id = "mining_v1"',
                'purpose = "strict mining evaluation"',
                'split_policy = "time_ordered_oos_and_walk_forward"',
                'forward_return_definition = "next_open_to_open_v1"',
                'universe = "csi500"',
                'date_start = "2024-01-02"',
                'date_end = "2024-01-11"',
                "",
                "[[slices]]",
                'slice_id = "formation"',
                'role = "in_sample"',
                'date_start = "2024-01-02"',
                'date_end = "2024-01-05"',
                "",
                "[[slices]]",
                'slice_id = "validation"',
                'role = "validation"',
                'date_start = "2024-01-08"',
                'date_end = "2024-01-09"',
                "",
                "[[slices]]",
                'slice_id = "oos"',
                'role = "oos"',
                'date_start = "2024-01-10"',
                'date_end = "2024-01-11"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("factor_autoresearch.sample_protocol.MINING_V1_DRAFT_PATH", draft_path)

    protocol = build_sample_protocol_from_dataset(sample_dataset_dir, sample_protocol_id="mining_v1")

    assert protocol.rules["date_source"] == "draft_config"
    assert protocol.rules["draft_config_path"] == str(draft_path)
    assert protocol.as_dict()["slices"] == [
        {
            "slice_id": "formation",
            "role": "in_sample",
            "date_start": "2024-01-02",
            "date_end": "2024-01-05",
        },
        {
            "slice_id": "validation",
            "role": "validation",
            "date_start": "2024-01-08",
            "date_end": "2024-01-09",
        },
        {
            "slice_id": "oos",
            "role": "oos",
            "date_start": "2024-01-10",
            "date_end": "2024-01-11",
        },
    ]


def test_build_sample_protocol_is_stable_for_reordered_duplicate_trade_dates(sample_dataset_dir) -> None:
    manifest = json.loads((sample_dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    panel = pd.read_parquet(sample_dataset_dir / "panel.parquet")
    original_dates = panel["trade_date"].tolist()
    reordered_dates = list(reversed(original_dates)) + original_dates[:3]

    protocol_a = build_sample_protocol(
        dataset_manifest=manifest,
        trade_dates=original_dates,
        sample_protocol_id="mining_v1",
    )
    protocol_b = build_sample_protocol(
        dataset_manifest=manifest,
        trade_dates=reordered_dates,
        sample_protocol_id="mining_v1",
    )

    assert canonical_json(protocol_a.as_dict()) == canonical_json(protocol_b.as_dict())
    assert protocol_a.sample_protocol_hash == protocol_b.sample_protocol_hash


def test_build_mainboard_walkforward_protocol_uses_real_trade_dates() -> None:
    manifest = {
        "dataset_id": "mainboard_pressure_v1",
        "sample_protocol_id": "mining_v1_mainboard_walkforward",
        "sample_protocol_config": {
            "formation_years": 5,
            "embargo_trade_days": 20,
            "test_years": 1,
            "final_oos_start": "2026-01-01",
            "final_oos_end": "2026-05-31",
        },
        "date_start": "2014-01-01",
        "date_end": "2026-05-31",
        "warmup_start": "2013-01-01",
        "forward_return_definition": "next_open_to_open_v1",
        "universe": "mainboard",
    }
    trade_dates = pd.bdate_range("2013-01-01", "2026-05-31")

    protocol = build_sample_protocol(
        dataset_manifest=manifest,
        trade_dates=trade_dates,
    )

    slices = protocol.as_dict()["slices"]
    roles = [sample_slice["role"] for sample_slice in slices]
    assert protocol.sample_protocol_id == "mining_v1_mainboard_walkforward"
    assert protocol.split_policy == "walk_forward_5y_20d_embargo_1y_test_final_oos"
    assert protocol.dataset_date_range == {
        "date_start": "2014-01-01",
        "date_end": "2026-05-31",
    }
    assert protocol.observed_date_range == {
        "date_start": "2013-01-01",
        "date_end": "2026-05-29",
    }
    assert protocol.rules["walk_forward"] == {
        "formation_years": 5,
        "embargo_trade_days": 20,
        "test_years": 1,
        "step_years": 1,
        "generated_pairs": 6,
    }
    assert slices[0] == {
        "slice_id": "wf_001_formation",
        "role": "walk_forward_formation",
        "date_start": "2014-01-01",
        "date_end": "2018-12-31",
        "pair_id": "wf_001",
    }
    assert slices[1] == {
        "slice_id": "wf_001_embargo",
        "role": "walk_forward_embargo",
        "date_start": "2019-01-01",
        "date_end": "2019-01-28",
        "pair_id": "wf_001",
    }
    assert slices[2] == {
        "slice_id": "wf_001_test",
        "role": "walk_forward_test",
        "date_start": "2019-01-29",
        "date_end": "2020-01-28",
        "pair_id": "wf_001",
    }
    assert roles.count("walk_forward_test") == 6
    assert slices[-1] == {
        "slice_id": "final_oos",
        "role": "final_oos",
        "date_start": "2026-01-01",
        "date_end": "2026-05-29",
    }


def test_mainboard_walkforward_protocol_hash_is_stable_for_config_order() -> None:
    manifest_a = {
        "dataset_id": "mainboard_pressure_v1",
        "sample_protocol_id": "mining_v1_mainboard_walkforward",
        "sample_protocol_config": {
            "formation_years": 5,
            "embargo_trade_days": 20,
            "test_years": 1,
            "final_oos_start": "2026-01-01",
            "final_oos_end": "2026-05-31",
        },
        "date_start": "2014-01-01",
        "date_end": "2026-05-31",
        "warmup_start": "2013-01-01",
        "forward_return_definition": "next_open_to_open_v1",
        "universe": "mainboard",
    }
    manifest_b = {
        **manifest_a,
        "sample_protocol_config": {
            "final_oos_end": "2026-05-31",
            "test_years": 1,
            "final_oos_start": "2026-01-01",
            "embargo_trade_days": 20,
            "formation_years": 5,
        },
    }
    trade_dates = pd.bdate_range("2013-01-01", "2026-05-31").tolist()

    protocol_a = build_sample_protocol(dataset_manifest=manifest_a, trade_dates=trade_dates)
    protocol_b = build_sample_protocol(
        dataset_manifest=manifest_b,
        trade_dates=list(reversed(trade_dates)) + trade_dates[:5],
    )

    assert canonical_json(protocol_a.as_dict()) == canonical_json(protocol_b.as_dict())
    assert protocol_a.sample_protocol_hash == protocol_b.sample_protocol_hash


def test_build_sample_protocol_raises_on_missing_manifest_fields(sample_dataset_dir) -> None:
    manifest = json.loads((sample_dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest.pop("universe")

    with pytest.raises(ValueError, match="dataset manifest missing required fields: universe"):
        build_sample_protocol(
            dataset_manifest=manifest,
            trade_dates=["2024-01-02", "2024-01-03"],
            sample_protocol_id="sandbox_v1",
        )


def test_build_sample_protocol_raises_when_mining_dates_are_too_short(sample_dataset_dir) -> None:
    manifest = json.loads((sample_dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    panel = pd.read_parquet(sample_dataset_dir / "panel.parquet")
    short_dates = sorted(panel["trade_date"].dt.strftime("%Y-%m-%d").unique().tolist())[:7]

    with pytest.raises(ValueError, match="mining_v1 requires at least 8 unique trade dates"):
        build_sample_protocol(
            dataset_manifest=manifest,
            trade_dates=short_dates,
            sample_protocol_id="mining_v1",
        )
