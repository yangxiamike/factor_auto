# Factor Autoresearch Compute Engine v1 Metrics Acceleration Spec + Plan

## 1. 这份文档解决什么问题

这份文档是 Compute Engine v1 的后续加速计划。

上一轮 v1 已经把 `legacy` 路径从 300 秒级压到 30 秒级左右。核心收益来自：

- 把长表 pandas 流程改成矩阵化流程。
- 复用 `PanelStore`、returns cube、industry matrix、neutralization design。
- 因子表达式直接在 `date x asset` 矩阵上计算。
- 减少重复 registry 读取和候选级日志开销。

但最新 profiling 显示，当前 30 秒级耗时已经不主要来自表达式计算，也不主要来自 parquet 写入，而是集中在 metrics（指标计算）内部。

所以本计划要回答的是：

- 是否继续作为 `engine=v1` 的内部优化？
- 哪些指标内核必须加速？
- 加速时哪些指标口径绝对不能变？
- 如何把 30 秒级继续压到 10 秒级附近？
- 如何验收“更快但仍然等价”？

结论先说在前面：**metrics acceleration 应该合并进 Compute Engine v1，作为 v1 的内部指标内核加速层，不新开 `engine=numba` 或 `engine=v2`。**

## 2. 📌 当前 profiling 结论

本轮诊断基于当前 `compute-engine-v1` worktree，数据集和候选固定为：

```text
dataset: datasets/sandbox_v1
candidates: candidate_factors/candidates.jsonl
candidate_count: 30
date_count: 485
asset_count: 687
panel_rows: 333195
horizons: 1d, 5d, 20d
```

非 profiler 分段计时结果：

```text
TOTAL                                       25.878s
Evaluator._evaluate_candidates              23.537s
Evaluator._compute_v1_metrics_from_matrix   20.173s
_stable_quantile_stats                      14.670s
_rowwise_spearman                            4.064s
_rowwise_corr                                2.213s
Evaluator._preprocess_factor_matrix          2.532s
ArtifactWriter.write_factor_values           1.536s
V1FactorCalc.calculate_matrix                0.777s
Evaluator._prepare_v1_runtime                0.551s
ArtifactWriter.write_results                 0.021s
```

并发探针结果：

```text
jobs=1   26.250s
jobs=2   29.094s
jobs=3   31.801s
```

当前判断：

- ✅ 表达式计算已经不是主要瓶颈。
- ✅ parquet 写入不是主要瓶颈。
- ✅ 预处理仍有优化空间，但不是第一优先级。
- ❌ 候选级线程并发当前不适合作为主优化路径。
- 🔥 第一瓶颈是 metrics 内部高频小截面统计。

## 3. 🧩 这和上一轮 v1 优化的区别

上一轮 v1 解决的是“数据怎么流”。

它把评价链路从长表 pandas 流程改成矩阵化流程，可以理解成：

```text
先把路修成高速公路。
```

这一轮 metrics acceleration 解决的是“高速公路上的收费站太慢”。

当前每天、每个 horizon、每个候选都要做：

- IC（因子值和未来收益的 Pearson 相关）
- RankIC（因子排序和未来收益排序的 Spearman 相关）
- quantile returns（分桶收益）
- long-short return（多空收益）
- monotonicity（分桶收益单调性）

这些函数在当前实现中仍然有大量 pandas / scipy 小函数调用。单次调用不慢，但调用次数很高，累计成本很大。

所以本轮不是重新设计 v1，而是加速 v1 内部 metrics kernel（指标内核）。

## 4. 总体目标

### 4.1 性能目标

以当前固定 sandbox 数据和 30 个候选为基准：

- 基线：当前 `engine=v1 --jobs 1` 约 26 到 30 秒。
- 目标：warm run（预热后运行）`<= 12s`。
- 强目标：warm run `<= 10s`。
- stretch：warm run 进入个位数秒。

说明：

- warm run 指依赖、模块、JIT 编译缓存等准备完成后的运行耗时。
- cold run（冷启动运行）必须记录，但不作为第一阶段硬门槛。
- 如果引入 Numba（Python JIT 编译器，把部分 Python/NumPy 循环编译成机器码），首次编译耗时需要单独记录。

### 4.2 正确性目标

加速后必须保持评价语义稳定：

- `candidate_results.jsonl` 中每个候选的状态不变。
- `best_horizon` 不变。
- `failure_bucket` 不变。
- `metrics.parquet` 在容忍浮点误差内等价。
- `ic_series.parquet` 在容忍浮点误差内等价。
- `registry` eligible 结果不变。
- `--jobs 1` 和 `--jobs auto` 结果一致。

当前 v1 与 legacy 已知存在极小浮点漂移：少数 `ic_series.ic` 单元在约 `1e-9` 绝对量级、`1e-7` 相对量级有差异。

因此本轮验收重点不是“bitwise 完全一致”，而是：

- 决策产物必须一致。
- 指标在明确 tolerance（容忍误差）内一致。
- 新内核和当前 v1 NumPy 路径必须可对照。

## 5. 非目标

本轮不做：

- ❌ 不新增 `--engine numba`。
- ❌ 不新增 `--engine v2`。
- ❌ 不把 Polars 放进 runtime 主链路。
- ❌ 不把 DuckDB 改成核心指标计算执行器。
- ❌ 不引入 GPU。
- ❌ 不改 candidate DSL。
- ❌ 不改 gate 规则。
- ❌ 不为了提速减少 metrics 输出字段。
- ❌ 不为了提速跳过 factor artifact 写出，除非另起产物瘦身计划。

## 6. 技术方案

### 6.1 方案总览

保留外部入口：

```bash
uv run fm factor evaluate --engine v1 ...
```

在 v1 内部增加 metrics kernel 加速层：

```text
Evaluator
  -> V1FactorCalc
  -> preprocess_factor_matrix
  -> compute_candidate_metrics_from_matrix
       -> metrics kernel backend
            -> numpy baseline
            -> numba accelerated path
```

建议默认策略：

```text
backend = "auto"
```

语义：

- `auto`：如果 Numba 可用且编译成功，则使用加速内核；否则回退到 NumPy baseline。
- `numpy`：强制使用当前可解释基线路径，方便调试和等价性测试。
- `numba`：强制使用 Numba 内核，若不可用则报错，方便 benchmark。

### 6.2 第一优先级：metrics 内核

优先加速以下函数：

1. `_stable_quantile_stats`

   当前耗时约 `14.670s`，是第一瓶颈。

   加速目标：

   - 保持 qcut 等价分桶口径。
   - 保持 stable sort（稳定排序）行为。
   - 避免每个交易日构造 pandas Series。
   - 避免每个交易日调用 scipy Spearman。

2. `_rowwise_spearman`

   当前耗时约 `4.064s`。

   加速目标：

   - 对每日横截面做平均排名。
   - 再用轻量 Pearson 公式计算 ranked correlation。
   - 处理 tie（并列值）时和 pandas `rank(method="average")` 对齐。

3. `_rowwise_corr`

   当前耗时约 `2.213s`。

   加速目标：

   - 避免 `np.corrcoef` 每日小数组调用。
   - 用手写 mean / dot / variance 公式计算。
   - 保持样本不足和零方差时返回 NaN。

### 6.3 第二优先级：批量化指标输出

如果第一优先级后仍不能进入 12 秒以内，再评估：

- 减少 `ic_series_rows.append(dict(...))` 的 Python 字典构造开销。
- 先用 NumPy 数组收集，再一次性构建 DataFrame。
- 避免在 candidate 内部多次创建小对象。

这一步不改变输出文件，只改变内部构造方式。

### 6.4 第三优先级：预处理内核

如果 metrics 已经压缩到较低水平，下一瓶颈会变成预处理：

```text
Evaluator._preprocess_factor_matrix: 约 2.532s
```

可优化方向：

- winsorize by date
- zscore by date
- neutralize residual calculation

但这一块涉及中性化矩阵、缺失值、行业暴露和线性代数，正确性风险比 metrics 更高，所以不作为第一批任务。

### 6.5 暂不押注候选级并发

当前结果显示：

```text
jobs=1   26.250s
jobs=2   29.094s
jobs=3   31.801s
```

因此本轮不把候选级并发作为主优化路径。

后续只有在 Numba 内核释放 GIL（Global Interpreter Lock，Python 全局解释器锁）并且 metrics 内核变成真正 CPU-bound 后，才重新评估并发。

## 7. 正确性约束

### 7.1 指标口径不能变

以下口径必须保持：

- IC：每日横截面 Pearson correlation。
- RankIC：每日横截面 Spearman correlation，排名使用平均排名处理并列。
- 分桶：保持当前 qcut 等价逻辑。
- long-short：最高分桶平均收益减最低分桶平均收益。
- monotonicity：分桶序号与分桶收益的 Spearman correlation。
- coverage：有效样本数 / universe 样本数。
- min cross-section size：低于 gate 最小样本数时当日 IC / RankIC 置为 NaN。

### 7.2 NaN 和边界行为不能变

必须覆盖：

- 全 NaN 行。
- 有效样本数不足。
- 因子值全部相同。
- 收益值全部相同。
- 分桶数不足。
- tie 很多的横截面。
- universe mask 内外混合。
- forward return 有缺失。

### 7.3 输出合同不能变

以下文件结构和字段不应改变：

```text
runs/{run_id}/results/candidate_results.jsonl
runs/{run_id}/results/metrics.parquet
runs/{run_id}/results/ic_series.parquet
runs/{run_id}/results/diagnostics.parquet
runs/{run_id}/factors/{candidate_id}.parquet
runs/{run_id}/summary.md
```

如果未来要做“轻量 artifact 模式”，应该单独开 plan，不混进本次 metrics acceleration。

## 8. 实施计划

### Task 1：固化 baseline 和 profiling 脚本

目标：先把当前 26 到 30 秒基线记录清楚。

涉及：

```text
factor_autoresearch/compute_v1/benchmark.py
docs/plans/factor-autoresearch-compute-engine-v1-metrics-acceleration-plan.md
```

产出：

- 记录 `jobs=1`、`jobs=auto`、`jobs=2`、`jobs=3` 的耗时。
- 记录 metrics / preprocess / calculator / artifact 的分段耗时。
- 区分 cold run 和 warm run。

验收：

- 可以稳定复现当前瓶颈排序。
- benchmark 输出不修改 registry。

### Task 2：增加 metrics backend 边界

目标：让 metrics 内核可切换，但外部仍然是 `engine=v1`。

建议新增或调整：

```text
factor_autoresearch/compute_v1/metrics.py
factor_autoresearch/compute_v1/metrics_kernels.py
factor_autoresearch/compute_v1/metrics_kernels_numba.py
```

设计：

- `metrics.py` 保持对外 API。
- `metrics_kernels.py` 提供 NumPy baseline。
- `metrics_kernels_numba.py` 提供可选 Numba 实现。
- 如果 Numba 不存在，测试和运行仍可回退。

验收：

- 默认行为与当前 v1 一致。
- 无 Numba 环境下测试仍可通过。

### Task 3：实现轻量 Pearson / Spearman 内核

目标：替换 `_rowwise_corr` 和 `_rowwise_spearman` 的高开销路径。

要点：

- 用 NumPy baseline 先实现。
- 再用 Numba 实现同样语义。
- tie 使用 average rank。
- 样本不足和零方差返回 NaN。

验收：

- 单元测试覆盖 tie、NaN、零方差、样本不足。
- 与 pandas/scipy 参考结果在 tolerance 内一致。

### Task 4：实现分桶统计内核

目标：替换 `_stable_quantile_stats` 高频路径。

要点：

- 保持稳定排序。
- 保持当前 qcut 等价边界。
- 用数组收集 bucket mean。
- monotonicity 不再调用 pandas Series corr。

验收：

- 与当前 v1 分桶收益、long-short、monotonicity 在 tolerance 内一致。
- 特别测试重复因子值、缺失收益、分桶不足。

### Task 5：批量构建 ic_series 和 horizon rows

目标：减少 Python dict/list 小对象构造成本。

要点：

- 内部用 NumPy 数组暂存每日指标。
- 每个 candidate/horizon 完成后再构建 DataFrame。
- 输出 schema 不变。

验收：

- `metrics.parquet` schema 不变。
- `ic_series.parquet` schema 不变。
- legacy/v1 决策结果不变。

### Task 6：Numba 依赖和回退策略

目标：让 Numba 成为可控加速依赖，而不是不可解释黑盒。

需要确认：

- `pyproject.toml` 是否加入 `numba`。
- `uv.lock` 是否更新。
- Windows 本地和 CI 是否能安装。

建议策略：

- `auto` 默认回退，不因 Numba 缺失导致 v1 失败。
- benchmark 可显式要求 `numba`，方便发现未启用加速。
- 首次编译耗时单独记录。

验收：

- 无 Numba 时 v1 可运行。
- 有 Numba 时 warm run 使用加速路径。
- 加速路径失败时错误信息清楚。

### Task 7：等价性测试

目标：防止“快了但口径变了”。

测试层级：

- kernel 级：小数组对比 pandas/scipy。
- candidate 级：单候选对比当前 v1 baseline。
- batch 级：30 候选完整输出对比。
- engine 级：legacy 与 v1 决策产物对比。

验收：

- `candidate_results` 一致。
- `metrics` 在 tolerance 内一致。
- `ic_series` 在 tolerance 内一致。
- `diagnostics` 一致或在已解释 tolerance 内一致。

### Task 8：最终 benchmark 和验收报告

目标：确认是否达到 10 秒级目标。

必须运行：

```bash
uv run pytest -q
uv run ruff check .
uv run fm factor validate --candidates candidate_factors/candidates.jsonl --dataset datasets/sandbox_v1
uv run fm factor evaluate --engine v1 --jobs 1 --candidates candidate_factors/candidates.jsonl --dataset datasets/sandbox_v1 --run-id compute_engine_v1_metrics_accel_serial
uv run fm factor evaluate --engine v1 --jobs auto --candidates candidate_factors/candidates.jsonl --dataset datasets/sandbox_v1 --run-id compute_engine_v1_metrics_accel_auto
```

需要报告：

- cold run 耗时。
- warm run 耗时。
- serial 耗时。
- auto 耗时。
- metrics 分段耗时。
- 与当前 v1 baseline 的输出差异。
- 与 legacy 的决策产物差异。

## 9. 验收标准

### 9.1 必须满足

1. 外部 CLI 仍然使用 `--engine v1`。
2. 默认运行不要求用户知道内部 backend。
3. 无 Numba 环境下仍有可运行回退路径。
4. 完整测试通过。
5. `ruff check .` 通过。
6. `candidate_results` 与当前 v1 baseline 一致。
7. `metrics` 与当前 v1 baseline 在 tolerance 内一致。
8. `ic_series` 与当前 v1 baseline 在 tolerance 内一致。
9. `registry` eligible 结果不变。
10. warm run `<= 12s`。

### 9.2 强目标

1. warm run `<= 10s`。
2. `jobs=auto` 不慢于 `jobs=1`。
3. metrics 分段耗时从约 `20s` 降到 `6s` 以内。

### 9.3 Stretch

1. warm run 进入个位数秒。
2. 在不改变输出合同的前提下，factor artifact 写出和 metrics 构造进一步减负。
3. 重新评估候选级并发是否因为 Numba 释放 GIL 而变得有效。

## 10. 风险与回滚

### 10.1 风险：指标口径漂移

风险：

- 手写 rank / corr / quantile 后，tie、NaN、边界分桶可能和 pandas 不一致。

缓解：

- 先保留 NumPy baseline。
- 每个 kernel 都和 pandas/scipy 做小样本对照。
- 完整 batch 做 artifacts 等价性检查。

回滚：

- backend 切回 `numpy`。
- 保留当前 v1 metrics 路径作为 fallback。

### 10.2 风险：Numba 安装和首次编译成本

风险：

- Windows 或 CI 安装失败。
- cold run 因首次编译变慢。

缓解：

- Numba 可选。
- cold / warm 分开记录。
- 无 Numba 时自动回退。

回滚：

- 移除 Numba backend 启用条件。
- 保留依赖但默认不启用，或完全移除依赖。

### 10.3 风险：并发继续无收益

风险：

- 即使 Numba 加速后，候选级并发仍然受内存带宽或调度开销限制。

缓解：

- 不把并发作为本轮主验收。
- 只在 metrics 内核足够快后重新测试。

回滚：

- `jobs=auto` 保持当前小 batch 串行策略。

## 11. 最终判断

本轮最合理的工程路径是：

```text
不新开 engine
不先上 Polars / DuckDB / GPU
不押注候选级并发
先把 metrics kernel 这几个高频小函数打掉
```

也就是说：

- 上一轮 v1 已经完成“架构级提速”。
- 下一轮应该做“指标内核级提速”。
- 文档单独开 plan，但实现合并进 v1。

如果这份 plan 验收通过，Compute Engine v1 将从当前 30 秒级进入 10 秒级附近，并保留现有 CLI、artifact、gate 和 registry 合同。
