from pathlib import Path

from factor_autoresearch.config import load_experiment_config


def test_load_experiment_config() -> None:
    config = load_experiment_config(Path("configs/csi500_ohlcv_sandbox_v1.toml"))
    assert config.dataset_id == "sandbox_v1"
    assert "industry" not in config.allowed_fields
    assert config.gate.version == "candidate_gate_v1"
    assert config.config_hash.startswith("sha256:")
    assert config.prepare.include_markets == []
    assert config.prepare.exclude_markets == []
    assert config.prepare.include_exchanges == []
    assert config.prepare.exclude_exchanges == []

def test_load_mainboard_pressure_config() -> None:
    config = load_experiment_config(Path("configs/mainboard_ohlcv_pressure_v1.toml"))
    assert config.dataset_id == "mainboard_pressure_v1"
    assert config.universe == "mainboard"
    assert config.source_universe_key == "univ_trade_base"
    assert config.prepare.include_markets == ["主板"]
    assert config.prepare.exclude_markets == []
    assert config.prepare.include_exchanges == []
    assert config.prepare.exclude_exchanges == []
