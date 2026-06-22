from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from factor_autoresearch.candidates import Candidate
from factor_autoresearch.config import ExperimentConfig
from factor_autoresearch.gate import GateDecision
from factor_autoresearch.metrics import MetricsResult


def append_registry_record(
    *,
    registry_path: str | Path,
    candidate: Candidate,
    config: ExperimentConfig,
    decision: GateDecision,
    metrics_result: MetricsResult,
    run_id: str,
    factor_values_path: str,
    summary_path: str,
) -> bool:
    registry_path = Path(registry_path)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    dedupe_key = (candidate.candidate_id, config.dataset_id, run_id)
    existing: set[tuple[str, str, str]] = set()
    if registry_path.exists():
        with registry_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                raw = json.loads(text)
                existing.add((raw["factor_id"], raw["dataset_id"], raw["run_id"]))
    if dedupe_key in existing:
        return False

    best_row = metrics_result.horizon_rows.loc[metrics_result.horizon_rows["horizon"] == decision.best_horizon].iloc[0]
    payload = {
        "factor_id": candidate.candidate_id,
        "name": candidate.name,
        "category": candidate.category,
        "expression_hash": f"sha256:{sha256(candidate.expression.encode('utf-8')).hexdigest()}",
        "expected_direction": candidate.expected_direction,
        "signal_direction": decision.signal_direction,
        "dataset_id": config.dataset_id,
        "experiment_id": config.experiment_id,
        "run_id": run_id,
        "status": decision.status,
        "best_horizon": decision.best_horizon,
        "best_horizon_score": decision.best_horizon_score,
        "metrics": {
            f"ic_mean_{decision.best_horizon}": float(best_row["ic_mean"]),
            f"rankic_mean_{decision.best_horizon}": float(best_row["rankic_mean"]),
            f"monotonicity_{decision.best_horizon}": float(best_row["monotonicity"]),
            "coverage_mean": float(metrics_result.aggregate["coverage_mean"]),
            "complexity_score": int(metrics_result.aggregate["complexity_score"]),
        },
        "gate": {
            "version": config.gate.version,
            "passed": decision.passed,
            "failed_rules": decision.failed_rules,
        },
        "artifacts": {
            "summary": summary_path,
            "factor_values": factor_values_path,
        },
    }
    with registry_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return True
