# Factor Autoresearch 流程型模块风格迁移计划

## 1. 计划目标

第三批迁移聚焦流程型模块：

```text
factor_autoresearch/evaluate.py
factor_autoresearch/prepare.py
factor_autoresearch/cli.py
```

这批目标不是把流程代码改成算子式短函数，而是让主流程更容易扫读：

- 模块开头说明职责
- 文件内按流程阶段分区
- 类和函数补充中文 docstring
- 长流程拆成小步骤函数
- 保持 CLI、落盘结构、dataset 构造和评估结果语义不变

## 2. 迁移原则

### 2.1 主流程优先清晰

流程型模块的主函数应该像目录一样展示步骤。

例如：

```text
载入数据
载入候选
准备运行目录
逐个评估候选
写出结果
渲染 summary
```

细节逻辑可以下沉到辅助函数，但不为了拆而拆。

### 2.2 防御代码继续保留

这批模块包含 CLI、文件系统、外部 parquet 数据和评估落盘，属于系统边界层。

必须保留：

- dataset manifest 校验
- CLI 参数约束
- source data 目录存在性检查
- universe 为空检查
- candidate 运行异常隔离
- summary / manifest / results 输出字段

### 2.3 不改行为合同

第三批不得改变：

- CLI 命令名称
- CLI 输出 JSON 字段
- run 目录结构
- summary markdown 内容结构
- manifest 字段
- panel / forward_returns 字段
- candidate status / failure_bucket 语义

## 3. `evaluate.py` 迁移计划

### 3.1 模块定位

`evaluate.py` 是评估批处理编排模块。

它负责把这些组件串起来：

- `DataLoader`
- `FactorCalc`
- `preprocess_factor`
- `compute_candidate_metrics`
- `apply_candidate_gate`
- `ArtifactWriter`
- `RegistryWriter`

### 3.2 目标结构

建议分区：

```text
模块说明
import
常量和 logger
结果结构
基础辅助函数
静态校验入口
评估编排器
summary 渲染
```

### 3.3 具体动作

- 给 `EvaluationArtifacts` 补中文 docstring
- 给 `_sha256_file`、`validate_dataset_contract`、`run_static_validation` 补中文 docstring
- 给 `Evaluator` 和所有方法补中文 docstring
- `evaluate_batch` 保持主流程清晰，不改行为
- 可以新增轻量辅助方法：
  - `_invalid_result`
  - `_collect_invalid_records`
  - `_append_metrics_frames`
  - `_write_batch_outputs`
- `evaluate_candidate` 保留运行异常隔离，不展开到批处理层

### 3.4 不允许改变

- `EvaluationArtifacts` 字段
- `run_static_validation` 返回结构
- `evaluate_candidate` 返回结构
- `summary.md` 表格字段
- runtime error 的 `failure_bucket="runtime_error"`
- validate failed 的 `failure_bucket="validate_failed"`

## 4. `prepare.py` 迁移计划

### 4.1 模块定位

`prepare.py` 是固定数据集构造模块。

它负责：

- 从 zer0share 风格 parquet 源数据读取交易日、股票池、行情、复权因子、行业信息
- 构造训练用 panel
- 构造 forward returns
- 写出 dataset 目录

### 4.2 目标结构

建议分区：

```text
模块说明
import
结果结构
日期辅助函数
源数据读取函数
数据集构造函数
写出入口
```

### 4.3 具体动作

- 给 `PreparedDataset` 补中文 docstring
- 给所有 `_read_*` 函数补中文 docstring
- 给 `_build_panel`、`_build_forward_returns`、`prepare_fixed_dataset` 补中文 docstring
- 给 `_yyyymmdd` 补中文 docstring
- 可把 `prepare_fixed_dataset` 内部步骤用局部辅助函数或清晰段落整理
- 保持 DuckDB 查询和字段选择逻辑不变

### 4.4 不允许改变

- 输出文件名：
  - `panel.parquet`
  - `forward_returns.parquet`
  - `manifest.json`
  - `README.md`
- panel 字段和顺序
- forward return 字段命名
- hfq 价格计算逻辑
- 行业成员有效期判断逻辑

## 5. `cli.py` 迁移计划

### 5.1 模块定位

`cli.py` 是 Typer 命令入口。

它负责：

- 解析命令行参数
- 加载 config
- 构造 context
- 调用 dataset prepare / factor validate / factor evaluate / experiment clean
- 输出简洁 JSON 结果

### 5.2 目标结构

建议分区：

```text
模块说明
import
Typer app 定义
默认配置
dataset 命令
factor 命令
experiment 命令
主入口
```

### 5.3 具体动作

- 给模块补中文说明
- 给每个 command 函数补中文 docstring
- 给 `main` 补中文 docstring
- 允许新增小辅助函数用于 JSON 输出，例如 `_echo_json`
- 保持命令名、参数名和输出字段不变

### 5.4 不允许改变

- `dataset prepare-fixed`
- `factor validate`
- `factor evaluate`
- `experiment clean`
- `DEFAULT_CONFIG`
- 各命令输出 JSON 字段
- validate 有 invalid 时返回非 0

## 6. 子代理分工

本批可以并行执行，写入范围必须隔离：

```text
Agent A: factor_autoresearch/evaluate.py
Agent B: factor_autoresearch/prepare.py
Agent C: factor_autoresearch/cli.py
```

每个 agent 只能修改自己负责的文件。

如果发现必须修改共享文件，先停止并回报，不要自行扩大范围。

## 7. 测试计划

执行前后建议运行：

```bash
uv run pytest tests/test_evaluate.py tests/test_cli.py tests/test_prepare.py
```

如果改动影响上下游，再补充：

```bash
uv run pytest tests/test_smoke_run.py tests/test_package_imports.py
```

最终建议至少运行：

```bash
uv run pytest tests/test_evaluate.py tests/test_cli.py tests/test_prepare.py tests/test_smoke_run.py
```

## 8. 验收标准

- 三个模块都有模块级说明
- 顶层类和函数都有中文 docstring
- 文件内部有清晰分区标题
- 主流程比迁移前更容易扫读
- 无公开行为变化
- 相关测试通过

## 9. 完成后沉淀

第三批完成后，可以把前三批验证过的规则整理成正式代码规范：

```text
docs/architecture/factor-autoresearch-code-style.md
```

该规范应覆盖：

- 纯计算模块
- IO 边界模块
- 流程编排模块
- CLI 模块
- 注释和 docstring 风格
