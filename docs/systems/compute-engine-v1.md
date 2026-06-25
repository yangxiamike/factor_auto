# Compute Engine v1 系统说明

## 📌 结论

Compute Engine v1 是当前因子评价链路的性能升级版。

它已经完成：

- ✅ `legacy / v1` 双引擎路由
- ✅ `PanelStore(date x asset)` 矩阵化数据容器
- ✅ 矩阵化因子表达式计算
- ✅ 表达式 DAG / cache 复用
- ✅ 矩阵化 preprocess
- ✅ 矩阵化 metrics
- ✅ 可选 Numba metrics backend
- ✅ candidate-level parallelism
- ✅ benchmark / equivalence / guardrails
- ✅ 主板压力测试基线

当前判断：

- 20-30 个 candidates 的日常研究规模下，不需要继续做性能大改。
- 后续 OOS（out-of-sample，样本外检验）和 walk-forward（滚动前推验证）应作为评价外层能力推进，不应塞回 `compute_v1` 核心。
- 合并 main 前，重点是保住正确性、可复现性和性能护栏。

## 🧩 系统定位

v1 不替代 legacy 的正确性地位。

当前系统采用双引擎结构：

```text
legacy engine
  -> pandas 正确性基准

v1 engine
  -> PanelStore
  -> V1FactorCalc
  -> matrix preprocess
  -> matrix metrics
  -> same gate / same artifacts
```

外部入口保持统一：

```bash
fm factor evaluate --engine legacy
fm factor evaluate --engine v1 --jobs 1
fm factor evaluate --engine v1 --jobs auto
```

默认语义仍由同一套 config、candidate DSL、preprocess、metrics、gate、artifact 合同约束。

## 🧱 当前技术栈

| 层级 | 当前选择 | 说明 |
| --- | --- | --- |
| 语言 | Python | 保持研究系统可读、可改、可测试 |
| 正确性基准 | pandas legacy | 用于 legacy / v1 等价校验 |
| v1 主计算 | NumPy | `date x asset` 矩阵计算 |
| 可选加速 | Numba | metrics kernel 可选 backend，失败可回退 NumPy |
| 数据产物 | Parquet | dataset、factor values、metrics、IC series |
| 配置 | TOML | experiment / gate 配置 |
| 表达式 | 受限 Python AST DSL | 安全、可控，不引入完整量化框架 |
| 测试 | pytest | 单元、等价、smoke、guardrails |
| 并发 | candidate-level parallelism | 候选级并发，输出顺序稳定 |

暂不进入主链路：

- Polars
- DuckDB runtime
- GPU
- 新 engine

原因：

- 当前 CPU-only v1 已达性能目标。
- 引入新 DataFrame / query runtime 会增加一套计算语义。
- 当前最重要的是 legacy / v1 等价，而不是继续堆技术栈。

## 🚀 已完成的优化

| 优化方向 | legacy / 毛坯版 | compute engine v1 |
| --- | --- | --- |
| 数据布局 | pandas MultiIndex 长表 | `PanelStore(date x asset)` 矩阵 |
| 表达式计算 | pandas / groupby / rolling | `V1FactorCalc` + NumPy kernels |
| 子表达式复用 | 每个 candidate 重复算 | `ExpressionCache` + `expression_dag` |
| 时间序列算子 | rolling 路径 | `delay / ts_mean / ts_std / ts_rank` kernels |
| 横截面算子 | 每日 groupby rank/zscore | 行级 `cs_rank / cs_zscore` |
| 预处理 | 每日 pandas winsorize / zscore / neutralize | 矩阵化 preprocess + neutralization design 复用 |
| 指标计算 | pandas 按 horizon/date 循环 | returns cube + rowwise IC / RankIC / quantile stats |
| metrics backend | pandas only | NumPy baseline + optional Numba |
| 并发 | 串行逐候选 | `--jobs 1 / auto / N` |
| benchmark | 无统一运行报告 | `benchmark.json` + projected runtime |
| 护栏 | 手工对比 | guardrails 脚本 + CI workflow |

## 📊 性能基线

### csi500 sandbox

当前 warm run 记录：

| 场景 | 结果 |
| --- | --- |
| dataset | `sandbox_v1` |
| candidates | 30 |
| engine | `v1` |
| jobs | `1` |
| warmup run | 约 9.8 秒 |
| warm run | 约 8.5 秒 |

### 主板压力测试

基准文件：

```text
runs/mainboard_pressure_v1_auto_decision_report/benchmark.json
```

关键结果：

| 项目 | 数值 |
| --- | ---: |
| engine | `v1` |
| jobs | `auto` |
| candidates | 30 |
| trade_days | 485 |
| panel_rows | 1,543,755 |
| universe_daily_mean | 2,878.484536 |
| total_seconds | 54.654126 |
| calculate_seconds | 2.938471 |
| preprocess_seconds | 19.519223 |
| metrics_seconds | 21.708060 |
| artifact_seconds | 6.488580 |
| projected_seconds_10y_30c | 283.976079 |
| classification | `strong_green` |
| top_bottleneck_stage | `metrics_seconds` |
| should_trigger_optimization_loop | `false` |

解释：

- 当前主板规模下，10 年 x 30 candidates 的线性外推约 4.73 分钟。
- 仍在 5 分钟强目标内。
- 当前最大瓶颈是 metrics，其次是 preprocess。
- 但在 20-30 candidates 的目标规模下，暂不需要为性能继续大改。

## ✅ 正确性验证

v1 的核心验收不是“更快”，而是“更快且不改语义”。

已覆盖的等价层：

- candidate decision 一致
- best horizon 一致
- failure bucket 一致
- metrics schema 一致
- metrics 数值在 tolerance 内一致
- IC series 数值在 tolerance 内一致
- v1 serial / v1 parallel 一致
- diagnostics 非空表容差对比已有 guardrail test

最近验收命令和结果：

```bash
uv run python scripts/run_compute_v1_guardrails.py
# 15 passed

python -m pytest tests/test_compute_v1_calculator.py tests/test_compute_v1_preprocess.py tests/test_compute_v1_metrics.py tests/test_compute_v1_metrics_backends.py tests/test_compute_v1_parallel.py tests/test_compute_v1_panel.py tests/test_compute_v1_kernels.py tests/test_compute_v1_equivalence.py tests/test_compute_v1_benchmark.py tests/test_compute_v1_runtime_estimator.py -q
# 47 passed, 1 skipped

python -m pytest -q
# 108 passed, 1 skipped
```

## 🧪 Guardrails

仓库级规则在：

```text
AGENTS.md
```

统一命令：

```bash
uv run python scripts/run_compute_v1_guardrails.py
```

覆盖：

- `tests/test_compute_v1_benchmark.py`
- `tests/test_compute_v1_equivalence.py`
- `tests/test_compute_v1_runtime_estimator.py`

规则：

- 只改测试、benchmark、diagnostics、runtime estimate、文档时，至少跑 guardrails。
- 改到 `compute_v1` 核心模块时，再跑 compute_v1 suite。
- 合并前或大改后，再跑全量 `pytest`。

## 🔭 OOS / Walk-Forward 边界

后续 OOS 和 walk-forward 不应改变 compute engine v1 核心职责。

推荐结构：

```text
same factor values
  -> full sample metrics / gate
  -> OOS metrics / gate
  -> walk-forward slice metrics / gate
```

原则：

- 因子原始值尽量只算一次。
- `PanelStore`、returns cube、industry matrix、market cap exposure 尽量复用。
- slice 级 metrics / gate 单独计算。
- 如果 slice 改变验证口径，不复用该 slice 的评价结果。
- 不把样本切片逻辑塞进 `compute_v1` kernels。

当前 runtime estimator 在：

```text
factor_autoresearch/compute_v1/runtime_estimator.py
```

它用于估算：

- OOS multiplier
- walk-forward windows
- 目标 years / candidates
- projected seconds / minutes
- strong_green / green / yellow / red 分类

## ⚠️ 复杂度红线

以下事情合并 main 前不做：

- 不引入 Polars / DuckDB 到 compute 主链路。
- 不新增 `engine=v2`。
- 不改 IC / RankIC / monotonicity / quantile return 定义。
- 不改 gate 阈值和判定语义。
- 不改 candidate DSL。
- 不改 forward return definition。
- 不改 universe membership。
- 不为了速度跳过 artifact 合同。

如果未来出现以下情况，再单独立项：

- 10 年 x 主板 x 30 candidates 长期超过 10 分钟。
- OOS / walk-forward 后长期进入 `yellow` 或 `red`。
- metrics / preprocess 出现明确可复现瓶颈。
- artifact 写出成为主要瓶颈。

## 📋 合并 main 前检查清单

合并前至少确认：

- [ ] `compute-engine-v1` 分支工作区干净。
- [ ] `uv run python scripts/run_compute_v1_guardrails.py` 通过。
- [ ] compute_v1 suite 通过。
- [ ] 全量 `python -m pytest -q` 通过。
- [ ] `docs/systems/compute-engine-v1.md` 已更新。
- [ ] 不存在未解释的 legacy / v1 等价差异。
- [ ] 不存在为了性能修改计算语义的改动。
- [ ] 不需要继续做 Polars / DuckDB / GPU 主链路改造。

## 📎 相关文件

核心实现：

- `factor_autoresearch/compute_v1/panel.py`
- `factor_autoresearch/compute_v1/calculator.py`
- `factor_autoresearch/compute_v1/kernels.py`
- `factor_autoresearch/compute_v1/preprocess.py`
- `factor_autoresearch/compute_v1/metrics.py`
- `factor_autoresearch/compute_v1/metrics_kernels.py`
- `factor_autoresearch/compute_v1/metrics_kernels_numba.py`
- `factor_autoresearch/engine/parallel.py`
- `factor_autoresearch/evaluate.py`

验证与护栏：

- `factor_autoresearch/compute_v1/equivalence.py`
- `factor_autoresearch/compute_v1/benchmark.py`
- `factor_autoresearch/compute_v1/runtime_estimator.py`
- `scripts/run_compute_v1_guardrails.py`
- `.github/workflows/compute-v1-guardrails.yml`
- `AGENTS.md`

说明文档：

- `docs/plans/factor-autoresearch-mainboard-pressure-optimization-plan.md`
- `docs/plans/factor-autoresearch-compute-v1-guardrails.md`
- `docs/experiments/mainboard-pressure-benchmark-v1.md`
