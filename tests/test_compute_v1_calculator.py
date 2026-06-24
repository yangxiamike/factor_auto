import pandas as pd

from factor_autoresearch.calculator import FactorCalc
from factor_autoresearch.candidates import Candidate
from factor_autoresearch.compute_v1.calculator import V1FactorCalc
from factor_autoresearch.data_loader import DataLoader


def _candidate(expression: str, lookback_days: int = 5) -> Candidate:
    return Candidate(
        candidate_id="fa_v1",
        name="v1",
        expression=expression,
        expected_direction="positive",
        hypothesis="v1",
        category="momentum",
        lookback_days=lookback_days,
        created_at="2026-06-22",
        notes="v1",
    )


def test_v1_factor_calc_matches_legacy(sample_dataset_dir, test_config) -> None:
    dataset = DataLoader(config=test_config, dataset_path=sample_dataset_dir).load()
    legacy = FactorCalc(test_config)
    v1 = V1FactorCalc(test_config)
    candidate = _candidate("cs_rank(ts_return(close_hfq, 3))", 3)

    expected = legacy.calculate(candidate, dataset)
    result = v1.calculate(candidate, dataset)

    pd.testing.assert_series_equal(result, expected)


def test_v1_factor_calc_reuses_expression_cache(sample_dataset_dir, test_config) -> None:
    dataset = DataLoader(config=test_config, dataset_path=sample_dataset_dir).load()
    calc = V1FactorCalc(test_config)
    candidate = _candidate("ts_mean(close_hfq, 3) + ts_mean(close_hfq, 3)", 3)

    _ = calc.calculate(candidate, dataset)

    assert calc.cache.hits > 0
