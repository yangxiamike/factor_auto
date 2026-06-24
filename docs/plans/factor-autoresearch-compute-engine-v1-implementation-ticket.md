# Factor Autoresearch 计算引擎 v1 实施工单

日期：2026-06-24

关联规格：

```text
docs/framework/factor-autoresearch-compute-engine-v1-spec.md   # 计算引擎 v1 规格说明
docs/plans/factor-autoresearch-calculation-profiling-initial-diagnosis.md
                                                               # 当前计算性能诊断
```

## 1. 工单目标

本工单把 Compute Engine v1（计算引擎 v1）从规格说明拆成可执行工程任务。

这一版要完成三类实际提速：

- `Matrix engine`（矩阵化计算）：用 `PanelStore + NumPy / Numba kernels`（面板存储 + 数组 / 编译算子）替代 pandas 热路径。
- `Expression cache`（表达式缓存复用）：用 `Expression DAG / cache`（表达式图 / 缓存）复用跨候选子表达式。
- `Candidate parallelism`（候选级并发）：用 `--jobs`（并发 worker 数）让不同候选并行评估。

这一版还要完成一类调研：

- `Technology feasibility`（技术可行性调研）：记录 `Polars / DuckDB / GPU`（列式表引擎 / 嵌入式分析数据库 / 显卡加速）哪些暂不做、为什么暂不做、以后什么条件下再做。

硬目标：

```text
legacy baseline ~= 332.167s                 # 旧引擎当前基线
v1 hard target <= 33s                       # v1 硬目标：至少 10 倍提速
v1 stretch target <= 11s                    # v1 展望目标：约 30 倍提速
```

## 2. 执行前置要求

本任务必须先开一个新的 worktree（独立工作区），不要直接在当前主工作区里实施大规模代码改动。

推荐命令：

```bash
git worktree add ..\factor_autoresearch_compute_engine_v1 -b feature/compute-engine-v1
                                               # 新建独立 worktree 和功能分支
cd ..\factor_autoresearch_compute_engine_v1    # 进入独立工作区
```

原因：

- 当前主工作区已有多份文档、实验产物和 v0 hardening 改动。
- Compute Engine v1 会触碰 evaluator、metrics、preprocess、operators、CLI、tests，改动面较大。
- 新 worktree 可以降低误改当前工作区的风险，也方便多 agent 并行分工。

约束：

- 不允许在没有确认 worktree 的情况下开始大规模实现。
- 不允许删除或回滚当前主工作区已有改动。
- 所有工程改动都应发生在新 worktree 的 `feature/compute-engine-v1` 分支。
- 当前主工作区只保留 spec / ticket（规格 / 工单）类文档改动。
- 每个 Task（任务）结束后必须单独 commit（提交）一次，不把多个任务混在同一个 commit 里。
- 每个 commit message（提交信息）必须能看出对应 Task 编号和主要内容。

推荐提交格式：

```text
compute-v1 task 1: add equivalence harness       # Task 1：等价性工具
compute-v1 task 2: add panel store               # Task 2：面板存储
compute-v1 task 3: add core kernels              # Task 3：核心算子
```

## 3. 建议 Agent 编排

本任务允许使用 subagent（子代理）和 multi-agent（多代理）协作。

总原则：

- Coordinator（主协调者）负责拆任务、定边界、合并结果、跑最终验收。
- Explorer（代码勘察代理）负责读现有逻辑，不直接改代码。
- Worker（实现代理）负责具体模块，必须有清晰文件边界。
- Verifier（验证代理）负责等价性、性能和失败分析。

模型强度由执行者根据任务难度自行分配，但推荐如下：

| 角色 | 推荐模型强度 | 适用任务 |
| --- | --- | --- |
| Coordinator（主协调者） | 5.4 high 或 5.5 medium | 总体设计、任务切分、合并冲突、验收判断 |
| Explorer（代码勘察） | 5.4 medium | 读现有 evaluator / metrics / preprocess / artifact 语义 |
| Kernel Worker（算子实现） | 5.4 high 或 5.5 high | `ts_rank`、IC、RankIC、Numba kernel 等高风险计算 |
| Engine Worker（引擎实现） | 5.4 high | `PanelStore`、DAG、cache、engine routing |
| Parallel Worker（并发实现） | 5.4 medium / high | `--jobs`、单 writer、serial / parallel 等价 |
| Verifier（验证） | 5.4 high | equivalence harness、benchmark、回归测试 |
| Docs Worker（文档） | 5.4 medium | feasibility note、架构说明、验收记录 |

并行规则：

- 可以多个 subagent 同时工作，但必须分配不重叠的 write scope（写入范围）。
- 不同 worker 不应同时修改同一核心文件。
- 每个 worker 结束时必须报告 changed files（修改文件列表）和 test result（测试结果）。
- 每个 Task 完成并通过该 Task 的局部验收后，负责该 Task 的 worker 或 Coordinator 必须创建一个独立 commit（提交）。
- 如果一个 Task 被多个 subagent 分工完成，由 Coordinator 负责合并后统一 commit。
- 如果结果不确定，优先让 Verifier 做验证，不靠口头判断。

## 4. 目标代码结构

Compute Engine v1 完成后，代码结构建议如下。

说明：

- `NEW`（新增）表示 v1 新增模块。
- `EXTEND`（扩展）表示现有模块继续保留，但要接入 v1。
- `KEEP`（保持）表示尽量不改变外部语义，只作为下游复用。

```text
factor_autoresearch/
  cli.py                                      # EXTEND：命令行入口，新增 --engine / --jobs
  config.py                                   # EXTEND：配置读取，新增 evaluation.engine / evaluation.jobs
  evaluate.py                                 # EXTEND：评估编排，接入 legacy / v1 双引擎

  data_loader.py                              # KEEP：现有数据加载入口，继续产出 DatasetBundle
  calculator.py                               # KEEP：legacy 旧计算路径，作为对照和 fallback
  preprocess.py                               # KEEP：legacy 旧预处理路径，作为对照和 fallback
  metrics.py                                  # KEEP：legacy 旧指标路径，作为对照和 fallback
  diagnostics.py                              # KEEP：legacy 旧体检路径，作为对照和 fallback
  gate.py                                     # KEEP：裁判逻辑保持不变
  artifacts.py                                # EXTEND：产物写入保持 schema，不同 engine 共用
  registry.py                                 # KEEP：候选登记表语义保持不变

  engine/
    __init__.py                               # NEW：计算引擎包入口
    legacy.py                                 # NEW：legacy engine 适配层，包装现有 pandas 路径
    v1.py                                     # NEW：v1 engine 编排入口
    routing.py                                # NEW：根据 --engine 选择 legacy / v1
    parallel.py                               # NEW：候选级并发执行和单 writer 汇总

  compute_v1/
    __init__.py                               # NEW：v1 计算核心包入口
    panel.py                                  # NEW：PanelStore，日期 x 股票矩阵存储
    kernels.py                                # NEW：NumPy / Numba 核心算子
    expression_dag.py                         # NEW：表达式 DAG 和 cache key
    cache.py                                  # NEW：表达式结果缓存
    calculator.py                             # NEW：v1 表达式计算器
    preprocess.py                             # NEW：v1 矩阵化预处理
    metrics.py                                # NEW：v1 矩阵化指标计算
    diagnostics.py                            # NEW：v1 体检计算，可复用 metrics kernels
    equivalence.py                            # NEW：legacy / v1 等价性比较工具
    benchmark.py                              # NEW：性能计时和报告工具，可选

tests/
  test_compute_v1_panel.py                    # NEW：PanelStore 测试
  test_compute_v1_kernels.py                  # NEW：核心算子等价性测试
  test_compute_v1_expression_dag.py           # NEW：表达式图 / 缓存测试
  test_compute_v1_preprocess.py               # NEW：预处理等价性测试
  test_compute_v1_metrics.py                  # NEW：指标等价性测试
  test_compute_v1_engine.py                   # NEW：v1 engine 集成测试
  test_compute_v1_parallel.py                 # NEW：串行 / 并行等价性测试
  test_compute_v1_cli.py                      # NEW/EXTEND：--engine / --jobs CLI 测试

docs/framework/
  factor-autoresearch-compute-engine-v1-spec.md
                                               # KEEP：规格说明

docs/plans/
  factor-autoresearch-compute-engine-v1-implementation-ticket.md
                                               # KEEP：本实施工单
  factor-autoresearch-compute-engine-v1-technology-feasibility.md
                                               # NEW：Polars / DuckDB / GPU 可行性记录
```

### 4.1 模块边界

`engine/`（引擎编排层）负责选择和调度，不放具体矩阵算法：

- `engine/legacy.py`（旧引擎适配）：把现有 pandas 路径包装成统一 engine 接口。
- `engine/v1.py`（新引擎适配）：调用 `compute_v1/` 下的矩阵化实现。
- `engine/routing.py`（引擎路由）：根据 CLI / config 选择 `legacy` 或 `v1`。
- `engine/parallel.py`（并发调度）：只处理候选级并发和结果汇总。

`compute_v1/`（v1 计算核心层）负责计算，不直接处理 CLI 和文件写入：

- `panel.py`（面板存储）：负责 DatasetBundle 到矩阵的转换。
- `kernels.py`（算子）：负责 NumPy / Numba 热点计算。
- `expression_dag.py`（表达式图）：负责表达式归一化和依赖关系。
- `cache.py`（缓存）：负责跨候选中间结果复用。
- `preprocess.py`（预处理）：负责矩阵化缩尾、标准化、中性化。
- `metrics.py`（指标）：负责批量 IC、RankIC、分层单调性。
- `diagnostics.py`（体检）：负责体检报告，尽量复用指标算子。
- `equivalence.py`（等价性）：负责 legacy / v1 对比。

现有 legacy 模块继续保留：

- 作为 correctness oracle（正确性参照）。
- 作为 fallback（回退路径）。
- 作为 equivalence harness（等价性工具）的对照来源。

### 4.2 不推荐的结构

不要把所有新代码都塞进：

```text
factor_autoresearch/evaluate.py              # 不推荐：会让评估编排变成巨型文件
factor_autoresearch/metrics.py               # 不推荐：会混淆 legacy 和 v1 语义
factor_autoresearch/calculator.py            # 不推荐：会让旧路径和新路径互相污染
```

不要让 `compute_v1/` 直接写 artifacts（运行产物）或 registry（候选登记表）。

原因：

- v1 计算核心应该只负责计算。
- artifacts / registry 是外部契约，应由评估编排层统一写入。
- 这样 legacy 和 v1 才能共用同一套产物写入逻辑。

## 5. 推荐任务拆分

### Task 0：新建 worktree 和基线记录

目标：

- 开独立 worktree。
- 记录 legacy（旧引擎）当前行为和性能基线。

建议命令：

```bash
uv run pytest -v                            # 当前测试基线
uv run ruff check .                         # 当前代码风格基线
uv run fm factor validate --candidates candidate_factors/candidates.jsonl --dataset datasets/sandbox_v1
                                               # 候选校验基线
uv run fm factor evaluate --candidates candidate_factors/candidates.jsonl --dataset datasets/sandbox_v1 --run-id compute_engine_v1_legacy_baseline
                                               # 旧引擎评估基线
```

产物：

```text
runs/compute_engine_v1_legacy_baseline/summary.md
runs/compute_engine_v1_legacy_baseline/results/candidate_results.jsonl
runs/compute_engine_v1_legacy_baseline/results/metrics.parquet
runs/compute_engine_v1_legacy_baseline/results/ic_series.parquet
runs/compute_engine_v1_legacy_baseline/results/diagnostics.parquet
```

验收：

- legacy baseline 可以稳定跑通。
- baseline run id 和性能数字被记录到后续 equivalence report（等价性报告）里。
- 完成后提交 commit：`compute-v1 task 0: record baseline`（记录基线）。

### Task 1：Equivalence Harness（等价性对比工具）

目标：

- 在实现 v1 前，先建立 legacy / v1 对比框架。
- 即使 v1 还是 stub（占位实现），也先定义比较口径。

范围：

```text
tests/                                   # 测试目录
factor_autoresearch/compute_v1/equivalence.py
                                          # 可选：等价性对比工具
scripts/                                  # 可选：本地对比脚本
```

必须比较：

- candidate result（候选结果）
- metrics（汇总指标）
- ic series（日度 IC / RankIC）
- diagnostics（体检报告）
- gate decision（裁判结论）
- failed rules（失败规则）
- best horizon（最优预测周期）

验收：

- 能清楚报告一致 / 不一致。
- 能显示具体字段差异。
- 支持 float tolerance（浮点容差）。
- 完成后提交 commit：`compute-v1 task 1: add equivalence harness`（新增等价性工具）。

### Task 2：PanelStore（面板存储）

目标：

- 从现有 dataset（数据集）构建日期 x 股票矩阵。
- 给 v1 engine（新引擎）提供统一数据入口。

建议范围：

```text
factor_autoresearch/compute_v1/panel.py    # PanelStore 数据结构
tests/test_panel.py                        # PanelStore 测试
```

要求：

- 固定 `date_index`（日期索引）。
- 固定 `asset_index`（股票索引）。
- 支持 `field_map`（字段到矩阵的映射）。
- 支持 `universe mask`（股票池掩码）。
- 支持回写到 legacy long-format（旧长表格式）。

验收：

- 同一字段从 legacy dataset 和 PanelStore 读出后语义一致。
- NaN（空值）和 universe（股票池）行为一致。
- 完成后提交 commit：`compute-v1 task 2: add panel store`（新增面板存储）。

### Task 3：Kernel Layer（算子层）

目标：

- 实现 v1 热点算子。
- 优先替代最慢的 pandas 逻辑。

建议范围：

```text
factor_autoresearch/compute_v1/kernels.py  # NumPy / Numba 算子
tests/test_kernels.py                      # 算子等价性测试
```

第一批算子：

```text
ts_return                                  # 时间序列收益
ts_mean                                    # 时间序列均值
ts_std                                     # 时间序列标准差
ts_rank                                    # 时间序列排名
cs_rank                                    # 横截面排名
cs_zscore                                  # 横截面标准化
daily_ic                                   # 日度 IC
daily_rankic                               # 日度 RankIC
```

优先级：

1. `ts_rank`（时间序列排名）
2. `daily_ic`（日度 IC）
3. `daily_rankic`（日度 RankIC）
4. `cs_zscore / cs_rank`（横截面标准化 / 排名）

验收：

- 每个 kernel 都有 legacy equivalence tests（旧引擎等价性测试）。
- 对 tie policy（并列值处理）有明确测试。
- 对 NaN（空值）有明确测试。
- 完成后提交 commit：`compute-v1 task 3: add core kernels`（新增核心算子）。

### Task 4：Expression DAG / Cache（表达式图 / 缓存）

目标：

- 把候选表达式拆成可复用的表达式图。
- 相同子表达式只计算一次。

建议范围：

```text
factor_autoresearch/compute_v1/expression_dag.py
                                             # 表达式图
factor_autoresearch/compute_v1/cache.py      # 表达式缓存
factor_autoresearch/compute_v1/calculator.py # v1 表达式计算器
tests/test_expression_dag.py                # 表达式缓存测试
```

要求：

- cache key（缓存键）不包含 candidate id（候选 id）。
- cache key 必须包含 operator（算子）、参数、子表达式。
- serial（串行）和 parallel（并行）结果一致。

验收：

- 两个候选共用同一子表达式时，缓存命中可被测试证明。
- cache 不改变计算结果。
- 完成后提交 commit：`compute-v1 task 4: add expression cache`（新增表达式缓存）。

### Task 5：Preprocess Engine（预处理引擎）

目标：

- 把 winsorize、zscore、neutralize 从 pandas 热路径迁到矩阵逻辑。

建议范围：

```text
factor_autoresearch/compute_v1/preprocess.py
                                             # v1 预处理
tests/test_preprocess_v1.py                 # 预处理等价性测试
```

要求：

- `winsorize_by_date`（按日缩尾）等价。
- `zscore_by_date`（按日标准化）等价。
- `neutralize_by_date`（按日中性化）等价。
- 缓存 industry dummy / exposure design（行业哑变量 / 暴露矩阵）。

验收：

- 关键候选预处理后的因子值与 legacy 一致或在明确 tolerance 内一致。
- gate decision 不变。
- 完成后提交 commit：`compute-v1 task 5: add preprocess engine`（新增预处理引擎）。

### Task 6：Metrics / Diagnostics Engine（指标 / 体检引擎）

目标：

- 批量化计算 IC、RankIC、positive ratio、monotonicity。
- diagnostics 复用 v1 数据结构和 kernel。

建议范围：

```text
factor_autoresearch/compute_v1/metrics.py   # v1 指标引擎
factor_autoresearch/compute_v1/diagnostics.py
                                             # v1 体检引擎，可选
tests/test_metrics_v1.py                    # 指标等价性测试
```

要求：

- 多 horizon（预测周期）共享 factor matrix（因子矩阵）。
- daily IC / RankIC 使用矩阵规约，避免逐日 pandas `Series.corr`。
- 输出 schema（字段结构）保持不变。

验收：

- `metrics.parquet` 字段一致。
- `ic_series.parquet` 字段一致。
- `diagnostics.parquet` 字段一致。
- best horizon 和 failed rules 一致。
- 完成后提交 commit：`compute-v1 task 6: add metrics engine`（新增指标 / 体检引擎）。

### Task 7：Engine Routing / CLI（引擎路由 / 命令行）

目标：

- 增加 `--engine` 和 `--jobs` 参数。
- 支持 legacy / v1 双引擎。

建议范围：

```text
factor_autoresearch/evaluate.py             # 评估编排
factor_autoresearch/engine/routing.py        # 引擎路由
factor_autoresearch/engine/legacy.py         # legacy 引擎适配
factor_autoresearch/engine/v1.py             # v1 引擎适配
factor_autoresearch/cli.py                  # 命令行入口，实际文件按仓库现状调整
factor_autoresearch/config.py               # 配置读取
tests/test_cli.py                           # CLI 测试，按现有结构调整
```

新增参数：

```text
--engine {legacy,v1}                        # 选择计算引擎
--jobs {auto,N}                             # 选择并发 worker 数
```

验收：

- `--engine legacy` 行为与当前一致。
- `--engine v1 --jobs 1` 可运行。
- `--engine v1 --jobs auto` 可运行。
- manifest（运行清单）记录 engine / jobs。
- 完成后提交 commit：`compute-v1 task 7: add engine routing`（新增引擎路由）。

### Task 8：Candidate-Level Parallelism（候选级并发）

目标：

- 多 candidate（候选因子）并行评估。
- 产物写入仍保持单 writer（单写入器）。

建议范围：

```text
factor_autoresearch/engine/parallel.py       # 并发执行工具
factor_autoresearch/evaluate.py             # 调度接线
tests/test_parallel_equivalence.py          # 串行 / 并行等价性
```

要求：

- 并发发生在候选评估层。
- PanelStore 只读共享。
- artifact / registry 写入统一汇总。
- serial / parallel 输出顺序稳定。

验收：

- `--jobs 1` 和 `--jobs 2` 结果一致。
- `--jobs auto` 结果稳定。
- 没有文件写入竞争。
- 完成后提交 commit：`compute-v1 task 8: add candidate parallelism`（新增候选级并发）。

### Task 9：Technology Feasibility Note（技术可行性记录）

目标：

- 明确 Polars / DuckDB / GPU 这一版不进 runtime 的原因。
- 记录未来什么条件下再考虑。

新增文档：

```text
docs/plans/factor-autoresearch-compute-engine-v1-technology-feasibility.md
                                               # 技术可行性记录
```

内容：

- `Polars`（列式 DataFrame 引擎）适合 / 不适合的位置。
- `DuckDB`（嵌入式分析数据库）适合 / 不适合的位置。
- `GPU`（显卡加速）适合 / 不适合的位置。
- v2 触发条件，例如更大 universe（股票池）、更多候选、更长历史。

验收：

- 文档能说明哪些暂不做。
- 文档能说明为什么暂不做。
- 文档能说明后续何时重新评估。
- 完成后提交 commit：`compute-v1 task 9: add technology feasibility note`（新增技术可行性记录）。

### Task 10：Rollout / Default Switch（上线 / 默认切换）

目标：

- 完成 shadow -> opt-in -> default（影子模式 -> 显式选择 -> 默认启用）。

要求：

- shadow mode（影子模式）能跑 legacy / v1 对比。
- opt-in mode（显式选择模式）支持 `--engine v1`。
- default mode（默认模式）只在全部验收通过后启用。
- legacy fallback（旧引擎回退）长期保留。

验收：

- 未达 10 倍硬目标前，不默认启用 v1。
- 任何 v1 unsupported operator（暂不支持算子）都要有可读错误或明确 fallback 策略。
- 完成后提交 commit：`compute-v1 task 10: enable rollout path`（新增上线 / 回退路径）。

## 6. 推荐执行顺序

推荐顺序：

```text
Task 0: worktree + baseline                 # 独立工作区和基线
Task 1: equivalence harness                 # 等价性工具
Task 2: PanelStore                          # 面板存储
Task 3: kernels                             # 算子层
Task 4: expression DAG / cache              # 表达式图 / 缓存
Task 5: preprocess engine                   # 预处理引擎
Task 6: metrics / diagnostics engine        # 指标 / 体检引擎
Task 7: engine routing / CLI                # 引擎路由 / 命令行
Task 8: candidate parallelism               # 候选级并发
Task 9: technology feasibility note         # 技术可行性记录
Task 10: rollout / default switch           # 上线 / 默认切换
```

允许并行的部分：

- Task 2 和 Task 3 可以并行启动，但 kernel worker 需要使用固定测试 fixture。
- Task 5 和 Task 6 可以由不同 worker 并行做，但必须共享 equivalence harness。
- Task 9 可以由 docs worker 并行完成。

不建议并行的部分：

- Task 1 必须先于大规模实现。
- Task 7 / Task 8 涉及总线接线，应在核心 v1 行为稳定后做。
- Task 10 必须最后做。

## 7. 最终验收

必须通过：

```bash
uv run pytest -v                            # 全量测试
uv run ruff check .                         # 代码风格检查
uv run fm factor validate --candidates candidate_factors/candidates.jsonl --dataset datasets/sandbox_v1
                                               # 候选校验
uv run fm factor evaluate --engine legacy --candidates candidate_factors/candidates.jsonl --dataset datasets/sandbox_v1 --run-id compute_engine_v1_legacy_check
                                               # 旧引擎检查
uv run fm factor evaluate --engine v1 --jobs 1 --candidates candidate_factors/candidates.jsonl --dataset datasets/sandbox_v1 --run-id compute_engine_v1_v1_serial_check
                                               # 新引擎串行检查
uv run fm factor evaluate --engine v1 --jobs auto --candidates candidate_factors/candidates.jsonl --dataset datasets/sandbox_v1 --run-id compute_engine_v1_v1_parallel_check
                                               # 新引擎并行检查
```

必须一致：

- candidate count（候选数量）
- validate status（校验状态）
- gate passed status（裁判通过状态）
- failed rules（失败规则）
- best horizon（最优预测周期）
- candidate result schema（候选结果字段结构）
- metrics schema（指标字段结构）
- diagnostics schema（体检字段结构）
- registry semantics（登记表语义）

必须达标：

```text
v1 wall time <= 33s                         # 硬目标
```

如果没有达标：

- 不允许默认启用 v1。
- 必须提交 profiling report（性能剖析报告）。
- 必须列出剩余瓶颈和下一轮计划。

提交要求：

- Task 0 到 Task 10 每个任务至少有一个独立 commit（提交）。
- 不允许把多个已完成 Task 合并成一个大 commit。
- 最终验收修复可以单独提交为 `compute-v1 final: fix verification issues`（最终验收修复）。
- 最终 PR / 合并请求中必须列出每个 Task 对应的 commit。

## 8. Definition of Done（完成定义）

本工单完成的标准：

- 新 worktree 中完成 Compute Engine v1 实现。
- 实现后的代码结构与“目标代码结构”基本一致；如有偏离，必须在最终说明中解释原因。
- Task 0 到 Task 10 都有对应独立 commit。
- legacy / v1 等价性通过。
- v1 serial / v1 parallel 等价性通过。
- 当前 sandbox 上 v1 达到 10 倍硬目标。
- 产物 schema 和 gate 结论不变。
- `Polars / DuckDB / GPU` 技术可行性记录已落文档。
- default switch（默认切换）只在验收通过后发生。
- legacy fallback（旧引擎回退）仍可用。

## 9. 重要提醒

- 这不是单点 `ts_rank` 优化工单。
- 这不是只做 metrics 向量化工单。
- 这不是直接替换为 Polars / DuckDB / GPU 的工单。
- 这是一次计算框架升级工单：矩阵化、缓存复用、候选级并发一起进入 v1。
