"""
区块4因子值资产模块
负责保存和读取 raw / preprocessed factor values。
不负责事件账本和因子状态决策。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import pandas as pd

from factor_autoresearch.factor_assets import list_factor_records


# ============== 数据结构 ==============
@dataclass(frozen=True)
class LibraryFactorValuesLoadResult:
    """资产值加载结果: 返回可复用 active values 与跳过原因。"""

    values: dict[str, pd.Series]
    loaded_factor_ids: tuple[str, ...]
    skipped: tuple[dict[str, str], ...]


# ============== 基础辅助函数 ==============
def _canonical_json(payload: object) -> str:
    """稳定 JSON: 用于哈希和口径比较。"""

    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def _scope_payload(
    *,
    factor_id: str,
    source_universe_key: object,
    forward_return_definition: object,
    sample_protocol_hash: object,
    preprocess_config_hash: object,
    date_start: str,
    date_end: str,
) -> dict[str, object]:
    """值范围载荷: 统一 scope hash 输入字段。"""

    return {
        "factor_id": factor_id,
        "source_universe_key": source_universe_key,
        "forward_return_definition": forward_return_definition,
        "sample_protocol_hash": sample_protocol_hash,
        "preprocess_config_hash": preprocess_config_hash,
        "date_start": date_start,
        "date_end": date_end,
    }


def build_value_scope_hash(
    *,
    factor_id: str,
    source_universe_key: object,
    forward_return_definition: object,
    sample_protocol_hash: object,
    preprocess_config_hash: object,
    date_start: str,
    date_end: str,
) -> str:
    """值范围哈希: 为同因子多口径值文件生成稳定目录键。"""

    payload = _scope_payload(
        factor_id=factor_id,
        source_universe_key=source_universe_key,
        forward_return_definition=forward_return_definition,
        sample_protocol_hash=sample_protocol_hash,
        preprocess_config_hash=preprocess_config_hash,
        date_start=date_start,
        date_end=date_end,
    )
    return f"sha256_{sha256(_canonical_json(payload).encode('utf-8')).hexdigest()}"


def _series_to_frame(series: pd.Series, column_name: str) -> pd.DataFrame:
    """序列转表: 统一落盘为 trade_date/ts_code/value 三列。"""

    if not isinstance(series.index, pd.MultiIndex):
        raise ValueError("factor values must use a MultiIndex with trade_date and ts_code")
    return pd.DataFrame(
        {
            "trade_date": series.index.get_level_values("trade_date"),
            "ts_code": series.index.get_level_values("ts_code"),
            column_name: series.to_numpy(),
        }
    )


def _value_hash(series: pd.Series) -> str:
    """值哈希: 对 Series 的索引和值生成稳定摘要。"""

    hashed = pd.util.hash_pandas_object(series.astype(float), index=True).to_numpy()
    return f"sha256:{sha256(hashed.tobytes()).hexdigest()}"


def _asset_values_dir(asset_store_dir: str | Path, factor_id: str, value_scope_hash: str) -> Path:
    """值目录: 统一拼装资产值路径。"""

    return Path(asset_store_dir) / "values" / factor_id / value_scope_hash


def _scope_mismatch_reason(manifest: dict[str, object], expected: dict[str, object]) -> str | None:
    """口径差异原因: 返回首个不匹配字段。"""

    for key in (
        "source_universe_key",
        "forward_return_definition",
        "sample_protocol_hash",
        "preprocess_config_hash",
        "date_start",
        "date_end",
    ):
        if _canonical_json(manifest.get(key)) != _canonical_json(expected.get(key)):
            return f"{key}_mismatch"
    return None


def save_factor_values(
    asset_store_dir: str | Path,
    *,
    factor_id: str,
    expression_hash: str,
    source_run_id: str,
    source_universe_key: object,
    forward_return_definition: object,
    sample_protocol_hash: object,
    preprocess_config_hash: object,
    raw_factor: pd.Series,
    preprocessed_factor: pd.Series,
    created_at: str,
) -> dict[str, object]:
    """保存因子值: 写 raw/preprocessed parquet 与 manifest。"""

    if len(raw_factor) != len(preprocessed_factor):
        raise ValueError("raw_factor and preprocessed_factor must have the same number of rows")
    date_start = pd.Timestamp(raw_factor.index.get_level_values("trade_date").min()).strftime("%Y-%m-%d")
    date_end = pd.Timestamp(raw_factor.index.get_level_values("trade_date").max()).strftime("%Y-%m-%d")
    value_scope_hash = build_value_scope_hash(
        factor_id=factor_id,
        source_universe_key=source_universe_key,
        forward_return_definition=forward_return_definition,
        sample_protocol_hash=sample_protocol_hash,
        preprocess_config_hash=preprocess_config_hash,
        date_start=date_start,
        date_end=date_end,
    )
    output_dir = _asset_values_dir(asset_store_dir, factor_id, value_scope_hash)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_frame = _series_to_frame(raw_factor.rename("raw_value"), "raw_value")
    preprocessed_frame = _series_to_frame(preprocessed_factor.rename("factor_value"), "factor_value")
    raw_path = output_dir / "raw.parquet"
    preprocessed_path = output_dir / "preprocessed.parquet"
    manifest_path = output_dir / "manifest.json"
    raw_frame.to_parquet(raw_path, index=False)
    preprocessed_frame.to_parquet(preprocessed_path, index=False)

    manifest = {
        "factor_id": factor_id,
        "expression_hash": expression_hash,
        "source_run_id": source_run_id,
        "source_universe_key": source_universe_key,
        "forward_return_definition": forward_return_definition,
        "sample_protocol_hash": sample_protocol_hash,
        "preprocess_config_hash": preprocess_config_hash,
        "date_start": date_start,
        "date_end": date_end,
        "row_count": int(len(preprocessed_factor)),
        "value_hash": _value_hash(preprocessed_factor),
        "created_at": created_at,
        "value_scope_hash": value_scope_hash,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "value_scope_hash": value_scope_hash,
        "manifest_path": manifest_path,
        "raw_path": raw_path,
        "preprocessed_path": preprocessed_path,
    }


def load_library_factor_values(
    asset_store_dir: str | Path,
    *,
    source_universe_key: object,
    forward_return_definition: object,
    sample_protocol_hash: object,
    preprocess_config_hash: object,
    date_start: str,
    date_end: str,
) -> LibraryFactorValuesLoadResult:
    """读取资产值: 只返回 active 因子的 matching preprocessed values。"""

    expected = _scope_payload(
        factor_id="*",
        source_universe_key=source_universe_key,
        forward_return_definition=forward_return_definition,
        sample_protocol_hash=sample_protocol_hash,
        preprocess_config_hash=preprocess_config_hash,
        date_start=date_start,
        date_end=date_end,
    )
    values: dict[str, pd.Series] = {}
    loaded_ids: list[str] = []
    skipped: list[dict[str, str]] = []

    for record in list_factor_records(asset_store_dir, status="active"):
        factor_id = str(record["factor_id"])
        scopes = list(record.get("value_scopes", []))
        if not scopes:
            skipped.append({"factor_id": factor_id, "reason": "missing_value_scope"})
            continue

        matched = False
        for value_scope_hash in scopes:
            manifest_path = _asset_values_dir(asset_store_dir, factor_id, value_scope_hash) / "manifest.json"
            if not manifest_path.exists():
                skipped.append({"factor_id": factor_id, "reason": "missing_manifest"})
                continue
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            mismatch = _scope_mismatch_reason(
                manifest,
                {**expected, "factor_id": factor_id},
            )
            if mismatch is not None:
                skipped.append({"factor_id": factor_id, "reason": mismatch})
                continue
            frame = pd.read_parquet(manifest_path.parent / "preprocessed.parquet")
            series = (
                frame.assign(trade_date=pd.to_datetime(frame["trade_date"]))
                .set_index(["trade_date", "ts_code"])["factor_value"]
                .astype(float)
                .rename(factor_id)
            )
            values[factor_id] = series
            loaded_ids.append(factor_id)
            matched = True
            break
        if not matched and factor_id not in values and not any(item["factor_id"] == factor_id for item in skipped):
            skipped.append({"factor_id": factor_id, "reason": "scope_not_found"})

    return LibraryFactorValuesLoadResult(
        values=values,
        loaded_factor_ids=tuple(loaded_ids),
        skipped=tuple(skipped),
    )

