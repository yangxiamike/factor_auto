from factor_autoresearch.calculator import FactorCalc
from factor_autoresearch.candidates import Candidate
from factor_autoresearch.data_loader import DataLoader
from factor_autoresearch.metrics import compute_candidate_metrics
from factor_autoresearch.preprocess import preprocess_factor


def test_preprocess_and_metrics(sample_dataset_dir, test_config) -> None:
    dataset = DataLoader(config=test_config, dataset_path=sample_dataset_dir).load()
    candidate = Candidate(
        candidate_id="fa_pipeline",
        name="pipeline",
        expression="cs_rank((close_hfq - open_hfq) / open_hfq)",
        expected_direction="positive",
        hypothesis="pipeline",
        category="intraday",
        lookback_days=1,
        created_at="2026-06-22",
        notes="pipeline",
    )
    calc = FactorCalc(test_config)
    raw = calc.calculate(candidate, dataset)
    processed = preprocess_factor(raw, dataset, test_config)
    metrics = compute_candidate_metrics(
        candidate_id=candidate.candidate_id,
        factor=processed,
        dataset=dataset,
        config=test_config,
        complexity_score=calc.complexity_score(candidate),
    )
    assert metrics.aggregate["coverage_mean"] > 0
    assert not metrics.horizon_rows.empty
