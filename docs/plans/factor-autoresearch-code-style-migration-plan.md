# Factor Autoresearch 代码风格迁移总计划

## 1. 计划目标

把 `operators.py` 重构过程中沉淀出的写法，迁移到项目中其他核心模块。

这次迁移的目标不是重写业务逻辑，而是统一代码的阅读体验：

- 模块开头先说明职责
- 文件内部按职责分区块
- 类和函数补充简短中文 docstring
- 纯计算函数尽量表达“怎么算”
- 防御性代码集中在边界层
- 流程型代码突出主路径，细节留在辅助函数里

## 2. 已有样板

当前参考样板是：

```text
factor_autoresearch/operators.py
factor_autoresearch/calculator.py
factor_autoresearch/expression.py
```

其中 `operators.py` 的风格作为主要样板：

- 模块级说明
- 命名约定
- `# ============== 分区标题 ==============`
- 函数 docstring 使用 `功能名: 一句话说明`
- 注册表集中放在文件底部

## 3. 迁移原则

### 3.1 先整理阅读结构，再考虑重构

第一轮迁移以阅读结构为主：

- 补模块说明
- 补函数 / 类 docstring
- 补分区标题
- 清理明显影响阅读的变量名和重复防御

不主动做大规模行为重构。

### 3.2 防御代码放在边界层

应该保留防御代码的地方：

- CLI 参数入口
- JSON / TOML / Parquet 读取
- 文件写入和删除
- manifest / schema 校验
- 空数据、缺字段、重复主键
- 除零、零标准差、空截面等数学边界

应该减少防御代码的地方：

- 已经由上游 validator 保证的内部函数
- 纯计算函数里重复校验同一件事
- 为了统一接口而加入的无用参数
- 挤压主逻辑阅读的兜底分支

### 3.3 命名按场景选择

短命名适合：

- 算子
- 数学计算
- 局部窗口函数

例如：

```text
x, y, d, p, g, v
```

长命名适合：

- CLI
- IO
- evaluate 主流程
- 跨函数传递的重要对象

例如：

```text
candidate
dataset
config
metrics_result
registry_path
```

## 4. 第一批迁移范围

第一批聚焦“纯计算 / 规则函数”。

这些模块逻辑已经相对成型，适合直接套用 `operators.py` 的风格。

```text
factor_autoresearch/preprocess.py
factor_autoresearch/metrics.py
factor_autoresearch/gate.py
factor_autoresearch/data_loader.py
factor_autoresearch/candidates.py
```

### 4.1 `preprocess.py`

定位：

- 因子预处理函数集合
- 主要包含 winsorize、zscore、neutralize

迁移动作：

- 增加模块说明
- 按“截面处理 / 中性化 / 预处理入口”分区
- 给每个函数补中文 docstring
- 视情况把内部 `_winsorize` / `_zscore` 注释成“单日截面函数”

注意：

- 不改变 MAD winsorize 口径
- 不改变 z-score 口径
- 不改变中性化回归逻辑

### 4.2 `metrics.py`

定位：

- 计算候选因子的 IC、RankIC、分组收益、单调性和聚合指标

迁移动作：

- 增加模块说明
- 按“指标结果 / 基础辅助函数 / 候选指标计算”分区
- 给 `MetricsResult`、`_safe_spearman`、`_assign_quantiles`、`compute_candidate_metrics` 补 docstring
- 在长函数内部用少量局部段落变量增强阅读

注意：

- 不改指标口径
- 不改 horizon 结果字段
- 不改 `ic_series` 和 `horizon_rows` 输出结构

### 4.3 `gate.py`

定位：

- 根据指标和 gate 配置判断候选因子是否通过

迁移动作：

- 增加模块说明
- 按“结果结构 / 辅助函数 / gate 主逻辑”分区
- 给 `GateDecision`、`_clamp`、`apply_candidate_gate` 补 docstring
- 把评分组件相关变量保持清晰，不强行短命名

注意：

- 不改通过 / 拒绝规则
- 不改 failure bucket
- 不改 `details` 字段

### 4.4 `data_loader.py`

定位：

- 从固定 dataset 目录读取 panel、forward_returns 和 manifest

迁移动作：

- 增加模块说明
- 按“字段合同 / 数据包 / 加载器”分区
- 给 `DatasetBundle`、`DataLoader`、`load` 补 docstring
- 让 manifest 校验、缺列校验、重复主键校验更容易扫读

注意：

- 这是边界层，防御代码应该保留
- 不改索引结构
- 不改必需字段列表

### 4.5 `candidates.py`

定位：

- 读取和校验候选因子 JSONL

迁移动作：

- 增加模块说明
- 按“字段规则 / 数据结构 / 解析函数 / 加载入口”分区
- 给 `Candidate`、`InvalidCandidateRecord`、`_parse_candidate`、`load_candidates`、`load_candidate_batch` 补 docstring
- 保留 forbidden fields、required fields、重复 id 校验

注意：

- 这是外部输入边界，防御代码应该保留
- 不改 JSONL 格式
- 不改 invalid record 输出结构

## 5. 第二批迁移范围

第二批聚焦“IO / 配置 / 运行上下文 / 产物写入”。

这些模块是系统边界层，不适合删太多防御逻辑，主要做说明和分区。

```text
factor_autoresearch/config.py
factor_autoresearch/context.py
factor_autoresearch/artifacts.py
factor_autoresearch/registry.py
factor_autoresearch/cleanup.py
factor_autoresearch/logging_config.py
```

### 5.1 `config.py`

定位：

- 读取 TOML 配置并构造实验配置对象

迁移动作：

- 增加模块说明
- 按“配置结构 / 配置读取 / 配置哈希”分区
- 给各个 dataclass 和加载函数补 docstring

注意：

- 不改配置字段
- 不改 hash 生成逻辑
- 不改 gate config 路径解析逻辑

### 5.2 `context.py`

定位：

- 保存一次 evaluate run 的稳定上下文

迁移动作：

- 统一中文模块说明
- 给属性路径补简短 docstring 或保留清晰 property 名
- 确认职责只限于 run 级路径和配置，不加入业务逻辑

注意：

- 该模块已经比较清楚，只做轻量风格统一

### 5.3 `artifacts.py`

定位：

- 集中写出 run 目录下的 manifest、summary、factor values、results

迁移动作：

- 统一中文模块说明
- 按“目录准备 / 单文件写入 / 结果写入”分区
- 给 `ArtifactWriter` 和各方法补 docstring

注意：

- 不改文件名
- 不改目录结构
- 不改写出格式

### 5.4 `registry.py`

定位：

- append-only candidate registry 写入器

迁移动作：

- 统一中文模块说明
- 按“注册写入 / 去重读取”分区
- 给 `RegistryWriter`、`append_passed`、`_existing_keys` 补 docstring

注意：

- 不改 append-only 语义
- 不改 `(candidate_id, dataset_id, run_id)` 去重逻辑

### 5.5 `cleanup.py`

定位：

- 清理指定 experiment 的 runs 目录和 registry 记录

迁移动作：

- 增加模块说明
- 给 `CleanupReport` 和 `clean_experiment_outputs` 补 docstring
- 保留删除前的路径安全检查

注意：

- 这是高风险边界层，删除保护不能减少
- 不改 dry-run 行为

### 5.6 `logging_config.py`

定位：

- 统一配置控制台和文件日志

迁移动作：

- 增加模块说明
- 给 `configure_logging` 补 docstring
- 保留默认字段，避免日志格式化缺 key

## 6. 暂不纳入前两批的模块

```text
factor_autoresearch/evaluate.py
factor_autoresearch/prepare.py
factor_autoresearch/cli.py
```

原因：

- 这三个是流程型模块
- 文件较长，直接套 docstring 不够
- 后续应单独做“流程主路径整理计划”

建议：

- 前两批完成后，再为这三个模块写第三批计划
- 第三批重点不是注释，而是拆主流程、提炼步骤函数、降低长函数阅读成本

## 7. 执行方式

### 7.1 第一批执行方式

执行前：

```bash
uv run pytest tests/test_preprocess.py tests/test_preprocess_metrics.py tests/test_metrics.py tests/test_gate_registry.py tests/test_data_loader.py tests/test_candidates.py
```

执行动作：

- 每个文件只做风格迁移和轻量整理
- 不改变公开函数签名
- 不改变测试期望

执行后：

```bash
uv run pytest tests/test_preprocess.py tests/test_preprocess_metrics.py tests/test_metrics.py tests/test_gate_registry.py tests/test_data_loader.py tests/test_candidates.py
```

### 7.2 第二批执行方式

执行前：

```bash
uv run pytest tests/test_config.py tests/test_context.py tests/test_artifacts.py tests/test_cleanup.py tests/test_logging_config.py tests/test_gate_registry.py
```

执行动作：

- 补模块说明和 docstring
- 保留 IO / 删除 / 写入相关防御逻辑
- 不改变路径、文件名、JSON 字段和 registry 格式

执行后：

```bash
uv run pytest tests/test_config.py tests/test_context.py tests/test_artifacts.py tests/test_cleanup.py tests/test_logging_config.py tests/test_gate_registry.py
```

## 8. 验收标准

第一批验收：

- 目标文件有模块级说明
- 主要函数和类都有中文 docstring
- 纯计算函数的主逻辑更容易扫读
- 防御代码没有从外部输入边界被误删
- 相关测试通过

第二批验收：

- IO / 配置 / 产物模块说明统一
- 类和方法说明清楚
- 文件路径、落盘格式、registry 语义不变
- 删除和写入保护仍在
- 相关测试通过

总体验收：

```bash
uv run pytest
```

如果全量测试成本较高，至少运行第一批和第二批的专项测试集合。

## 9. 后续沉淀

前两批完成后，再把实际迁移中验证过的规则整理成正式代码规范文档。

建议文档路径：

```text
docs/architecture/factor-autoresearch-code-style.md
```

文档内容应包括：

- 模块说明规范
- 分区标题规范
- docstring 写法
- 命名规范
- 防御代码放置原则
- 纯计算函数写法
- 流程型模块写法
