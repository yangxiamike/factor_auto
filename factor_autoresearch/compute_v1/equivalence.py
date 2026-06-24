from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pandas as pd
from pandas.api.types import is_numeric_dtype


@dataclass(frozen=True)
class CandidateResultDiff:
    index: int
    candidate_id: str | None
    field: str
    legacy_value: Any
    v1_value: Any
    reason: str


@dataclass(frozen=True)
class CandidateResultsComparison:
    matches: bool
    row_count_match: bool
    legacy_count: int
    v1_count: int
    diffs: list[CandidateResultDiff]


@dataclass(frozen=True)
class SchemaComparison:
    matches: bool
    missing_in_v1: list[str]
    extra_in_v1: list[str]
    dtype_mismatches: list[dict[str, str]]


@dataclass(frozen=True)
class DataFrameValueDiff:
    row: int
    column: str
    legacy_value: Any
    v1_value: Any
    reason: str


@dataclass(frozen=True)
class DataFrameComparison:
    matches: bool
    row_count_match: bool
    legacy_rows: int
    v1_rows: int
    schema: SchemaComparison
    diffs: list[DataFrameValueDiff]


@dataclass(frozen=True)
class EquivalenceReport:
    matches: bool
    candidate_results: CandidateResultsComparison
    metrics: DataFrameComparison
    ic_series: DataFrameComparison
    diagnostics: DataFrameComparison


def compare_equivalence(
    *,
    legacy_results: list[dict[str, Any]],
    v1_results: list[dict[str, Any]],
    legacy_metrics: pd.DataFrame,
    v1_metrics: pd.DataFrame,
    legacy_ic_series: pd.DataFrame,
    v1_ic_series: pd.DataFrame,
    legacy_diagnostics: pd.DataFrame | None = None,
    v1_diagnostics: pd.DataFrame | None = None,
    float_tolerance: float = 1e-9,
    float_rel_tolerance: float = 1e-8,
) -> EquivalenceReport:
    candidate_results = compare_candidate_results(
        legacy_results=legacy_results,
        v1_results=v1_results,
        float_tolerance=float_tolerance,
        float_rel_tolerance=float_rel_tolerance,
    )
    metrics = compare_dataframes(
        legacy_frame=legacy_metrics,
        v1_frame=v1_metrics,
        float_tolerance=float_tolerance,
        float_rel_tolerance=float_rel_tolerance,
    )
    ic_series = compare_dataframes(
        legacy_frame=legacy_ic_series,
        v1_frame=v1_ic_series,
        float_tolerance=float_tolerance,
        float_rel_tolerance=float_rel_tolerance,
    )
    diagnostics = compare_dataframes(
        legacy_frame=legacy_diagnostics if legacy_diagnostics is not None else pd.DataFrame(),
        v1_frame=v1_diagnostics if v1_diagnostics is not None else pd.DataFrame(),
        float_tolerance=float_tolerance,
        float_rel_tolerance=float_rel_tolerance,
    )
    return EquivalenceReport(
        matches=candidate_results.matches and metrics.matches and ic_series.matches and diagnostics.matches,
        candidate_results=candidate_results,
        metrics=metrics,
        ic_series=ic_series,
        diagnostics=diagnostics,
    )


def compare_candidate_results(
    *,
    legacy_results: list[dict[str, Any]],
    v1_results: list[dict[str, Any]],
    float_tolerance: float = 1e-9,
    float_rel_tolerance: float = 1e-8,
) -> CandidateResultsComparison:
    diffs: list[CandidateResultDiff] = []
    legacy_count = len(legacy_results)
    v1_count = len(v1_results)
    row_count_match = legacy_count == v1_count

    for index, (legacy_row, v1_row) in enumerate(zip(legacy_results, v1_results, strict=False)):
        candidate_id = str(legacy_row.get("id", v1_row.get("id"))) if isinstance(legacy_row, dict) and isinstance(v1_row, dict) else None
        all_fields = sorted(set(legacy_row.keys()) | set(v1_row.keys()))
        for field in all_fields:
            legacy_has = field in legacy_row
            v1_has = field in v1_row
            if not legacy_has or not v1_has:
                diffs.append(
                    CandidateResultDiff(
                        index=index,
                        candidate_id=candidate_id,
                        field=field,
                        legacy_value=legacy_row.get(field),
                        v1_value=v1_row.get(field),
                        reason="missing_field",
                    )
                )
                continue
            if not _values_match(legacy_row[field], v1_row[field], float_tolerance, float_rel_tolerance):
                diffs.append(
                    CandidateResultDiff(
                        index=index,
                        candidate_id=candidate_id,
                        field=field,
                        legacy_value=legacy_row[field],
                        v1_value=v1_row[field],
                        reason="value_mismatch",
                    )
                )

    if not row_count_match:
        longer_rows = legacy_results if legacy_count > v1_count else v1_results
        reason = "missing_row_in_v1" if legacy_count > v1_count else "extra_row_in_v1"
        for index in range(min(legacy_count, v1_count), max(legacy_count, v1_count)):
            row = longer_rows[index]
            diffs.append(
                CandidateResultDiff(
                    index=index,
                    candidate_id=str(row.get("id")) if isinstance(row, dict) and row.get("id") is not None else None,
                    field="__row__",
                    legacy_value=legacy_results[index] if index < legacy_count else None,
                    v1_value=v1_results[index] if index < v1_count else None,
                    reason=reason,
                )
            )

    return CandidateResultsComparison(
        matches=row_count_match and not diffs,
        row_count_match=row_count_match,
        legacy_count=legacy_count,
        v1_count=v1_count,
        diffs=diffs,
    )


def compare_dataframes(
    *,
    legacy_frame: pd.DataFrame,
    v1_frame: pd.DataFrame,
    float_tolerance: float = 1e-9,
    float_rel_tolerance: float = 1e-8,
) -> DataFrameComparison:
    legacy_frame = legacy_frame.reset_index(drop=True)
    v1_frame = v1_frame.reset_index(drop=True)

    schema = _compare_schema(legacy_frame, v1_frame)
    legacy_rows = len(legacy_frame)
    v1_rows = len(v1_frame)
    row_count_match = legacy_rows == v1_rows
    diffs: list[DataFrameValueDiff] = []

    common_columns = [column for column in legacy_frame.columns if column in v1_frame.columns]
    for row in range(min(legacy_rows, v1_rows)):
        for column in common_columns:
            legacy_value = legacy_frame.iloc[row][column]
            v1_value = v1_frame.iloc[row][column]
            if not _values_match(legacy_value, v1_value, float_tolerance, float_rel_tolerance):
                diffs.append(
                    DataFrameValueDiff(
                        row=row,
                        column=column,
                        legacy_value=legacy_value,
                        v1_value=v1_value,
                        reason="value_mismatch",
                    )
                )

    return DataFrameComparison(
        matches=schema.matches and row_count_match and not diffs,
        row_count_match=row_count_match,
        legacy_rows=legacy_rows,
        v1_rows=v1_rows,
        schema=schema,
        diffs=diffs,
    )


def _compare_schema(legacy_frame: pd.DataFrame, v1_frame: pd.DataFrame) -> SchemaComparison:
    legacy_columns = list(legacy_frame.columns)
    v1_columns = list(v1_frame.columns)
    missing_in_v1 = [column for column in legacy_columns if column not in v1_columns]
    extra_in_v1 = [column for column in v1_columns if column not in legacy_columns]

    dtype_mismatches: list[dict[str, str]] = []
    for column in legacy_columns:
        if column not in v1_frame.columns:
            continue
        legacy_dtype = str(legacy_frame[column].dtype)
        v1_dtype = str(v1_frame[column].dtype)
        if legacy_dtype != v1_dtype:
            dtype_mismatches.append(
                {
                    "column": column,
                    "legacy_dtype": legacy_dtype,
                    "v1_dtype": v1_dtype,
                }
            )

    return SchemaComparison(
        matches=not missing_in_v1 and not extra_in_v1 and not dtype_mismatches,
        missing_in_v1=missing_in_v1,
        extra_in_v1=extra_in_v1,
        dtype_mismatches=dtype_mismatches,
    )


def _values_match(
    legacy_value: Any,
    v1_value: Any,
    float_tolerance: float,
    float_rel_tolerance: float,
) -> bool:
    if isinstance(legacy_value, dict) and isinstance(v1_value, dict):
        keys = set(legacy_value.keys()) | set(v1_value.keys())
        return all(
            key in legacy_value
            and key in v1_value
            and _values_match(legacy_value[key], v1_value[key], float_tolerance, float_rel_tolerance)
            for key in keys
        )

    if isinstance(legacy_value, list) and isinstance(v1_value, list):
        return len(legacy_value) == len(v1_value) and all(
            _values_match(left, right, float_tolerance, float_rel_tolerance)
            for left, right in zip(legacy_value, v1_value, strict=False)
        )

    if _is_null_like(legacy_value) and _is_null_like(v1_value):
        return True

    if _is_number(legacy_value) and _is_number(v1_value):
        return math.isclose(
            float(legacy_value),
            float(v1_value),
            rel_tol=float_rel_tolerance,
            abs_tol=float_tolerance,
        )

    return legacy_value == v1_value


def _is_null_like(value: Any) -> bool:
    return bool(pd.isna(value)) if not isinstance(value, (dict, list, tuple, set)) else False


def _is_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    return is_numeric_dtype(type(value))
