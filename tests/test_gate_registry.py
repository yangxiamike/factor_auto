import json

from factor_autoresearch.calculator import FactorCalc
from factor_autoresearch.candidates import Candidate
from factor_autoresearch.context import EvaluationContext
from factor_autoresearch.data_loader import DataLoader
from factor_autoresearch.gate import apply_candidate_gate
from factor_autoresearch.metrics import compute_candidate_metrics
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
