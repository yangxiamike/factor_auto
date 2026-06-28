"""配置读取与运行参数模型。"""

from __future__ import annotations

import json
import tomllib
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any


# ============== 基础校验辅助 ==============
def _hash_payload(payload: dict[str, Any]) -> str:
    """生成稳定的配置哈希。"""

    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return f"sha256:{sha256(canonical.encode('utf-8')).hexdigest()}"


def _load_toml(path: Path) -> dict[str, Any]:
    """读取 TOML 文件，兼容带 BOM 的 UTF-8 文本。"""

    return tomllib.loads(path.read_text(encoding="utf-8-sig"))


def _require_table(raw: dict[str, Any], key: str) -> dict[str, Any]:
    """读取 TOML 子表。"""

    value = raw[key]
    if not isinstance(value, dict):
        raise TypeError(f"{key} must be a TOML table")
    return value


def _require_string(raw: dict[str, Any], key: str) -> str:
    """读取字符串字段。"""

    value = raw[key]
    if not isinstance(value, str):
        raise TypeError(f"{key} must be a string")
    return value


def _require_int(raw: dict[str, Any], key: str) -> int:
    """读取整数字段。"""

    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{key} must be an integer")
    return int(value)


def _require_float(raw: dict[str, Any], key: str) -> float:
    """读取浮点字段。"""

    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{key} must be a number")
    return float(value)


def _require_str_list(raw: dict[str, Any], key: str) -> list[str]:
    """读取字符串列表。"""

    value = raw[key]
    if not isinstance(value, list):
        raise TypeError(f"{key} must be a list of strings")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise TypeError(f"{key} must be a list of strings")
        items.append(item)
    return items


def _require_int_list(raw: dict[str, Any], key: str) -> list[int]:
    """读取整数列表。"""

    value = raw[key]
    if not isinstance(value, list):
        raise TypeError(f"{key} must be a list of integers")
    items: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int):
            raise TypeError(f"{key} must be a list of integers")
        items.append(int(item))
    return items


# ============== 配置模型 ==============
@dataclass(frozen=True)
class Block3ScreeningConfig:
    """Block3 screening gate 配置。"""

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
        """转换为普通字典。"""

        return asdict(self)


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


# ============== Block3 读取 ==============
def load_block3_screening_config(config_path: str | Path) -> Block3ScreeningConfig:
    """读取 Block3 screening gate 配置。"""

    config_file = Path(config_path).resolve()
    raw = _load_toml(config_file)
    gate0 = _require_table(raw, "gate0")
    gate1 = _require_table(raw, "gate1")
    gate2 = _require_table(raw, "gate2")
    gate2_replacement = _require_table(raw, "gate2_replacement")
    gate3 = _require_table(raw, "gate3")

    config = Block3ScreeningConfig(
        version=_require_string(raw, "version"),
        screening_gate_profile=_require_string(raw, "screening_gate_profile"),
        admission_horizon=_require_string(raw, "admission_horizon"),
        metric_compute_policy=_require_string(raw, "metric_compute_policy"),
        screening_sample_roles=_require_str_list(raw, "screening_sample_roles"),
        expression_depth_max=_require_int(gate0, "expression_depth_max"),
        coverage_mean_min=_require_float(gate0, "coverage_mean_min"),
        effective_trade_days_min=_require_int(gate0, "effective_trade_days_min"),
        min_cross_section_size=_require_int(gate0, "min_cross_section_size"),
        finite_ratio_min=_require_float(gate0, "finite_ratio_min"),
        std_min=_require_float(gate0, "std_min"),
        unique_ratio_min=_require_float(gate0, "unique_ratio_min"),
        quantiles=_require_int(gate0, "quantiles"),
        admission_quality_metric=_require_string(gate1, "admission_quality_metric"),
        admission_quality_min=_require_float(gate1, "admission_quality_min"),
        admission_stability_metric=_require_string(gate1, "admission_stability_metric"),
        admission_stability_min=_require_float(gate1, "admission_stability_min"),
        batch_corr_threshold=_require_float(gate2, "batch_corr_threshold"),
        library_corr_threshold=_require_float(gate2, "library_corr_threshold"),
        correlation_min_overlap=_require_int(gate2, "correlation_min_overlap"),
        tie_break_order=_require_str_list(gate2, "tie_break_order"),
        replacement_quality_metric=_require_string(
            gate2_replacement, "replacement_quality_metric"
        ),
        replacement_absolute_quality_min=_require_float(
            gate2_replacement, "replacement_absolute_quality_min"
        ),
        replacement_improvement_ratio_min=_require_float(
            gate2_replacement, "replacement_improvement_ratio_min"
        ),
        correlated_factor_count_required=_require_int(
            gate2_replacement, "correlated_factor_count_required"
        ),
        directional_long_short_sharpe_min=_require_float(
            gate3, "directional_long_short_sharpe_min"
        ),
        long_short_effective_days_min=_require_int(gate3, "long_short_effective_days_min"),
        monotonicity_score_min=_require_float(gate3, "monotonicity_score_min"),
        turnover_proxy_max=_require_float(gate3, "turnover_proxy_max"),
    )

    if config.admission_horizon != "5d":
        raise ValueError("admission_horizon must be 5d")
    return config


# ============== 现有 gate 读取 ==============
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


# ============== 实验配置读取 ==============
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