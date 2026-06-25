# 主板压力测试结果 v1

## 结论

本轮 `compute_engine_v1` 在 CPU-only、`v1 + jobs=auto` 下，主板规模压力测试达到当前 5 分钟目标。

- 测试口径：沪深主板派生 universe，剔除口径来自 `univ_trade_base` + `prepare.include_markets = ["主板"]`
- 数据窗口：2024-01-01 到 2025-12-31，共 485 个交易日
- 样本规模：1,543,755 panel rows，日均 universe 约 2,878 只股票
- 候选数量：30 个 candidates
- 实测总耗时：54.654126 秒
- 10 年 x 30 candidates 外推：283.976079 秒，约 4.73 分钟
- 目标线：300 秒，约 5 分钟
- 分类：strong_green
- 是否触发下一轮优化：false

## 分段耗时

- calculate_seconds: 2.938471
- preprocess_seconds: 19.519223
- metrics_seconds: 21.708060
- artifact_seconds: 6.488580
- top_bottleneck_stage: metrics_seconds

## 判断规则

本轮 benchmark 报告使用 252 个交易日/年做线性外推，并以 `10年 x 30 candidates` 作为 CPU-only 目标验收口径。

- strong_green: <= 300 秒
- green: <= 600 秒
- yellow: <= 1200 秒
- red: > 1200 秒

当前结果为 `strong_green`，所以本轮不继续触发优化 loop。后续如果主板样本扩大、候选表达式复杂度明显上升，优先 profiling `metrics_seconds` 和 `preprocess_seconds`。