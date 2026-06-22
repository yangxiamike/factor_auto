import json

from factor_autoresearch.cleanup import clean_experiment_outputs


def test_cleanup_dry_run_and_apply(tmp_path) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    run_dir = runs_dir / "run_001"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(json.dumps({"experiment_id": "csi500_ohlcv_sandbox_v1"}), encoding="utf-8")
    registry_path = tmp_path / "candidate_factors" / "registry.jsonl"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps({"factor_id": "fa_1", "experiment_id": "csi500_ohlcv_sandbox_v1"}) + "\n",
        encoding="utf-8",
    )

    dry = clean_experiment_outputs(
        experiment_id="csi500_ohlcv_sandbox_v1",
        runs_dir=runs_dir,
        registry_path=registry_path,
        yes=False,
    )
    assert dry.dry_run is True
    assert run_dir.exists()

    done = clean_experiment_outputs(
        experiment_id="csi500_ohlcv_sandbox_v1",
        runs_dir=runs_dir,
        registry_path=registry_path,
        yes=True,
    )
    assert done.registry_removed == 1
    assert not run_dir.exists()
