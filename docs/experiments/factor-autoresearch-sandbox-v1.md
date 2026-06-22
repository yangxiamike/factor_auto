# CSI500 OHLCV Sandbox v1 实验规格

## 1. 定位

本文件是第一轮 baseline sandbox experiment spec。

它依赖框架合同：

```text
docs/framework/factor-autoresearch-framework-v1.md
```

framework spec 定义 Codex 和 Python tools 的职责边界。本文件只定义这次实验的具体环境：

- 使用什么 universe。
- 使用什么数据和 forward return。
- 允许什么 DSL 搜索空间。
- category 如何分类。
- 指标和 candidate gate 如何评分。
- 第一轮 Agent loop 的具体限制。

## 2. 实验目标

搭建第一个真实可跑、可复现的 A 股日频因子研究实验室。

v1 目标不是挖出最强因子，而是验证：

```text
Codex 追加候选 DSL
-> Python tools 静态 validate
-> Python tools 固定评价
-> run artifacts 落盘
-> pass 因子进入 candidate registry
-> Codex 写 research notes
-> 多轮后蒸馏 memory
```

## 3. 实验边界

v1 固定做：

- universe：CSI 500 / 中证 500 方向股票池。
- 日期：`2024-01-01` 到 `2025-12-31`。
- 数据频率：日频。
- 特征：后复权 OHLCV。
- forward return：1d、3d、5d。
- 评价预处理：行业中性化、市值中性化、winsorize、zscore。
- 候选来源：Codex 手写 DSL 表达式。
- 每轮候选数量：30。
- registry：只写通过 candidate gate 的候选。

v1 不做：

- 全 A 股票池。
- OOS、walk-forward 或 train/test split。
- 交易成本建模。
- 与 registry 已有因子的相关性检查。
- 财务、分钟级或盘口特征。
- 将行业或市值作为 DSL 可搜索特征；它们只作为评价预处理暴露。
- 自动模板搜索。
- 自动表达式树搜索。
- official factor 晋升。

## 4. 数据集

固定数据集存放在：

```text
datasets/sandbox_v1/
```

该数据集由维护者通过 `fm dataset prepare-fixed` 从本地 zer0share 生成。候选因子评价阶段只能读取该固定数据集，不能直接查询 zer0share。

### 4.1 Universe

实验 universe 使用 CSI 500 / 中证 500 方向股票池。

配置中使用逻辑名称：

```text
universe = "csi500"
```

manifest 必须记录实际 zer0share universe key。如果底层数据源的 key 不是 `csi500`，则由配置文件做映射，但实验文档仍以 `csi500` 作为 profile 名称。

基础过滤原则：

- CSI 方向股票池筛选，以及 ST、退市整理、停牌、低流动性、低成交量、涨停、跌停等基础过滤由 zer0share 的受控数据生成流程处理。
- 评价阶段不重复做动态 universe 过滤，也不根据候选因子值临时修改 universe。
- 评价阶段只使用 `in_universe == true` 的样本。
- universe membership 可以随日期变化，但必须由固定数据集显式给出。
- manifest 必须记录 zer0share 的 source universe key 和已继承的基础过滤口径，便于和 zer0share 对齐。

### 4.2 日期范围

```text
date_start = "2024-01-01"
date_end = "2025-12-31"
```

本实验将两年数据作为一个整体评价区间，不做 OOS split。summary 可以输出年份或月份观察，但不用于 candidate gate。

### 4.3 `panel.parquet`

必需字段：

```text
trade_date
ts_code
in_universe
industry
market_cap
open_hfq
high_hfq
low_hfq
close_hfq
volume
```

字段规则：

- `trade_date` 是交易日。
- `ts_code` 是证券代码。
- `in_universe` 是固定数据集给出的 membership。
- `industry` 是评价预处理使用的行业分组暴露，不进入 DSL 搜索字段。
- `market_cap` 是评价预处理使用的市值暴露，不进入 DSL 搜索字段。
- OHLC 全部为后复权价格。
- `volume` 使用 zer0share 日频行情中的原始成交量字段。
- 主键 `(trade_date, ts_code)` 必须唯一。
- 推荐排序为 `(trade_date, ts_code)`。

### 4.4 `forward_returns.parquet`

必需字段：

```text
trade_date
ts_code
fwd_ret_1d
fwd_ret_3d
fwd_ret_5d
```

forward return 定义：

```text
fwd_ret_h = open_hfq[t + h + 1] / open_hfq[t + 1] - 1
```

含义：

- day `t` 收盘后得到信号。
- 下一交易日后复权开盘价进场。
- 持有 `h` 个交易日后，用后复权开盘价退出。

如果进场或退出开盘价缺失，该样本的 forward return 记为缺失，不做填充。

### 4.5 `manifest.json`

示例：

```json
{
  "dataset_id": "sandbox_v1",
  "experiment_id": "csi500_ohlcv_sandbox_v1",
  "created_at": "2026-06-22",
  "source": "zer0share",
  "source_path": "/Users/ml/Documents/agent-factor/packages/zer0share",
  "universe": "csi500",
  "source_universe_key": "csi500",
  "date_start": "2024-01-01",
  "date_end": "2025-12-31",
  "adjustment": "hfq",
  "features": ["open_hfq", "high_hfq", "low_hfq", "close_hfq", "volume"],
  "preprocess_exposures": ["industry", "market_cap"],
  "base_filters_inherited": ["csi_membership", "st", "delisting", "suspension", "low_liquidity", "low_volume", "limit_up", "limit_down"],
  "forward_returns": ["1d", "3d", "5d"],
  "forward_return_definition": "next_open_to_open_v1"
}
```

## 5. 数据预处理和数值规则

### 5.1 原始数据

v1 对候选因子值做固定评价预处理，但不修改固定 dataset 和 forward return。

默认处理顺序：

```text
raw factor values
-> winsorize
-> zscore
-> industry + size neutralization
-> metric calculation
```

规则：

- winsorize 和 zscore 是评价阶段默认处理，不要求候选表达式显式写出。
- 行业和市值中性化在 winsorize 和 zscore 之后执行，只在每个 `trade_date` 的 `in_universe == true` 样本内做。
- 行业和市值必须在同一个横截面模型中同时中性化，不做先行业、后市值的串行残差处理。
- 默认中性化定义为每日横截面 OLS：`factor_z ~ industry dummies + log(market_cap)`，评价使用该回归残差。
- 行业暴露使用固定 dataset 中的 `industry` 字段。
- 市值暴露使用固定 dataset 中的 `market_cap` 字段；`market_cap <= 0` 时该样本按市值暴露缺失处理。
- 缺失值不填充；原始字段、因子值、行业、市值或 forward return 缺失时，该样本按缺失处理。
- 评价阶段不做额外动态 universe 过滤；CSI、ST、退市整理、停牌、低流动性、低成交量、涨停、跌停等基础过滤应由 zer0share 数据生成阶段完成并写入 `in_universe` / manifest。

### 5.2 表达式计算

数值规则：

- 除零产生缺失值。
- `log(x)` 中 `x <= 0` 产生缺失值。
- `inf` 和 `-inf` 统一转为缺失值。
- 时间序列函数按 `ts_code` 分组、按 `trade_date` 排序计算。
- 横截面函数按 `trade_date` 在 `in_universe == true` 样本内计算。

`cs_rank`、`cs_zscore` 等研究表达式变换必须由表达式显式写出。评价阶段仍会在原始表达式输出后统一执行 5.1 的默认 winsorize、zscore 和中性化。

### 5.3 中性化位置

v1 启用行业和市值中性化。中性化放在：

```text
raw factor values
-> winsorize
-> zscore
-> industry + size neutralization
-> metric calculation
```

它不应该修改固定 dataset，也不应该修改 forward return 定义。中性化、winsorize、zscore 的配置和参数必须写入 run manifest，保证同一 dataset、candidate JSONL、config 和 tool version 重复运行时可复现。

## 6. 候选因子格式

候选因子存放在：

```text
candidate_factors/candidates.jsonl
```

每行一个 JSON 对象。

示例：

```json
{
  "id": "fa_0001_range_position",
  "name": "range position",
  "expression": "cs_rank((close_hfq - low_hfq) / (high_hfq - low_hfq))",
  "expected_direction": "positive",
  "hypothesis": "收盘价越接近日内高点，可能代表更强的日内需求。",
  "category": "intraday",
  "lookback_days": 1,
  "created_at": "2026-06-22",
  "notes": "csi500_ohlcv_sandbox_v1 baseline candidate"
}
```

### 6.1 `expected_direction`

`expected_direction` 是 Codex 写候选时给出的研究先验：

- `positive`：表达式值越高，预期未来收益越高。
- `negative`：表达式值越高，预期未来收益越低。

v1 不通过写 `-(expression)` 来表达反向假设。如果结果显示方向相反，该候选大概率 gate failed；Codex 可以在下一轮追加同一想法但 `expected_direction` 相反的新候选。

### 6.2 `category`

`category` 是受控枚举。v1 只允许：

```text
momentum
reversal
volatility
liquidity
volume
intraday
gap
```

分类含义：

- `momentum`：短窗口价格趋势、收益延续。
- `reversal`：短期过度上涨或下跌后的反转。
- `volatility`：振幅、波动扩张或收缩、range 结构。
- `liquidity`：成交活跃度、流动性 proxy。
- `volume`：成交量变化、放量或缩量。
- `intraday`：日内位置，例如 close 在 high-low 或 open-close 区间中的相对位置。
- `gap`：开盘相对上一交易日价格的跳空结构。

不设置 `other`。如果候选无法归类，说明需要人类协商是否扩展 category。

## 7. 搜索空间

### 7.1 允许字段

v1 只允许：

```text
open_hfq
high_hfq
low_hfq
close_hfq
volume
```

### 7.2 允许表达的基础概念

表达式 DSL 应能覆盖：

```text
intraday_return = close_hfq / open_hfq - 1
range_position = (close_hfq - low_hfq) / (high_hfq - low_hfq)
daily_range = high_hfq / low_hfq - 1
short_window_return = close_hfq / delay(close_hfq, n) - 1
volume_change = volume / delay(volume, n) - 1
```

评价器不要求候选直接使用这些名称，它们只是说明 v1 预期覆盖的表达式家族。

### 7.3 允许运算和函数

允许的算术运算：

```text
+ - * / unary -
```

允许的函数：

```text
abs(x)
log(x)
delay(x, n)
ts_mean(x, n)
ts_std(x, n)
ts_delta(x, n)
ts_return(x, n)
ts_rank(x, n)
cs_rank(x)
cs_zscore(x)
```

允许窗口参数：

```text
1, 3, 5, 10, 20
```

允许简单数字常量，但不鼓励通过大量 magic constants 调参。complexity score 必须计入常量节点。

### 7.4 搜索深度

v1 允许：

- 单字段派生。
- 时间序列窗口变换。
- 横截面 rank / zscore。
- 两个基础信号的简单组合。
- 有限嵌套表达式。

v1 不做：

- 自动表达式树搜索。
- 大规模参数网格搜索。
- 人工阈值规则搜索。
- 三个以上基础信号的复杂组合。

complexity 上限由 gate 指定。

## 8. Validate

`fm factor validate` 检查：

- JSONL 能否解析。
- 必需字段是否存在。
- candidate id 是否唯一。
- `expected_direction` 是否为 `positive` 或 `negative`。
- `category` 是否在 v1 枚举中。
- 表达式能否解析。
- 字段和函数是否在白名单中。
- 窗口参数是否在白名单中。
- 声明或推断 lookback 是否在限制内。
- complexity 是否在限制内。

validate 不读取真实因子值，不计算 coverage、IC、RankIC 或 scoring。

## 9. Metrics

对每个候选因子和每个 horizon，v1 计算：

```text
IC
RankIC
ICIR
coverage
quantile_returns
long_short_return
monotonicity
complexity_score
```

定义：

- `IC`：每日横截面 Pearson 相关，之后对有效日期求均值。
- `RankIC`：每日横截面 Spearman 相关，之后对有效日期求均值。
- `ICIR`：IC 时间序列均值除以标准差，用作观察指标，不直接进入 v1 score。
- `coverage`：有效因子值数量除以可评价 universe 样本数量。
- `quantile_returns`：按因子值分 5 层后的各层平均 forward return。
- `long_short_return`：最高分位收益减最低分位收益。
- `monotonicity`：分层序号与分层平均 forward return 的 Spearman 相关。
- `complexity_score`：基于表达式树大小、窗口使用和常量节点的确定性复杂度分数。

每个交易日必须有足够横截面样本才计算当日 IC / RankIC。v1 建议最小有效样本数为 100。

## 10. Candidate Gate

candidate gate 用于判断候选是否进入 `candidate_factors/registry.jsonl`。

硬性条件：

```text
validate passed
coverage_mean >= 0.70
effective_trade_days >= 60
complexity_score <= 12
best_horizon_score >= 1.0
```

directional 指标按 `expected_direction` 调整：

```text
direction_sign = 1 if expected_direction == "positive" else -1
directional_ic_mean_h = direction_sign * ic_mean_h
directional_rankic_mean_h = direction_sign * rankic_mean_h
directional_monotonicity_h = direction_sign * monotonicity_h
```

每个 horizon 的分数：

```text
ic_component_h = clamp(directional_ic_mean_h / 0.01, 0, 2)
rankic_component_h = clamp(directional_rankic_mean_h / 0.01, 0, 2)
monotonicity_component_h = clamp(directional_monotonicity_h, 0, 1)

horizon_score_h =
  0.30 * ic_component_h
+ 0.40 * rankic_component_h
+ 0.30 * monotonicity_component_h
```

`best_horizon_score` 是 1d、3d、5d 中最大的 `horizon_score_h`。

v1 的 score 故意偏简单。它的作用是筛出值得继续研究的 candidate，不是 production official gate。

## 11. Failure Bucket

本实验只使用三个 failure bucket：

```text
validate_failed
gate_failed
runtime_error
```

具体原因写入 `details`。例如：

```json
{
  "id": "fa_0031_volume_surge",
  "status": "candidate_fail",
  "failure_bucket": "gate_failed",
  "details": {
    "coverage_mean": 0.83,
    "best_horizon": "5d",
    "best_horizon_score": 0.62,
    "ic_component": 0.31,
    "rankic_component": 0.78,
    "monotonicity_component": 0.42
  }
}
```

## 12. Run 输出

每次 evaluate 写出：

```text
runs/{run_id}/
  manifest.json
  summary.md
  factors/
    {factor_id}.parquet
  results/
    candidate_results.jsonl
    metrics.parquet
    ic_series.parquet
  logs/
    evaluate.log
```

`summary.md` 格式：

```md
# Run smoke_001 Summary

## Dataset
dataset_id:
experiment_id:
universe:
date_range:
features:
adjustment:
forward_return_definition:

## Batch Result
evaluated:
passed:
failed:
invalid:
errors:

## Candidate Results
| id | status | best_horizon | score | ic | rankic | monotonicity | coverage | complexity | failure_bucket | details |

## Failed / Invalid
| id | failure_bucket | details |

## Notes
- ...
```

## 13. Candidate Registry

通过 candidate gate 的候选追加写入：

```text
candidate_factors/registry.jsonl
```

失败、无效或运行错误的候选不写 registry，只保存在 run artifacts。

registry 示例：

```json
{
  "factor_id": "fa_0001_range_position",
  "name": "range position",
  "category": "intraday",
  "expression_hash": "sha256:...",
  "expected_direction": "positive",
  "signal_direction": "positive",
  "dataset_id": "sandbox_v1",
  "experiment_id": "csi500_ohlcv_sandbox_v1",
  "run_id": "smoke_001",
  "status": "candidate_pass",
  "best_horizon": "5d",
  "best_horizon_score": 1.2,
  "metrics": {
    "ic_mean_5d": 0.011,
    "rankic_mean_5d": 0.013,
    "monotonicity_5d": 0.67,
    "coverage_mean": 0.91,
    "complexity_score": 7
  },
  "gate": {
    "version": "candidate_gate_v1",
    "passed": true,
    "failed_rules": []
  },
  "artifacts": {
    "summary": "runs/smoke_001/summary.md",
    "factor_values": "runs/smoke_001/factors/fa_0001_range_position.parquet"
  }
}
```

## 14. Agent Loop

后续应单独沉淀 sandbox v1 runbook，用于描述每轮实验如何从 memory / research notes 出发、追加候选、运行 validate/evaluate、读取 summary 并更新 notes。runbook 应作为执行计划的一部分加入目录结构；本 spec 只记录该需求，不在当前版本创建或要求读取该文件。

本实验的 Codex loop：

1. 阅读当前轮任务说明、`memory.md` 和 `research_notes.md`。
2. 在 `candidate_factors/candidates.jsonl` 末尾追加 30 个候选。
3. 每个候选必须包含 `expected_direction` 和受控 `category`。
4. 运行 `fm factor validate`。
5. 运行 `fm factor evaluate`。
6. 阅读 `runs/{run_id}/summary.md`。
7. 将本轮观察写入 `research_notes.md`。
8. 只有多轮稳定 insight 才更新 `memory.md`。

Codex 不能：

- 修改既有候选记录。
- 删除候选记录。
- 修改 dataset、config、gate 或 evaluator。
- 直接访问 zer0share。
- 写入 registry。
- 写入 official factors。

## 15. Research Notes 和 Memory

`research_notes.md` 记录当前实验细节：

- 当前 batch intent。
- 候选生成思路。
- run 观察。
- failed ideas。
- next batch plan。

`memory.md` 只记录多轮稳定的长期 insight：

- recommended directions。
- forbidden directions。
- strategic insights。
- transform hints。
- open questions。

memory 不因为单个候选 pass 或 fail 就更新。

## 16. 验收标准

v1 experiment 验收通过条件：

1. 可以生成固定 `datasets/sandbox_v1`。
2. dataset 覆盖 CSI 500 / 中证 500 方向股票池，日期范围为 2024-01-01 到 2025-12-31。
3. dataset 包含后复权 OHLCV、universe membership、评价预处理暴露 `industry` / `market_cap`，以及 1d/3d/5d forward returns。
4. 评价阶段不直接访问 zer0share。
5. Codex 只能追加 `candidates.jsonl`，并维护 `research_notes.md` 和 `memory.md`。
6. 系统可以校验并评价每轮 30 个手写 DSL 候选。
7. 每个候选在 run result 中得到 `candidate_pass`、`candidate_fail`、`invalid` 或 `error`。
8. 每个失败或无效候选都有 `failure_bucket` 和 `details`。
9. 每次 run 的输出都写入 `runs/{run_id}/`。
10. 通过 gate 的候选追加写入 `candidate_factors/registry.jsonl`。
11. 未通过 gate 的候选不写入 registry。
12. `official_factors/` 除文档外保持不变。
13. 同一个 dataset、candidate JSONL、config 和 tool version 重复运行，应产生相同指标和 summary。

## 17. 后续实验扩展

v1.5 / v2 可以考虑：

- 加入 OOS 或 walk-forward。
- 加入 amount、turnover、市值、行业或财务特征。
- 加入 registry 相关性检查。
- 加入更严格的稳定性指标。
- 加入交易成本和换手 proxy。
- 加入 official factor 晋升流程。
- 在手写 DSL 闭环稳定后，再加入模板搜索或自动候选生成。
