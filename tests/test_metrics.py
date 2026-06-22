from factor_autoresearch.calculator import FactorCalc
from factor_autoresearch.candidates import Candidate
from factor_autoresearch.data_loader import DataLoader
from factor_autoresearch.metrics import compute_candidate_metrics
from factor_autoresearch.preprocess import preprocess_factor


def test_compute_candidate_metrics_returns_horizon_rows(sample_dataset_dir, test_config) -> None:
    dataset = DataLoader().load(sample_dataset_dir, test_config)
    candidate = Candidate(
        candidate_id="fa_metric",
        name="metric",
        expression="cs_rank((close_hfq - open_hfq) / open_hfq)",
        expected_direction="positive",
        hypothesis="metric",
        category="intraday",
        lookback_days=1,
        created_at="2026-06-22",
        notes="metric",
    )
    calc = FactorCalc()
    raw = calc.calculate(candidate, dataset, test_config)
    processed = preprocess_factor(raw, dataset, test_config)
    metrics = compute_candidate_metrics(
        candidate_id=candidate.candidate_id,
        factor=processed,
        dataset=dataset,
        config=test_config,
        complexity_score=calc.complexity_score(candidate, test_config),
    )
    assert not metrics.horizon_rows.empty
    assert metrics.aggregate["effective_trade_days"] >= 3
