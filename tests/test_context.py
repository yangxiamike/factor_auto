from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from factor_autoresearch.context import EvaluationContext


def test_evaluation_context_exposes_stable_run_paths(test_config, tmp_path) -> None:
    context = EvaluationContext(
        config=test_config,
        dataset_path=tmp_path / "dataset",
        candidates_path=tmp_path / "candidates.jsonl",
        registry_path=tmp_path / "registry.jsonl",
        runs_dir=tmp_path / "runs",
        run_id="run_001",
        verbose=True,
    )

    assert context.run_dir == tmp_path / "runs" / "run_001"
    assert context.registry_path == tmp_path / "registry.jsonl"
    assert context.manifest_path == context.run_dir / "manifest.json"
    assert context.summary_path == context.run_dir / "summary.md"
    assert context.logs_dir == context.run_dir / "logs"
    assert context.factors_dir == context.run_dir / "factors"
    assert context.results_dir == context.run_dir / "results"
    assert context.verbose is True
    assert context.quiet is False


def test_evaluation_context_is_frozen(test_config, tmp_path) -> None:
    context = EvaluationContext(
        config=test_config,
        dataset_path=tmp_path / "dataset",
        candidates_path=tmp_path / "candidates.jsonl",
        registry_path=tmp_path / "registry.jsonl",
        runs_dir=tmp_path / "runs",
        run_id="run_001",
    )

    with pytest.raises(FrozenInstanceError):
        context.run_id = "run_002"
