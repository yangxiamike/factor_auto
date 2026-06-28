"""Load experiment and gate configuration."""

from __future__ import annotations

import json
import tomllib
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any


# ============== Hash helpers ==============
def _hash_payload(payload: dict[str, Any]) -> str:
    """Return a stable sha256 hash for a configuration payload."""

    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return f"sha256:{sha256(canonical.encode('utf-8')).hexdigest()}"


# ============== Config models ==============
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
    warmup_start: str
    sample_protocol_id: str | None
    sample_protocol_config: dict[str, Any]
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


@dataclass(frozen=True)
class Block3ScreeningConfig:
    """Block3 screening 配置: 描述 Gate0-Gate3 的筛选阈值与样本口径。"""

    version: str
    screening_gate_profile: str
    admission_horizon: str
    metric_compute_policy: str
    screening_sample_roles: list[str]
    expression_depth_max: int
    coverage_mean_min: float
    effective_trade_days_min: int
    min_cross_section_size: int
    finite_ratio_min: float
    std_min: float
    unique_ratio_min: float
    quantiles: int
    admission_quality_metric: str
    admission_quality_min: float
    admission_stability_metric: str
    admission_stability_min: float
    batch_corr_threshold: float
    library_corr_threshold: float
    correlation_min_overlap: int
    tie_break_order: list[str]
    replacement_quality_metric: str
    replacement_absolute_quality_min: float
    replacement_improvement_ratio_min: float
    correlated_factor_count_required: int
    directional_long_short_sharpe_min: float
    long_short_effective_days_min: int
    monotonicity_score_min: float
    turnover_proxy_max: float

    def as_dict(self) -> dict[str, Any]:
        """Return a plain dictionary suitable for serialization and tracing."""

        return asdict(self)


# ============== Load helpers ==============
def _load_toml(path: Path) -> dict[str, Any]:
    """Read a TOML file, accepting UTF-8 files with or without BOM."""

    return tomllib.loads(path.read_text(encoding="utf-8-sig"))


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


def _load_gate_config(gate_path: Path) -> GateConfig:
    """Load gate configuration from a TOML file."""

    gate_raw = _load_toml(gate_path)["gate"]
    return GateConfig(
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


def _load_sample_protocol_config(experiment_path: Path, raw: dict[str, Any]) -> dict[str, Any]:
    """Load inline or referenced sample protocol configuration."""

    value = raw.get("sample_protocol_config", {})
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        protocol_path = (experiment_path.parent.parent / value).resolve()
        if not protocol_path.exists() and Path(value).exists():
            protocol_path = Path(value).resolve()
        loaded = _load_toml(protocol_path)
        if "embargo_trading_days" in loaded and "embargo_trade_days" not in loaded:
            loaded["embargo_trade_days"] = loaded["embargo_trading_days"]
        loaded["config_path"] = str(protocol_path)
        return loaded
    if value is None:
        return {}
    raise TypeError("sample_protocol_config must be a TOML table, a path string, or omitted")


def _load_block3_screening_config(raw: dict[str, Any]) -> Block3ScreeningConfig:
    """Load Block3 screening configuration from parsed TOML content."""

    screening_raw = raw["screening_gate"]
    return Block3ScreeningConfig(
        version=screening_raw["version"],
        screening_gate_profile=screening_raw["screening_gate_profile"],
        admission_horizon=screening_raw["admission_horizon"],
        metric_compute_policy=screening_raw["metric_compute_policy"],
        screening_sample_roles=list(screening_raw["screening_sample_roles"]),
        expression_depth_max=int(screening_raw["expression_depth_max"]),
        coverage_mean_min=float(screening_raw["coverage_mean_min"]),
        effective_trade_days_min=int(screening_raw["effective_trade_days_min"]),
        min_cross_section_size=int(screening_raw["min_cross_section_size"]),
        finite_ratio_min=float(screening_raw["finite_ratio_min"]),
        std_min=float(screening_raw["std_min"]),
        unique_ratio_min=float(screening_raw["unique_ratio_min"]),
        quantiles=int(screening_raw["quantiles"]),
        admission_quality_metric=screening_raw["admission_quality_metric"],
        admission_quality_min=float(screening_raw["admission_quality_min"]),
        admission_stability_metric=screening_raw["admission_stability_metric"],
        admission_stability_min=float(screening_raw["admission_stability_min"]),
        batch_corr_threshold=float(screening_raw["batch_corr_threshold"]),
        library_corr_threshold=float(screening_raw["library_corr_threshold"]),
        correlation_min_overlap=int(screening_raw["correlation_min_overlap"]),
        tie_break_order=list(screening_raw["tie_break_order"]),
        replacement_quality_metric=screening_raw["replacement_quality_metric"],
        replacement_absolute_quality_min=float(screening_raw["replacement_absolute_quality_min"]),
        replacement_improvement_ratio_min=float(screening_raw["replacement_improvement_ratio_min"]),
        correlated_factor_count_required=int(screening_raw["correlated_factor_count_required"]),
        directional_long_short_sharpe_min=float(screening_raw["directional_long_short_sharpe_min"]),
        long_short_effective_days_min=int(screening_raw["long_short_effective_days_min"]),
        monotonicity_score_min=float(screening_raw["monotonicity_score_min"]),
        turnover_proxy_max=float(screening_raw["turnover_proxy_max"]),
    )


# ============== Public loaders ==============
def load_experiment_config(config_path: str | Path) -> ExperimentConfig:
    """Load an experiment config and its referenced gate config."""

    experiment_path = Path(config_path).resolve()
    raw = _load_toml(experiment_path)
    gate_path = (experiment_path.parent.parent / raw["gate_config"]).resolve()
    gate = _load_gate_config(gate_path)
    gate_payload = {"gate": gate.as_dict()}
    payload = {
        "experiment": raw,
        "gate": gate_payload,
    }
    prepare_raw = raw["prepare"]
    sample_protocol_config = _load_sample_protocol_config(experiment_path, raw)
    return ExperimentConfig(
        experiment_id=raw["experiment_id"],
        dataset_id=raw["dataset_id"],
        universe=raw["universe"],
        date_start=raw["date_start"],
        date_end=raw["date_end"],
        warmup_start=str(raw.get("warmup_start", raw["date_start"])),
        sample_protocol_id=raw.get("sample_protocol_id"),
        sample_protocol_config=sample_protocol_config,
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


def load_block3_screening_config(config_path: str | Path) -> Block3ScreeningConfig:
    """Load the standalone Block3 screening gate configuration."""

    return _load_block3_screening_config(_load_toml(Path(config_path).resolve()))
