# Factor Autoresearch Code Structure

这份文档说明重构后的 `factor_autoresearch/` 模块边界，帮助后续开发者快速判断“改哪里”和“不要把什么重新缠在一起”。

## 1. 主调用链

```text
CLI
  -> EvaluationContext
  -> Evaluator
     -> DataLoader
     -> FactorCalc
        -> ExpressionValidator
        -> operators
     -> preprocess
     -> metrics
     -> gate
     -> ArtifactWriter
     -> RegistryWriter
```

## 2. 各模块职责

### `context.py`

- 定义一次 evaluate run 的稳定上下文。
- 集中保存 `config`、路径、`run_id`、日志开关。
- 只表达上下文，不承载业务逻辑。

### `operators.py`

- 放 DSL 支持的纯算子实现。
- 每个算子只关心“给定序列、窗口、panel 怎么算”。
- `OPERATOR_REGISTRY` 是受支持 operator 的唯一注册表。

### `expression.py`

- 做 DSL 静态安全校验和元信息分析。
- 负责字段白名单、函数白名单、window 白名单、参数个数校验。
- 输出 `ExpressionMetadata`，包括复杂度和推断回看窗口。

### `calculator.py`

- `FactorCalc` 是 DSL 的薄入口。
- 对外暴露：
  - `validate_candidate(candidate)`
  - `complexity_score(candidate)`
  - `calculate(candidate, dataset)`
- 不再内嵌 operator 细节和大段静态校验逻辑。

### `data_loader.py`

- `DataLoader(config, dataset_path)` 负责加载固定 dataset。
- 校验 `manifest.json`、必需字段和主键唯一性。
- 返回 `DatasetBundle`，不缓存可变大对象。

### `artifacts.py`

- `ArtifactWriter(context)` 负责 run 目录和落盘动作。
- 管理：
  - `manifest.json`
  - `summary.md`
  - `results/*.jsonl|parquet`
  - `factors/*.parquet`

### `registry.py`

- `RegistryWriter(path)` 负责 append-only candidate registry。
- 只写通过 gate 的候选。
- 保持 `(candidate_id, dataset_id, run_id)` 幂等去重。

### `evaluate.py`

- `Evaluator(context)` 串起完整批处理。
- 负责：
  - 载入 dataset
  - 载入 candidates
  - validate -> calculate -> preprocess -> metrics -> gate
  - 单候选异常隔离
  - 调用 artifact / registry writer
- 不再直接处理 operator 实现和 artifact 文件路径拼接细节。

### 继续保持纯函数的模块

- `preprocess.py`
- `metrics.py`
- `gate.py`

这些模块输入输出边界清楚，不需要额外状态对象。

## 3. 为什么没有引入 base class / ABC

当前项目只有一套明确实现：

- 一套 factor DSL calculator
- 一套 dataset loader
- 一套 evaluator 流程

这时先上 `BaseCalculator`、`BaseEvaluator`、`BaseLoader` 只会增加空抽象层。现在更适合的做法是：

- 先把职责拆干净
- 等出现第二套实现时，再决定是否需要 `Protocol` 或更轻的抽象

## 4. 状态化对象 vs 纯函数

状态化对象：

- `EvaluationContext`
- `FactorCalc`
- `DataLoader`
- `ArtifactWriter`
- `RegistryWriter`
- `Evaluator`

纯函数核心：

- operators 中的具体算子
- `preprocess_factor`
- `compute_candidate_metrics`
- `apply_candidate_gate`

这条边界的意思很简单：稳定上下文进对象，可复用计算规则留在函数里。
