# Factor Autoresearch Framework v1 设计规格

## 1. 目标

定义 Factor Autoresearch 的框架层合同。

框架层只回答：

- Codex 和 Python tools 如何分工。
- 候选因子如何提交、校验、评价和落盘。
- run artifacts、candidate registry、research notes、memory 的职责边界。
- Agent 能改什么、不能改什么。

框架层不决定某一次实验的 universe、日期范围、特征集合、category、scoring 权重或 gate 阈值。这些内容由 experiment spec 和配置文件决定。

## 2. 文档分层

系统文档分为三层：

```text
framework spec
  定义长期稳定的工具合同、Agent 权限和研究闭环。

experiment spec
  定义某一次 sandbox 实验的 universe、数据、搜索空间、指标和 gate。

implementation plan
  定义如何分阶段实现代码、测试和迁移旧 orchestration。
```

v1 对应文件：

```text
docs/framework/factor-autoresearch-framework-v1.md
docs/experiments/factor-autoresearch-sandbox-v1.md
```

本文件是 framework spec。`factor-autoresearch-sandbox-v1.md` 是第一轮 CSI500 OHLCV sandbox experiment spec。

## 3. 核心分工

### 3.1 Python tools

Python tools 是确定性工具层，负责：

- 从受控数据源生成固定实验数据集。
- 校验候选 JSONL 和 DSL。
- 计算候选因子值。
- 计算评价指标。
- 执行 experiment gate。
- 写出 run artifacts。
- 将通过 gate 的候选追加写入 candidate registry。

Python tools 不负责：

- 生成研究假设。
- 决定下一轮候选方向。
- 总结研究经验。
- 修改 memory。
- 编排多轮研究循环。

### 3.2 Codex

Codex 是 research orchestrator，负责：

- 阅读 experiment spec、memory、research notes 和 run summary。
- 追加手写 DSL 候选因子。
- 调用 Python tools 做 validate 和 evaluate。
- 根据结果写入 research notes。
- 在多轮稳定 insight 出现后更新 memory。

Codex 不负责：

- 直接访问原始数据库。
- 直接计算因子值或指标。
- 修改 evaluator、gate、dataset、universe 或 source data。
- 偷偷改变 experiment spec 来优化结果。
- 将候选直接写入 official factors。

## 4. 最小目录合同

框架要求以下目录和文件语义：

```text
factor_autoresearch/
  AGENTS.md
  program.md
  memory.md
  research_notes.md
  pyproject.toml

  configs/
    {experiment}.toml
    {gate}.toml

  datasets/
    {dataset_id}/
      panel.parquet
      forward_returns.parquet
      manifest.json
      README.md

  factor_autoresearch/
    data_loader.py
    prepare.py
    evaluate.py
    expression.py
    metrics.py
    registry.py
    cli.py

  candidate_factors/
    candidates.jsonl
    registry.jsonl

  official_factors/
    README.md

  runs/
    .gitkeep

  tests/
```

具体 experiment 可以增加配置文件和文档，但不能改变这些核心路径的语义。

## 5. 权限边界

Codex 第一阶段只能追加或维护：

```text
candidate_factors/candidates.jsonl  # 只追加候选记录，不修改或删除既有记录
memory.md
research_notes.md
```

Python CLI 工具可以生成或更新：

```text
runs/{run_id}/**
candidate_factors/registry.jsonl
datasets/{dataset_id}/**  # 仅 prepare-fixed，由维护者运行
```

Codex 不允许修改：

```text
configs/**
datasets/**
factor_autoresearch/**
official_factors/**
candidate_factors/registry.jsonl
pyproject.toml
tests/**
```

候选因子评价阶段不能直接查询原始数据源，只能读取固定 dataset。

## 6. Candidate JSONL 通用合同

候选因子存放在：

```text
candidate_factors/candidates.jsonl
```

每一行是一个 JSON 对象。框架要求的通用字段：

```json
{
  "id": "fa_0001_example",
  "name": "example factor",
  "expression": "<experiment_dsl_expression>",
  "expected_direction": "positive",
  "hypothesis": "因子背后的研究假设。",
  "category": "<experiment_category>",
  "lookback_days": 5,
  "created_at": "2026-06-22",
  "notes": "human readable notes"
}
```

字段语义：

- `id`：候选因子稳定 ID，必须唯一。
- `name`：可读名称。
- `expression`：受限 DSL 表达式。
- `expected_direction`：研究先验，取值为 `positive` 或 `negative`。
- `hypothesis`：经济或微观结构假设。
- `category`：由 experiment spec 定义的受控枚举。
- `lookback_days`：候选声明的最大回看天数。
- `created_at`：日期。
- `notes`：补充说明。

候选记录不能包含：

```text
universe
date_start
date_end
forward_return_definition
gate
data_source
```

这些字段由 experiment spec、配置文件和固定 dataset 决定。

## 7. Expression DSL 通用要求

表达式语言必须是受限、确定性 DSL，不能执行任意 Python 代码。

框架要求：

- 只能引用 experiment spec 允许的字段。
- 只能使用 experiment spec 允许的函数和窗口参数。
- 只能使用明确支持的算术运算。
- parser 必须拒绝未知字段、未知函数和任意代码执行。
- evaluator 必须将非法数值统一处理为缺失值或明确错误。
- expression complexity 必须可确定、可复现。

字段集合、函数集合、窗口参数和 complexity 上限由 experiment spec 定义。

## 8. CLI 合同

### 8.1 准备固定数据集

仅维护者运行：

```bash
fm dataset prepare-fixed \
  --config configs/{experiment}.toml \
  --output datasets/{dataset_id}
```

预期输出：

```text
datasets/{dataset_id}/panel.parquet
datasets/{dataset_id}/forward_returns.parquet
datasets/{dataset_id}/manifest.json
datasets/{dataset_id}/README.md
```

`prepare-fixed` 是数据冻结工具。它可以访问受控数据源，但产出的 dataset 一旦用于评价，就视为不可变输入。

### 8.2 校验候选因子

```bash
fm factor validate \
  --dataset datasets/{dataset_id} \
  --candidates candidate_factors/candidates.jsonl
```

validate 只做静态合法性检查：

- JSONL 能否解析。
- 必需字段是否存在。
- candidate id 是否唯一。
- `expected_direction` 是否合法。
- `category` 是否在 experiment spec 枚举中。
- 表达式能否解析。
- 字段、函数、窗口、lookback 和 complexity 是否合法。

validate 不读取真实因子值，不计算 coverage、IC、RankIC 或其他研究指标。

### 8.3 评价候选因子

```bash
fm factor evaluate \
  --dataset datasets/{dataset_id} \
  --candidates candidate_factors/candidates.jsonl \
  --run-id {run_id}
```

evaluate 只读取固定 dataset、候选 JSONL 和配置文件。

预期 run 输出：

```text
runs/{run_id}/
  manifest.json
  summary.md
  factors/
    {factor_id}.parquet
  results/
    candidate_results.jsonl
    metrics.parquet
    ic_series.parquet
  logs/
    evaluate.log
```

## 9. Validate / Gate 轨迹

框架只保留两层研究轨迹：

1. `validate`：候选是否合法，失败则不能进入评价。
2. `candidate gate`：候选合法且评价完成后，是否值得进入 candidate registry。

run result 状态：

```text
candidate_pass
candidate_fail
invalid
error
```

failure bucket 只保留：

```text
validate_failed
gate_failed
runtime_error
```

含义：

- `validate_failed`：静态候选检查失败。
- `gate_failed`：候选合法且评价完成，但未通过 experiment gate。
- `runtime_error`：工具、数据读取或评价运行时异常。

具体失败原因写入 `details`，不扩展顶层 failure bucket。

## 10. Candidate Registry

candidate registry 存放在：

```text
candidate_factors/registry.jsonl
```

registry 只追加通过 candidate gate 的候选。未通过 gate、无效或运行错误的候选只记录在 run artifacts 中。

registry 记录必须包含：

```json
{
  "factor_id": "fa_0001_example",
  "name": "example factor",
  "category": "<experiment_category>",
  "expression_hash": "sha256:...",
  "expected_direction": "positive",
  "signal_direction": "positive",
  "dataset_id": "dataset_id",
  "run_id": "run_id",
  "status": "candidate_pass",
  "best_horizon": "<experiment_horizon>",
  "best_horizon_score": 1.2,
  "metrics": {},
  "gate": {
    "version": "candidate_gate_v1",
    "passed": true,
    "failed_rules": []
  },
  "artifacts": {
    "summary": "runs/{run_id}/summary.md",
    "factor_values": "runs/{run_id}/factors/fa_0001_example.parquet"
  }
}
```

`signal_direction` 由 best horizon 的原始 RankIC 符号决定：

- `positive`：因子值越高，对应未来收益越高。
- `negative`：因子值越高，对应未来收益越低。

## 11. Research Notes

`research_notes.md` 是当前研究过程的工作笔记。

它可以记录：

- 当前 run 的 intent。
- 候选生成思路。
- run summary 的观察。
- failed ideas。
- 下一轮候选计划。

评价器不读取 `research_notes.md`。

## 12. Memory

`memory.md` 是长期 research memory。

它记录搜索空间层面的长期指导，不记录完整实验日志。只有当多个 run 中反复出现稳定模式，或出现可复用的研究判断时，Codex 才能更新 memory。

memory 应优先记录：

- recommended directions。
- forbidden directions。
- strategic insights。
- transform hints。
- open questions。

memory 不应该记录：

- 完整指标表。
- registry 状态。
- 单个候选的流水账。
- 一次性实验噪音。

## 13. Program 循环

框架层 program 循环：

1. 阅读 experiment spec、memory 和 research notes。
2. 追加一批手写 DSL 候选因子。
3. 运行 `fm factor validate`。
4. 运行 `fm factor evaluate`。
5. 阅读 `runs/{run_id}/summary.md`。
6. 将本轮观察写入 `research_notes.md`。
7. 只有多轮稳定 insight 才写入 `memory.md`。

具体每轮候选数量、允许 category、搜索深度和 gate 由 experiment spec 决定。

## 14. 可复现性要求

同一个 dataset、candidate JSONL、experiment config 和 gate config 重复运行，应产生相同的指标、summary 和 registry-eligible 结果。

run manifest 必须记录：

- dataset id。
- experiment id。
- config hash。
- candidate file hash。
- gate version。
- tool version 或 git commit。
- run id。

## 15. v1 框架非目标

framework v1 不支持：

- 自动因子发现。
- LLM API 调用。
- multi-agent 调度。
- Codex 修改 evaluator 或 gate。
- Codex 动态修改 universe、forward return 或 dataset。
- 写入 official factors。
- production official factor 晋升流程。
