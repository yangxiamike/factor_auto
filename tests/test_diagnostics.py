
from factor_autoresearch.data_loader import DataLoader
from factor_autoresearch.diagnostics import build_candidate_diagnostics


def test_build_candidate_diagnostics_outputs_year_and_industry(sample_dataset_dir, test_config) -> None:
    dataset = DataLoader(config=test_config, dataset_path=sample_dataset_dir).load()
    factor = (
        (dataset.panel["close_hfq"] - dataset.panel["open_hfq"]) / dataset.panel["open_hfq"]
    ).rename("factor")

    diagnostics = build_candidate_diagnostics(
        candidate_id="fa_diag",
        factor=factor,
        dataset=dataset,
        config=test_config,
    )

    assert not diagnostics.empty
    assert list(diagnostics.columns) == [
        "candidate_id",
        "slice_type",
        "slice_value",
        "horizon",
        "ic_mean",
        "rankic_mean",
        "ic_positive_ratio",
        "rankic_positive_ratio",
        "coverage_mean",
        "effective_trade_days",
    ]
    assert set(diagnostics["slice_type"]) == {"year", "industry"}
    assert set(diagnostics["horizon"]) == set(test_config.horizons)
    assert diagnostics["candidate_id"].eq("fa_diag").all()
    assert diagnostics["effective_trade_days"].ge(0).all()
    year_rows = diagnostics[diagnostics["slice_type"] == "year"]
    industry_rows = diagnostics[diagnostics["slice_type"] == "industry"]
    assert set(year_rows["slice_value"]) == {"2024"}
    assert set(industry_rows["slice_value"]) == {"IND_A"}
