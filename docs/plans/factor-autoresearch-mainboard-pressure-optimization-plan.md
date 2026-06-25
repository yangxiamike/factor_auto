# Factor Autoresearch Mainboard Pressure Optimization Plan

日期：2026-06-25

## 1. 这份 plan 解决什么问题

Compute Engine v1（计算引擎 v1）当前已经把 `csi500 / sandbox_v1 / 30 candidates` 的 warm run 压到 10 秒级。

最新本地实测：

```text
worktree: C:\Users\hp\Documents\factor_autoresearch\.worktrees\compute_engine_v1
dataset: datasets/sandbox_v1
universe: csi500
candidates: candidate_factors/candidates.jsonl
candidate_count: 30
engine: v1
jobs: 1

warmup evaluate batch: about 9.8s
warm evaluate batch: about 8.5s
```

这说明当前小样本 sandbox 上，v1 已经达到第一阶段性能目标。

下一步问题不再是“中证500两年能不能跑快”，而是：

- 未来真实使用的沪深主板 universe 下，当前 v1 到底需要多久。
- 推算到 8 到 10 年历史、20 到 30 个候选因子时，是否能支撑日常因子挖掘。
- 如果不达标，Agent 应如何基于 profiling（性能剖析）自主派生优化子计划并实施。

本 plan 是一个压力测试与优化闭环计划，不是重新设计 Compute Engine v1。

## 2. 当前边界

### 2.1 已经完成

- `PanelStore`（面板存储）：把长表数据转成 `date x asset` 矩阵。
- `V1FactorCalc`（v1 因子计算器）：在矩阵上计算候选表达式。
- `ExpressionCache` / `expression_dag`（表达式缓存 / 表达式图）：复用公共子表达式。
- `preprocess_factor_matrix`（矩阵化预处理）：执行 winsorize、zscore、中性化。
- `compute_candidate_metrics_from_matrix`（矩阵化指标）：计算 IC、RankIC、分层收益等。
- `metrics_kernels` / `metrics_kernels_numba`（指标内核）：提供 NumPy baseline 和 Numba 加速路径。
- `--engine legacy / v1` 路由。
- `--jobs` 并发接口。
- `compute_v1` 测试套件和 benchmark helper。

### 2.2 不在本 plan 中重做

- 不重做 `PanelStore`。
- 不重做 v1 engine routing。
- 不新开 `engine=v2`。
- 不引入 GPU。
- 不为了提速修改 candidate DSL。
- 不为了提速减少 metrics 输出字段。
- 不为了提速改变 gate、forward return、universe 或 OOS 语义。

## 3. 目标 workload

正式目标场景：

```text
universe: 沪深主板
exclude: 北交所 / 科创板 / 创业板
history: 8 到 10 年
candidates: 20 到 30 个
horizons: 1d / 5d / 20d
engine: v1
hardware: CPU-only
evaluation: full evaluation
```

这里的 full evaluation（完整评价）包括：

- candidate expression calculation（候选表达式计算）
- preprocess（预处理）
- IC / RankIC
- quantile returns（分层收益）
- long-short return（多空收益）
- monotonicity（单调性）
- diagnostics（诊断表）
- gate（候选验收）
- artifacts（运行产物）

## 4. 性能目标

主目标口径：

```text
沪深主板 x 10年 x 30 candidates x full evaluation x CPU-only
```

验收分档：

```text
strong green: <= 5分钟
green:        <= 10分钟
yellow:       10 到 20分钟
red:          > 20分钟
```

解释：

- `<= 5分钟` 是强目标，说明系统可以支撑较高频的 Agent 挖掘迭代。
- `<= 10分钟` 是硬验收目标，说明 CPU-only v1 在正式主板口径下可用。
- `10 到 20分钟` 可以继续推进研究主线，但必须记录瓶颈并进入 targeted optimization loop（定向优化循环）。
- `> 20分钟` 会明显拖慢批量挖因子，必须先优化到 `<= 10分钟`。

## 5. 阶段 A：固化当前 v1 小样本基线

目的：

- 把当前 `csi500 / sandbox_v1` 的 10 秒级事实写入后续报告。
- 作为主板压力测试的放大参考。
- 确认 v1 主链路在小样本上没有退化。

建议命令：

```bash
uv run fm factor evaluate \
  --engine v1 \
  --jobs 1 \
  --candidates candidate_factors/candidates.jsonl \
  --dataset datasets/sandbox_v1 \
  --run-id compute_engine_v1_csi500_baseline_jobs1
```

可选对照：

```bash
uv run fm factor evaluate \
  --engine v1 \
  --jobs auto \
  --candidates candidate_factors/candidates.jsonl \
  --dataset datasets/sandbox_v1 \
  --run-id compute_engine_v1_csi500_baseline_auto
```

输出要求：

- 记录 cold run（冷启动）和 warm run（预热后运行）。
- 记录 `jobs=1` 与 `jobs=auto`。
- 记录总耗时。
- 如果已有分段计时工具，记录 calculate / preprocess / metrics / artifact。

## 6. 阶段 B：构建 mainboard pressure dataset

目标 universe：

```text
沪深主板
剔除北交所
剔除科创板
剔除创业板
```

推荐做法：

- 优先在 zer0share 上游生成固定 universe key，例如 `univ_trade_mainboard`。
- 如果短期没有该 key，可以从 `univ_trade_base` 派生，但派生结果必须落成固定 universe membership。
- 不允许在 evaluate 阶段临时过滤市场板块。

建议命名：

```text
experiment_id = "mainboard_ohlcv_pressure_v1"
dataset_id = "mainboard_pressure_v1"
universe = "mainboard"
source_universe_key = "univ_trade_mainboard"
```

当前压力测试先使用本地可用历史。

正式成本推算按：

```text
8年
10年
20 candidates
30 candidates
```

## 7. 阶段 C：运行 mainboard pressure benchmark

最小 benchmark：

```bash
uv run fm factor evaluate \
  --engine v1 \
  --jobs 1 \
  --dataset datasets/mainboard_pressure_v1 \
  --candidates candidate_factors/candidates.jsonl \
  --run-id mainboard_pressure_v1_jobs1
```

并发对照：

```bash
uv run fm factor evaluate \
  --engine v1 \
  --jobs auto \
  --dataset datasets/mainboard_pressure_v1 \
  --candidates candidate_factors/candidates.jsonl \
  --run-id mainboard_pressure_v1_auto
```

必须记录：

- universe 日均股票数。
- trade days（交易日数量）。
- panel rows（样本行数）。
- candidate count（候选数量）。
- total wall time（总耗时）。
- calculate time（表达式计算耗时）。
- preprocess time（预处理耗时）。
- metrics time（指标耗时）。
- artifact time（产物写出耗时）。
- jobs=1 / jobs=auto 对比。
- 内存峰值，如工具可得。

## 8. 阶段 D：推算正式挖掘成本

Agent 拿到 mainboard pressure benchmark 后，必须先做成本推算，再判断是否优化。

推算表必须包含：

```text
8年 x 20 candidates
8年 x 30 candidates
10年 x 20 candidates
10年 x 30 candidates
```

如果后续加入 OOS（out-of-sample，样本外检验）：

```text
OOS multiplier: 1.2x 到 1.5x，按实际切片方式说明
```

如果后续加入 walk-forward（滚动前推验证）：

```text
walk-forward multiplier: 按窗口数量单独估算，例如 3x / 5x
```

输出格式：

```text
current pressure cost:
- dataset
- universe daily mean
- trade days
- candidate count
- total seconds
- seconds per candidate

projected mining cost:
- 8y / 20 candidates
- 8y / 30 candidates
- 10y / 20 candidates
- 10y / 30 candidates
- OOS adjusted estimate
- walk-forward adjusted estimate

classification:
- strong green / green / yellow / red
```

## 9. 阶段 E：Agent 决策协议

Agent 不凭感觉判断“慢不慢”，必须按以下协议执行。

### 9.1 如果 strong green

条件：

```text
10年 x 主板 x 30 candidates x full evaluation <= 5分钟
```

动作：

- 记录强目标达成。
- 不再进入性能优化。
- 后续优先推进 OOS gate、walk-forward 和因子验收协议。

### 9.2 如果 green

条件：

```text
10年 x 主板 x 30 candidates x full evaluation <= 10分钟
```

动作：

- 记录硬验收达成。
- 不阻塞后续研究主线。
- 记录 top bottleneck，作为后续优化候选。

### 9.3 如果 yellow

条件：

```text
10年 x 主板 x 30 candidates x full evaluation > 10分钟
且 <= 20分钟
```

动作：

- 可以继续推进研究主线。
- 必须启动 targeted optimization loop。
- subagent 需要提出一轮低风险优化方案。
- 目标是尽量压到 `<= 10分钟`，如距离 `<= 5分钟` 不超过 2x，则可继续追强目标。

### 9.4 如果 red

条件：

```text
10年 x 主板 x 30 candidates x full evaluation > 20分钟
```

动作：

- 暂停把该引擎作为正式挖掘默认路径。
- 必须启动 targeted optimization loop。
- subagent 需要基于 profiling 生成优化子计划并实施。
- 复测必须使用同一个 mainboard pressure benchmark。
- 直到推算进入 `<= 10分钟`。

## 10. 阶段 F：Subagent targeted optimization loop

主 plan 只定义边界和决策规则。

具体 profiling、定位、制定子计划、实施优化，由 subagent 负责。

### 10.1 subagent 输入

subagent 必须读取：

- mainboard pressure benchmark report。
- csi500 v1 baseline report。
- 当前 run artifacts。
- 当前 profiling report。
- 相关代码路径。

### 10.2 subagent 输出

subagent 必须产出：

```text
1. profiling report
2. top bottleneck table
3. proposed optimization sub-plan
4. expected speedup
5. risk level
6. equivalence test plan
7. implementation summary
8. before / after benchmark
9. remaining bottlenecks
```

### 10.3 优化路由表

如果 `metrics` 最大：

- 优化 metrics kernel。
- 优化 quantile stats。
- 优化 RankIC / Spearman。
- 优化 IC / Pearson。
- 减少 `metrics.parquet` / `ic_series.parquet` 内部构造开销。
- 检查 Numba backend 是否实际启用。

如果 `preprocess` 最大：

- 优化 winsorize by date。
- 优化 zscore by date。
- 优化 neutralization residual calculation。
- 复用 neutralization design。
- 复用 industry matrix 和 market cap exposure。

如果 `artifact` 最大：

- 单独开 lightweight artifact plan。
- 不在本 plan 内直接跳过 factor values。
- 不改变当前默认 artifact 合同。

如果 `jobs=auto` 慢：

- 默认保持 `jobs=1`。
- 只有在内核释放 GIL 且任务变成 CPU-bound 后，再重新评估并行。

如果 `calculate` 重新变慢：

- 检查 `ts_rank` / rolling kernels。
- 检查 expression cache 命中率。
- 检查公共子表达式是否跨候选复用。

如果内存成为瓶颈：

- 检查 matrix dtype。
- 检查临时矩阵数量。
- 检查 returns cube 和 factor matrix 生命周期。
- 避免为每个 candidate 重复 materialize 大对象。

## 11. 正确性约束

任何优化都必须保持以下语义不变：

- universe membership。
- forward return definition。
- gate threshold。
- candidate DSL。
- horizon 列表。
- preprocess 数学含义。
- IC / RankIC 口径。
- quantile returns 口径。
- diagnostics schema。
- artifact 默认合同。

每一轮优化必须通过：

```text
candidate_results.jsonl 决策一致
best_horizon 一致
failure_bucket 一致
failed_rules 一致
metrics.parquet tolerance 内一致
ic_series.parquet tolerance 内一致
diagnostics.parquet schema 不变
summary.md 结构不变
```

当前可接受数值口径：

- 决策产物必须一致。
- 浮点指标允许明确 tolerance 内误差。
- 如果某项误差超过 tolerance，subagent 必须解释来源并补测试。

## 12. 推荐执行顺序

```text
1. 固化 csi500 v1 10s 级别 baseline。
2. 准备 mainboard pressure dataset。
3. 跑 mainboard pressure benchmark。
4. 输出成本推算表。
5. 按 strong green / green / yellow / red 分类。
6. 如果 yellow 或 red，启动 subagent targeted optimization loop。
7. subagent profiling。
8. subagent 生成优化子计划。
9. subagent 实施优化。
10. 跑等价性测试。
11. 复测 mainboard pressure benchmark。
12. 更新报告和剩余瓶颈。
```

## 13. 完成定义

本 plan 完成的条件：

- 已有 csi500 v1 baseline 记录。
- 已有 mainboard pressure benchmark 结果。
- 已有 8 到 10 年、20 到 30 candidates 的成本推算。
- 已有 green / yellow / red 判断。
- 如果结果为 green 或 strong green，记录通过并进入样本协议 / OOS / 因子验收。
- 如果结果为 yellow 或 red，subagent 已完成至少一轮 targeted optimization loop。
- 最终 `10年 x 主板 x 30 candidates x full evaluation` 推算进入 `<= 10分钟`，或明确列出未达标瓶颈和下一轮计划。

强完成目标：

```text
10年 x 主板 x 30 candidates x full evaluation <= 5分钟
```

硬完成目标：

```text
10年 x 主板 x 30 candidates x full evaluation <= 10分钟
```

