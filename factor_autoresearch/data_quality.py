from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from factor_autoresearch.config import ExperimentConfig
from factor_autoresearch.data_loader import FORWARD_COLUMNS, PANEL_COLUMNS

PRIMARY_KEY = ["trade_date", "ts_code"]
DECLARED_RANGE_BOUNDARY_TOLERANCE_DAYS = 7
REQUIRED_DATASET_FILES = ["manifest.json", "panel.parquet", "forward_returns.parquet"]
REQUIRED_MANIFEST_FIELDS = [
    "dataset_id",
    "experiment_id",
    "date_start",
    "date_end",
    "source",
    "source_universe_key",
    "base_filters_inherited",
    "forward_return_definition",
]
OHLCV_COLUMNS = ["open_hfq", "high_hfq", "low_hfq", "close_hfq", "volume"]
EXPOSURE_COLUMNS = ["industry", "market_cap"]
FORWARD_RETURN_VALUE_COLUMNS = [column for column in FORWARD_COLUMNS if column not in PRIMARY_KEY]

PASS = "pass"
FAIL = "fail"
WARNING = "warning"
CheckOutcome = Literal["pass", "fail", "warning"]


@dataclass(frozen=True)
class DataQualityOptions:
    """Thresholds for non-blocking statistical warnings."""

    universe_low_count_ratio: float = 0.8
    missing_rate_warning: float = 0.05
    forward_non_tail_missing_rate_warning: float = 0.02
    market_cap_nonpositive_warning: float = 0.0


@dataclass(frozen=True)
class DataQualityCheckResult:
    """A single quality check result suitable for JSON/Markdown reports."""

    check_id: str
    outcome: CheckOutcome
    message: str
    details: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DataQualityReport:
    """Structured report for frozen dataset quality checks."""

    dataset_path: str
    dataset_id: str | None
    experiment_id: str | None
    overall_outcome: CheckOutcome
    summary: dict[str, Any]
    metrics: dict[str, Any]
    checks: list[DataQualityCheckResult]

    def as_dict(self) -> dict[str, Any]:
        return {
            "dataset_path": self.dataset_path,
            "dataset_id": self.dataset_id,
            "experiment_id": self.experiment_id,
            "overall_outcome": self.overall_outcome,
            "summary": self.summary,
            "metrics": self.metrics,
            "checks": [check.as_dict() for check in self.checks],
        }

    def to_markdown(self) -> str:
        lines = [
            "# Data Quality Report",
            "",
            f"- dataset_path: `{self.dataset_path}`",
            f"- dataset_id: `{self.dataset_id or 'unknown'}`",
            f"- experiment_id: `{self.experiment_id or 'unknown'}`",
            f"- overall_outcome: `{self.overall_outcome}`",
            f"- checks: `{self.summary['total_checks']}`",
            f"- fails: `{self.summary['fail_count']}`",
            f"- warnings: `{self.summary['warning_count']}`",
            "",
            "## Metrics",
            "",
            "```json",
            json.dumps(self.metrics, ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
            "## Checks",
            "",
        ]
        for check in self.checks:
            lines.extend(
                [
                    f"### {check.check_id}",
                    "",
                    f"- outcome: `{check.outcome}`",
                    f"- message: {check.message}",
                    "```json",
                    json.dumps(check.details, ensure_ascii=False, indent=2, sort_keys=True),
                    "```",
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"


def build_data_quality_report(
    dataset_path: str | Path,
    *,
    config: ExperimentConfig | None = None,
    options: DataQualityOptions | None = None,
) -> DataQualityReport:
    """Run frozen dataset quality checks and return a structured report."""

    dataset_dir = Path(dataset_path).resolve()
    resolved_options = options or DataQualityOptions()
    checks: list[DataQualityCheckResult] = []
    metrics: dict[str, Any] = {}

    required_paths = {name: dataset_dir / name for name in REQUIRED_DATASET_FILES}
    missing_files = [name for name, path in required_paths.items() if not path.exists()]
    if missing_files:
        checks.append(
            DataQualityCheckResult(
                check_id="required_files",
                outcome=FAIL,
                message="dataset is missing required files",
                details={"missing_files": missing_files},
            )
        )
    else:
        checks.append(
            DataQualityCheckResult(
                check_id="required_files",
                outcome=PASS,
                message="all required dataset files are present",
                details={"files": REQUIRED_DATASET_FILES},
            )
        )

    manifest = _load_manifest(required_paths["manifest.json"], checks)
    panel = _load_frame(required_paths["panel.parquet"], "panel.parquet", checks)
    forward_returns = _load_frame(
        required_paths["forward_returns.parquet"], "forward_returns.parquet", checks
    )

    dataset_id = _pick_dataset_id(manifest, config, dataset_dir)
    experiment_id = _pick_experiment_id(manifest, config)

    if manifest is not None:
        _check_manifest_required_fields(manifest, checks)
        if config is not None:
            _check_manifest_config_consistency(manifest, config, checks)

    prepared_panel = _prepare_dataset_frame(panel, "panel.parquet", PANEL_COLUMNS, checks)
    prepared_forward = _prepare_dataset_frame(
        forward_returns, "forward_returns.parquet", FORWARD_COLUMNS, checks
    )

    panel_primary_key_ok = False
    forward_primary_key_ok = False
    if prepared_panel is not None:
        panel_primary_key_ok = _check_primary_key_uniqueness(
            prepared_panel, "panel.parquet", checks
        )
    if prepared_forward is not None:
        forward_primary_key_ok = _check_primary_key_uniqueness(
            prepared_forward, "forward_returns.parquet", checks
        )

    if prepared_panel is not None and prepared_forward is not None:
        _check_date_range_consistency(prepared_panel, prepared_forward, manifest, config, checks)
    if (
        prepared_panel is not None
        and prepared_forward is not None
        and panel_primary_key_ok
        and forward_primary_key_ok
    ):
        _collect_daily_universe_metrics(prepared_panel, resolved_options, checks, metrics)
        _collect_missing_rate_metrics(prepared_panel, resolved_options, checks, metrics)
        _collect_forward_return_metrics(
            prepared_panel, prepared_forward, resolved_options, checks, metrics
        )
        _collect_market_cap_metrics(prepared_panel, resolved_options, checks, metrics)

    overall_outcome = _overall_outcome(checks)
    summary = {
        "total_checks": len(checks),
        "fail_count": sum(check.outcome == FAIL for check in checks),
        "warning_count": sum(check.outcome == WARNING for check in checks),
        "passed_count": sum(check.outcome == PASS for check in checks),
    }
    return DataQualityReport(
        dataset_path=str(dataset_dir),
        dataset_id=dataset_id,
        experiment_id=experiment_id,
        overall_outcome=overall_outcome,
        summary=summary,
        metrics=metrics,
        checks=checks,
    )


def _load_manifest(
    manifest_path: Path,
    checks: list[DataQualityCheckResult],
) -> dict[str, Any] | None:
    if not manifest_path.exists():
        return None
    try:
        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except json.JSONDecodeError as exc:
        checks.append(
            DataQualityCheckResult(
                check_id="manifest_json_valid",
                outcome=FAIL,
                message="manifest.json is not valid JSON",
                details={"error": str(exc)},
            )
        )
        return None
    checks.append(
        DataQualityCheckResult(
            check_id="manifest_json_valid",
            outcome=PASS,
            message="manifest.json is valid JSON",
            details={},
        )
    )
    return manifest


def _load_frame(
    file_path: Path,
    file_label: str,
    checks: list[DataQualityCheckResult],
) -> pd.DataFrame | None:
    if not file_path.exists():
        return None
    try:
        return pd.read_parquet(file_path)
    except Exception as exc:  # pragma: no cover - defensive fallback
        checks.append(
            DataQualityCheckResult(
                check_id=f"{file_label}_readable",
                outcome=FAIL,
                message=f"{file_label} could not be read",
                details={"error": str(exc)},
            )
        )
        return None


def _check_manifest_required_fields(
    manifest: dict[str, Any],
    checks: list[DataQualityCheckResult],
) -> None:
    missing_fields = [
        field
        for field in REQUIRED_MANIFEST_FIELDS
        if field not in manifest or manifest[field] is None or manifest[field] == ""
    ]
    if missing_fields:
        checks.append(
            DataQualityCheckResult(
                check_id="manifest_required_fields",
                outcome=FAIL,
                message="manifest is missing required fields",
                details={"missing_fields": missing_fields},
            )
        )
        return
    checks.append(
        DataQualityCheckResult(
            check_id="manifest_required_fields",
            outcome=PASS,
            message="manifest includes required contract fields",
            details={"fields": REQUIRED_MANIFEST_FIELDS},
        )
    )


def _check_manifest_config_consistency(
    manifest: dict[str, Any],
    config: ExperimentConfig,
    checks: list[DataQualityCheckResult],
) -> None:
    mismatches: dict[str, dict[str, Any]] = {}
    for field in ("dataset_id", "experiment_id", "forward_return_definition"):
        manifest_value = manifest.get(field)
        config_value = getattr(config, field)
        if manifest_value != config_value:
            mismatches[field] = {"manifest": manifest_value, "config": config_value}
    if mismatches:
        checks.append(
            DataQualityCheckResult(
                check_id="manifest_config_consistency",
                outcome=FAIL,
                message="manifest does not match config on key identity fields",
                details={"mismatches": mismatches},
            )
        )
        return
    checks.append(
        DataQualityCheckResult(
            check_id="manifest_config_consistency",
            outcome=PASS,
            message="manifest matches config on key identity fields",
            details={
                "checked_fields": ["dataset_id", "experiment_id", "forward_return_definition"]
            },
        )
    )


def _prepare_dataset_frame(
    frame: pd.DataFrame | None,
    file_label: str,
    required_columns: list[str],
    checks: list[DataQualityCheckResult],
) -> pd.DataFrame | None:
    if frame is None:
        return None
    missing_columns = sorted(set(required_columns).difference(frame.columns))
    if missing_columns:
        checks.append(
            DataQualityCheckResult(
                check_id=f"{file_label}_required_columns",
                outcome=FAIL,
                message=f"{file_label} is missing required columns",
                details={"missing_columns": missing_columns},
            )
        )
        return None
    checks.append(
        DataQualityCheckResult(
            check_id=f"{file_label}_required_columns",
            outcome=PASS,
            message=f"{file_label} includes required columns",
            details={"required_columns": required_columns},
        )
    )

    prepared = frame.loc[:, required_columns].copy()
    prepared["trade_date"] = pd.to_datetime(prepared["trade_date"], errors="coerce")
    invalid_trade_dates = int(prepared["trade_date"].isna().sum())
    if invalid_trade_dates:
        checks.append(
            DataQualityCheckResult(
                check_id=f"{file_label}_trade_date_parseable",
                outcome=FAIL,
                message=f"{file_label} contains unparseable trade_date values",
                details={"invalid_trade_date_count": invalid_trade_dates},
            )
        )
        return None
    checks.append(
        DataQualityCheckResult(
            check_id=f"{file_label}_trade_date_parseable",
            outcome=PASS,
            message=f"{file_label} trade_date values are parseable",
            details={},
        )
    )
    return prepared


def _check_primary_key_uniqueness(
    frame: pd.DataFrame,
    file_label: str,
    checks: list[DataQualityCheckResult],
) -> bool:
    duplicate_count = int(frame.duplicated(PRIMARY_KEY).sum())
    if duplicate_count:
        checks.append(
            DataQualityCheckResult(
                check_id=f"{file_label}_primary_key_unique",
                outcome=FAIL,
                message=f"{file_label} contains duplicate (trade_date, ts_code)",
                details={"duplicate_count": duplicate_count},
            )
        )
        return False
    checks.append(
        DataQualityCheckResult(
            check_id=f"{file_label}_primary_key_unique",
            outcome=PASS,
            message=f"{file_label} has unique (trade_date, ts_code)",
            details={},
        )
    )
    return True


def _check_date_range_consistency(
    panel: pd.DataFrame,
    forward_returns: pd.DataFrame,
    manifest: dict[str, Any] | None,
    config: ExperimentConfig | None,
    checks: list[DataQualityCheckResult],
) -> None:
    panel_range = _frame_date_range(panel)
    forward_range = _frame_date_range(forward_returns)
    details: dict[str, Any] = {
        "panel_range": panel_range,
        "forward_returns_range": forward_range,
    }
    mismatches: list[str] = []

    if panel_range != forward_range:
        mismatches.append("panel.parquet and forward_returns.parquet date ranges differ")

    manifest_start = None
    manifest_end = None
    if manifest is not None and "date_start" in manifest and "date_end" in manifest:
        manifest_start = _parse_date_value(manifest["date_start"])
        manifest_end = _parse_date_value(manifest["date_end"])
        details["manifest_range"] = {
            "date_start": _format_date(manifest_start),
            "date_end": _format_date(manifest_end),
        }
        if manifest_start is None or manifest_end is None:
            mismatches.append("manifest date_start/date_end could not be parsed")
        else:
            panel_start = _parse_date_value(panel_range["date_start"])
            panel_end = _parse_date_value(panel_range["date_end"])
            forward_start = _parse_date_value(forward_range["date_start"])
            forward_end = _parse_date_value(forward_range["date_end"])
            if (
                not _range_respects_declared_bounds(panel_start, panel_end, manifest_start, manifest_end)
                or not _range_gap_is_within_tolerance(panel_start, panel_end, manifest_start, manifest_end)
            ):
                mismatches.append("panel.parquet date range is not compatible with manifest date range")
            if (
                not _range_respects_declared_bounds(
                    forward_start,
                    forward_end,
                    manifest_start,
                    manifest_end,
                )
                or not _range_gap_is_within_tolerance(
                    forward_start,
                    forward_end,
                    manifest_start,
                    manifest_end,
                )
            ):
                mismatches.append(
                    "forward_returns.parquet date range is not compatible with manifest date range"
                )

    if config is not None:
        details["config_range"] = {
            "date_start": config.date_start,
            "date_end": config.date_end,
        }
        if manifest_start is not None and manifest_end is not None:
            if config.date_start != _format_date(manifest_start) or config.date_end != _format_date(
                manifest_end
            ):
                mismatches.append("config date range does not match manifest date range")

    if mismatches:
        checks.append(
            DataQualityCheckResult(
                check_id="date_range_consistency",
                outcome=FAIL,
                message="date ranges are not internally consistent",
                details={**details, "mismatches": mismatches},
            )
        )
        return
    checks.append(
        DataQualityCheckResult(
            check_id="date_range_consistency",
            outcome=PASS,
            message="panel, forward returns and declared date ranges are consistent",
            details=details,
        )
    )


def _collect_daily_universe_metrics(
    panel: pd.DataFrame,
    options: DataQualityOptions,
    checks: list[DataQualityCheckResult],
    metrics: dict[str, Any],
) -> None:
    all_trade_dates = panel["trade_date"].drop_duplicates().sort_values()
    universe_panel = panel.loc[_universe_mask(panel)]
    daily_counts = universe_panel.groupby("trade_date").size().reindex(all_trade_dates, fill_value=0)
    if daily_counts.empty:
        metrics["daily_universe"] = {
            "min": 0,
            "max": 0,
            "mean": 0.0,
            "median": 0.0,
            "dates_below_threshold": [],
        }
        checks.append(
            DataQualityCheckResult(
                check_id="daily_universe_counts",
                outcome=WARNING,
                message="dataset contains no in-universe rows",
                details=metrics["daily_universe"],
            )
        )
        return

    threshold = float(daily_counts.median()) * options.universe_low_count_ratio
    low_dates = [date.strftime("%Y-%m-%d") for date in daily_counts[daily_counts < threshold].index]
    metrics["daily_universe"] = {
        "min": int(daily_counts.min()),
        "max": int(daily_counts.max()),
        "mean": float(daily_counts.mean()),
        "median": float(daily_counts.median()),
        "threshold": threshold,
        "dates_below_threshold": low_dates,
    }
    if low_dates:
        checks.append(
            DataQualityCheckResult(
                check_id="daily_universe_counts",
                outcome=WARNING,
                message="daily universe counts fall below the warning threshold on some dates",
                details=metrics["daily_universe"],
            )
        )
        return
    checks.append(
        DataQualityCheckResult(
            check_id="daily_universe_counts",
            outcome=PASS,
            message="daily universe counts are stable within the warning threshold",
            details=metrics["daily_universe"],
        )
    )


def _collect_missing_rate_metrics(
    panel: pd.DataFrame,
    options: DataQualityOptions,
    checks: list[DataQualityCheckResult],
    metrics: dict[str, Any],
) -> None:
    universe_panel = panel.loc[_universe_mask(panel)]
    ohlcv_missing_rates = {
        column: _safe_missing_rate(universe_panel[column]) for column in OHLCV_COLUMNS
    }
    exposure_missing_rates = {
        column: _safe_missing_rate(universe_panel[column]) for column in EXPOSURE_COLUMNS
    }
    metrics["missing_rates"] = {
        "ohlcv": ohlcv_missing_rates,
        "exposures": exposure_missing_rates,
        "warning_threshold": options.missing_rate_warning,
    }

    ohlcv_issues = {
        column: rate
        for column, rate in ohlcv_missing_rates.items()
        if rate > options.missing_rate_warning
    }
    checks.append(
        DataQualityCheckResult(
            check_id="ohlcv_missing_rates",
            outcome=WARNING if ohlcv_issues else PASS,
            message=(
                "OHLCV missing rates exceed the warning threshold"
                if ohlcv_issues
                else "OHLCV missing rates are within the warning threshold"
            ),
            details={
                "missing_rates": ohlcv_missing_rates,
                "warning_columns": sorted(ohlcv_issues),
                "warning_threshold": options.missing_rate_warning,
            },
        )
    )

    exposure_issues = {
        column: rate
        for column, rate in exposure_missing_rates.items()
        if rate > options.missing_rate_warning
    }
    checks.append(
        DataQualityCheckResult(
            check_id="exposure_missing_rates",
            outcome=WARNING if exposure_issues else PASS,
            message=(
                "industry or market_cap missing rates exceed the warning threshold"
                if exposure_issues
                else "industry and market_cap missing rates are within the warning threshold"
            ),
            details={
                "missing_rates": exposure_missing_rates,
                "warning_columns": sorted(exposure_issues),
                "warning_threshold": options.missing_rate_warning,
            },
        )
    )


def _collect_forward_return_metrics(
    panel: pd.DataFrame,
    forward_returns: pd.DataFrame,
    options: DataQualityOptions,
    checks: list[DataQualityCheckResult],
    metrics: dict[str, Any],
) -> None:
    universe_panel = panel.loc[_universe_mask(panel)].copy()
    universe_forward = forward_returns.set_index(PRIMARY_KEY).reindex(
        universe_panel.set_index(PRIMARY_KEY).index
    )
    trade_dates = sorted(universe_panel["trade_date"].drop_duplicates())

    coverage_by_horizon: dict[str, Any] = {}
    warning_columns: list[str] = []
    for column in FORWARD_RETURN_VALUE_COLUMNS:
        horizon_days = _extract_horizon_days(column)
        tail_span = min(horizon_days + 1, len(trade_dates))
        tail_dates = set(trade_dates[-tail_span:]) if trade_dates else set()
        row_dates = universe_panel["trade_date"]
        tail_mask = row_dates.isin(tail_dates)
        non_tail_mask = ~tail_mask

        series = universe_forward[column]
        overall_coverage = _safe_coverage_rate(series)
        non_tail_coverage = _safe_coverage_rate(series.loc[non_tail_mask.to_numpy()])
        expected_tail_missing_rate = _safe_missing_rate(series.loc[tail_mask.to_numpy()])
        non_tail_missing_rate = _safe_missing_rate(series.loc[non_tail_mask.to_numpy()])

        coverage_by_horizon[column] = {
            "overall_coverage": overall_coverage,
            "non_tail_coverage": non_tail_coverage,
            "expected_tail_missing_rate": expected_tail_missing_rate,
            "non_tail_missing_rate": non_tail_missing_rate,
            "tail_date_count": int(tail_mask.sum()),
        }
        if non_tail_missing_rate > options.forward_non_tail_missing_rate_warning:
            warning_columns.append(column)

    metrics["forward_return_coverage"] = {
        "by_horizon": coverage_by_horizon,
        "warning_threshold": options.forward_non_tail_missing_rate_warning,
    }
    checks.append(
        DataQualityCheckResult(
            check_id="forward_return_coverage",
            outcome=WARNING if warning_columns else PASS,
            message=(
                "forward return coverage has unexpected non-tail missing values"
                if warning_columns
                else "forward return coverage is consistent outside expected tail dates"
            ),
            details={
                "warning_horizons": warning_columns,
                "coverage": coverage_by_horizon,
                "warning_threshold": options.forward_non_tail_missing_rate_warning,
            },
        )
    )


def _collect_market_cap_metrics(
    panel: pd.DataFrame,
    options: DataQualityOptions,
    checks: list[DataQualityCheckResult],
    metrics: dict[str, Any],
) -> None:
    universe_market_cap = panel.loc[_universe_mask(panel), "market_cap"]
    nonpositive_mask = universe_market_cap.le(0).fillna(False)
    nonpositive_rate = float(nonpositive_mask.mean()) if len(nonpositive_mask) else 0.0
    metrics["market_cap_nonpositive"] = {
        "nonpositive_rate": nonpositive_rate,
        "nonpositive_count": int(nonpositive_mask.sum()),
        "warning_threshold": options.market_cap_nonpositive_warning,
    }
    checks.append(
        DataQualityCheckResult(
            check_id="market_cap_nonpositive_rate",
            outcome=WARNING if nonpositive_rate > options.market_cap_nonpositive_warning else PASS,
            message=(
                "market_cap contains non-positive in-universe values"
                if nonpositive_rate > options.market_cap_nonpositive_warning
                else "market_cap is positive for in-universe rows"
            ),
            details=metrics["market_cap_nonpositive"],
        )
    )


def _pick_dataset_id(
    manifest: dict[str, Any] | None,
    config: ExperimentConfig | None,
    dataset_dir: Path,
) -> str | None:
    if manifest is not None and manifest.get("dataset_id") is not None:
        return str(manifest["dataset_id"])
    if config is not None:
        return config.dataset_id
    return dataset_dir.name or None


def _pick_experiment_id(
    manifest: dict[str, Any] | None,
    config: ExperimentConfig | None,
) -> str | None:
    if manifest is not None and manifest.get("experiment_id") is not None:
        return str(manifest["experiment_id"])
    if config is not None:
        return config.experiment_id
    return None


def _frame_date_range(frame: pd.DataFrame) -> dict[str, str | None]:
    return {
        "date_start": _format_date(frame["trade_date"].min()),
        "date_end": _format_date(frame["trade_date"].max()),
    }


def _parse_date_value(value: Any) -> pd.Timestamp | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed


def _format_date(value: pd.Timestamp | None) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _safe_missing_rate(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0
    return float(series.isna().mean())


def _safe_coverage_rate(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0
    return float(series.notna().mean())


def _extract_horizon_days(column: str) -> int:
    if not column.startswith("fwd_ret_") or not column.endswith("d"):
        raise ValueError(f"unsupported forward return column: {column}")
    return int(column.removeprefix("fwd_ret_").removesuffix("d"))


def _universe_mask(panel: pd.DataFrame) -> pd.Series:
    return panel["in_universe"].fillna(False).astype(bool)


def _range_respects_declared_bounds(
    actual_start: pd.Timestamp | None,
    actual_end: pd.Timestamp | None,
    declared_start: pd.Timestamp,
    declared_end: pd.Timestamp,
) -> bool:
    if actual_start is None or actual_end is None:
        return False
    return actual_start >= declared_start and actual_end <= declared_end


def _range_gap_is_within_tolerance(
    actual_start: pd.Timestamp | None,
    actual_end: pd.Timestamp | None,
    declared_start: pd.Timestamp,
    declared_end: pd.Timestamp,
) -> bool:
    if actual_start is None or actual_end is None:
        return False
    start_gap_days = int((actual_start - declared_start).days)
    end_gap_days = int((declared_end - actual_end).days)
    return start_gap_days <= DECLARED_RANGE_BOUNDARY_TOLERANCE_DAYS and end_gap_days <= DECLARED_RANGE_BOUNDARY_TOLERANCE_DAYS


def _overall_outcome(checks: list[DataQualityCheckResult]) -> CheckOutcome:
    if any(check.outcome == FAIL for check in checks):
        return FAIL
    if any(check.outcome == WARNING for check in checks):
        return WARNING
    return PASS
