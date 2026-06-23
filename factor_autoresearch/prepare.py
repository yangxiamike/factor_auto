"""
固定数据集准备模块: 从 zer0share 风格源数据构造 panel、forward returns 和落盘产物。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from factor_autoresearch.config import ExperimentConfig


# ============== 结果结构 ==============
@dataclass(frozen=True)
class PreparedDataset:
    """准备结果: 汇总 panel、forward returns 和 manifest 三类输出。"""

    panel: pd.DataFrame
    forward_returns: pd.DataFrame
    manifest: dict[str, object]


# ============== 日期辅助函数 ==============
def _yyyymmdd(date_text: str) -> str:
    """日期转码: 把 YYYY-MM-DD 转成 DuckDB 查询使用的 YYYYMMDD。"""

    return date_text.replace("-", "")


# ============== 源数据读取函数 ==============
def _read_trade_dates(conn: duckdb.DuckDBPyConnection, data_dir: Path, config: ExperimentConfig) -> pd.DataFrame:
    """读取交易日: 按配置区间加载上交所开市日历。"""

    pattern = str(data_dir / "stock" / "trade_cal" / "exchange=*" / "data.parquet")
    sql = """
        select cast(cal_date as varchar) as trade_date
        from read_parquet(?, hive_partitioning=true)
        where exchange = 'SSE'
          and is_open = true
          and cast(cal_date as varchar) between ? and ?
        order by trade_date
    """
    return conn.execute(sql, [pattern, _yyyymmdd(config.date_start), _yyyymmdd(config.date_end)]).fetchdf()


def _read_universe_members(
    conn: duckdb.DuckDBPyConnection, data_dir: Path, config: ExperimentConfig
) -> pd.DataFrame:
    """读取股票池: 按日期区间加载目标 universe 的成分股。"""

    pattern = str(
        data_dir
        / "stock"
        / "universe"
        / f"name={config.source_universe_key}"
        / "date=*"
        / "data.parquet"
    )
    sql = """
        select cast(replace(cast(trade_date as varchar), '-', '') as varchar) as trade_date, ts_code
        from read_parquet(?, hive_partitioning=true)
        where cast(replace(cast(trade_date as varchar), '-', '') as varchar) between ? and ?
    """
    return conn.execute(sql, [pattern, _yyyymmdd(config.date_start), _yyyymmdd(config.date_end)]).fetchdf()


def _read_table_for_codes(
    conn: duckdb.DuckDBPyConnection,
    pattern: str,
    date_column: str,
    start_date: str,
    end_date: str,
    columns: list[str],
) -> pd.DataFrame:
    """读取表数据: 按股票池和日期区间过滤通用行情类 parquet 表。"""

    sql = f"""
        select {", ".join(columns)}
        from read_parquet(?, hive_partitioning=true) as src
        join codes using(ts_code)
        where cast(replace(cast({date_column} as varchar), '-', '') as varchar) between ? and ?
    """
    return conn.execute(sql, [pattern, start_date, end_date]).fetchdf()


def _read_industry_members(
    conn: duckdb.DuckDBPyConnection, data_dir: Path, industry_source: str
) -> pd.DataFrame:
    """读取行业归属: 加载股票行业成员及其生效区间。"""

    if industry_source.startswith("sw_"):
        pattern = str(data_dir / "stock" / "industry" / "sw_member" / "data.parquet")
    else:
        pattern = str(data_dir / "stock" / "industry" / "ci_member" / "data.parquet")
    sql = """
        select
            ts_code,
            l1_name as industry,
            cast(strptime(in_date, '%Y%m%d') as date) as in_date,
            case
                when out_date is null or out_date = '' then null
                else cast(strptime(out_date, '%Y%m%d') as date)
            end as out_date
        from read_parquet(?)
        join codes using(ts_code)
    """
    return conn.execute(sql, [pattern]).fetchdf()


# ============== 数据集构造函数 ==============
def _build_panel(
    trading_days: pd.DataFrame,
    universe_members: pd.DataFrame,
    daily_kline: pd.DataFrame,
    daily_basic: pd.DataFrame,
    adj_factor: pd.DataFrame,
    ci_members: pd.DataFrame,
) -> pd.DataFrame:
    """构造 panel: 拼接交易网格、股票池、行情、市值和行业信息。"""

    codes = pd.DataFrame({"ts_code": sorted(universe_members["ts_code"].unique().tolist())})
    trading_days = trading_days.rename(columns={"trade_date": "trade_date_text"})
    trading_days["trade_date"] = pd.to_datetime(trading_days["trade_date_text"], format="%Y%m%d")
    grid = trading_days.assign(_key=1).merge(codes.assign(_key=1), on="_key").drop(columns="_key")
    grid = grid[["trade_date", "ts_code"]]

    universe = universe_members.copy()
    universe["trade_date"] = pd.to_datetime(universe["trade_date"], format="%Y%m%d")
    universe["in_universe"] = True

    daily_kline = daily_kline.copy()
    daily_kline["trade_date"] = pd.to_datetime(daily_kline["trade_date"])
    daily_basic = daily_basic.copy()
    daily_basic["trade_date"] = pd.to_datetime(daily_basic["trade_date"])
    adj_factor = adj_factor.copy()
    adj_factor["trade_date"] = pd.to_datetime(adj_factor["trade_date"])

    panel = grid.merge(
        universe[["trade_date", "ts_code", "in_universe"]],
        on=["trade_date", "ts_code"],
        how="left",
    )
    panel["in_universe"] = panel["in_universe"].fillna(False)
    panel = panel.merge(
        daily_kline[["trade_date", "ts_code", "open", "high", "low", "close", "vol"]],
        on=["trade_date", "ts_code"],
        how="left",
    )
    panel = panel.merge(
        daily_basic[["trade_date", "ts_code", "total_mv"]],
        on=["trade_date", "ts_code"],
        how="left",
    )
    panel = panel.merge(
        adj_factor[["trade_date", "ts_code", "adj_factor"]],
        on=["trade_date", "ts_code"],
        how="left",
    )

    industry_lookup = grid.merge(ci_members.copy(), on="ts_code", how="left")
    active_industry = industry_lookup[
        (industry_lookup["in_date"].isna() | (industry_lookup["trade_date"] >= industry_lookup["in_date"]))
        & (
            industry_lookup["out_date"].isna()
            | (industry_lookup["trade_date"] <= industry_lookup["out_date"])
        )
    ].copy()
    active_industry = active_industry.sort_values(["trade_date", "ts_code", "in_date"])
    active_industry = active_industry.drop_duplicates(["trade_date", "ts_code"], keep="last")
    panel = panel.merge(
        active_industry[["trade_date", "ts_code", "industry"]],
        on=["trade_date", "ts_code"],
        how="left",
    )

    for raw, adjusted in [
        ("open", "open_hfq"),
        ("high", "high_hfq"),
        ("low", "low_hfq"),
        ("close", "close_hfq"),
    ]:
        panel[adjusted] = panel[raw] * panel["adj_factor"]

    panel = panel.rename(columns={"total_mv": "market_cap", "vol": "volume"})
    panel = panel[
        [
            "trade_date",
            "ts_code",
            "in_universe",
            "industry",
            "market_cap",
            "open_hfq",
            "high_hfq",
            "low_hfq",
            "close_hfq",
            "volume",
        ]
    ].sort_values(["trade_date", "ts_code"])
    return panel


def _build_forward_returns(panel: pd.DataFrame) -> pd.DataFrame:
    """构造未来收益: 基于复权开盘价生成 1/5/20 日 forward returns。"""

    ordered = panel.sort_values(["ts_code", "trade_date"]).copy()
    grouped = ordered.groupby("ts_code", sort=False)["open_hfq"]
    entry_open = grouped.shift(-1)
    result = ordered[["trade_date", "ts_code"]].copy()
    for horizon in (1, 5, 20):
        exit_open = grouped.shift(-(horizon + 1))
        result[f"fwd_ret_{horizon}d"] = (exit_open / entry_open) - 1.0
    return result.sort_values(["trade_date", "ts_code"])


# ============== 写出入口 ==============
def prepare_fixed_dataset(
    *,
    config: ExperimentConfig,
    output_path: str | Path,
) -> PreparedDataset:
    """准备固定数据集: 读取源数据、构造标准产物并写入数据集目录。"""

    source_data_dir = (config.source_path / "data").resolve()
    if not source_data_dir.exists():
        raise FileNotFoundError(f"zer0share data directory not found: {source_data_dir}")

    start_date = _yyyymmdd(config.date_start)
    end_date = _yyyymmdd(config.date_end)

    conn = duckdb.connect()
    try:
        trading_days = _read_trade_dates(conn, source_data_dir, config)
        universe_members = _read_universe_members(conn, source_data_dir, config)
        if universe_members.empty:
            raise ValueError("source universe is empty for the requested date range")

        universe_codes = pd.DataFrame({"ts_code": sorted(universe_members["ts_code"].unique().tolist())})
        conn.register("codes", universe_codes)

        daily_kline = _read_table_for_codes(
            conn,
            str(source_data_dir / "stock" / "daily_kline" / "date=*" / "data.parquet"),
            "trade_date",
            start_date,
            end_date,
            ["ts_code", "trade_date", "open", "high", "low", "close", "vol"],
        )
        daily_basic = _read_table_for_codes(
            conn,
            str(source_data_dir / "stock" / "daily_basic" / "date=*" / "data.parquet"),
            "trade_date",
            start_date,
            end_date,
            ["ts_code", "trade_date", "total_mv"],
        )
        adj_factor = _read_table_for_codes(
            conn,
            str(source_data_dir / "stock" / "adj_factor" / "date=*" / "data.parquet"),
            "trade_date",
            start_date,
            end_date,
            ["ts_code", "trade_date", "adj_factor"],
        )
        ci_members = _read_industry_members(conn, source_data_dir, config.industry_source)
    finally:
        conn.close()

    # 保持 panel 和 forward_returns 的结构不变，只整理主流程的扫读顺序。
    panel = _build_panel(trading_days, universe_members, daily_kline, daily_basic, adj_factor, ci_members)
    panel = panel.replace([np.inf, -np.inf], np.nan)
    forward_returns = _build_forward_returns(panel)

    manifest = {
        "dataset_id": config.dataset_id,
        "experiment_id": config.experiment_id,
        "created_at": pd.Timestamp.now("UTC").strftime("%Y-%m-%d"),
        "source": config.source,
        "source_path": str(config.source_path),
        "universe": config.universe,
        "source_universe_key": config.source_universe_key,
        "date_start": config.date_start,
        "date_end": config.date_end,
        "adjustment": config.adjustment,
        "features": config.features,
        "preprocess_exposures": config.preprocess_exposures,
        "base_filters_inherited": config.base_filters_inherited,
        "forward_returns": config.horizons,
        "forward_return_definition": config.forward_return_definition,
    }

    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(output_dir / "panel.parquet", index=False)
    forward_returns.to_parquet(output_dir / "forward_returns.parquet", index=False)

    with (output_dir / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)

    readme = "\n".join(
        [
            f"# Dataset {config.dataset_id}",
            "",
            f"- experiment_id: {config.experiment_id}",
            f"- source: {config.source}",
            f"- source_path: {config.source_path}",
            f"- source_universe_key: {config.source_universe_key}",
            f"- date_range: {config.date_start} to {config.date_end}",
            f"- adjustment: {config.adjustment}",
            f"- forward_return_definition: {config.forward_return_definition}",
        ]
    )
    (output_dir / "README.md").write_text(readme + "\n", encoding="utf-8")
    return PreparedDataset(panel=panel, forward_returns=forward_returns, manifest=manifest)
