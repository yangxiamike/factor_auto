from __future__ import annotations

import json

import pandas as pd

from factor_autoresearch.artifacts import ArtifactWriter
from factor_autoresearch.context import EvaluationContext


def test_artifact_writer_prepares_and_writes_run_outputs(test_config, tmp_path) -> None:
    context = EvaluationContext(
        config=test_config,
        dataset_path=tmp_path / "dataset",
        candidates_path=tmp_path / "candidates.jsonl",
        registry_path=tmp_path / "registry.jsonl",
        runs_dir=tmp_path / "runs",
        run_id="run_001",
    )
    writer = ArtifactWriter(context)

    assert writer.prepare_run_dir() == context.run_dir
    assert context.factors_dir.exists()
    assert context.results_dir.exists()
    assert context.logs_dir.exists()

    manifest_path = writer.write_manifest({"run_id": context.run_id, "dataset_id": test_config.dataset_id})
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["run_id"] == "run_001"

    index = pd.MultiIndex.from_tuples(
        [
            (pd.Timestamp("2024-01-02"), "000001.SZ"),
            (pd.Timestamp("2024-01-02"), "000002.SZ"),
        ],
        names=["trade_date", "ts_code"],
    )
    raw_factor = pd.Series([1.0, 2.0], index=index)
    processed_factor = pd.Series([0.1, 0.2], index=index)
    factor_path = writer.write_factor_values("fa_demo", raw_factor, processed_factor)
    factor_frame = pd.read_parquet(factor_path)
    assert list(factor_frame.columns) == ["trade_date", "ts_code", "raw_factor", "factor"]
    assert factor_frame["raw_factor"].tolist() == [1.0, 2.0]

    results = [{"id": "fa_demo", "status": "candidate_pass"}]
    metrics_frame = pd.DataFrame([{"candidate_id": "fa_demo", "horizon": "1d", "rankic_mean": 0.2}])
    ic_series_frame = pd.DataFrame([{"candidate_id": "fa_demo", "trade_date": "2024-01-02", "horizon": "1d"}])
    paths = writer.write_results(results, metrics_frame, ic_series_frame)
    assert paths["results"].exists()
    assert paths["metrics"].exists()
    assert paths["ic_series"].exists()
    assert json.loads(paths["results"].read_text(encoding="utf-8").strip())["id"] == "fa_demo"

    summary_path = writer.write_summary("# summary\n")
    assert summary_path.read_text(encoding="utf-8") == "# summary\n"
