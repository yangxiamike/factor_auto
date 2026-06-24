# Factor Autoresearch 计算引擎 v1 规格说明

日期：2026-06-24

## 1. 目标

本规格说明定义下一阶段的计算引擎重构。目标不是只优化某一个慢函数，而是把当前以 pandas / MultiIndex 为主的逐候选计算路径，升级为一套更快、更可复用、更容易并发、也能随时回退的矩阵化计算系统。

核心目标：

- 保持现有 `fm factor evaluate`（因子评估命令）的研究语义不变。
- 保持现有 `gate`（入库裁判）、`artifact`（运行产物）、`summary`（运行摘要）、`registry`（候选因子登记表）的外部契约不变。
- 建立 `legacy / v1 equivalence harness`（旧引擎 / 新引擎等价性对比工具），先证明结果一致，再默认启用新引擎。
- 第一类提速：使用 `PanelStore(date x asset)`（面板存储：日期 x 股票的矩阵布局）和 `NumPy / Numba kernels`（数组计算 / 编译加速算子）做矩阵化计算。
- 第二类提速：引入 `Expression DAG / cache`（表达式有向图 / 中间结果缓存），让同一批候选之间可以复用子表达式结果。
- 第三类提速：引入 `candidate-level parallelism`（候选级并发），让不同候选因子可以并行评估。
- 技术可行性调研：记录 `Polars / DuckDB / GPU`（列式表引擎 / 嵌入式分析数据库 / 显卡加速）是否适合后续阶段引入。
- 在当前 sandbox 小规模数据上做到至少 10 倍提速；30 倍作为展望目标，不作为 v1 硬验收。

当前性能基线：

```text
dataset: datasets/sandbox_v1                         # 数据集：当前沙盒数据
candidates: candidate_factors/candidates.jsonl        # 候选因子文件：30 个候选
candidate_count: 30                                    # 候选数量
baseline_wall_time: 332.167s                           # 当前总耗时基线
```

v1 硬目标：

```text
v1_wall_time <= 33s                                    # 新引擎总耗时不超过 33 秒
```

v1 展望目标：

```text
v1_wall_time <= 11s                                    # 新引擎展望目标约 30 倍提速
```

## 2. 非目标

本阶段不做这些事：

- 不改变因子表达式 DSL（因子表达式语言）的用户写法。
- 不改变当前 `gate v0`（第一版入库裁判）的判定口径。
- 不改变 `candidate registry`（候选因子登记表）的入库语义。
- 不引入 `GPU runtime`（GPU 运行时）。
- 不把 `Polars / DuckDB`（新的表计算 / 查询引擎）作为 v1 运行时依赖。
- 不做新的自动候选生成器。
- 不做官方因子晋升流程。
- 不把 `diagnostics`（体检报告）纳入 gate 判定。
- 不为了提速牺牲 legacy / v1（旧引擎 / 新引擎）结果可比性。

`Polars`（列式 DataFrame 引擎）、`DuckDB`（嵌入式分析数据库）、`GPU`（显卡加速）只在本阶段做可行性记录，用来判断 v2 以后是否值得引入。

## 3. 当前问题

根据初步 profiling（性能剖析），当前总耗时约 332 秒，主要开销如下：

| 阶段 | 耗时 | 占比 | 主要原因 |
| --- | ---: | ---: | --- |
| `metrics`（指标计算） | 148.503s | 44.7% | 逐 horizon（预测周期）/ 逐日期执行 pandas groupby、corr、rank、qcut，重复开销高 |
| `calculate`（表达式计算） | 91.720s | 27.6% | `ts_rank`（时间序列排名）使用 rolling apply，每个窗口创建 pandas `Series` |
| `preprocess`（因子预处理） | 56.066s | 16.9% | 逐日期 winsorize（缩尾）、zscore（标准化）、neutralize（中性化） |
| `diagnostics`（体检报告） | 35.807s | 10.8% | 已经过一次向量化优化，当前不是第一优先级 |
| `gate / validate`（裁判 / 校验） | 约 0s | 约 0% | 可以忽略 |

当前系统适合原型验证，但不适合更大规模候选评估：

- `MultiIndex DataFrame / Series`（pandas 多级索引表 / 序列）在热路径上对象开销过高。
- 每个 candidate（候选因子）独立计算，不能复用相同子表达式。
- pandas `rolling / groupby`（滚动窗口 / 分组）在大量小组计算中开销明显。
- `metrics`（指标计算）对每个 horizon（预测周期）重复组织数据和计算日度统计。
- `preprocess`（预处理）的行业中性化会重复构建设计矩阵。
- 并发边界不清晰，难以稳定扩展。

## 4. 提速来源分区

这一版 v1 的提速不是单点优化，而是分成四个区块。前三个区块进入 v1 实施范围，第四个区块只做可行性记录。

| 区块 | 是否进入 v1 实施 | 作用 | 说明 |
| --- | --- | --- | --- |
| `Matrix engine`（矩阵化计算） | 是 | 降低 pandas 对象开销 | 用 `PanelStore`（面板存储）和 `NumPy / Numba kernels`（数组 / 编译算子）替代热路径上的 MultiIndex、groupby、rolling apply |
| `Expression cache`（表达式缓存复用） | 是 | 减少重复计算 | 把候选表达式拆成 `Expression DAG`（表达式图），相同子表达式只算一次 |
| `Candidate parallelism`（候选级并发） | 是 | 提高吞吐 | 不同 candidate（候选因子）并行评估，artifact（产物）仍由单 writer（写入器）统一落盘 |
| `Technology feasibility`（技术可行性调研） | 只调研，不进 runtime | 判断后续路线 | 评估 `Polars / DuckDB / GPU`（列式表引擎 / 嵌入式分析数据库 / 显卡加速）是否适合 v2 或更大规模场景 |

v1 明确要做：

- 做矩阵化计算：`PanelStore + NumPy / Numba kernels`（面板存储 + 数组 / 编译算子）。
- 做缓存复用：`Expression DAG / cache`（表达式图 / 缓存）。
- 做候选级并发：`candidate-level parallelism`（候选级并发）。
- 做可行性记录：`Polars / DuckDB / GPU feasibility`（列式表引擎 / 嵌入式数据库 / 显卡加速可行性）。

v1 明确不做：

- 不把 `Polars`（列式 DataFrame 引擎）作为默认计算引擎。
- 不把 `DuckDB`（嵌入式分析数据库）作为 metrics / factor runtime（指标 / 因子运行时）。
- 不引入 `GPU runtime`（GPU 运行时）。
- 不让这些技术调研阻塞 v1 的矩阵化、缓存、并发落地。

提速目标拆解：

```text
legacy baseline ~= 332s                     # 旧引擎基线耗时
matrix engine gain                          # 矩阵化收益：减少 pandas 对象和 groupby 开销
expression cache gain                       # 缓存收益：减少跨候选重复子表达式
candidate parallelism gain                  # 并发收益：多个候选同时评估
v1 hard target <= 33s                       # v1 硬目标：至少 10 倍提速
v1 stretch target <= 11s                    # v1 展望目标：约 30 倍提速
```

## 5. 总体设计

v1 使用双引擎架构：

```text
legacy engine                              # 旧引擎：当前 pandas 实现
  current pandas implementation             # 当前实现：作为对照、回退、回归测试基线

v1 engine                                  # 新引擎：矩阵化计算实现
  PanelStore                               # 面板存储：日期 x 股票矩阵
    -> Expression DAG / Cache              # 表达式图 / 缓存：复用中间计算
    -> NumPy / Numba Kernels               # 数组 / 编译算子：替代 pandas 热路径
    -> Preprocess Engine                   # 预处理引擎：缩尾、标准化、中性化
    -> Metrics Engine                      # 指标引擎：IC、RankIC、分层单调性
    -> Diagnostics Engine                  # 体检引擎：年份、行业等切片报告
    -> unchanged gate / artifacts          # 保持不变：裁判和运行产物
```

外部入口保持不变，只新增 engine（计算引擎）选择：

```text
fm factor evaluate --engine legacy          # 使用旧引擎
fm factor evaluate --engine v1              # 使用新引擎
```

通过验收后，默认命令改用 v1：

```text
fm factor evaluate                          # 默认使用新引擎
```

legacy engine（旧引擎）继续保留为 fallback（回退方案）：

```text
fm factor evaluate --engine legacy          # 显式切回旧引擎
```

## 6. 数据模型

### 6.1 PanelStore（面板存储）

`PanelStore`（面板存储）是 v1 的核心数据容器。

逻辑形状：

```text
rows: trade_date                            # 行：交易日
cols: asset                                 # 列：股票
values: float64 matrix                      # 值：双精度浮点矩阵
```

基础字段：

```text
open                                        # 开盘价
high                                        # 最高价
low                                         # 最低价
close                                       # 收盘价
close_hfq                                  # 后复权收盘价
volume                                      # 成交量
amount                                      # 成交额
forward_return_1d                           # 未来 1 日收益
forward_return_5d                           # 未来 5 日收益
forward_return_20d                          # 未来 20 日收益
industry                                    # 行业分类
market_cap or neutralization exposures      # 市值或中性化暴露变量
universe mask                               # 股票池掩码：哪些股票当天可用
```

必备索引：

```text
date_index                                  # 日期索引：有序交易日
asset_index                                 # 股票索引：稳定股票顺序
field_map: field_name -> ndarray            # 字段映射：字段名到矩阵
```

约束：

- 所有矩阵必须共享同一个 `date_index`（日期索引）和 `asset_index`（股票索引）。
- 缺失值用 `NaN`（空值）表示。
- 股票池用 boolean mask（布尔掩码）表示。
- 写入 artifacts（运行产物）前，再转换回现有 long-format schema（长表格式）。
- v1 内部不把 MultiIndex pandas 对象作为热路径数据结构。

### 6.2 结果转换

v1 内部可以使用矩阵格式，但外部产物必须保持兼容。

必须保持的产物：

```text
runs/{run_id}/results/candidate_results.jsonl       # 候选评估结果
runs/{run_id}/results/metrics.parquet               # 汇总指标
runs/{run_id}/results/ic_series.parquet             # 日度 IC / RankIC 序列
runs/{run_id}/results/diagnostics.parquet           # 体检报告
runs/{run_id}/manifest.json                         # 本次运行清单
runs/{run_id}/summary.md                            # 本次运行摘要
candidate_factors/registry.jsonl                    # 候选因子登记表
```

## 7. Expression DAG / Cache（表达式图 / 缓存）

当前候选因子表达式之间存在可复用子表达式，例如：

```text
ts_return(close_hfq, 1)                    # 时间序列收益：后复权收盘价 1 日收益
ts_rank(close_hfq, 10)                     # 时间序列排名：后复权收盘价 10 日窗口排名
ts_rank(volume, 10)                        # 时间序列排名：成交量 10 日窗口排名
cs_zscore(...)                             # 横截面标准化：同一天股票之间标准化
```

v1 需要把表达式解析为 DAG（有向无环图）：

```text
candidate expression                       # 候选因子表达式
  -> normalized operator tree              # 归一化算子树
  -> stable expression key                 # 稳定表达式键
  -> cached ndarray result                 # 缓存后的矩阵结果
```

缓存粒度：

- `field:close_hfq`（基础字段：后复权收盘价）。
- `ts_return(field:close_hfq,1)`（单算子表达式：1 日收益）。
- `cs_zscore(sub_expr_key)`（组合表达式：对子表达式做横截面标准化）。

缓存约束：

- cache key（缓存键）必须包含算子名、参数、子表达式 key。
- cache key 不应包含 candidate id（候选 id），否则无法跨候选复用。
- cache（缓存）只保存纯计算结果，不保存 gate / artifact（裁判 / 产物）结果。
- cache 必须在同一 dataset（数据集）、同一 universe（股票池）、同一 preprocess config（预处理配置）下使用。
- v1 serial（新引擎串行）和 v1 parallel（新引擎并行）的 cache 结果必须一致。

## 8. Kernel Layer（算子层）

v1 kernel layer（算子层）负责替代热路径上的 pandas rolling / groupby / rank。

第一批必须覆盖：

```text
ts_return                                  # 时间序列收益
ts_mean                                    # 时间序列均值
ts_std                                     # 时间序列标准差
ts_rank                                    # 时间序列排名
ts_delta                                   # 时间序列差分
ts_corr                                    # 时间序列相关性
cs_rank                                    # 横截面排名
cs_zscore                                  # 横截面标准化
cs_winsorize                               # 横截面缩尾
neutralize                                 # 中性化
daily_ic                                   # 日度 IC
daily_rankic                               # 日度 RankIC
quantile_monotonicity                      # 分层单调性
```

实现原则：

- 先用 NumPy（数组计算库）写清楚矩阵语义。
- 对热点窗口算子和逐日期批量统计使用 Numba（Python 编译加速器）。
- 每个 kernel（算子）必须有 legacy equivalence tests（旧引擎等价性测试）。
- Numba 只作为 runtime dependency（运行时依赖），不改变用户侧命令。
- kernel 输入输出均以 ndarray / mask（矩阵 / 掩码）为主。

`ts_rank`（时间序列排名）是第一优先级算子，因为当前实现会在每个 rolling window（滚动窗口）里创建 pandas `Series`。

## 9. Preprocess Engine（预处理引擎）

v1 preprocess（预处理）需要一起重做，不再放到后续阶段。

覆盖当前语义：

```text
winsorize_by_date                          # 按日期缩尾
zscore_by_date                             # 按日期标准化
neutralize_by_date                         # 按日期中性化
coverage / effective dates handling         # 覆盖率 / 有效交易日处理
```

优化方向：

- winsorize / zscore（缩尾 / 标准化）用矩阵按日期批处理。
- neutralize（中性化）复用按日期 / 行业构建好的 exposure design（暴露设计矩阵）。
- 避免每个候选、每个日期重复构造 industry dummy（行业哑变量）。
- 保持对 NaN（空值）、universe mask（股票池掩码）、industry missing（行业缺失）的 legacy 行为一致。

验收重点：

- 同一候选、同一日期的预处理后因子值，与 legacy（旧引擎）一致或在可解释 tolerance（容差）内一致。
- 如果 tolerance 不是 bitwise equal（逐位完全一致），必须在测试或说明里写清原因。
- gate decision（裁判结论）必须一致。

## 10. Metrics Engine（指标引擎）

v1 metrics（指标计算）是第一阶段最大收益点。

覆盖当前指标：

```text
ic_mean                                    # IC 均值
rankic_mean                                # RankIC 均值
icir                                       # IC 信息比率
rankic_ir                                  # RankIC 信息比率
coverage_mean                              # 平均覆盖率
effective_trade_days                       # 有效交易日数量
ic_positive_ratio                          # IC 为正的日期占比
rankic_positive_ratio                      # RankIC 为正的日期占比
directional_ic_mean                        # 方向调整后的 IC 均值
directional_rankic_mean                    # 方向调整后的 RankIC 均值
directional_ic_positive_ratio              # 方向调整后的 IC 正占比
directional_rankic_positive_ratio          # 方向调整后的 RankIC 正占比
directional_monotonicity                   # 方向调整后的分层单调性
horizon_score                              # 单个预测周期评分
best_horizon                               # 最优预测周期
```

优化方向：

- 对每个 horizon（预测周期）批量计算所有日期的 IC / RankIC。
- Pearson IC（线性相关 IC）用 grouped sums / matrix reductions（分组求和 / 矩阵规约），避免逐日 `Series.corr`。
- RankIC（排序相关 IC）用按日期 rank（排名）后的 Pearson 相关。
- quantile / monotonicity（分位分层 / 单调性）尽量矩阵化；必要时保留小范围循环，但避免 pandas 对象创建。
- 多个 horizon 共享同一个 factor matrix（因子矩阵），只替换 forward return matrix（未来收益矩阵）。

验收重点：

- `metrics.parquet`（汇总指标文件）schema（字段结构）与 legacy 一致。
- `ic_series.parquet`（日度 IC 文件）schema 与 legacy 一致。
- best horizon（最优预测周期）一致。
- failed rules（失败规则列表）一致。
- score（评分）在 tight tolerance（严格容差）内一致。

## 11. Diagnostics Engine（体检引擎）

diagnostics（体检报告）当前已不是最大瓶颈，但 v1 仍应统一到新数据模型。

要求：

- 复用 `PanelStore`（面板存储）和 metrics kernels（指标算子）。
- 保持 `diagnostics.parquet`（体检报告文件）schema 不变。
- 不改变 diagnostics 只用于研究体检、不参与 gate 的定位。
- 不把 diagnostics 作为 v1 性能硬目标的第一优先级。

## 12. Candidate-Level Parallelism（候选级并发）

v1 必须包含候选级并发。

并发边界：

```text
shared read-only PanelStore                # 共享只读面板数据
shared or precomputed expression cache      # 共享或预先计算的表达式缓存
candidate evaluation tasks                 # 候选评估任务
  -> calculate                              # 计算表达式
  -> preprocess                             # 预处理
  -> metrics                                # 指标计算
  -> diagnostics                            # 体检报告
  -> gate result                            # 裁判结果
single writer                               # 单写入器：统一写文件
  -> artifacts / registry updates           # 运行产物 / 登记表更新
```

设计原则：

- 并发只发生在 candidate evaluation（候选评估）层。
- artifact 写入（产物写入）保持单线程汇总，避免文件竞争。
- v1 serial（串行）与 v1 parallel（并行）必须结果一致。
- parallel worker count（并发 worker 数）可配置。

建议参数：

```text
fm factor evaluate --engine v1 --jobs 1       # 新引擎串行
fm factor evaluate --engine v1 --jobs auto    # 新引擎自动并发
fm factor evaluate --engine v1 --jobs 8       # 新引擎 8 个 worker
```

默认策略：

- 本地默认 `auto`（自动并发）。
- CI / equivalence tests（持续集成 / 等价性测试）使用 `--jobs 1` 和固定 `--jobs 2` 各跑一轮。

## 13. 技术选型策略

v1 允许新增：

```text
numba                                      # Python 编译加速器
```

v1 不新增 runtime dependencies（运行时依赖）：

```text
polars                                     # 列式 DataFrame 引擎
duckdb                                     # 嵌入式分析数据库
gpu frameworks                             # GPU 计算框架
```

原因：

- 当前热点主要是矩阵、滚动窗口、排名、相关性计算，NumPy / Numba 能直接覆盖。
- Polars / DuckDB 更适合表式查询和懒执行，但当前核心瓶颈是 panel matrix operators（面板矩阵算子）。
- GPU 会增加数据搬运、环境、CI 和 fallback（回退）复杂度；在当前 2 年 x 500 股票 x 30 候选规模下，不应作为 v1 前提。

但 v1 需要产出一份技术可行性记录：

```text
docs/plans/factor-autoresearch-compute-engine-v1-technology-feasibility.md
                                               # 技术可行性说明：Polars / DuckDB / GPU 是否值得 v2 引入
```

内容包括：

- Polars（列式 DataFrame）是否适合替代 artifact / long-table（产物 / 长表）处理。
- DuckDB（嵌入式分析数据库）是否适合 run artifact 查询和跨 run 分析。
- GPU（显卡加速）是否在更大 universe（股票池）/ 更大候选批次下有价值。

## 14. Rollout / Fallback（上线 / 回退）

上线分三步：

### 14.1 Shadow Mode（影子模式）

legacy（旧引擎）和 v1（新引擎）同时运行，v1 结果只用于比较。

要求：

- 输出 equivalence report（等价性报告）。
- 不改变 registry（候选登记表）。
- 不改变默认 engine（默认引擎）。

### 14.2 Opt-in Mode（显式选择模式）

允许用户显式选择：

```text
fm factor evaluate --engine v1              # 显式使用新引擎
```

要求：

- v1 可写完整 artifacts（运行产物）。
- legacy（旧引擎）仍为默认。
- 如果 v1 遇到 unsupported operator（暂不支持的算子），应清晰报错或自动 fallback（回退），具体策略需要测试覆盖。

### 14.3 Default Mode（默认模式）

通过验收后：

```text
fm factor evaluate                          # 默认使用新引擎
```

保留：

```text
fm factor evaluate --engine legacy          # 显式切回旧引擎
```

用于审计、回归和紧急回退。

## 15. Equivalence Harness（等价性对比工具）

在做大规模实现前，必须先建立 equivalence harness（等价性对比工具）。

比较层级：

```text
kernel equivalence                          # 算子等价性
preprocess equivalence                      # 预处理等价性
metrics equivalence                         # 指标等价性
candidate result equivalence                # 候选结果等价性
run artifact equivalence                    # 运行产物等价性
serial / parallel equivalence               # 串行 / 并行等价性
```

至少覆盖：

- 快速普通候选。
- `ts_rank`（时间序列排名）慢候选。
- 正向 `expected_direction`（预期方向）候选。
- 负向 `expected_direction` 候选。
- 覆盖率较低候选。
- 不同行业 / 日期缺失情况。
- 1d / 5d / 20d horizons（预测周期）。

允许 tolerance（容差）：

```text
float_abs_tol: 1e-10                        # 浮点绝对误差
float_rel_tol: 1e-8                         # 浮点相对误差
```

如果某些 rank / quantile（排名 / 分位）边界因为 tie behavior（并列值处理）不能 bitwise equal（逐位完全一致），必须：

- 写明差异来源。
- 固定 tie policy（并列值处理规则）。
- 确保 gate decision（裁判结论）一致。
- 确保 summary（摘要）中的关键指标在可接受 tolerance（容差）内一致。

## 16. CLI / Config Contract（命令行 / 配置契约）

新增 CLI 参数：

```text
--engine {legacy,v1}                        # 选择计算引擎
--jobs {auto,N}                             # 选择并发 worker 数
```

建议新增 config（配置）：

```toml
[evaluation]                                # 评估配置段
engine = "v1"                               # 默认计算引擎
jobs = "auto"                               # 默认并发策略
```

manifest（运行清单）必须记录：

```json
{
  "engine": "v1",
  "engine_comment": "计算引擎：v1 表示新矩阵引擎",
  "engine_version": "compute_engine_v1",
  "engine_version_comment": "引擎版本：计算引擎 v1",
  "jobs": "auto",
  "jobs_comment": "并发策略：auto 表示自动选择",
  "equivalence_baseline": "legacy",
  "equivalence_baseline_comment": "等价性基线：legacy 表示旧引擎",
  "gate_config_hash": "..."
}
```

## 17. 验收标准

### 17.1 正确性

必须通过：

```text
uv run pytest -v                            # 运行测试
uv run ruff check .                         # 运行代码风格检查
```

必须跑通：

```text
uv run fm factor validate --candidates candidate_factors/candidates.jsonl --dataset datasets/sandbox_v1
                                               # 校验候选因子
uv run fm factor evaluate --engine legacy --candidates candidate_factors/candidates.jsonl --dataset datasets/sandbox_v1 --run-id compute_engine_v1_legacy_check
                                               # 用旧引擎跑基线
uv run fm factor evaluate --engine v1 --jobs 1 --candidates candidate_factors/candidates.jsonl --dataset datasets/sandbox_v1 --run-id compute_engine_v1_v1_serial_check
                                               # 用新引擎串行跑
uv run fm factor evaluate --engine v1 --jobs auto --candidates candidate_factors/candidates.jsonl --dataset datasets/sandbox_v1 --run-id compute_engine_v1_v1_parallel_check
                                               # 用新引擎并行跑
```

legacy / v1（旧引擎 / 新引擎）必须一致：

- candidate count（候选数量）一致。
- validate status（校验状态）一致。
- gate passed status（是否通过裁判）一致。
- failed rules（失败规则）一致。
- best horizon（最优预测周期）一致。
- candidate result top-level schema（候选结果顶层字段结构）一致。
- metrics schema（指标字段结构）一致。
- diagnostics schema（体检字段结构）一致。
- registry update semantics（登记表更新语义）一致。

### 17.2 性能

在当前 sandbox（沙盒数据）规模下：

```text
legacy baseline ~= 332.167s                 # 旧引擎基线
v1 hard target <= 33s                       # 新引擎硬目标
v1 stretch target <= 11s                    # 新引擎展望目标
```

如果没有达到 hard target（硬目标）：

- 不允许默认启用 v1。
- 必须保留 profiling report（性能剖析报告）。
- 必须列出剩余瓶颈和下一步优化计划。

### 17.3 可运维性

必须满足：

- v1 失败时有可读错误。
- unsupported operator（暂不支持的算子）有明确提示。
- 用户可以显式切回 legacy（旧引擎）。
- run manifest（运行清单）能看出本次使用哪个 engine（引擎）。
- summary（摘要）能看出本次是否使用 v1。
- technology feasibility note（技术可行性记录）能说明 Polars / DuckDB / GPU 哪些暂不做、为什么暂不做、以后什么条件下再做。

## 18. 实施顺序

建议分 8 个 patch group（改动批次）：

1. `Equivalence harness`（等价性对比工具）
   - 建立 legacy / v1 对比工具。
   - 固定比较字段、tolerance（容差）、报告格式。

2. `PanelStore`（面板存储）
   - 从现有 dataset（数据集）构建矩阵面板。
   - 支持字段读取、mask（掩码）、long-format（长表格式）回写。

3. `Kernel layer`（算子层）
   - 实现第一批 NumPy / Numba kernels（数组 / 编译算子）。
   - 优先覆盖 `ts_rank`（时间序列排名）、`daily_ic`（日度 IC）、`daily_rankic`（日度 RankIC）。

4. `Expression DAG / cache`（表达式图 / 缓存）
   - 表达式归一化。
   - 子表达式缓存。
   - 跨候选复用。

5. `Preprocess Engine`（预处理引擎）
   - 矩阵化 winsorize / zscore（缩尾 / 标准化）。
   - 缓存 neutralize exposure design（中性化暴露设计矩阵）。
   - 对齐 legacy（旧引擎）行为。

6. `Metrics / Diagnostics Engine`（指标 / 体检引擎）
   - 批量 horizon metrics（预测周期指标）。
   - diagnostics（体检）复用 v1 kernels（新算子）。
   - 保持 artifact schema（产物字段结构）。

7. `Candidate-level parallelism`（候选级并发）
   - 增加 `--jobs` 参数。
   - 验证 serial / parallel equivalence（串行 / 并行等价性）。
   - 单 writer（写入器）汇总 artifacts（运行产物）。

8. `Rollout and default switch`（上线和默认切换）
   - shadow -> opt-in -> default（影子模式 -> 显式选择 -> 默认启用）。
   - 更新 manifest / summary（运行清单 / 摘要）。
   - 写 technology feasibility note（技术可行性记录）。

## 19. 风险

主要风险：

- rank tie policy（排名并列值处理）与 pandas 不完全一致。
- quantile boundary behavior（分位边界行为）与 `qcut` 不完全一致。
- neutralize（中性化）对 NaN（空值）、单行业、rank-deficient matrix（秩不足矩阵）的处理出现偏差。
- Numba 首次编译时间影响 benchmark（性能基准）口径。
- 并发 cache（缓存）设计不当导致非确定性。
- artifact ordering（产物排序）变化导致 diff（差异对比）噪音。

缓解方式：

- equivalence harness（等价性对比工具）先行。
- serial v1（新引擎串行）先通过，再打开 parallel（并行）。
- artifact 写入统一排序。
- benchmark（性能基准）区分 cold run（冷启动）和 warm run（预热后运行）。
- unsupported / uncertain operator（暂不支持 / 不确定算子）先 fallback legacy（回退旧引擎），再逐步迁移。

## 20. 最终定义

Compute Engine v1（计算引擎 v1）不是单点算法优化，而是一次计算框架升级。

它的成功标准不是“某一个慢函数变快”，而是：

```text
same research contract                      # 研究契约不变
same gate decisions                         # 裁判结论不变
same artifacts                              # 运行产物不变
faster execution                            # 执行速度更快
clear fallback                              # 回退路径清晰
clear path to larger candidate batches      # 能扩展到更大候选批次
```

当以上条件满足后，v1 才可以成为默认 evaluation engine（评估引擎）。
