import json
from dataclasses import replace

import pandas as pd

from factor_autoresearch.calculator import FactorCalc
from factor_autoresearch.candidates import Candidate
from factor_autoresearch.context import EvaluationContext
from factor_autoresearch.data_loader import DataLoader
from factor_autoresearch.gate import apply_candidate_gate
from factor_autoresearch.metrics import MetricsResult, compute_candidate_metrics
from factor_autoresearch.preprocess import preprocess_factor
from factor_autoresearch.registry import RegistryWriter


def test_gate_and_registry(sample_dataset_dir, test_config, tmp_path) -> None:
    dataset = DataLoader(config=test_config, dataset_path=sample_dataset_dir).load()
    candidate = Candidate(
        candidate_id="fa_gate",
        name="gate",
        expression="cs_rank((close_hfq - open_hfq) / open_hfq)",
        expected_direction="positive",
        hypothesis="gate",
        category="intraday",
        lookback_days=1,
        created_at="2026-06-22",
        notes="gate",
    )
    context = EvaluationContext(
        config=test_config,
        dataset_path=sample_dataset_dir,
        candidates_path=tmp_path / "candidates.jsonl",
        registry_path=tmp_path / "registry.jsonl",
        runs_dir=tmp_path / "runs",
        run_id="run_001",
    )
    calc = FactorCalc(test_config)
    processed = preprocess_factor(calc.calculate(candidate, dataset), dataset, test_config)
    metrics = compute_candidate_metrics(
        candidate_id=candidate.candidate_id,
        factor=processed,
        dataset=dataset,
        config=test_config,
        complexity_score=calc.complexity_score(candidate),
        expected_direction=candidate.expected_direction,
    )
    decision = apply_candidate_gate(candidate, metrics, test_config)
    writer = RegistryWriter(context.registry_path)
    written = writer.append_passed(
        candidate=candidate,
        decision=decision,
        metrics_result=metrics,
        context=context,
        factor_values_path=context.run_dir / "factors" / "fa_gate.parquet",
    )
    assert written is True
    assert decision.failed_rules == []
    lines = context.registry_path.read_text(encoding="utf-8").strip().splitlines()
    payload = json.loads(lines[0])
    assert payload["factor_id"] == "fa_gate"
    assert writer.append_passed(
        candidate=candidate,
        decision=decision,
        metrics_result=metrics,
        context=context,
        factor_values_path=context.run_dir / "factors" / "fa_gate.parquet",
    ) is False


def test_gate_failed_candidate_is_not_written_to_registry(tmp_path, test_config) -> None:
    candidate = Candidate(
        candidate_id="fa_gate_fail",
        name="gate fail",
        expression="cs_rank(close_hfq / open_hfq)",
        expected_direction="positive",
        hypothesis="gate fail",
        category="intraday",
        lookback_days=1,
        created_at="2026-06-22",
        notes="gate fail",
    )
    config = replace(
        test_config,
        gate=replace(
            test_config.gate,
            coverage_mean_min=0.8,
            effective_trade_days_min=5,
            complexity_score_max=12,
            best_horizon_directional_ic_mean_min=0.03,
            best_horizon_directional_rankic_mean_min=0.03,
            best_horizon_directional_ic_positive_ratio_min=0.6,
            best_horizon_directional_rankic_positive_ratio_min=0.6,
            best_horizon_directional_monotonicity_min=0.0,
            best_horizon_score_min=1.0,
        ),
    )
    context = EvaluationContext(
        config=config,
        dataset_path=tmp_path / "dataset",
        candidates_path=tmp_path / "candidates.jsonl",
        registry_path=tmp_path / "registry.jsonl",
        runs_dir=tmp_path / "runs",
        run_id="run_002",
    )
    metrics = MetricsResult(
        horizon_rows=pd.DataFrame(
            [
                {
                    "candidate_id": candidate.candidate_id,
                    "horizon": "5d",
                    "ic_mean": 0.01,
                    "rankic_mean": 0.02,
                    "ic_positive_ratio": 0.55,
                    "rankic_positive_ratio": 0.58,
                    "directional_ic_positive_ratio": 0.45,
                    "directional_rankic_positive_ratio": 0.42,
                    "directional_ic_mean": 0.01,
                    "directional_rankic_mean": 0.02,
                    "directional_monotonicity": 0.0,
                    "monotonicity": 0.0,
                    "coverage_mean": 0.75,
                    "effective_trade_days": 4,
                    "complexity_score": 13,
                }
            ]
        ),
        ic_series=pd.DataFrame(),
        aggregate={
            "candidate_id": candidate.candidate_id,
            "coverage_mean": 0.75,
            "effective_trade_days": 4,
            "complexity_score": 13,
        },
    )
    decision = apply_candidate_gate(candidate, metrics, config)
    writer = RegistryWriter(context.registry_path)

    assert decision.passed is False
    assert decision.failure_bucket == "gate_failed"
    assert decision.failed_rules == [
        "coverage_mean",
        "effective_trade_days",
        "complexity_score",
        "best_horizon_directional_ic_mean",
        "best_horizon_directional_rankic_mean",
        "best_horizon_directional_ic_positive_ratio",
        "best_horizon_directional_rankic_positive_ratio",
        "best_horizon_directional_monotonicity",
    ]
    assert "best_horizon_score" not in decision.failed_rules
    assert decision.details["best_horizon_ic_positive_ratio"] == 0.55
    assert decision.details["best_horizon_directional_ic_positive_ratio"] == 0.45
    assert writer.append_passed(
        candidate=candidate,
        decision=decision,
        metrics_result=metrics,
        context=context,
        factor_values_path=context.run_dir / "factors" / "fa_gate_fail.parquet",
    ) is False
    assert context.registry_path.exists() is False
