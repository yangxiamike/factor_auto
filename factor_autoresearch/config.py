"""Load experiment and gate configuration."""

from __future__ import annotations

import json
import tomllib
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

def _hash_payload(payload: dict[str, Any]) -> str:
    """Return a stable sha256 hash for a configuration payload."""

    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return f"sha256:{sha256(canonical.encode('utf-8')).hexdigest()}"


@dataclass(frozen=True)
class GateConfig:
    """Gate thresholds and scoring weights."""

    version: str
    coverage_mean_min: float
    effective_trade_days_min: int
    complexity_score_max: int
    best_horizon_directional_ic_mean_min: float
    best_horizon_directional_rankic_mean_min: float
    best_horizon_directional_ic_positive_ratio_min: float
    best_horizon_directional_rankic_positive_ratio_min: float
    best_horizon_directional_monotonicity_min: float
    best_horizon_score_min: float
    min_cross_section_size: int
    quantiles: int
    weights: dict[str, float]
    components: dict[str, float]

    def as_dict(self) -> dict[str, Any]:
        """Return a plain dictionary suitable for hashing and persistence."""

        return asdict(self)


@dataclass(frozen=True)
class PrepareConfig:
    """Dataset preparation options."""

    price_start_buffer_days: int
    use_incremental_universe: bool
    include_markets: list[str]
    exclude_markets: list[str]
    include_exchanges: list[str]
    exclude_exchanges: list[str]


@dataclass(frozen=True)
class PreprocessConfig:
    """Factor preprocessing options."""

    winsorize_mad_scale: float
    size_exposure: str


@dataclass(frozen=True)
class ExperimentConfig:
    """Complete configuration for one experiment run."""

    experiment_id: str
    dataset_id: str
    universe: str
    date_start: str
    date_end: str
    adjustment: str
    forward_return_definition: str
    allowed_fields: list[str]
    allowed_functions: list[str]
    allowed_windows: list[int]
    categories: list[str]
    horizons: list[str]
    features: list[str]
    preprocess_exposures: list[str]
    source: str
    source_path: Path
    source_universe_key: str
    industry_source: str
    base_filters_inherited: list[str]
    gate: GateConfig
    prepare: PrepareConfig
    preprocess: PreprocessConfig
    gate_config_path: Path
    gate_config_hash: str
    config_hash: str

    def as_dict(self) -> dict[str, Any]:
        """Return a plain dictionary suitable for artifact output."""

        payload = asdict(self)
        payload["source_path"] = str(self.source_path)
        payload["gate_config_path"] = str(self.gate_config_path)
        payload["gate_config_hash"] = self.gate_config_hash
        payload["config_hash"] = self.config_hash
        return payload


def _load_toml(path: Path) -> dict[str, Any]:
    """Read a TOML file."""

    with path.open("rb") as handle:
        return tomllib.load(handle)


def _get_gate_threshold(
    gate_raw: dict[str, Any],
    new_key: str,
    legacy_key: str,
) -> float:
    """Read a gate threshold with fallback to the legacy field name."""
    if new_key in gate_raw:
        return float(gate_raw[new_key])
    if legacy_key in gate_raw:
        return float(gate_raw[legacy_key])
    return 0.0


def load_experiment_config(config_path: str | Path) -> ExperimentConfig:
    """Load an experiment config and its referenced gate config."""

    experiment_path = Path(config_path).resolve()
    raw = _load_toml(experiment_path)
    gate_path = (experiment_path.parent.parent / raw["gate_config"]).resolve()
    gate_raw = _load_toml(gate_path)["gate"]
    gate = GateConfig(
        version=gate_raw["version"],
        coverage_mean_min=float(gate_raw["coverage_mean_min"]),
        effective_trade_days_min=int(gate_raw["effective_trade_days_min"]),
        complexity_score_max=int(gate_raw["complexity_score_max"]),
        best_horizon_directional_ic_mean_min=_get_gate_threshold(
            gate_raw,
            "best_horizon_directional_ic_mean_min",
            "best_horizon_ic_mean_min",
        ),
        best_horizon_directional_rankic_mean_min=_get_gate_threshold(
            gate_raw,
            "best_horizon_directional_rankic_mean_min",
            "best_horizon_rankic_mean_min",
        ),
        best_horizon_directional_ic_positive_ratio_min=_get_gate_threshold(
            gate_raw,
            "best_horizon_directional_ic_positive_ratio_min",
            "best_horizon_ic_positive_ratio_min",
        ),
        best_horizon_directional_rankic_positive_ratio_min=_get_gate_threshold(
            gate_raw,
            "best_horizon_directional_rankic_positive_ratio_min",
            "best_horizon_rankic_positive_ratio_min",
        ),
        best_horizon_directional_monotonicity_min=_get_gate_threshold(
            gate_raw,
            "best_horizon_directional_monotonicity_min",
            "best_horizon_monotonicity_min",
        ),
        best_horizon_score_min=float(gate_raw["best_horizon_score_min"]),
        min_cross_section_size=int(gate_raw["min_cross_section_size"]),
        quantiles=int(gate_raw["quantiles"]),
        weights={key: float(value) for key, value in gate_raw["weights"].items()},
        components={key: float(value) for key, value in gate_raw["components"].items()},
    )
    gate_payload = {"gate": gate.as_dict()}
    payload = {
        "experiment": raw,
        "gate": gate_payload,
    }
    prepare_raw = raw["prepare"]
    return ExperimentConfig(
        experiment_id=raw["experiment_id"],
        dataset_id=raw["dataset_id"],
        universe=raw["universe"],
        date_start=raw["date_start"],
        date_end=raw["date_end"],
        adjustment=raw["adjustment"],
        forward_return_definition=raw["forward_return_definition"],
        allowed_fields=list(raw["allowed_fields"]),
        allowed_functions=list(raw["allowed_functions"]),
        allowed_windows=[int(value) for value in raw["allowed_windows"]],
        categories=list(raw["categories"]),
        horizons=list(raw["horizons"]),
        features=list(raw["features"]),
        preprocess_exposures=list(raw["preprocess_exposures"]),
        source=raw["source"],
        source_path=Path(raw["source_path"]).resolve(),
        source_universe_key=raw["source_universe_key"],
        industry_source=raw["industry_source"],
        base_filters_inherited=list(raw["base_filters_inherited"]),
        gate=gate,
        prepare=PrepareConfig(
            price_start_buffer_days=int(prepare_raw["price_start_buffer_days"]),
            use_incremental_universe=bool(prepare_raw["use_incremental_universe"]),
            include_markets=list(prepare_raw.get("include_markets", [])),
            exclude_markets=list(prepare_raw.get("exclude_markets", [])),
            include_exchanges=list(prepare_raw.get("include_exchanges", [])),
            exclude_exchanges=list(prepare_raw.get("exclude_exchanges", [])),
        ),
        preprocess=PreprocessConfig(
            winsorize_mad_scale=float(raw["preprocess"]["winsorize_mad_scale"]),
            size_exposure=raw["preprocess"]["size_exposure"],
        ),
        gate_config_path=gate_path,
        gate_config_hash=_hash_payload(gate_payload),
        config_hash=_hash_payload(payload),
    )
