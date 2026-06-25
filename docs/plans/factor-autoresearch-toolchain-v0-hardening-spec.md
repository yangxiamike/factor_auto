# Factor Autoresearch Toolchain v0 Hardening Spec

## 1. 目标

本 spec 定义下一阶段要做的事情：把当前已经能跑通的 factor sandbox，固化成一个可信的因子研究工具链 v0。

当前项目已经具备基础闭环：

```text
候选因子 JSONL
  -> validate
  -> calculate
  -> preprocess
  -> metrics
  -> gate
  -> run artifacts
  -> candidate registry
  -> research notes / memory
```

下一阶段不是马上做自动挖掘，也不是马上做计算加速，而是先把这条链变成一个更可靠的裁判系统。

本阶段完成后，系统应该能稳定回答：

- 一个候选因子是否合法。
- 它的 IC / RankIC / 分层表现是否达到入库标准。
- 它为什么通过或没通过 gate。
- 它在年份、行业、horizon 上是否有明显不稳定。
- 本次 run 用了哪套数据、配置、候选文件和 gate。
- 同一输入重复 evaluate 时，核心结果是否可复现。
- Agent 后续应该如何阅读结果、总结研究、更新 notes 和 memory。

## 2. 非目标

本阶段不做以下事情：

- 不做自动候选生成器。
- 不做 Alpha101 批量导入。
- 不做 mutation / tree search / crossover。
- 不允许 Agent 修改 evaluator、gate、dataset、config、preprocess 或 forward return。
- 不做 official factor 晋升。
- 不把 diagnostics 直接纳入 gate。
- 不做大规模计算优化。

计算优化应放在本阶段之后。原因是：先固化裁判合同和复现测试，再优化计算，才能判断优化是否改变了结果语义。

## 3. 总体设计

Toolchain v0 分为四层：

```text
1. Canonical evaluation
   固定 calculate / preprocess / metrics 的含义。

2. Baseline gate
   用硬约束 + 综合评分决定是否进入 candidate registry。

3. Diagnostics
   输出最小体检报告，用于研究归因，但不参与 gate。

4. Research protocol
   规范 Agent 如何读结果、写 research notes、何时更新 memory。
```

目录结构不做大改。主要新增或扩展：

```text
configs/
  candidate_gate_baseline_v0.toml

factor_autoresearch/
  diagnostics.py
  metrics.py
  gate.py
  evaluate.py
  artifacts.py
  config.py

codex/
  program.md

docs/plans/
  factor-autoresearch-toolchain-v0-hardening-spec.md
```

## 4. Baseline Gate v0

### 4.1 Gate 定位

Baseline gate v0 是真实 candidate registry 的入库门槛。

它不是 production official factor gate，也不是最终交易因子晋升标准。但它也不能太松。进入 `candidate_factors/registry.jsonl` 的因子，至少应该具备基本预测强度、方向稳定性、覆盖率和可解释复杂度。

### 4.2 两层结构

Gate 使用两层结构：

```text
硬约束
  -> 全部通过后
综合评分
  -> 达标后写入 registry
```

硬约束用于过滤明显不合格候选。综合评分用于比较候选是否有足够综合质量。

### 4.3 硬约束

默认 baseline gate v0 使用以下规则：

```text
coverage_mean >= 0.80
effective_trade_days >= 240
complexity_score <= 12

best_horizon_directional_ic_mean >= 0.03
best_horizon_directional_rankic_mean >= 0.03
best_horizon_ic_positive_ratio >= 0.60
best_horizon_rankic_positive_ratio >= 0.60
best_horizon_directional_monotonicity > 0
```

含义：

- `coverage_mean`：因子覆盖率不能太低，否则结果不可比。
- `effective_trade_days`：有效交易日要足够，避免少量样本偶然通过。
- `complexity_score`：早期因子库优先收简单、可解释、可变异的候选。
- `directional_ic_mean`：按 `expected_direction` 调整后，IC 要达到最低预测强度。
- `directional_rankic_mean`：排序能力要达到最低标准。
- `ic_positive_ratio`：IC 方向不能只靠少数日期贡献。
- `rankic_positive_ratio`：排序方向在多数时间要成立。
- `directional_monotonicity`：分层收益方向不能明显反向。

### 4.4 综合评分

综合评分仍使用 IC、RankIC、monotonicity 三个组件：

```text
score = 0.30 * IC_component
      + 0.45 * RankIC_component
      + 0.25 * Monotonicity_component
```

默认要求：

```text
best_horizon_score >= 1.00
```

RankIC 权重略高于 IC，因为当前系统主要服务横截面排序型选股研究。

### 4.5 Gate 输出

每个候选最终输出必须包含：

```text
passed
status
failure_bucket
failed_rules
best_horizon
best_horizon_score
signal_direction
details
```

`failed_rules` 必须是结构化列表，例如：

```json
["directional_ic_mean", "rankic_positive_ratio"]
```

`failure_bucket` 仍保持现有顶层分类：

```text
validate_failed
gate_failed
runtime_error
```

不要为了每种 gate 失败原因扩展顶层 bucket。具体原因进入 `failed_rules` 和 `details`。

## 5. Metrics 增强

### 5.1 新增指标

在现有 IC / RankIC / ICIR / coverage / quantile / monotonicity 基础上，新增：

```text
ic_positive_ratio
rankic_positive_ratio
directional_ic_mean
directional_rankic_mean
directional_monotonicity
```

其中：

- `ic_positive_ratio`：每日 IC 大于 0 的比例。
- `rankic_positive_ratio`：每日 RankIC 大于 0 的比例。
- `directional_*`：根据 candidate 的 `expected_direction` 统一调整方向后的指标。

注意：

- 原始 `ic_mean`、`rankic_mean` 仍然保留。
- `directional_*` 用于 gate 和 summary。
- 原始指标用于审计和后续分析。

### 5.2 Horizon 选择

Gate 仍按 best horizon 选择。

每个 horizon 都计算一组完整指标，然后选取 `horizon_score` 最高的 horizon 作为 gate 判定依据。

不要在本阶段引入多个 horizon 同时必须达标的规则。那属于后续 stability gate 或 promotion gate。

## 6. Diagnostics v0

### 6.1 定位

Diagnostics 是体检报告，不是 gate。

它用于回答：

- 一个因子是不是只在某一年有效。
- 一个因子是不是只靠少数行业贡献。
- 一个因子在 1d / 5d / 20d 哪个 horizon 更稳定。

Diagnostics 结果帮助 Agent 做研究归因，也为未来 gate v1 提供证据，但本阶段不参与 pass/fail。

### 6.2 输出文件

新增输出：

```text
runs/{run_id}/results/diagnostics.parquet
```

### 6.3 第一版切片

第一版只做两个 slice：

```text
year
industry
```

每个 slice 内，对每个 candidate 和 horizon 输出：

```text
candidate_id
slice_type
slice_value
horizon
ic_mean
rankic_mean
ic_positive_ratio
rankic_positive_ratio
coverage_mean
effective_trade_days
```

暂不做：

- quarter。
- size bucket。
- liquidity bucket。
- market regime。
- correlation / novelty。

这些后续可以作为 diagnostics v1/v2 增加。

## 7. Artifacts 和审计

### 7.1 Run Manifest

`runs/{run_id}/manifest.json` 需要记录：

```text
run_id
experiment_id
dataset_id
config_hash
gate_config_hash
gate_version
candidate_file_hash
tool_version
candidate_count
dataset_manifest
preprocess
```

其中 `gate_config_hash` 必须只反映 gate 配置内容，不应依赖本地绝对路径。

### 7.2 Candidate Results

`runs/{run_id}/results/candidate_results.jsonl` 每条记录应包含：

```text
id
status
failure_bucket
failed_rules
best_horizon
best_horizon_score
signal_direction
details
metrics
```

无效候选和 runtime error 也应保持字段结构稳定。无法计算的字段可以为 `null` 或省略在 `details` 中说明，但顶层语义要稳定。

### 7.3 Summary

`runs/{run_id}/summary.md` 应适合人和 Agent 快速阅读。

至少包含：

- 本次 run 的数据、候选数、通过数、失败数、invalid 数、error 数。
- 每个候选的 status、best horizon、score、failed rules。
- 通过候选表。
- 失败原因聚合，例如多少候选卡在 `directional_ic_mean`、多少候选卡在 `rankic_positive_ratio`。
- diagnostics 文件路径。

## 8. Registry 规则

`candidate_factors/registry.jsonl` 只写通过 baseline gate 的候选。

以下候选不得写入 registry：

- validate failed。
- runtime error。
- gate failed。
- diagnostics 体检较弱但 gate 通过与否不受 diagnostics 影响，本阶段仍按 baseline gate 决定。

Registry 保持 append-only，并继续按：

```text
(candidate_id, dataset_id, run_id)
```

做去重。

本阶段不把 diagnostics 字段写入 registry，避免把观察层误认为正式入库标准。

## 9. Agent Research Protocol v0

### 9.1 Agent 权限

Agent 当前阶段是研究员，不是裁判。

允许：

```text
读取 experiment spec / summary / diagnostics / registry
追加 candidate_factors/candidates.jsonl
运行 validate / evaluate
更新 codex/research_notes.md
在多轮稳定后提议更新 codex/memory.md
```

禁止：

```text
修改 evaluator
修改 gate
修改 dataset
修改 config
修改 preprocess
修改 forward return
直接写 registry
单轮结果写入 memory
```

### 9.2 Research Notes 模板

`codex/research_notes.md` 每轮建议按以下结构写：

```text
## Batch {run_id}

### 1. 本轮目标
说明本轮要测试的研究方向。

### 2. 候选来源
说明候选来自上一轮变异、人工假设、经典因子、失败候选修正等。

### 3. 结果总览
记录 evaluated / passed / failed / invalid / error。

### 4. 通过候选共性
总结通过候选集中在哪些 category、horizon、方向和复杂度。

### 5. 失败候选归因
按 failed_rules 总结失败原因。

### 6. 体检观察
阅读 diagnostics，记录 year / industry / horizon 上的明显稳定或不稳定现象。

### 7. 下一轮候选路径
说明下一轮继续扩展什么、停止什么、变异什么。

### 8. Memory 判断
默认不更新 memory。只有多轮重复出现的稳定结论，才提出 memory 更新建议。
```

### 9.3 Memory 标准

`codex/memory.md` 只记录长期稳定 insight。

可以写：

- 多轮反复成立的有效方向。
- 多轮反复失效的方向。
- 可复用的 transform hint。
- 对搜索空间有长期指导意义的经验。

不应该写：

- 单次 run 的流水账。
- 单个候选的完整指标表。
- 尚未复验的一次性结论。
- 为了让某个候选通过而修改规则的想法。

## 10. 测试计划

必须新增或更新测试：

```text
test_config.py
  - gate_config_hash 稳定
  - gate TOML 内容变化时 hash 变化

test_metrics.py
  - ic_positive_ratio 正确
  - rankic_positive_ratio 正确
  - directional 指标按 expected_direction 正确

test_gate_registry.py
  - baseline gate 硬约束生效
  - failed_rules 正确
  - 未通过 gate 不写 registry

test_evaluate.py
  - candidate_results.jsonl 输出 failed_rules
  - manifest 输出 gate_config_hash
  - summary 包含 failed rules 聚合

test_diagnostics.py
  - diagnostics.parquet 生成
  - year / industry slice 字段完整

test_smoke_run.py
  - validate -> evaluate 完整跑通
  - diagnostics 文件存在
  - registry 只包含 candidate_pass
```

验收命令：

```bash
uv run pytest -v
uv run ruff check .
uv run fm factor validate --dataset datasets/sandbox_v1 --candidates candidate_factors/candidates.jsonl --verbose
uv run fm factor evaluate --dataset datasets/sandbox_v1 --candidates candidate_factors/candidates.jsonl --run-id toolchain_v0_smoke --verbose
```

## 11. 实施顺序

建议按以下顺序实施：

```text
1. 新增 baseline gate 配置。
2. 增强 metrics，加入 positive ratio 和 directional metrics。
3. 改 gate，支持硬约束 + score 两层规则。
4. 改 evaluate/artifacts，落 failed_rules、gate_config_hash、summary 聚合。
5. 新增 diagnostics.py 和 diagnostics.parquet 输出。
6. 更新 codex/program.md 的 Agent research protocol。
7. 补测试。
8. 跑 smoke evaluate 验证完整链路。
```

## 12. 后续阶段

本阶段完成后，再进入：

```text
Phase 2: Calculation profiling
  找 calculate / preprocess / metrics 的真实瓶颈。

Phase 3: Calculation optimization
  优化 groupby、neutralization、operator、metrics 计算。

Phase 4: Agent Research Loop v0
  让 Agent 自动生成候选、跑实验、读体检、写 notes。

Phase 5: Gate v1 / Promotion Gate
  再考虑 year stability、industry stability、correlation、novelty。
```

本 spec 的核心原则是：

```text
先可信，再加速。
先固定裁判，再放权 Agent。
先有观察层，再把观察纳入 gate。
```
