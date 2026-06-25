# 主板 Mining v1 Source Pipeline Review

日期：2026-06-25

## 📌 本轮结论

- 真实 `source_universe_key` 已确认，键名是 `univ_trade_mainboard`。
- zer0share 主板 universe 已补齐到本轮正式协议所需历史窗口，真实分区覆盖为 `2013-01-04` 到 `2026-05-29`，分区数 `3252`。
- 这与协议声明的 `warmup_start = 2013-01-01`、正式评分窗口 `2014-01-01` 到 `2026-05-31` 是兼容的；差异仅来自交易日历，首尾非交易日不会阻塞正式使用。
- 区块2已基于这份真实主板 universe 成功重跑 `mainboard_mining_v1`，产出正式 dataset，当前 `panel` 行数为 `11001516`。
- 样本协议 `mining_v1_mainboard_walkforward` 已成功从 dataset 生成稳定切片，`sample_protocol_hash` 为 `sha256:d2026a033c3ca760addc4e9224488f89c3cfb6bad87e5d7e73f357ad05768eac`。
- data quality 当前结果为 `warning`，不是 `fail`。唯一保留项是 warmup 早期主板股票池数量偏低，这与上游股票池包含上市满一定天数等过滤有关，属于预热期可解释现象，不阻塞正式评分窗口使用。

## 🧩 本轮实际运行

### 1. zer0share 历史补数

已补齐并覆盖以下关键日表到 `2013-01-01` 到 `2026-05-31`：

- `daily_kline`
- `adj_factor`
- `daily_basic`
- `stock_st`
- `suspend_d`
- `stk_limit`

其中 `index_weight` 曾遇到频率限制，但不影响本轮主板正式 dataset prepare 所需主链路。

### 2. zer0share 主板 universe 重建

运行区间：

```text
2013-01-01 ~ 2026-05-31
```

结果摘要：

```text
range: 2013-01-01 ~ 2026-05-31, trading_days: 3252, built: 2747, skipped: 505
univ_trade_mainboard: 6367642
```

真实输出目录：

```text
C:\Users\hp\Documents\zer0share\data\stock\universe\name=univ_trade_mainboard
```

真实覆盖：

- first partition：`20130104`
- last partition：`20260529`
- partition count：`3252`

### 3. 区块2正式 dataset prepare

真实输出目录：

```text
C:\Users\hp\Documents\factor_autoresearch\.worktrees\block2_a_line\datasets\mainboard_mining_v1
```

prepare 输出摘要：

```json
{"dataset_id":"mainboard_mining_v1","output":"datasets\\mainboard_mining_v1","rows":11001516}
```

manifest 已记录：

- `source_universe_key = univ_trade_mainboard`
- `date_start = 2014-01-01`
- `date_end = 2026-05-31`
- `warmup_start = 2013-01-01`
- `sample_protocol_id = mining_v1_mainboard_walkforward`
- `sample_protocol_hash = sha256:d2026a033c3ca760addc4e9224488f89c3cfb6bad87e5d7e73f357ad05768eac`
- `data_quality_report` 路径信息

### 4. data quality 结果

当前结果：

```text
overall_outcome = warning
```

当前 warning 项：

- `daily_universe_counts`
- 含义：warmup 早期若干交易日主板可交易样本数量低于中位数阈值
- 判断：这是预热期现象，不是正式评分窗口数据断裂，也不是主板 universe 缺失

当前没有 `fail` 项。

### 5. walk-forward 切片结果

当前协议输出：

- 6 组 walk-forward `formation + embargo + test`
- 1 个 `final_oos`

最终样本外（final OOS）真实交易日切片：

- declared：`2026-01-01` 到 `2026-05-31`
- realized：`2026-01-05` 到 `2026-05-29`

这同样是交易日历对齐结果，不构成 blocker。

## ✅ 当前已确认事项

- 正式主板 universe key：`univ_trade_mainboard`
- 上游历史覆盖已经满足区块2第一版正式挖因子所需总窗口
- prepare 主链路可真实跑通
- sample protocol 可真实落到 dataset 上
- data quality 已从 `fail` 修正到 `warning`

## ⚠️ 当前仍保留的注意项

1. warmup 期主板股票池数量偏低会继续在 quality report 中留下 warning。
2. 这个 warning 不应用于否定正式评分窗口本身，但后续汇报时应明确说明“预热期不参加评分”。
3. 如果后续把 quality 规则继续产品化，建议把 warmup 区和正式评分区分开统计，避免把预热期 warning 和正式期质量混在一起。

## 📊 当前 review 状态

```text
reviewed_with_warning_not_blocking
```

状态解释：

- 主板正式协议、上游真实覆盖、prepare 产出、切片生成都已经闭环。
- 当前保留项是 warning，不是 fail，也不是 blocker。
- 因此，区块2已经完成“第一版正式挖因子主板数据准备”的主链路打通；后续若继续优化，重点在 quality 报告口径细化，而不是再补主数据。