# Compute Engine v1 护栏计划

## 📌 结论

当前每轮 20-30 个 candidates 的规模下，不继续做性能大改。

这一阶段只补三类护栏：

- benchmark regression：看性能口径有没有明显退化
- diagnostics equivalence：看诊断表口径有没有跑偏
- OOS / walk-forward runtime estimate：先把未来成本算清楚

## 🧩 边界

这次明确不做：

- 不引入 Polars / DuckDB 作为新计算主路径
- 不新增 engine
- 不修改 IC / RankIC / gate / DSL / forward return / universe 语义
- 不把 OOS / walk-forward 混入 `compute_v1` 核心执行链路

目标不是重写引擎，而是先把护栏补齐。

## 📊 当前基线

当前基线按既有 benchmark 口径记录：

- `baseline_seconds`: `54.654126`
- `baseline_trade_days`: `485`
- `baseline_candidates`: `30`
- `projected 10y x 30 candidates`: `283.976077` 秒
- `classification`: `strong_green`

这说明在当前目标规模下，主链路还没有进入必须重构的区间。

## 🔧 后续策略

OOS 和 walk-forward 放在 `evaluate` 外层处理。

推荐结构：

```text
factor values
 -> full sample metrics/gate
 -> OOS metrics/gate
 -> walk-forward slice metrics/gate
```

执行原则：

- 尽量复用已算出的 factor values
- 只对 slice 级 metrics 和 gate 单独计算
- 不把样本外验证逻辑塞回 `compute_v1` 核心模块

## ⚠️ 复杂度红线

如果某个方案需要下面任意一项，就先视为过度复杂，暂时不做：

- 新增一套 engine
- 修改 candidate DSL
- 修改指标定义
- 让普通 `evaluate` 命令增加大量参数
- 让 summary 结果变得难扫读、难判断

## 👀 执行判断

后续如果只是：

- 补 benchmark 回归测试
- 补 diagnostics 等价测试
- 补 runtime 估算与说明文档

那就继续小步推进。

后续如果开始出现：

- benchmark 长期进入 `yellow` / `red`
- OOS / walk-forward 明显放大成本
- 诊断表口径经常偏移

再单独立项讨论是否需要更大级别的性能改造。
