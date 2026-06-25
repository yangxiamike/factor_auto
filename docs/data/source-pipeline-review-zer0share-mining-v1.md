# zer0share Mining v1 Source Pipeline Review

日期：2026-06-24

## 📌 结论

这次核查可以先得出 4 个可落地结论：

- ✅ `sandbox_v1` 明确继承了 zer0share 的日频 A 股数据口径，至少包括：SSE 交易日历、`univ_trade_zz500` 股票池成员、`daily_kline`、`daily_basic`、`adj_factor`，以及一套在 zer0share `universe.py` 中实现的基础过滤。
- ✅ `factor_autoresearch/prepare.py` 目前仍保留了“研究样本拼装”职责，而不是纯透传上游产物。它在本仓内继续负责构造日期-股票网格、合并 `in_universe`、生成后复权 OHLC、生成 `forward_returns`、写出 dataset manifest。
- ✅ 上游 `univ_trade_zz500` 的生成口径已有比较强的证据链：它来自 `univ_trade_base` 与中证 500 指数成分的交集，而 `univ_trade_base` 继承了 ST、停牌、一字涨跌停、流动性、市值等过滤。
- ⚠️ PIT（point-in-time，当时可见）仍有几处需要单独补证，重点在行业表是否存在回补，以及 `daily_basic.total_mv` / `adj_factor` 是否会被供应商事后修订。

## 🧩 本次核查范围

按任务限制，本次只读检查了以下内容：

- `factor_autoresearch/prepare.py`
- `docs/framework/factor-autoresearch-data-sample-protocol-v1-spec.md`
- `docs/experiments/factor-autoresearch-sandbox-v1.md`
- `C:/Users/hp/Documents/zer0share` 下与 `trade_cal` / `universe` / `daily_kline` / `daily_basic` / `adj_factor` / `industry` 相关的实际路径
- 为了确认上游股票池口径，补看了：
  - `C:/Users/hp/Documents/zer0share/zer0share/universe.py`
  - `C:/Users/hp/Documents/zer0share/tests/test_universe.py`
  - `C:/Users/hp/Documents/zer0share/zer0share/query/industry.py`
  - `C:/Users/hp/Documents/zer0share/zer0share/sync/industry.py`

本文件不复制上游实现代码，只记录可审计的口径结论、证据路径和待补风险。

## 📊 已查证的上游路径与字段

### 1. 交易日历

- 路径模式：`C:/Users/hp/Documents/zer0share/data/stock/trade_cal/exchange=*/data.parquet`
- `prepare.py` 当前只取 `exchange = 'SSE'` 且 `is_open = true`
- 抽样字段：`exchange`, `cal_date`, `is_open`, `pretrade_date`

结论：

- `sandbox_v1` 的交易日期边界不是本仓自己生成，而是继承 zer0share 的 SSE 开市日历。

### 2. 股票池成员

- 路径模式：`C:/Users/hp/Documents/zer0share/data/stock/universe/name=univ_trade_zz500/date=*/data.parquet`
- 抽样字段：`trade_date`, `universe`, `ts_code`, `date`, `name`
- `prepare.py` 通过 `config.source_universe_key` 读取 `name={source_universe_key}` 分区

结论：

- `sandbox_v1` 文档中的业务名是 `csi500`，但真正落地到上游的是 `source_universe_key`，当前实机存在的中证 500 路径是 `univ_trade_zz500`。

### 3. 日频行情

- 路径模式：`C:/Users/hp/Documents/zer0share/data/stock/daily_kline/date=*/data.parquet`
- 抽样字段：`ts_code`, `trade_date`, `open`, `high`, `low`, `close`, `pre_close`, `change`, `pct_chg`, `vol`, `amount`, `date`

结论：

- `prepare.py` 当前只消费其中 `open`, `high`, `low`, `close`, `vol`，并未直接使用 `amount`、`pre_close` 等字段。

### 4. 日频基础指标

- 路径模式：`C:/Users/hp/Documents/zer0share/data/stock/daily_basic/date=*/data.parquet`
- 抽样字段包含：`ts_code`, `trade_date`, `total_mv`, `circ_mv`, `limit_status` 等

结论：

- `prepare.py` 当前只消费 `total_mv`，并在本仓内重命名为 `market_cap`。

### 5. 复权因子

- 路径模式：`C:/Users/hp/Documents/zer0share/data/stock/adj_factor/date=*/data.parquet`
- 抽样字段：`ts_code`, `trade_date`, `adj_factor`, `date`

结论：

- `prepare.py` 在本仓内用 `raw_price * adj_factor` 生成 `open_hfq/high_hfq/low_hfq/close_hfq`。
- 也就是说，后复权价格不是直接从 zer0share 读取成品列，而是在本仓拼出来的。

### 6. 行业归属

- 实机存在路径：`C:/Users/hp/Documents/zer0share/data/stock/industry/sw_member/data.parquet`
- 实机不存在路径：`C:/Users/hp/Documents/zer0share/data/stock/industry/ci_member/data.parquet`
- `sw_member` 抽样字段：`l1_code`, `l1_name`, `l2_code`, `l2_name`, `l3_code`, `l3_name`, `ts_code`, `name`, `in_date`, `out_date`, `is_new`

结论：

- `prepare.py` 支持按 `industry_source` 在 `sw_member` / `ci_member` 二选一。
- 但在当前机器上，至少本次核查时只看到了 `sw_member` 成品数据，没有看到 `ci_member` 成品数据。
- 当前 `configs/csi500_ohlcv_sandbox_v1.toml` 已明确 `industry_source = "sw_l1_name"`，所以当前 `sandbox_v1` 实际走的是 SW 一级行业口径。
- `prepare.py` 的 CI 分支仍然保留，但在本机这份 `sandbox_v1` 配置上没有被启用。

## 🧩 sandbox_v1 继承了哪些 zer0share 口径

### 1. 股票池不是本仓计算的

zer0share `universe.py` 已明确：

- `univ_trade_zz500` 对应指数代码 `000905.SH`
- 它不是直接“指数成分表原样落地”
- 它是 `in_trade_base` 与该指数截至当日可见的最新成分交集

可审计证据路径：

- `C:/Users/hp/Documents/zer0share/zer0share/universe.py`
- `C:/Users/hp/Documents/zer0share/tests/test_universe.py`

### 2. 继承的基础过滤已能确认一大半

根据 `zer0share/universe.py`，`in_trade_base` 至少继承了这些条件：

- ✅ A 股普通股过滤：剔除 B 股、CDR 等
- ✅ 已上市
- ✅ 未退市
- ✅ 上市满 183 天
- ✅ 非 ST
- ✅ 20 日平均成交额达到阈值
- ✅ 通过 research base 市值底部过滤
- ✅ 非停牌
- ✅ 非一字涨停
- ✅ 非一字跌停
- ✅ 通过 trade base 市值底部过滤

说明：

- 文档里写的 `base_filters_inherited` 基本方向是对的。
- 但当前 manifest 里的名字还是“概念级标签”，不是“已审计字段级口径”。
- 例如 `low_liquidity`、`low_volume`、`limit_up`、`limit_down` 在 manifest 里是抽象名；真正实现里至少可以进一步细化成：
  - `avg_amount_20d >= 10000`
  - `not_bottom_market_cap(research_base, 2%)`
  - `not_bottom_market_cap(trade_base, 5%)`
  - `not one-price up/down limit`

### 3. `sandbox_v1` 继承的是“上游过滤结果”，不是“本仓重新过滤”

`docs/experiments/factor-autoresearch-sandbox-v1.md` 与 `docs/framework/factor-autoresearch-data-sample-protocol-v1-spec.md` 都要求：

- 评估阶段不重新做动态 universe 过滤
- 基础过滤应由 zer0share 完成
- 本仓只消费 `in_universe` 和 manifest 声明

这点和当前 `prepare.py` 的行为一致：

- 它只把 universe membership 读进来并转成布尔列
- 没有在本仓再跑 ST、停牌、流动性、涨跌停等规则

## 🔧 `prepare.py` 里仍保留的本仓逻辑

以下逻辑当前明确还在 `factor_autoresearch/prepare.py`，不是 zer0share 直接产出的冻结成品：

### 1. 交易网格构造

- 先读取整个日期区间的 SSE 开市日
- 再拿 universe 内出现过的全部 `ts_code`
- 做笛卡尔积，生成完整 `(trade_date, ts_code)` 网格

这意味着：

- panel 里会出现“不在当日 universe，但仍保留一行”的样本
- 是否评估，只靠 `in_universe` 控制

### 2. `in_universe` 布尔落盘

- 上游 universe 分区是“当日成员行”
- 本仓把它转成完整面板上的 `True/False`

### 3. 多表拼接

- 把 `daily_kline`、`daily_basic`、`adj_factor` 拼进 panel
- 把行业成员表按生效区间拼成单日行业暴露

### 4. 后复权 OHLC 生成

- `open_hfq/high_hfq/low_hfq/close_hfq` 是本仓根据原始 OHLC 与 `adj_factor` 计算出来的
- 这属于本仓派生口径，应在 manifest 里显式记录

### 5. forward return 生成

- `fwd_ret_1d/5d/20d` 仍在本仓本地计算
- 当前定义是 `next_open_to_open_v1`
- 公式含义与现有 spec 一致：信号在 `t` 日收盘后得到，`t+1` 开盘进场，`t+h+1` 开盘退出

### 6. 冻结产物与最小 manifest 写出

- `panel.parquet`
- `forward_returns.parquet`
- `manifest.json`
- `README.md`

## ✅ 已确认事项

以下内容，本次已经有足够证据支持：

- ✅ `sandbox_v1` 上游源头是 zer0share 本地数据目录，不是在线临时取数
- ✅ 交易日来自 `trade_cal/exchange=*`
- ✅ 股票池成员来自 `universe/name={source_universe_key}/date=*`
- ✅ 当前机器存在 `univ_trade_zz500` 实际路径
- ✅ 上游股票池并非裸指数成分，而是 trade base 与指数成分交集
- ✅ trade base 至少包含 ST、停牌、流动性、市值、一字涨跌停等过滤
- ✅ `daily_kline` / `daily_basic` / `adj_factor` / `sw_member` 实机路径存在且字段可读
- ✅ 本仓仍负责生成后复权 OHLC
- ✅ 本仓仍负责生成 `forward_returns`
- ✅ 本仓没有重做 ST、停牌、涨跌停等基础过滤

## ⚠️ PIT 风险与待确认项

### 1. 行业表 PIT 仍需上游补证

风险：

- 当前 `sandbox_v1` 已确认使用 `sw_l1_name`
- 但 `sw_member` 这张历史映射表是否存在回补，仍未拿到上游治理证明

待确认：

- `sw_member` 的历史回填策略
- `out_date` 更新是否严格代表当时可见状态

### 2. `daily_basic.total_mv` 的 PIT 性质未单独审计

已知：

- 本仓把 `total_mv` 直接当 `market_cap`

未证实：

- `total_mv` 是否是严格按当日口径冻结
- 供应商是否会对历史值做追溯修订

影响：

- 市值中性化可能出现轻微 hindsight bias（事后视角偏差）

### 3. `adj_factor` 的修订行为未单独审计

已知：

- 本仓后复权价格完全依赖 `adj_factor`

未证实：

- 上游 `adj_factor` 是否会在分红送转后回填全部历史
- 这种“后复权回填”是否被团队视为研究阶段可接受口径

影响：

- 如果目标是严格交易时点可见价格，后复权本身就不是 PIT 价格
- 如果目标是统一收益口径、便于因子研究，则可以接受，但必须在 manifest 中明确声明

### 4. 指数成分 PIT 仍建议补一层版本说明

已知：

- `univ_trade_zz500` 通过 `_latest_index_members(..., trade_date)` 取截至当日可见的最新指数成分

未证实：

- 上游 `index_weight` 分区是否会事后修正历史成分
- 当前没有在 dataset manifest 中记录股票池构建时所依赖的上游版本/快照说明

### 5. 本仓未记录“这次究竟走了哪条行业分支”

风险：

- 当前 manifest 只记了 `preprocess_exposures`
- 没记 `industry_source`、`industry_path`、`source_pipeline_review`

影响：

- 同样叫 `sandbox_v1`，未来可能出现“数据结构一样、行业口径不同”的不可见漂移

## 👀 对 manifest 的补充建议

建议把当前“最小 manifest”扩成“可审计 source pipeline manifest”。优先补这些字段：

### 1. source pipeline 基本身份

```json
{
  "source_pipeline": {
    "name": "zer0share_daily_equity_pipeline",
    "review_status": "reviewed_with_open_risks",
    "reviewed_at": "2026-06-24",
    "review_doc": "docs/data/source-pipeline-review-zer0share-mining-v1.md"
  }
}
```

### 2. 上游表级来源

```json
{
  "source_tables": {
    "trade_cal": {
      "path": "stock/trade_cal/exchange=*/data.parquet",
      "filter": "exchange='SSE' and is_open=true"
    },
    "universe": {
      "path": "stock/universe/name=univ_trade_zz500/date=*/data.parquet",
      "source_universe_key": "univ_trade_zz500"
    },
    "daily_kline": {
      "path": "stock/daily_kline/date=*/data.parquet",
      "columns": ["open", "high", "low", "close", "vol"]
    },
    "daily_basic": {
      "path": "stock/daily_basic/date=*/data.parquet",
      "columns": ["total_mv"]
    },
    "adj_factor": {
      "path": "stock/adj_factor/date=*/data.parquet",
      "columns": ["adj_factor"]
    },
    "industry": {
      "path": "stock/industry/sw_member/data.parquet",
      "industry_source": "sw_*"
    }
  }
}
```

### 3. 股票池构造口径

```json
{
  "source_universe_detail": {
    "business_universe": "csi500",
    "source_universe_key": "univ_trade_zz500",
    "build_module": "zer0share.universe.build_universes",
    "index_code": "000905.SH",
    "base_universe": "univ_trade_base"
  }
}
```

### 4. 已确认的继承过滤

建议不要只写抽象词，最好同时保留“实现级摘要”：

```json
{
  "base_filters_inherited_detail": {
    "confirmed": [
      "a_share_common_only",
      "listed",
      "not_delisted",
      "listing_age_ge_183d",
      "not_st",
      "avg_amount_20d_ge_10000",
      "not_bottom_market_cap_research_2pct",
      "not_suspended",
      "not_one_price_up_limit",
      "not_one_price_down_limit",
      "not_bottom_market_cap_trade_5pct"
    ],
    "pending_semantic_mapping": [
      "low_liquidity",
      "low_volume"
    ]
  }
}
```

### 5. 本仓派生逻辑

```json
{
  "local_prepare_logic": {
    "module": "factor_autoresearch.prepare",
    "responsibilities": [
      "build_date_code_grid",
      "materialize_in_universe_flag",
      "derive_hfq_ohlc_from_adj_factor",
      "derive_forward_returns_next_open_to_open_v1",
      "join_industry_effective_interval"
    ]
  }
}
```

### 6. PIT 声明与未决风险

```json
{
  "pit_review": {
    "confirmed_point_in_time": [
      "trade_cal_open_days",
      "universe_membership_partitioned_by_trade_date"
    ],
    "pending_confirmation": [
      "industry_snapshot_backfill_behavior",
      "daily_basic_total_mv_revision_behavior",
      "adj_factor_revision_behavior",
      "index_weight_revision_behavior"
    ]
  }
}
```

### 7. 版本追溯信息

如果能补，优先补这些：

- `source_commit`
- `source_file_hashes`
- `source_data_snapshot_date`
- `source_reviewed_paths`

如果暂时拿不到 commit，至少先把 `review_doc` 和 `source_tables` 写进去，不要只留一个 `source_path`。

## 🔧 对 `mining_v1` 的落地建议

`mining_v1` 比 `sandbox_v1` 更需要把 source boundary 说死，建议：

- ✅ 继续沿用 zer0share 股票池与日频数据源
- ✅ 继续由本仓生成 `forward_returns`
- ✅ 明确行业口径只能选一个，并固化进 manifest
- ✅ 在 manifest 中写明“后复权价格用于研究，不代表交易时点可见价格”
- ✅ 在 source pipeline review 通过前，不要把 `base_filters_inherited` 当成完全闭环的 PIT 证明

## 📌 建议的审计结论

可以把当前状态定义为：

- `sandbox_v1`：可用于开发和 smoke test，源头边界已基本清楚
- `mining_v1`：可以建立在同一上游源头上，但上线前至少还要补 3 个确认

待补 3 项：

1. `sw_member` 的历史回补行为是否可接受
2. `index_weight` 历史成分是否需要补版本追溯
3. `daily_basic.total_mv` 与 `adj_factor` 是否存在供应商事后修订

在这 3 项补完前，建议把 review 状态写为：

```text
reviewed_with_open_risks
```

而不是完全 `reviewed_closed`。
