# Factor Autoresearch 代码框架重构实施计划

## 1. 计划目标

把 `factor-autoresearch-code-framework-refactor-spec.md` 拆成可执行工程任务。

目标不是重写系统，而是在保持 sandbox v1 行为不变的前提下，把代码框架整理成更清晰的长期结构：

- 有固定上下文的组件变成实例
- 纯计算规则继续保持函数式
- operator / expression / artifact / registry 职责拆开
- `evaluate.py` 只保留编排职责

## 2. 当前基线

重构前先确认：

```bash
uv run pytest -v
uv run ruff check .
uv run fm factor validate --dataset datasets/sandbox_v1 --candidates candidate_factors/candidates.jsonl --verbose
uv run fm factor evaluate --dataset datasets/sandbox_v1 --candidates candidate_factors/candidates.jsonl --run-id refactor_baseline --verbose
```

并保存这些对照产物：

- `runs/refactor_baseline/summary.md`
- `runs/refactor_baseline/results/candidate_results.jsonl`
- `runs/refactor_baseline/results/metrics.parquet`
- `runs/refactor_baseline/results/ic_series.parquet`

## 3. 目标结构

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
└── ...
```

新增测试：

```text
tests/test_operators.py
tests/test_expression.py
tests/test_context.py
tests/test_artifacts.py
```

## 4. 任务拆分

### Task 1：新增 `operators.py`

- 把 operator 实现从 `calculator.py` 迁出
- 新增 `OperatorSpec`
- 建立 `OPERATOR_REGISTRY`
- 每个 operator 单独测试

验收：

- 时序函数仍按 `ts_code` 分组
- 横截面函数仍按 `trade_date + in_universe` 计算
- 除零 / `log` 非正数 / `inf` 清理行为一致

### Task 2：新增 `expression.py`

- 迁出 `ExpressionValidationError`
- 迁出 `ExpressionMetadata`
- 新增 `ExpressionValidator`
- 保留 complexity / lookback 推断

验收：

- 不依赖 dataset 即可完成静态校验
- attribute / subscript / lambda / comprehension / keyword args 继续拒绝

### Task 3：收窄 `calculator.py`

- `FactorCalc(config, operators=OPERATOR_REGISTRY)`
- `validate_candidate(candidate)`
- `complexity_score(candidate)`
- `calculate(candidate, dataset)`

验收：

- calculator 测试继续通过
- 恶意表达式继续拒绝
- raw factor values 与重构前一致

### Task 4：状态化 `DataLoader`

- `DataLoader(config, dataset_path).load()`
- 返回合同仍是 `DatasetBundle`

验收：

- manifest 校验行为不变
- 缺字段 / 重复主键 / dataset_id mismatch 行为不变

### Task 5：新增 `EvaluationContext`

- 引入 frozen dataclass
- 收住 run 级稳定上下文

验收：

- `context.run_dir == context.runs_dir / context.run_id`
- context 不允许运行中修改

### Task 6：拆 `ArtifactWriter`

- 从 `evaluate.py` 拆出 run 目录和写盘动作

验收：

- `runs/{run_id}` 结构不变
- 文件名和位置不变

### Task 7：引入 `RegistryWriter`

- 把 append-only registry 写入逻辑封装成实例

验收：

- 只写 passed candidate
- append-only 语义不变
- 重复 `(candidate_id, dataset_id, run_id)` 继续拒绝

### Task 8：改造 `Evaluator` 和 CLI 接线

- `Evaluator(context)`
- `CLI` 负责构造 `EvaluationContext`

验收：

- `fm factor validate` 行为不变
- `fm factor evaluate` 行为不变
- summary / metrics / registry / log 路径不变

### Task 9：清理兼容层和文档

- 删除旧签名残留
- 更新 README 中的代码结构说明

### Task 10：新增代码结构文档

- 新增 `docs/architecture/factor-autoresearch-code-structure.md`
- 解释主调用链、模块边界和为什么暂不引入 base class

## 5. 推荐执行顺序

```text
Task 1
-> Task 2
-> Task 3
-> Task 4
-> Task 5
-> Task 6
-> Task 7
-> Task 8
-> Task 9
-> Task 10
```

## 6. 行为一致性检查

重构后需要对比：

- `candidate_results.jsonl`
- `metrics.parquet`
- `ic_series.parquet`
- registry 中对应 run 的 pass 结果

对比原则：

- candidate status 一致
- failure bucket 一致
- pass / fail 一致
- metrics 数值一致或只允许极小浮点误差

## 7. 最终验收

```bash
uv run pytest -v
uv run ruff check .
uv run fm --help
uv run fm factor validate --dataset datasets/sandbox_v1 --candidates candidate_factors/candidates.jsonl --verbose
uv run fm factor evaluate --dataset datasets/sandbox_v1 --candidates candidate_factors/candidates.jsonl --run-id refactor_final --verbose
```

并确认：

- `runs/refactor_final/summary.md` 正常写出
- `runs/refactor_final/logs/evaluate.log` 正常写出
- 每个 candidate 都有最终状态
- registry 只追加 pass
- 代码结构文档存在
