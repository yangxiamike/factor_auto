import json

from factor_autoresearch.calculator import FactorCalc
from factor_autoresearch.candidates import Candidate
from factor_autoresearch.data_loader import DataLoader
from factor_autoresearch.gate import apply_candidate_gate
from factor_autoresearch.metrics import compute_candidate_metrics
from factor_autoresearch.preprocess import preprocess_factor
from factor_autoresearch.registry import append_registry_record


def test_gate_and_registry(sample_dataset_dir, test_config, tmp_path) -> None:
    dataset = DataLoader().load(sample_dataset_dir, test_config)
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
    calc = FactorCalc()
    processed = preprocess_factor(calc.calculate(candidate, dataset, test_config), dataset, test_config)
    metrics = compute_candidate_metrics(
        candidate_id=candidate.candidate_id,
        factor=processed,
        dataset=dataset,
        config=test_config,
        complexity_score=calc.complexity_score(candidate, test_config),
    )
    decision = apply_candidate_gate(candidate, metrics, test_config)
    registry_path = tmp_path / "registry.jsonl"
    written = append_registry_record(
        registry_path=registry_path,
        candidate=candidate,
        config=test_config,
        decision=decision,
        metrics_result=metrics,
        run_id="run_001",
        factor_values_path="runs/run_001/factors/fa_gate.parquet",
        summary_path="runs/run_001/summary.md",
    )
    assert written is True
    lines = registry_path.read_text(encoding="utf-8").strip().splitlines()
    payload = json.loads(lines[0])
    assert payload["factor_id"] == "fa_gate"
