from pathlib import Path

from conftest import write_test_config_files

from factor_autoresearch.config import load_experiment_config


def test_load_experiment_config() -> None:
    config = load_experiment_config(Path("configs/csi500_ohlcv_sandbox_v1.toml"))
    assert config.dataset_id == "sandbox_v1"
    assert "industry" not in config.allowed_fields
    assert config.gate.version == "candidate_gate_baseline_v0"
    assert config.gate_config_hash.startswith("sha256:")
    assert config.config_hash.startswith("sha256:")


def test_gate_config_hash_depends_on_gate_content_only(tmp_path) -> None:
    left = load_experiment_config(write_test_config_files(tmp_path / "left"))
    right = load_experiment_config(write_test_config_files(tmp_path / "right"))

    assert left.gate_config_hash == right.gate_config_hash
    assert left.config_hash != right.config_hash


def test_gate_config_hash_changes_when_gate_content_changes(tmp_path) -> None:
    experiment_path = write_test_config_files(tmp_path / "case")
    original = load_experiment_config(experiment_path)

    gate_path = experiment_path.parent / "candidate_gate_baseline_v0.toml"
    gate_text = gate_path.read_text(encoding="utf-8").replace(
        "best_horizon_score_min = 0.1",
        "best_horizon_score_min = 0.2",
    )
    gate_path.write_text(gate_text, encoding="utf-8")

    changed = load_experiment_config(experiment_path)
    assert changed.gate_config_hash != original.gate_config_hash
