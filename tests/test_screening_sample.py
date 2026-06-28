from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from factor_autoresearch.screening_sample import build_screening_sample_view


def test_build_screening_sample_view_filters_validation_slice_only(
    sample_dataset_dir,
    test_config,
) -> None:
    config = replace(test_config, sample_protocol_id="mining_v1")

    view = build_screening_sample_view(
        config=config,
        dataset_path=sample_dataset_dir,
        screening_sample_roles=["validation"],
    )

    trade_dates = [value.strftime("%Y-%m-%d") for value in view.evaluated_trade_dates]
    assert view.evaluated_slice_roles == ("validation",)
    assert trade_dates == ["2024-01-08", "2024-01-09"]
    assert view.evaluated_date_start == "2024-01-08"
    assert view.evaluated_date_end == "2024-01-09"
    assert sorted(view.panel_view.index.get_level_values("trade_date").unique().strftime("%Y-%m-%d")) == trade_dates
    assert (
        sorted(view.forward_returns_view.index.get_level_values("trade_date").unique().strftime("%Y-%m-%d"))
        == trade_dates
    )


def test_build_screening_sample_view_exposes_hash_for_run_payload(
    sample_dataset_dir,
    test_config,
) -> None:
    view = build_screening_sample_view(
        config=test_config,
        dataset_path=sample_dataset_dir,
        screening_sample_roles=["full_sample"],
    )

    payload = asdict(view)

    assert view.sample_protocol_hash.startswith("sha256:")
    assert payload["sample_protocol_hash"] == view.sample_protocol_hash


def test_build_screening_sample_view_keeps_fixed_forward_return_column(
    sample_dataset_dir,
    test_config,
) -> None:
    view = build_screening_sample_view(
        config=test_config,
        dataset_path=sample_dataset_dir,
        screening_sample_roles=["full_sample"],
    )

    assert "fwd_ret_5d" in view.forward_returns_view.columns
    assert not view.forward_returns_view["fwd_ret_5d"].isna().any()


def test_build_screening_sample_view_raises_on_unknown_slice_role(
    sample_dataset_dir,
    test_config,
) -> None:
    config = replace(test_config, sample_protocol_id="mining_v1")

    with pytest.raises(
        ValueError,
        match="screening sample roles not found in sample protocol: unknown_role",
    ):
        build_screening_sample_view(
            config=config,
            dataset_path=sample_dataset_dir,
            screening_sample_roles=["unknown_role"],
        )
