from factor_autoresearch.calculator import FactorCalc
from factor_autoresearch.candidates import Candidate
from factor_autoresearch.data_loader import DataLoader
from factor_autoresearch.preprocess import preprocess_factor


def test_preprocess_factor_outputs_residuals(sample_dataset_dir, test_config) -> None:
    dataset = DataLoader().load(sample_dataset_dir, test_config)
    candidate = Candidate(
        candidate_id="fa_pre",
        name="pre",
        expression="cs_rank((close_hfq - open_hfq) / open_hfq)",
        expected_direction="positive",
        hypothesis="pre",
        category="intraday",
        lookback_days=1,
        created_at="2026-06-22",
        notes="pre",
    )
    calc = FactorCalc()
    raw = calc.calculate(candidate, dataset, test_config)
    processed = preprocess_factor(raw, dataset, test_config)
    assert processed.notna().sum() > 0
