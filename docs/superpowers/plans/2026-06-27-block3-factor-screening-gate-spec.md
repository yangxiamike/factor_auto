# 区块3因子筛选 Gate v1 规格

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` when implementing this spec. This document defines the block3 screening design; it is not an implementation checklist.

日期：2026-06-27
工作树：`block3-a-line`

## 1. 目标

区块3负责把 Agent 挖出来的候选因子，筛成可以进入研究因子库的 `screened factors`。

第一版只做“研究因子库入库”，不做生产交易入库。

核心目标：

```text
候选因子
  -> 基础合法性检查
  -> RankIC / IC 预测力筛选
  -> correlation 去重与 replacement 标记
  -> 轻量交易 sanity check
  -> admitted / reject / duplicate / replace_candidate
```

## 2. 非目标

区块3 v1 暂不做：

- 不做 top-k 强行入库。
- 不保留 `watch` 状态。
- 不做完整 OOS / walk-forward。
- 不做完整 tear sheet。
- 不做行业、市值、regime 深度切片。
- 不做完整成本模型、容量模型和组合优化。
- 不做生产因子库入库。
- 不让 mining agent 绕过 gate。

这些放到后续 production / strategy evaluation layer。

## 3. 设计来源

### 3.1 参考 FactorMiner

FactorMiner 的筛选骨架是：

```text
Fast IC Screening
  -> Correlation Check
  -> Replacement Check
  -> Batch Deduplication
  -> Full Validation
  -> Admit to Factor Library
```

它的 admission 思路可以概括为：

```text
IC(alpha) >= tau_IC
max |corr(alpha, existing_factor)| < theta
```

这里的 IC 更接近横截面 RankIC 口径，也就是因子排序和未来收益排序的相关性。

我们采用它的核心：

```text
预测力筛选 + 相关性去重 + replacement + 入研究因子库
```

### 3.2 我们增加轻量交易检查

本项目不是为了写研究报告，而是为了给未来交易策略准备因子原材料。

所以区块3 v1 在 FactorMiner-style admission 后，增加轻量交易 sanity check：

```text
directional_long_short_sharpe
monotonicity_score
turnover_proxy
```

但这一步不是完整生产回测，只用于挡掉明显不可交易的候选。

## 4. 总体流程

```text
Agent 生成候选因子
  ↓
Gate 0：基础合法性 / coverage
  ↓
Gate 1：RankIC / IC 预测力筛选
  ↓
Gate 2：Correlation 去重
       - batch 内去重
       - 对 research_factor_library 去重
       - replacement 标记
  ↓
Gate 3：轻量交易 sanity check
  ↓
Admission Decision
  ↓
admitted / reject / duplicate / replace_candidate
  ↓
Agent 读取反馈，决定下一轮怎么挖
```
### 4.1 职责边界：Block3 只调用，不补算

Screening Gate 的工程边界按区块拆开：

| 区块 | 负责什么 | 不负责什么 | 缺口处理 |
| --- | --- | --- | --- |
| 区块1 / compute engine v1 | 提供 Gate0-Gate3 会用到的全部计算结果输出，包括表达式合法性、表达复杂度、因子暴露、RankIC、相关性、t 检验、单调性、换手代理 | 不决定候选是否入库，不写 screening 产物 | 如果 Gate 需要的指标当前没算，由 compute engine v1 新增接口或输出字段 |
| 区块2 / data sample layer | 提供数据集读取、样本协议、评价切片、forward return、股票池和追溯字段 | 不计算因子指标，不判断 gate | 如果 Gate 需要的数据视图当前没有，由区块2新增数据接口 |
| 区块3 / screening gate | 调用区块1和区块2接口，读取配置阈值，执行 Gate0-Gate3 判定，写 `evaluation_log`、`research_factor_library`、`replacement_queue` | 不自己推断缺失数据，不自己补算指标，不绕过 compute engine v1 | 发现缺指标或缺数据时，明确反馈给区块1或区块2补接口 |

这条边界是 hard rule：

```text
Block3 不拥有 metric calculator。
Block3 不拥有 data/sample builder。
Block3 只拥有 gate decision、orchestration、artifact writer。
```

所以，Screening v1 虽然只记录 Gate 判定字段，但这些字段的计算来源仍然是 compute engine v1；区块3只选择、消费、判定，不复制计算逻辑。


### 4.2 CLI 入口：evaluate 是新 Gate

Block3 screening v1 完成后，CLI 入口按业务含义重新命名：

| CLI 命令 | 调用对象 | 定位 |
| --- | --- | --- |
| `factor evaluate` | `block3_screening_runner.run_block3_screening` | 新的研究因子入库筛选主入口，执行 Gate0-Gate3 |
| `factor diagnose` | 旧 `evaluate.py` / `Evaluator` | 旧多 horizon、best_horizon、metrics / diagnostics 展开链路，只作为诊断工具 |

不新增公开的 `block3-screen` 命令。`block3_screening_runner.py` 是内部工程模块，不暴露工程名给日常使用者。

## 5. 状态模型

区块3 v1 只保留四种状态。

| 状态 | 含义 | 写入位置 |
| --- | --- | --- |
| `admitted` | 通过所有 gate，可进入研究因子库 | `research_factor_library` + `evaluation_log` |
| `reject` | 基础检查、预测力或轻量交易检查失败 | `evaluation_log` |
| `duplicate` | 与已有因子高度相似，且没有明显更好 | `evaluation_log` |
| `replace_candidate` | 与已有因子高度相似，但新因子明显更好 | `replacement_queue` + `evaluation_log` |

第一版不设 `watch`。

原因：

```text
过就入库；
不过就记录；
重复就拒绝；
更好才标记 replacement。
```

这样研究因子库更干净，也方便后续区块4实现。

## 6. Gate 0：基础质量门

目的：挡掉“不值得进入预测力评价”的候选。Gate0 不判断 alpha，只判断候选是否**合法、可算、不过度复杂、输出不是废值、样本够用**。

Screening v1 的指标输出原则：

```text
compute engine v1 只向 Block3 输出会直接参与 Gate 判定的指标。
诊断型指标不进入 Block3 screening 调用链路，也不写入 screening 产物。
```

### 6.1 检查逻辑分类

| 分类 | 要回答的问题 | 失败后的处理 |
| --- | --- | --- |
| 表达式合法性 | 表达式能不能解析、字段和函数是否允许 | `reject` |
| 泄漏防护 | 是否用了未来字段、label、forward return 等泄漏信息 | `reject` |
| 表达复杂度 | 表达式嵌套是否过深 | `reject` |
| 输出健康度 | 因子值是否全空、全常数、近似常数、NaN / inf 过多 | `reject` |
| 样本可用性 | 覆盖率、有效交易日、横截面股票数是否够用 | `reject` |

### 6.2 Gate0 字段和红线

| 中文含义 | 字段 | 红线 | 失败原因建议 |
| --- | --- | --- | --- |
| 表达式解析结果 | `expression_parse_status` | 解析失败 | `expression_parse_failed` |
| 字段 / 函数白名单结果 | `expression_allowlist_status` | 使用非白名单字段或函数 | `expression_not_allowed` |
| 泄漏检查结果 | `leakage_check_status` | 使用未来数据、label、forward return | `leakage_detected` |
| 表达式树深度 | `expression_depth` | `> 8` | `expression_too_deep` |
| 有限值覆盖率 | `coverage_mean` | `< 0.70` | `low_coverage` |
| 有效交易日数量 | `effective_trade_days` | `< 120` | `insufficient_trade_days` |
| 每日有效股票数中位数 | `median_valid_stock_count` | `< 100` | `insufficient_cross_section` |
| 有限值比例 | `finite_ratio` | `< 0.99` | `too_many_nan_or_inf` |
| 因子值标准差 | `std` | `<= 1e-12` | `constant_or_near_constant` |
| 有限值唯一值比例 | `unique_ratio` | `< 0.01` | `low_unique_ratio` |

说明：

- `expression_depth` 是 v1 唯一进入 hard gate 的表达复杂度指标；叶子节点深度为 1，每多一层函数或 operator 嵌套深度 +1。
- `node_count`、operator 数量、rolling window 分布不在 screening v1 计算，也不写入 screening 产物。
- 当前项目已有 `effective_trade_days` 命名，区块3 v1 沿用这个字段，不再新增同义的 `valid_trade_days`。
- 阈值必须来自配置和 run manifest，不直接写死进代码。

## 7. Gate 1：预测力门

目的：判断候选在固定预测周期上是否具备基本横截面预测力。Gate1 不看交易收益、不看换手、不做相关性去重。

### 7.1 检查逻辑分类

| 分类 | 要回答的问题 | 失败后的处理 |
| --- | --- | --- |
| 预测周期统一 | 是否只用固定 `5d` forward return | 周期不匹配时不进入 admission |
| 方向统一 | 候选声明的方向是否能把指标解释成“越大越好” | 方向缺失或非法时 `reject` |
| 预测力均值 | RankIC 均值是否足够强 | `reject` |
| 预测力稳定性 | RankIC IR 是否足够稳定 | `reject` |

### 7.2 Gate1 字段和红线

| 中文含义 | 字段 | 红线 | 失败原因建议 |
| --- | --- | --- | --- |
| 入库评价周期 | `admission_horizon` | 必须等于配置值，初始化为 `5d` | `invalid_admission_horizon` |
| 预期方向 | `expected_direction` | 只能是 `positive` 或 `negative` | `invalid_expected_direction` |
| 方向化 RankIC 均值 | `directional_rankic_mean` | `< 0.04` | `weak_rankic_mean` |
| 方向化 RankIC IR | `directional_rankic_ir` | `< 0.50` | `weak_rankic_ir` |

方向化口径：

```text
direction_sign = 1 if expected_direction == "positive" else -1
directional_metric = direction_sign * raw_metric
```

说明：

- Block3 v1 固定一个 `admission_horizon`，默认用 `5d`；不允许从多个 horizon 里选择 `best_horizon` 作为入库依据。
- Gate1 不计算、不记录 Pearson IC、原始 IC / ICIR、RankIC positive ratio 或其他 horizon 指标。
- FactorMiner 的 A 股示例使用 `IC >= 0.04` 和 `max_corr < 0.5`；这里采用相近量级作为初始化配置。
- `metric_compute_policy = "staged"` 表示只按 Gate 需要分阶段计算指标；未参与 Gate 判定的诊断指标不在 screening v1 计算。

## 8. Gate 2：相关性去重与 Replacement

目的：避免把同一类信号的变体重复收入研究因子库，同时识别“和旧因子很像但明显更好”的替换候选。

### 8.1 检查逻辑分类

| 分类 | 要回答的问题 | 失败后的处理 |
| --- | --- | --- |
| 比较范围一致性 | 新旧因子是否处在同一数据口径下 | 不比较，记录范围不一致 |
| 样本重叠充分性 | 对齐后的共同样本是否足够多 | 不判 duplicate，只记录 overlap 不足 |
| batch 内去重 | 本轮候选之间是否重复 | 保留排序更靠前者，其余 `duplicate` |
| library 去重 | 新候选是否和已入库因子过于相似 | `duplicate` 或进入 replacement 判断 |
| replacement 判断 | 新候选是否明显强于唯一命中的旧因子 | 通过后继续 Gate3，失败则 `duplicate` |

### 8.2 相关性字段和红线

| 中文含义 | 字段 | 红线 / 规则 | 失败或分流原因建议 |
| --- | --- | --- | --- |
| 数据源和样本口径 | `source_universe_key`、`forward_return_definition`、`sample_protocol_hash` | 必须一致才比较 | `correlation_scope_mismatch` |
| 对齐样本数 | `correlation_overlap_count` | `< 10000` 时不判重复 | `insufficient_correlation_overlap` |
| batch 内最大绝对 Spearman 相关 | `max_abs_corr_to_batch` | `>= 0.50` 判本轮重复 | `batch_duplicate` |
| library 最大绝对 Spearman 相关 | `max_abs_corr_to_library` | `>= 0.50` 进入 duplicate / replacement 分流 | `library_duplicate_or_replace` |
| 高相关旧因子数量 | `correlated_factor_count` | replacement 必须等于 `1` | `multiple_correlated_factors` |
| 命中的旧因子 | `matched_factor_id` | 仅用于记录和 replacement 比较 | 无命中则为空 |

相关性计算口径：

- 输入是预处理后的 factor exposure。
- 按 `(trade_date, ts_code)` 对齐样本。
- 缺失值不填充，只在双方同时有效的样本上计算。
- 使用绝对 Spearman 相关性，字段口径为 `max_abs_spearman_corr`。

### 8.3 Replacement 字段和红线

| 中文含义 | 字段 | 红线 / 规则 | 失败或分流原因建议 |
| --- | --- | --- | --- |
| 优劣比较主指标 | `replacement_quality_metric` | 初始化为 `directional_rankic_mean` | 配置缺失则 reject 配置 |
| 新因子绝对质量 | `replacement_absolute_quality_min` | 新因子质量必须 `>= 0.10` | `replacement_quality_too_low` |
| 新因子相对提升 | `replacement_improvement_ratio_min` | 新因子至少是旧因子 `1.30x` | `replacement_improvement_too_small` |
| 高相关旧因子命中数 | `correlated_factor_count_required` | 必须等于 `1` | `replacement_ambiguous_match` |

说明：

- `replace_candidate` 不等于自动替换，只进入 `replacement_queue` 等待后续确认。
- 如果一个候选同时高度相关多个旧因子，v1 不自动 replacement，避免误替换一组因子。
- replacement 不使用单一 `prediction_score` 做 admission 判断；如需排序，只按配置中的 `tie_break_order` 做辅助决策。

## 9. Gate 3：轻量经济含义门

目的：防止 RankIC 看起来不错，但经济含义明显不可用。Gate3 不是完整回测，不计算生产级成本、容量、执行规则。

这一步只对通过 Gate0、Gate1，且 Gate2 没有 duplicate 硬停的候选运行，节约算力。

### 9.1 检查逻辑分类

| 分类 | 要回答的问题 | 失败后的处理 |
| --- | --- | --- |
| 收益稳定性 | 多空收益是否稳定为正 | `reject` |
| 分层结构 | 因子分层收益是否大致单调 | `reject` |
| 交易可行性 | 高分组持仓集合是否过度换手 | `reject` |

### 9.2 Gate3 字段和红线

| 中文含义 | 字段 | 红线 | 失败原因建议 |
| --- | --- | --- | --- |
| 方向化多空收益 Sharpe | `directional_long_short_sharpe` | `< 1.00` 或非有限数 | `weak_long_short_sharpe` |
| 多空收益有效交易日 | `long_short_effective_days` | `< 50` | `insufficient_long_short_days` |
| 分层单调性得分 | `monotonicity_score` | `< 0.30` | `weak_monotonicity` |
| 高分组换手代理 | `turnover_proxy` | `> 0.70` | `excessive_turnover` |

说明：

- `directional_long_short_sharpe` 用方向化多空收益序列计算，用来判断单位波动下的收益是否足够强。
- `long_short_effective_days` 是方向化多空收益序列里的有效交易日数量；Gate0 已经前置拦截原始因子样本不足，Gate3 只处理通过前置条件后仍出现的多空收益序列样本不足。
- Sharpe 计算口径：`daily_directional_long_short = direction_sign * (top_quantile_return - bottom_quantile_return)`；`annualization_factor = sqrt(252 / horizon_days)`；`directional_long_short_sharpe = mean(daily_directional_long_short) / std(daily_directional_long_short) * annualization_factor`。
- `monotonicity_score` 衡量分层收益是否大致随因子排序单调变化。
- `turnover_proxy` 衡量高分组持仓集合变化幅度，用来挡掉极端高换手候选。
- Gate3 不计算、不记录 spread、bucket returns、完整回测 Sharpe 或其他分层收益诊断；这些留给后续 analysis / production gate。
- `replace_candidate` 也必须通过 Gate3；如果 Gate3 fail，最终仍是 `reject`，不进入 `replacement_queue`。

## 10. Admission Decision

最终状态流转：

| 触发条件 | 最终决策 | 说明 |
| --- | --- | --- |
| Gate0 任一 hard gate 失败 | `reject` | 基础质量不合格，不继续后续计算 |
| Gate1 预测力失败 | `reject` | 固定 5d 预测力不足 |
| Gate2 判定重复且不满足 replacement | `duplicate` | 不进入研究因子库 |
| Gate2 满足 replacement，Gate3 失败 | `reject` | 更强但经济 sanity 不过关 |
| Gate2 满足 replacement，Gate3 通过 | `replace_candidate` | 进入 replacement queue，等待后续确认 |
| 不重复且 Gate3 通过 | `admitted` | 写入研究因子库 |

注意：`replace_candidate` 不等于 `admitted`，也不自动替换旧因子。
## 11. 产物

区块3产物分三类：全量评估日志、研究因子库、替换候选队列。三类产物的职责不同，字段也按职责分组，不把所有字段混在一个无解释列表里。

### 11.1 `evaluation_log`

用途：记录所有候选，包括 `reject`、`duplicate`、`replace_candidate`、`admitted`。它是排查失败原因和复盘筛选过程的主日志。

| 分类 | 字段 | 中文解释 |
| --- | --- | --- |
| 候选身份 | `candidate_id` | 本次候选因子的唯一标识 |
| 候选身份 | `expression` | 因子表达式原文 |
| 候选身份 | `category` | 候选所属研究方向或因子类别 |
| 候选解释 | `economic_rationale` | 因子的经济含义说明，由候选生成方 / Agent 提供，Block3 只记录不打分 |
| 运行追溯 | `run_id` | 本次筛选运行编号 |
| 数据追溯 | `source_universe_key` | 使用的股票池 / 标的范围 |
| 数据追溯 | `forward_return_definition` | forward return（未来收益标签）的定义 |
| 样本追溯 | `sample_protocol_id` | 样本协议编号 |
| 样本追溯 | `sample_protocol_hash` | 样本协议内容哈希，用于复现 |
| 评价口径 | `admission_horizon` | 入库评价周期，v1 初始化为 `5d` |
| 评价口径 | `preprocess_config_hash` | 预处理配置哈希 |
| 评价口径 | `engine_version` | 计算引擎版本 |
| Gate 状态 | `gate0_status` | 基础质量门结果 |
| Gate 状态 | `gate1_status` | 预测力门结果 |
| Gate 状态 | `gate2_status` | 相关性 / replacement 门结果 |
| Gate 状态 | `gate3_status` | 轻量经济含义门结果 |
| 最终决策 | `decision` | 最终状态：`admitted`、`reject`、`duplicate`、`replace_candidate` |
| 最终决策 | `reject_reason` | 被拒绝或分流的主要原因 |
| Gate 指标 | `metrics` | 只包含 Gate 判定直接使用的指标 |
| 去重信息 | `matched_factor_id` | 命中的已入库旧因子，没有命中则为空 |
| Agent 反馈 | `agent_note` | 给 Agent 的简短可读反馈 |
| 时间追溯 | `created_at` | 记录创建时间 |

`metrics` 只能包含 Gate0-Gate3 判定直接使用的字段；不得写入 Pearson IC、positive ratio、spread、node_count、非 Gate 的 Sharpe 变体或其他诊断型附加指标。

### 11.2 `research_factor_library`

用途：只记录 `admitted` 因子。它是后续研究因子资产库的输入，不保存失败候选。

| 分类 | 字段 | 中文解释 |
| --- | --- | --- |
| 因子身份 | `factor_id` | 入库后的研究因子唯一标识 |
| 因子身份 | `expression` | 因子表达式原文 |
| 因子身份 | `expression_hash` | 表达式哈希，用于识别重复表达式 |
| 因子身份 | `category` | 因子类别或研究方向 |
| 因子解释 | `economic_rationale` | 入库因子的经济含义说明，用于后续人工复核和 Agent 复盘 |
| 来源追溯 | `source_run_id` | 产生该因子的筛选运行编号 |
| 数据追溯 | `source_universe_key` | 使用的股票池 / 标的范围 |
| 数据追溯 | `forward_return_definition` | forward return 定义 |
| 样本追溯 | `sample_protocol_id` | 样本协议编号 |
| 样本追溯 | `sample_protocol_hash` | 样本协议内容哈希 |
| 评价口径 | `admission_horizon` | 入库评价周期 |
| 评价口径 | `preprocess_config_hash` | 预处理配置哈希 |
| 评价口径 | `engine_version` | 计算引擎版本 |
| Gate1 指标 | `prediction_metrics` | 只保存预测力门使用的指标 |
| Gate2 指标 | `correlation_profile` | 只保存去重 / replacement 使用的相关性字段 |
| Gate3 指标 | `light_trading_profile` | 只保存轻量经济含义门使用的指标 |
| 入库决策 | `admission_decision` | 入库决策，正常应为 `admitted` |
| 入库决策 | `admission_reason` | 入库原因摘要 |
| 时间追溯 | `created_at` | 记录创建时间 |

`prediction_metrics`、`correlation_profile`、`light_trading_profile` 也只保存对应 Gate 判定字段，不承担研究诊断报告职责。

`economic_rationale` 是解释字段，不参与 Gate 判定；缺失时可以为空，但不能由 Block3 根据指标自动编造。

### 11.3 `replacement_queue`

用途：记录 `replace_candidate`。它不自动替换旧因子，只把候选交给后续区块或人工确认。

| 分类 | 字段 | 中文解释 |
| --- | --- | --- |
| 替换候选身份 | `candidate_factor_id` | 新候选因子编号 |
| 被替换对象 | `matched_factor_id` | 与新候选高度相关的旧因子编号 |
| 新因子指标 | `candidate_metrics` | 新候选用于 replacement 判断的 Gate 指标 |
| 旧因子指标 | `existing_metrics` | 被命中旧因子的对应指标 |
| 优劣差异 | `metrics_delta` | 新旧因子的质量差异和提升倍数 |
| 替换原因 | `replacement_reason` | 为什么进入 replacement queue |
| 队列状态 | `status` | 后续处理状态，例如 pending / approved / rejected |
| 时间追溯 | `created_at` | 记录创建时间 |

## 12. Agent 反馈

区块3不仅输出 gate 结果，也要给 Agent 可读反馈。反馈字段按“规模、状态、失败模式、下一步建议”分组。

| 分类 | 字段 / 内容 | 中文解释 |
| --- | --- | --- |
| 规模统计 | 本轮候选数 | 本轮一共评估了多少候选 |
| Gate0 统计 | 通过基础检查数量 | 有多少候选通过基础质量门 |
| Gate1 统计 | 通过预测力筛选数量 | 有多少候选具备基本 5d 预测力 |
| Gate2 统计 | duplicate 数量 | 有多少候选因为重复被分流 |
| Gate2 统计 | replace_candidate 数量 | 有多少候选进入替换队列 |
| 最终入库 | admitted 数量 | 有多少候选进入研究因子库 |
| 失败解释 | 主要 reject reason | 本轮最常见的拒绝原因 |
| 成功样本 | 表现最好的 admitted 因子 | 给 Agent 参考的成功案例 |
| 失败模式 | 最常见失败模式 | 给 Agent 规避的方向 |
| 下一步建议 | 下一轮可尝试方向 | Agent 下一轮生成候选的建议 |

Agent 的职责：解释指标、总结成功模式、总结失败模式、提出下一轮候选方向。

Agent 不负责：修改 gate 规则、绕过 hard gate、直接写入生产因子库。

## 13. 与区块1、区块2、区块4、区块5的边界

### 13.1 区块1：compute engine v1

compute engine v1 是 Gate 指标的唯一计算提供方。

| 分类 | compute engine v1 需要提供 | 中文解释 |
| --- | --- | --- |
| 表达式检查 | `expression_parse_status`、`expression_allowlist_status`、`leakage_check_status`、`expression_depth` | 解析、白名单、泄漏和表达式树深度 |
| 因子暴露 | 固定样本上的 factor exposure | 后续 RankIC、相关性、分层和换手都基于同一暴露结果 |
| Gate0 输出健康度 | `coverage_mean`、`effective_trade_days`、`median_valid_stock_count`、`finite_ratio`、`std`、`unique_ratio` | 基础质量门使用的全部健康度字段 |
| Gate1 预测力 | `directional_rankic_mean`、`directional_rankic_ir` | 固定 `admission_horizon` 的方向化 RankIC 结果 |
| Gate2 相关性 | `max_abs_corr_to_batch`、`max_abs_corr_to_library`、`correlation_overlap_count`、`correlated_factor_count`、`matched_factor_id` | batch 内去重、library 去重和 replacement 使用的相关性结果 |
| Gate3 经济含义 | `directional_long_short_sharpe`、`long_short_effective_days`、`monotonicity_score`、`turnover_proxy` | 轻量交易 sanity check 的四项结果 |

如果当前 compute engine v1 已有底层能力但输出字段不完整，应在 compute engine v1 增加 screening-facing output adapter。  
如果底层能力也没有，例如 `turnover_proxy`、`long_short_effective_days` 或 `directional_long_short_sharpe`，也应在 compute engine v1 内补齐，不能放到区块3里临时计算。

### 13.2 区块2：data sample layer

区块2是 Gate 数据和样本口径的唯一提供方。

| 分类 | 区块2需要提供 | 中文解释 |
| --- | --- | --- |
| 数据读取 | `DatasetBundle` / panel / forward returns | 统一读取候选评价所需的行情和未来收益 |
| 样本协议 | `sample_protocol_id`、`sample_protocol_hash`、slice roles | 固定本次 screening 使用哪些日期和样本切片 |
| 评价视图 | `ScreeningSampleView` | 把 panel、forward returns、样本日期、股票池口径整理成 Block3 可调用的输入 |
| 追溯字段 | `source_universe_key`、`forward_return_definition`、observed date range | 保证 Gate2 相关性比较在同一数据口径下发生 |

如果 Block3 需要某个数据字段或样本切片，但区块2没有提供，优先在区块2新增接口；Block3 不从 manifest 或 parquet 里自行拼装推断。

### 13.3 区块4：因子资产库
区块4负责把区块3产物变成可治理的因子资产。

| 分类 | 区块4负责内容 | 中文解释 |
| --- | --- | --- |
| 产物管理 | `evaluation_log` | 管理全量评估日志 |
| 产物管理 | `research_factor_library` | 管理研究因子库 |
| 产物管理 | `replacement_queue` | 管理替换候选队列 |
| 身份管理 | `factor_id` | 生成和维护稳定因子编号 |
| 去重追溯 | `expression_hash` | 维护表达式哈希和重复识别信息 |
| 来源链路 | `lineage` | 记录因子来自哪些候选、运行和替换关系 |
| 状态治理 | 状态变更记录 | 记录入库、替换、废弃、人工复核等状态变化 |

区块3只定义写入规则和所需字段，不负责资产库生命周期治理。

### 13.4 区块5：Agent 挖因子 Loop

区块5负责编排 Agent 如何使用区块3反馈继续生成候选。

| 分类 | 区块5负责内容 | 中文解释 |
| --- | --- | --- |
| 输入编排 | 研究方向输入 | 把研究主题传给 Agent |
| 候选生成 | Agent 生成候选 | 生成下一批表达式或变体 |
| 筛选调用 | 调用区块3评估 | 把候选交给 Gate0-Gate3 |
| 反馈读取 | 读取区块3反馈 | 理解通过、失败、重复、替换原因 |
| 迭代策略 | 生成下一轮候选 | 根据反馈调整搜索方向 |
| 停止控制 | 停止条件 | 决定何时结束一轮或一组实验 |

区块3不决定 Agent 大循环怎么结束。

## 14. 第二轮 Production Gate

以下内容不进入区块3 v1，但应作为后续生产筛选层。这里单独分类，是为了避免把生产回测字段误塞进 screening 产物。

| 分类 | 后续生产指标 | 中文解释 |
| --- | --- | --- |
| 样本外稳健性 | OOS / walk-forward | 样本外和滚动前推验证 |
| 时间切片 | recent 3y / 5y / 10y profile | 不同近端窗口的表现画像 |
| 完整回测 | 完整 long-short backtest | 正式多空组合回测 |
| 绩效风险 | 正式 Sharpe / drawdown / hit ratio | 收益风险和胜率指标 |
| 交易成本 | turnover / cost sensitivity | 换手、交易成本和成本敏感性 |
| 条件切片 | 行业 / 市值 / regime 切片 | 不同市场环境和股票属性下的表现 |
| 组合价值 | 组合贡献 | 加入组合后的边际贡献 |
| 生产去重 | 与生产因子库相关性 | 和生产库已有因子的相似度 |
| 生产替换 | 生产 replacement | 生产级替换决策 |

这些指标应成为因子的交易画像，用于判断：

```text
screened_factor -> tradable_candidate -> production_factor
```
## 15. 验收标准

- compute engine v1 是 Gate0-Gate3 指标的唯一计算提供方；区块3不得新增自己的 metric calculator。
- 区块2是数据读取、样本协议、forward return 和评价切片的唯一提供方；区块3不得自行推断缺失数据视图。
- 区块3发现缺少指标或数据时，应在执行计划中把缺口分配给区块1或区块2，而不是在区块3内临时补算。

区块3 v1 完成后，应满足：

- 候选因子可以经过统一 gate 流程得到四种决策：`admitted`、`reject`、`duplicate`、`replace_candidate`。
- 所有候选都进入 `evaluation_log`。
- Screening 产物只记录 Gate 判定字段，不写诊断型附加指标。
- 只有 `admitted` 进入 `research_factor_library`。
- 高相关但更好的候选进入 `replacement_queue`，不自动替换。
- Gate 0 使用 `expression_depth <= 8`、`coverage_mean >= 0.70`、`effective_trade_days >= 120`、`median_valid_stock_count >= 100`、`finite_ratio >= 0.99`、`std > 1e-12`、`unique_ratio >= 0.01` 的初始化配置。
- Gate 1 使用配置化 `screening_gate_profile`，不在代码或规格正文中固化最终 admission 阈值。
- 初始化 profile 可参考 FactorMiner 量级：`directional_rankic_mean >= 0.04`、`directional_rankic_ir >= 0.50`、`library_corr_threshold = 0.50`。
- Gate 2 相关性比较必须在同一 `source_universe_key`、`forward_return_definition`、`sample_protocol_hash` 下对齐样本。
- duplicate / replacement 的优劣比较使用配置化 `tie_break_order` 和 `replacement_quality_metric`，不使用 admission 专用 `prediction_score`。
- Gate 3 只做轻量经济含义 pass/fail，不做完整生产回测，不设 warning 状态。
- Gate 3 使用 `directional_long_short_sharpe >= 1.00`、`long_short_effective_days >= 50`、`monotonicity_score >= 0.30`、`turnover_proxy <= 0.70` 的初始化配置。
- `replace_candidate` 必须通过 Gate 3，否则最终仍应 `reject`。
- 不做 top-k 强行入库。
- 不做 `watch` 状态。
- Agent 可以读取结构化反馈，但不能绕过 gate。
- 所有结果可以追溯到 `run_id`、`source_universe_key`、`forward_return_definition`、`sample_protocol_hash`、`preprocess_config_hash` 和 `engine_version`。

## 16. 最终定义

区块3 v1 的本质是：

```text
用 FactorMiner-style 的强 gate 建一个干净的研究因子库；
用轻量交易 sanity check 保持交易目标不跑偏；
把完整交易画像留给第二轮 production gate。
```
