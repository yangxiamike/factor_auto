# Factor Autoresearch 代码框架重构 Spec

## 1. 目标

当前 `factor_autoresearch/` 已经能稳定跑通 sandbox v1，但代码组织上还有三个明显问题：

- 有稳定上下文的对象仍在每个方法里反复传 `config`、路径和 run 参数。
- `calculator.py` 同时承担 DSL 安全校验、operator 实现和因子计算。
- `evaluate.py` 同时承担主流程编排和 artifact / registry 落盘细节。

本次重构只调整代码结构，不改变以下合同：

- candidate JSONL schema
- config TOML schema
- dataset / run artifact 结构
- metrics 公式
- gate 规则
- registry append-only 语义
- CLI 命令名和主要参数

## 2. 设计原则

### 2.1 有稳定上下文的东西变成实例

- `FactorCalc(config)`
- `DataLoader(config, dataset_path)`
- `Evaluator(context)`
- `ArtifactWriter(context)`
- `RegistryWriter(path)`

### 2.2 纯计算规则继续保持函数

- 具体 operator 实现
- `preprocess_factor`
- `compute_candidate_metrics`
- `apply_candidate_gate`

### 2.3 不提前引入抽象基类

当前没有第二套 calculator / evaluator / loader 实现。

因此本轮不引入：

- `BaseCalculator`
- `BaseEvaluator`
- `BaseLoader`
- 复杂继承层

## 3. 目标模块结构

```text
factor_autoresearch/
├── context.py
├── operators.py
├── expression.py
├── calculator.py
├── data_loader.py
├── artifacts.py
├── registry.py
├── evaluate.py
├── preprocess.py
├── metrics.py
├── gate.py
└── cli.py
```

## 4. 核心对象

### `EvaluationContext`

保存一次 evaluate run 的稳定上下文：

- `config`
- `dataset_path`
- `candidates_path`
- `registry_path`
- `runs_dir`
- `run_id`
- `verbose`
- `quiet`

并提供：

- `run_dir`
- `manifest_path`
- `summary_path`
- `logs_dir`
- `factors_dir`
- `results_dir`

### `operators.py`

职责：

- 注册 DSL 支持的 operator
- 封装每个 operator 的纯计算实现

支持的 operator：

- `abs`
- `log`
- `delay`
- `ts_mean`
- `ts_std`
- `ts_delta`
- `ts_return`
- `ts_rank`
- `cs_rank`
- `cs_zscore`

### `expression.py`

职责：

- AST parse
- 字段白名单校验
- 函数白名单校验
- operator registry 存在性校验
- window 白名单校验
- 参数个数校验
- complexity score
- inferred lookback

### `calculator.py`

职责：

- 成为 DSL 的薄入口
- 调用 `ExpressionValidator`
- 调用 `OPERATOR_REGISTRY`

目标 API：

```python
calc = FactorCalc(config)
calc.validate_candidate(candidate)
calc.complexity_score(candidate)
calc.calculate(candidate, dataset)
```

### `data_loader.py`

职责：

- 固定上下文后加载 dataset
- 校验 manifest / 列结构 / 主键唯一性

目标 API：

```python
dataset = DataLoader(config=config, dataset_path=dataset_path).load()
```

### `ArtifactWriter`

职责：

- 创建 run 目录
- 写 `manifest.json`
- 写 `summary.md`
- 写 `candidate_results.jsonl`
- 写 `metrics.parquet`
- 写 `ic_series.parquet`
- 写 `factors/{candidate_id}.parquet`

### `RegistryWriter`

职责：

- 只写通过 gate 的候选
- 保持 append-only
- 按 `(candidate_id, dataset_id, run_id)` 做幂等去重

### `Evaluator`

职责：

- 读取 dataset
- 读取 candidates
- 串联 validate -> calculate -> preprocess -> metrics -> gate
- 隔离单候选运行异常
- 调用 `ArtifactWriter` 和 `RegistryWriter`

## 5. 验收标准

重构完成后应满足：

1. CLI 命令保持兼容
2. `runs/{run_id}` artifact 结构不变
3. registry append-only 语义不变
4. metrics / gate 结果与重构前一致
5. `FactorCalc` / `DataLoader` / `Evaluator` 都有明确初始化上下文
6. `operators.py` 可单测每个 operator
7. `expression.py` 可单测 DSL 静态校验
8. 全量测试和 `ruff` 通过
