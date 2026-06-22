from pathlib import Path

from factor_autoresearch.config import load_experiment_config


def test_load_experiment_config() -> None:
    config = load_experiment_config(Path("configs/csi500_ohlcv_sandbox_v1.toml"))
    assert config.dataset_id == "sandbox_v1"
    assert "industry" not in config.allowed_fields
    assert config.gate.version == "candidate_gate_v1"
    assert config.config_hash.startswith("sha256:")
