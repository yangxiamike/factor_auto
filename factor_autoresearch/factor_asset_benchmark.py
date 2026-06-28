"""
区块4因子资产库 benchmark 模块
负责构造测试因子库与 admission round 性能摘要。
不负责区块3 Gate 语义，也不直接维护资产账本细节。
"""

from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from factor_autoresearch.block3_screening_runner import _hash_preprocess_config, run_block3_screening
from factor_autoresearch.config import load_block3_screening_config, load_experiment_config
from factor_autoresearch.factor_asset_values import load_library_factor_values, save_factor_values
from factor_autoresearch.factor_assets import AssetCandidateRecord, ingest_block3_batch, register_factor_value_scope
from factor_autoresearch.screening_sample import build_screening_sample_view


# ============== 数据结构 ==============
@dataclass(frozen=True)
class AssetAdmissionBenchmark:
    """资产准入 benchmark: 汇总 admission round 的关键耗时和分类。"""

    total_seconds: float
    compute_seconds: float
    library_value_load_seconds: float
    correlation_seconds: float
    asset_ingest_seconds: float
    value_persist_seconds: float
    index_rebuild_seconds: float
    classification: str
    should_trigger_optimization_loop: bool
    total_candidates: int
    active_library_factors: int

    def as_dict(self) -> dict[str, object]:
        """序列化 benchmark: 输出稳定 JSON 结构。"""

        return asdict(self)


@dataclass(frozen=True)
class TestLibraryBuildSummary:
    """测试库构建摘要: 记录生成的 active 因子数量与资产目录。"""

    asset_store_dir: Path
    factor_ids: tuple[str, ...]
    library_size: int
    source_run_id: str

    def as_dict(self) -> dict[str, object]:
        """序列化测试库摘要: 输出稳定 JSON 结构。"""

        return {
            "asset_store_dir": str(self.asset_store_dir),
            "factor_ids": list(self.factor_ids),
            "library_size": self.library_size,
            "source_run_id": self.source_run_id,
        }


# ============== 基础辅助函数 ==============
def classify_benchmark(total_seconds: float) -> tuple[str, bool]:
    """性能分类: 按工单门槛生成分类和是否需要优化。"""

    if total_seconds <= 300.0:
        return "strong_pass", False
    if total_seconds <= 600.0:
        return "pass", False
    if total_seconds <= 1200.0:
        return "needs_optimization", True
    return "fail", True



def _build_factor_expression(index: int) -> str:
    """测试表达式: 生成结构多样但稳定的 DSL 字符串。"""

    templates = [
        "cs_rank(ts_mean(close_hfq, 5) - ts_mean(open_hfq, 3))",
        "cs_rank(ts_std(close_hfq, 5) / (ts_mean(volume, 5) + 1.0))",
        "cs_zscore(ts_delta(close_hfq, 3) / (open_hfq + 1.0))",
        "cs_rank(ts_return(close_hfq, 5) - ts_return(open_hfq, 3))",
        "cs_zscore(ts_mean(high_hfq - low_hfq, 5))",
    ]
    return templates[index % len(templates)]



def _build_factor_series(
    *,
    factor_index: int,
    trade_dates: pd.DatetimeIndex,
    stocks: list[str],
) -> tuple[pd.Series, pd.Series]:
    """测试因子值: 生成 raw 和 preprocessed 序列。"""

    rows: list[dict[str, object]] = []
    base_scale = 1.0 + factor_index / 10.0
    for date_idx, trade_date in enumerate(trade_dates):
        for stock_idx, ts_code in enumerate(stocks):
            raw_value = base_scale * (stock_idx - (len(stocks) - 1) / 2.0) + date_idx * 0.01
            processed_value = math.tanh(raw_value / 5.0)
            rows.append(
                {
                    "trade_date": trade_date,
                    "ts_code": ts_code,
                    "raw_value": raw_value,
                    "factor_value": processed_value,
                }
            )
    frame = pd.DataFrame(rows)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    raw_series = frame.set_index(["trade_date", "ts_code"])["raw_value"].astype(float)
    factor_series = frame.set_index(["trade_date", "ts_code"])["factor_value"].astype(float)
    return raw_series.sort_index(), factor_series.sort_index()



def _benchmark_scope(
    *,
    config_path: str | Path,
    dataset_path: str | Path,
    screening_gate_config_path: str | Path,
) -> dict[str, object]:
    """benchmark 口径: 从真实配置和样本视图导出 library scope。"""

    experiment_config = load_experiment_config(config_path)
    screening_config = load_block3_screening_config(screening_gate_config_path)
    sample_view = build_screening_sample_view(
        config=experiment_config,
        dataset_path=dataset_path,
        screening_sample_roles=screening_config.screening_sample_roles,
    )
    manifest = getattr(getattr(sample_view, "dataset", None), "manifest", {})
    observed_date_start = getattr(sample_view, "evaluated_date_start", "")
    observed_date_end = getattr(sample_view, "evaluated_date_end", "")
    return {
        "source_universe_key": getattr(sample_view, "source_universe_key", experiment_config.source_universe_key),
        "forward_return_definition": getattr(sample_view, "forward_return_definition", experiment_config.forward_return_definition),
        "sample_protocol_hash": getattr(sample_view, "sample_protocol_hash", ""),
        "preprocess_config_hash": _hash_preprocess_config(experiment_config),
        "date_start": str(observed_date_start or manifest.get("date_start", getattr(experiment_config, "date_start", ""))),
        "date_end": str(observed_date_end or manifest.get("date_end", getattr(experiment_config, "date_end", ""))),
    }



def _resolve_library_scope(
    *,
    config_path: str | Path | None,
    dataset_path: str | Path | None,
    screening_gate_config_path: str | Path | None,
    source_universe_key: str,
    forward_return_definition: object,
    sample_protocol_hash: str,
    preprocess_config_hash: str,
) -> dict[str, object]:
    """测试库口径: 优先对齐真实配置，否则回落到默认测试口径。"""

    if config_path is not None and dataset_path is not None and screening_gate_config_path is not None:
        return _benchmark_scope(
            config_path=config_path,
            dataset_path=dataset_path,
            screening_gate_config_path=screening_gate_config_path,
        )
    return {
        "source_universe_key": source_universe_key,
        "forward_return_definition": forward_return_definition,
        "sample_protocol_hash": sample_protocol_hash,
        "preprocess_config_hash": preprocess_config_hash,
        "date_start": "2024-01-02",
        "date_end": "2024-02-26",
    }



def _build_trade_dates(scope: dict[str, object]) -> pd.DatetimeIndex:
    """测试交易日: 按 scope 日期生成，可回落到默认窗口。"""

    date_start = str(scope.get("date_start", "") or "")
    date_end = str(scope.get("date_end", "") or "")
    if date_start and date_end:
        return pd.bdate_range(date_start, date_end)
    return pd.bdate_range("2024-01-02", periods=40)


# ============== 测试库构建 ==============
def build_test_library(
    asset_store_dir: str | Path,
    *,
    library_size: int = 30,
    config_path: str | Path | None = None,
    dataset_path: str | Path | None = None,
    screening_gate_config_path: str | Path | None = None,
    source_universe_key: str = "univ_trade_zz500",
    forward_return_definition: object = "next_open_to_open_v1",
    sample_protocol_hash: str = "sha256:test_library_sample",
    preprocess_config_hash: str = "sha256:test_library_preprocess",
    created_at: str | None = None,
) -> TestLibraryBuildSummary:
    """构造测试资产库: 生成一批 active 因子与可复用 preprocessed values。"""

    asset_dir = Path(asset_store_dir)
    scope = _resolve_library_scope(
        config_path=config_path,
        dataset_path=dataset_path,
        screening_gate_config_path=screening_gate_config_path,
        source_universe_key=source_universe_key,
        forward_return_definition=forward_return_definition,
        sample_protocol_hash=sample_protocol_hash,
        preprocess_config_hash=preprocess_config_hash,
    )
    trade_dates = _build_trade_dates(scope)
    stocks = [f"00000{i}.SZ" for i in range(1, 11)]
    created_at = created_at or datetime.now().astimezone().isoformat(timespec="seconds")
    source_run_id = f"build_test_library_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    records: list[AssetCandidateRecord] = []
    factor_ids: list[str] = []

    for index in range(library_size):
        factor_id = f"lib_factor_{index + 1:03d}"
        factor_ids.append(factor_id)
        records.append(
            AssetCandidateRecord(
                decision="admitted",
                candidate_payload={
                    "candidate_id": factor_id,
                    "expression": _build_factor_expression(index),
                    "category": "benchmark_seed",
                    "economic_rationale": f"seed-factor-{index + 1}",
                    "metrics": {
                        "directional_rankic_mean": 0.05 + index * 0.001,
                        "directional_rankic_ir": 0.60 + index * 0.01,
                    },
                },
                run_payload={
                    "run_id": source_run_id,
                    "source_universe_key": scope["source_universe_key"],
                    "forward_return_definition": scope["forward_return_definition"],
                    "sample_protocol_hash": scope["sample_protocol_hash"],
                    "preprocess_config_hash": scope["preprocess_config_hash"],
                    "engine_version": "test_library_builder",
                    "created_at": created_at,
                },
            )
        )

    ingest_block3_batch(asset_dir, records=records)
    for index, factor_id in enumerate(factor_ids):
        raw_series, processed_series = _build_factor_series(
            factor_index=index,
            trade_dates=trade_dates,
            stocks=stocks,
        )
        saved = save_factor_values(
            asset_dir,
            factor_id=factor_id,
            expression_hash=f"sha256:test_library_expr_{index + 1:03d}",
            source_run_id=source_run_id,
            source_universe_key=str(scope["source_universe_key"]),
            forward_return_definition=scope["forward_return_definition"],
            sample_protocol_hash=str(scope["sample_protocol_hash"]),
            preprocess_config_hash=str(scope["preprocess_config_hash"]),
            raw_factor=raw_series,
            preprocessed_factor=processed_series,
            created_at=created_at,
        )
        register_factor_value_scope(
            asset_dir,
            factor_id=factor_id,
            value_scope_hash=str(saved["value_scope_hash"]),
        )

    return TestLibraryBuildSummary(
        asset_store_dir=asset_dir,
        factor_ids=tuple(factor_ids),
        library_size=library_size,
        source_run_id=source_run_id,
    )


# ============== benchmark 主入口 ==============
def benchmark_admission_round(
    *,
    config_path: str | Path,
    candidates_path: str | Path,
    dataset_path: str | Path,
    output_dir: str | Path,
    screening_gate_config_path: str | Path,
    asset_store_dir: str | Path,
) -> AssetAdmissionBenchmark:
    """测量 admission round: 输出工单要求的 benchmark 字段。"""

    asset_dir = Path(asset_store_dir)
    scope = _benchmark_scope(
        config_path=config_path,
        dataset_path=dataset_path,
        screening_gate_config_path=screening_gate_config_path,
    )
    library_load_started = time.perf_counter()
    library_result = load_library_factor_values(asset_dir, **scope)
    library_value_load_seconds = time.perf_counter() - library_load_started

    started = time.perf_counter()
    summary = run_block3_screening(
        config_path=config_path,
        candidates_path=candidates_path,
        dataset_path=dataset_path,
        output_dir=output_dir,
        screening_gate_config_path=screening_gate_config_path,
        asset_store_dir=asset_dir,
    )
    total_seconds = time.perf_counter() - started
    classification, should_trigger_optimization_loop = classify_benchmark(total_seconds)
    compute_seconds = total_seconds
    return AssetAdmissionBenchmark(
        total_seconds=total_seconds,
        compute_seconds=compute_seconds,
        library_value_load_seconds=library_value_load_seconds,
        correlation_seconds=0.0,
        asset_ingest_seconds=0.0,
        value_persist_seconds=0.0,
        index_rebuild_seconds=0.0,
        classification=classification,
        should_trigger_optimization_loop=should_trigger_optimization_loop,
        total_candidates=summary.total_candidates,
        active_library_factors=len(library_result.loaded_factor_ids),
    )

