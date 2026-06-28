# Block3 Factor Screening Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现区块3因子筛选 Gate v1：固定 `admission_horizon = "5d"`，按 Gate0/Gate1/Gate2/Gate3 得到 `admitted`、`reject`、`duplicate`、`replace_candidate` 四种决策，并写出研究因子库相关 JSONL 产物。

**Architecture:** Block3 是筛选编排层，不是指标计算层，也不是数据样本层。Block3 只调用区块2提供的数据 / 样本视图，以及区块1 compute engine v1 提供的 Gate 指标输出；缺什么数据就让区块2补接口，缺什么指标就让 compute engine v1 补输出。

**Tech Stack:** Python 3.11+、pandas、numpy、pytest、ruff、现有 `factor_autoresearch` dataset / sample protocol / candidate / config / compute_v1 / block3 screening 结构。

---

## 执行边界

- 工作目录：`C:\Users\hp\Documents\factor_autoresearch\.worktrees\block3_a_line`
- 本计划只实现 Block3 research screening，不做 production gate。
- 不做多 horizon best selection；只用固定 `admission_horizon = "5d"`。
- Gate3 只保留 `pass` / `fail`，不设 warning。
- Screening 产物只记录 Gate 判定字段；Pearson IC、positive ratio、spread、node_count、非 Gate 的 Sharpe 变体等诊断字段留给后续 diagnose / analysis job。
- Block3 不新增 `block3_screening_metrics.py` 这类指标计算模块。
- 不改旧 candidate gate 的公开行为，不改 `factor_autoresearch/evaluate.py` 的旧 Evaluator 链路，旧测试必须继续通过。

## 职责总览

| 层级 | 新增 / 修改位置 | 负责内容 | 不负责内容 |
| --- | --- | --- | --- |
| 区块2 data sample layer | `factor_autoresearch/screening_sample.py` 或现有 sample/data 模块 | 构造 `ScreeningSampleView`，提供 dataset、sample protocol、评价切片、forward returns、追溯字段 | 不计算 RankIC、相关性、Sharpe、换手 |
| 区块1 compute engine v1 | `factor_autoresearch/compute_v1/screening.py` 或 `screening_outputs.py` | 计算并输出 Gate0-Gate3 所有判定指标 | 不判断是否入库，不写 JSONL 产物 |
| 区块3 screening gate | `factor_autoresearch/block3_screening.py`、`block3_screening_runner.py`、`block3_screening_artifacts.py` | 调用区块2和区块1接口，应用阈值，产生决策，写产物 | 不自行拼数据，不自行补算指标 |

## 文件结构

新增：

- `configs/block3_screening_gate_v1.toml`：Block3 初始化 profile。
- `factor_autoresearch/screening_sample.py`：区块2对 Block3 暴露的 screening 样本视图接口。
- `factor_autoresearch/compute_v1/screening.py`：compute engine v1 对 Block3 暴露的 Gate 指标输出接口。
- `factor_autoresearch/block3_screening.py`：四段 gate 决策逻辑，只消费指标，不计算指标。
- `factor_autoresearch/block3_screening_runner.py`：Block3 screening 独立编排入口，不依赖旧 `Evaluator`。
- `factor_autoresearch/block3_screening_artifacts.py`：`evaluation_log`、`research_factor_library`、`replacement_queue` JSONL 写入。
- `tests/test_block3_screening_config.py`
- `tests/test_candidates.py`
- `tests/test_screening_sample.py`
- `tests/test_compute_v1_screening.py`
- `tests/test_block3_screening_gate.py`
- `tests/test_block3_screening_artifacts.py`
- `tests/test_block3_screening_runner.py`

修改：

- `factor_autoresearch/candidates.py`：新增可选 `economic_rationale` 字段。
- `factor_autoresearch/config.py`：新增 `Block3ScreeningConfig` 和 `load_block3_screening_config`。
- `factor_autoresearch/cli.py`：把 `factor evaluate` 接到新 Block3 runner；把旧 `factor evaluate` 降级为 `factor diagnose`。
- `tests/test_cli.py`：覆盖 `factor evaluate` 新入口和 `factor diagnose` 旧诊断入口。

---

### Task 1: 配置模型与初始化 profile

**涉及文件：**

- 新增：`configs/block3_screening_gate_v1.toml`
- 修改：`factor_autoresearch/config.py`
- 测试：`tests/test_block3_screening_config.py`

- [ ] **Step 1: 写配置文件**

配置分组：

| 分组 | 配置项 | 作用 |
| --- | --- | --- |
| 运行口径 | `version`、`screening_gate_profile`、`admission_horizon`、`metric_compute_policy` | 追溯本次 screening 使用哪套规则 |
| 样本视图 | `screening_sample_roles` | 指定区块2应选择哪些 sample protocol slice 作为 Gate 评价样本 |
| Gate0 基础质量 | `expression_depth_max`、`coverage_mean_min`、`effective_trade_days_min`、`min_cross_section_size`、`finite_ratio_min`、`std_min`、`unique_ratio_min` | 控制表达式复杂度、样本可用性、输出健康度 |
| Gate1 预测力 | `admission_quality_*`、`admission_stability_*` | 控制固定 5d RankIC 的强度和稳定性 |
| Gate2 去重 | `batch_corr_threshold`、`library_corr_threshold`、`correlation_min_overlap`、`tie_break_order` | 控制重复因子识别和 batch 内保留顺序 |
| Gate2 replacement | `replacement_*`、`correlated_factor_count_required` | 控制什么时候把重复因子标成替换候选 |
| Gate3 经济含义 | `directional_long_short_sharpe_min`、`long_short_effective_days_min`、`monotonicity_score_min`、`turnover_proxy_max` | 控制轻量交易 sanity check |

初始化配置：

```toml
[screening_gate]
version = "block3_screening_gate_v1"                    # 规则版本，用于产物追溯
screening_gate_profile = "initial_research_factorminer_like_v1"  # 初始化筛选 profile 名称
admission_horizon = "5d"                                # 入库评价周期，v1 固定 5d
metric_compute_policy = "staged"                        # 分阶段计算，前序失败不算后序指标
screening_sample_roles = ["validation"]                  # 区块2选择哪些样本切片给 Gate 使用

expression_depth_max = 8                                 # Gate0 表达式树最大深度
coverage_mean_min = 0.70                                 # Gate0 因子有效覆盖率下限
effective_trade_days_min = 120                           # Gate0 有效交易日下限
min_cross_section_size = 100                             # Gate0 每日有效股票数中位数下限
finite_ratio_min = 0.99                                  # Gate0 有限值比例下限
std_min = 1e-12                                          # Gate0 因子标准差下限，防止常数因子
unique_ratio_min = 0.01                                  # Gate0 有限值唯一值比例下限
quantiles = 5                                            # Gate3 分层组数，默认五分组

admission_quality_metric = "directional_rankic_mean"     # Gate1 预测力主指标
admission_quality_min = 0.04                             # Gate1 方向化 RankIC 均值下限
admission_stability_metric = "directional_rankic_ir"     # Gate1 预测力稳定性指标
admission_stability_min = 0.50                           # Gate1 方向化 RankIC IR 下限

batch_corr_threshold = 0.50                              # Gate2 本轮候选之间的重复阈值
library_corr_threshold = 0.50                            # Gate2 与研究因子库的重复阈值
correlation_min_overlap = 10000                          # Gate2 相关性比较最小共同样本数
tie_break_order = ["directional_rankic_mean", "directional_rankic_ir", "coverage_mean"]  # Gate2 batch 内保留顺序

replacement_quality_metric = "directional_rankic_mean"   # Replacement 新旧优劣比较主指标
replacement_absolute_quality_min = 0.10                  # Replacement 新因子绝对质量下限
replacement_improvement_ratio_min = 1.30                 # Replacement 新因子相对旧因子的最小提升倍数
correlated_factor_count_required = 1                     # Replacement 只允许唯一命中旧因子

directional_long_short_sharpe_min = 1.00                 # Gate3 方向化多空收益 Sharpe 下限
long_short_effective_days_min = 50                       # Gate3 多空收益有效交易日下限
monotonicity_score_min = 0.30                            # Gate3 分层单调性得分下限
turnover_proxy_max = 0.70                                # Gate3 高分组换手代理上限
```

- [ ] **Step 2: 写配置加载测试**

测试必须证明：

| 检查点 | 目的 |
| --- | --- |
| 所有 Gate0-Gate3 阈值都能读出 | 防止阈值写死在代码里，包括 `long_short_effective_days_min` |
| `screening_sample_roles` 能读出 | 防止 Block3 自己决定样本切片 |
| `metric_compute_policy = "staged"` 能读出 | 防止后续误算全量诊断字段 |

- [ ] **Step 3: 实现配置 dataclass 和加载函数**

在 `Block3ScreeningConfig` 中加入全部配置项，尤其包括：

```python
screening_sample_roles: list[str]
long_short_effective_days_min: int
```

- [ ] **Step 4: 验证并提交**

```powershell
uv run pytest tests/test_block3_screening_config.py -v
git add configs/block3_screening_gate_v1.toml factor_autoresearch/config.py tests/test_block3_screening_config.py
git commit -m "feat: add block3 screening profile config"
```

---

### Task 2: 候选输入支持经济含义说明

**涉及文件：**

- 修改：`factor_autoresearch/candidates.py`
- 测试：`tests/test_candidates.py`

- [ ] **Step 1: 写候选 schema 测试**

测试目标：候选可以携带 `economic_rationale`，Block3 后续只记录这个字段，不用它替代指标判断。

必要断言：

| 场景 | 断言 |
| --- | --- |
| JSONL 中包含 `economic_rationale` | `Candidate.economic_rationale` 等于原文 |
| JSONL 中不包含该字段 | `Candidate.economic_rationale == ""` |
| 字段是空字符串 | 允许通过，产物写空字符串 |
| 字段不是字符串 | 候选解析失败，错误信息指向 `economic_rationale` |

- [ ] **Step 2: 修改 Candidate dataclass 和解析逻辑**

新增字段：

```python
@dataclass(frozen=True)
class Candidate:
    """候选因子: Agent 输出并交给评估链路处理的最小结构。"""

    candidate_id: str
    name: str
    expression: str
    expected_direction: str
    category: str
    economic_rationale: str = ""
```

解析规则：

- `economic_rationale` 可选。
- 缺失时写空字符串。
- 存在时必须是字符串。
- 该字段不进入表达式校验，不影响 Gate 判定。

- [ ] **Step 3: 验证并提交**

```powershell
uv run pytest tests/test_candidates.py -v
git add factor_autoresearch/candidates.py tests/test_candidates.py
git commit -m "feat: allow factor economic rationale"
```

---
### Task 3: 区块2提供 ScreeningSampleView

**涉及文件：**

- 新增：`factor_autoresearch/screening_sample.py`
- 测试：`tests/test_screening_sample.py`

- [ ] **Step 1: 写样本视图测试**

测试目标：Block3 不再直接读 parquet、manifest 或 sample protocol 细节，而是调用区块2接口。

`ScreeningSampleView` 字段分组：

| 分类 | 字段 | 中文解释 |
| --- | --- | --- |
| 数据对象 | `dataset`、`panel_view`、`forward_returns_view` | compute engine v1 实际使用的数据输入 |
| 样本口径 | `sample_protocol_id`、`sample_protocol_hash`、`evaluated_slice_roles` | 本次 Gate 评价用到哪些样本切片 |
| 时间范围 | `evaluated_date_start`、`evaluated_date_end`、`evaluated_trade_dates` | 本次 Gate 实际覆盖的日期范围 |
| 数据追溯 | `source_universe_key`、`forward_return_definition`、`dataset_id` | Gate2 相关性比较和产物追溯必需字段 |

必要断言：

| 场景 | 断言 |
| --- | --- |
| 配置传入 `screening_sample_roles = ["validation"]` | 返回视图只包含 validation slice 日期 |
| 样本协议有 hash | `sample_protocol_hash` 非空，并进入 run payload |
| forward return 视图存在 `fwd_ret_5d` | compute engine v1 可以按固定 horizon 评价 |
| 请求不存在的 slice role | 抛出清晰错误，不让 Block3 自己 fallback |

- [ ] **Step 2: 实现区块2接口**

建议公共接口：

```python
@dataclass(frozen=True)
class ScreeningSampleView:
    """Block3 筛选使用的数据和样本视图。"""

    dataset: DatasetBundle
    panel_view: pd.DataFrame
    forward_returns_view: pd.DataFrame
    sample_protocol_id: str
    sample_protocol_hash: str
    evaluated_slice_roles: tuple[str, ...]
    evaluated_date_start: str
    evaluated_date_end: str
    evaluated_trade_dates: tuple[pd.Timestamp, ...]
    source_universe_key: str
    forward_return_definition: dict[str, object]
    dataset_id: str
```

```python
def build_screening_sample_view(
    *,
    config: ExperimentConfig,
    dataset_path: str | Path,
    screening_sample_roles: Sequence[str],
) -> ScreeningSampleView:
    """读取数据集并按样本协议构造 Block3 评价视图。"""
```

实现规则：

- 接收 `ExperimentConfig`，因为现有 `DataLoader` 需要 config 校验 manifest。
- 复用 `DataLoader.load()` 读取 `DatasetBundle`。
- 复用 `build_sample_protocol_from_dataset()` 生成或读取样本协议。
- 只按配置指定的 sample slice role 过滤日期。
- 不在区块3中重复实现 manifest 校验、日期切片或 forward return 拼接。

- [ ] **Step 3: 验证并提交**

```powershell
uv run pytest tests/test_screening_sample.py -v
git add factor_autoresearch/screening_sample.py tests/test_screening_sample.py
git commit -m "feat: expose screening sample view"
```

---

### Task 4: compute engine v1提供 Gate 指标输出

**涉及文件：**

- 新增：`factor_autoresearch/compute_v1/screening.py`
- 修改：按需修改 `factor_autoresearch/compute_v1/metrics.py`、`metrics_kernels.py`、`calculator.py`
- 测试：`tests/test_compute_v1_screening.py`

- [ ] **Step 1: 写 compute v1 screening 输出测试**

测试目标：所有 Gate 指标都来自 compute engine v1，Block3 不拥有指标计算函数。

输出字段分组：

| Gate | 字段 | 中文解释 |
| --- | --- | --- |
| Gate0 表达式与健康度 | `expression_parse_status`、`expression_allowlist_status`、`leakage_check_status`、`expression_depth`、`coverage_mean`、`effective_trade_days`、`median_valid_stock_count`、`finite_ratio`、`std`、`unique_ratio` | 基础质量门全部字段 |
| Gate1 预测力 | `admission_horizon`、`expected_direction`、`directional_rankic_mean`、`directional_rankic_ir` | 固定 horizon 的方向化 RankIC 结果 |
| Gate2 相关性 | `max_abs_corr_to_batch`、`max_abs_corr_to_library`、`correlation_overlap_count`、`correlated_factor_count`、`matched_factor_id` | 去重和 replacement 使用字段 |
| Gate3 经济含义 | `directional_long_short_sharpe`、`long_short_effective_days`、`monotonicity_score`、`turnover_proxy` | 轻量交易 sanity check 四指标 |

必要断言：

| 检查点 | 断言 |
| --- | --- |
| 返回字段瘦身 | 不返回 Pearson IC、positive ratio、spread、node_count、非 Gate 的 Sharpe 变体、非 5d horizon |
| 固定 horizon | 只读取配置中的 `admission_horizon` |
| 缺失底层能力 | 在 compute v1 内补齐或明确抛出 `MissingComputeV1MetricError`，不让 Block3 fallback |
| staged 支持 | Gate0 fail 时可以只返回 Gate0 字段；后序字段可不计算 |

- [ ] **Step 2: 定义 compute v1 输出对象**

建议公共对象：

```python
@dataclass(frozen=True)
class Block3ScreeningMetricBundle:
    """compute engine v1 输出给 Block3 的 Gate 指标包。"""

    gate0_metrics: dict[str, object]
    gate1_metrics: dict[str, object]
    gate2_metrics: dict[str, object]
    gate3_metrics: dict[str, object]
    factor_exposure_ref: str | None
    engine_version: str
```

建议公共接口：

```python
def compute_block3_screening_metrics(
    *,
    candidate: Candidate,
    sample_view: ScreeningSampleView,
    config: Block3ScreeningConfig,
    library_factors: pd.DataFrame | None = None,
    batch_factors: pd.DataFrame | None = None,
    requested_gates: Sequence[str] = ("gate0", "gate1", "gate2", "gate3"),
) -> Block3ScreeningMetricBundle:
    """为 Block3 计算指定 Gate 需要的全部指标。"""
```

- [ ] **Step 3: 复用现有 compute engine 能力**

| 需求 | 复用位置 | 需要补什么 |
| --- | --- | --- |
| 表达式合法性 | `V1FactorCalc.validate_candidate()` | 输出 parse / allowlist / leakage 状态的稳定字段 |
| 表达式复杂度 | `V1FactorCalc.complexity_score()` 或 AST validator | 明确 `expression_depth` 口径，先只把树深度作为 hard gate |
| 因子暴露 | `V1FactorCalc.calculate_matrix()`、`PanelStore.from_dataset()` | 统一暴露矩阵，供 Gate0-Gate3 共用 |
| RankIC | `compute_candidate_metrics_from_matrix()`、`MetricsBackend.rowwise_spearman()` | 增加 `directional_rankic_ir` 输出，且只暴露固定 horizon |
| 分层单调性 | `MetricsBackend.quantile_stats()` | 输出瘦身后的 `monotonicity_score` |
| 多空 Sharpe | 可基于 quantile long-short 序列新增 kernel | 新增 `directional_long_short_sharpe`，有效样本不足或波动不可用时输出非有限数 |
| 多空有效天数 | 多空收益序列 | 新增 `long_short_effective_days`，按方向化多空收益序列的有限值天数计算 |
| 换手代理 | 新增 compute v1 kernel | 新增 `turnover_proxy`，按高分组集合 Jaccard 距离计算 |
| 相关性去重 | 新增 compute v1 screening correlation helper | 输出 batch / library 最大绝对 Spearman 和 overlap |

- [ ] **Step 4: 验证并提交**

```powershell
uv run pytest tests/test_compute_v1_screening.py tests/test_compute_v1_metrics.py -v
uv run python scripts/run_compute_v1_guardrails.py
git add factor_autoresearch/compute_v1 tests/test_compute_v1_screening.py
git commit -m "feat: expose compute v1 screening metrics"
```

---

### Task 5: 区块3只做 Gate 决策

**涉及文件：**

- 新增：`factor_autoresearch/block3_screening.py`
- 测试：`tests/test_block3_screening_gate.py`

- [ ] **Step 1: 写状态测试**

`Block3GateInputs` 只接收已计算好的 metric bundle 和配置，不接收 raw panel、forward returns 或 factor frame。

覆盖状态：

| 场景 | 期望结果 | 说明 |
| --- | --- | --- |
| 基础质量、预测力、去重、经济含义都通过 | `admitted` | 新因子进入研究因子库 |
| `expression_depth > 8` | `reject` | Gate0 拦截 |
| `coverage_mean < 0.70` 或 `median_valid_stock_count < 100` | `reject` | 样本不足 |
| `directional_rankic_mean` 不达标 | `reject` | 预测力不足 |
| 与旧因子高相关但不更好 | `duplicate` | 重复因子，不入库 |
| 与唯一旧因子高相关且质量提升 `1.30x` | `replace_candidate` | 进入 replacement queue |
| `directional_long_short_sharpe` 不达标或非有限数 | `reject` | 经济含义不过关 |
| `long_short_effective_days < 50` | `reject` | 多空收益有效样本不足 |

- [ ] **Step 2: 实现决策对象**

公共对象：

```python
@dataclass(frozen=True)
class Block3GateInputs:
    """Block3 Gate 判定输入: 只包含配置和 compute v1 已算好的指标。"""

    config: Block3ScreeningConfig
    metrics: Block3ScreeningMetricBundle
    existing_factor_metrics: Mapping[str, object] | None = None
```

```python
def apply_block3_screening_gate(inputs: Block3GateInputs) -> Block3GateDecision:
    """应用 Gate0-Gate3 阈值并返回最终筛选决策。"""
```

实现规则：

- Gate0/Gate1/Gate2/Gate3 只读取 metric bundle 字段。
- Gate3 对 `long_short_effective_days < config.long_short_effective_days_min` 判定失败，默认阈值为 50。
- 如果必要字段缺失，抛出清晰错误，提示应由 compute engine v1 补输出。
- 不在 `block3_screening.py` 中导入 pandas / numpy 做指标计算。
- 不在 `block3_screening.py` 中读取 parquet / manifest / sample protocol。

- [ ] **Step 3: 验证并提交**

```powershell
uv run pytest tests/test_block3_screening_gate.py -v
git add factor_autoresearch/block3_screening.py tests/test_block3_screening_gate.py
git commit -m "feat: add block3 screening gate decisions"
```

---

### Task 6: 区块3产物写入

**涉及文件：**

- 新增：`factor_autoresearch/block3_screening_artifacts.py`
- 测试：`tests/test_block3_screening_artifacts.py`

- [ ] **Step 1: 写 artifact writer 测试**

产物写入测试覆盖：

| 检查点 | 断言 |
| --- | --- |
| 全量评估日志 | `evaluation_log.jsonl` 有所有候选记录 |
| admitted 入库 | `research_factor_library.jsonl` 只写 admitted |
| replace_candidate 入队 | `replacement_queue.jsonl` 只写 replace_candidate |
| metrics 字段瘦身 | 只包含 Gate0-Gate3 判定字段 |
| 禁止诊断字段 | 不包含 Pearson IC、positive ratio、spread、node_count、非 Gate 的 Sharpe 变体等字段 |
| 追溯字段 | 包含区块2提供的 sample / data 字段和 compute v1 的 `engine_version` |
| 经济含义说明 | `evaluation_log` 和 `research_factor_library` 写入 `economic_rationale`，但不参与 Gate 判定 |

- [ ] **Step 2: 实现 writer**

公共接口：

```python
class Block3ScreeningWriter:
    """Block3 筛选产物写入器。"""

    def write(
        self,
        *,
        decision: Block3GateDecision,
        candidate_payload: dict[str, object],
        run_payload: dict[str, object],
    ) -> None:
        """按最终决策写入 evaluation/library/replacement JSONL。"""
```

payload 规则：

| payload | 来源 | 必须包含 |
| --- | --- | --- |
| `candidate_payload` | 候选输入 + compute v1 metric bundle | candidate identity、expression、category、`economic_rationale`、Gate metrics、matched factor |
| `run_payload` | 区块2 sample view + config + compute v1 | run id、数据口径、样本协议、预处理哈希、引擎版本、创建时间 |
| `metrics` | compute v1 输出 | 只保存 Gate 判定字段 |

写入前过滤或拒绝非 Gate 诊断指标，保证 screening artifacts 不变成研究诊断报告。

- [ ] **Step 3: 验证并提交**

```powershell
uv run pytest tests/test_block3_screening_artifacts.py -v
git add factor_autoresearch/block3_screening_artifacts.py tests/test_block3_screening_artifacts.py
git commit -m "feat: write block3 screening artifacts"
```

---

### Task 7: CLI 入口切换与独立 runner 编排

**涉及文件：**

- 新增：`factor_autoresearch/block3_screening_runner.py`
- 修改：`factor_autoresearch/cli.py`
- 测试：`tests/test_block3_screening_runner.py`
- 测试：`tests/test_cli.py`

- [ ] **Step 1: 写 runner 编排测试**

测试目标：`factor evaluate` 走 Block3 screening；旧 `Evaluator` 不改、不删，只通过 `factor diagnose` 暴露。

`run_block3_screening` 编排顺序必须是：

```text
load_block3_screening_config
  -> build_screening_sample_view(config=experiment_config, ...)  # 区块2
  -> load_candidate_batch                 # 候选输入，含 economic_rationale
  -> for each candidate:
       compute_block3_screening_metrics   # 区块1 / compute engine v1
       apply_block3_screening_gate         # 区块3
       Block3ScreeningWriter.write         # 区块3
```

必要断言：

| 检查点 | 断言 |
| --- | --- |
| 新入口不依赖旧 Evaluator | 测试 monkeypatch `factor_autoresearch.evaluate.Evaluator` 后，`factor evaluate` 仍能调用 runner |
| 旧入口降级 | `factor diagnose --help` 仍暴露旧评估参数，例如 `--engine`、`--jobs` |
| 数据来源 | runner 调用 `build_screening_sample_view` |
| 指标来源 | runner 调用 `compute_block3_screening_metrics` |
| 产物写入 | runner 调用 `Block3ScreeningWriter.write` |
| 解释字段 | `economic_rationale` 进入 writer payload |

- [ ] **Step 2: 实现 `block3_screening_runner.py`**

公共接口：

```python
def run_block3_screening(
    *,
    config_path: str | Path,
    candidates_path: str | Path,
    dataset_path: str | Path,
    output_dir: str | Path,
    screening_gate_config_path: str | Path,
) -> Block3ScreeningRunSummary:
    """运行 Block3 screening: 调用区块2、compute v1、Gate 判定和产物写入。"""
```

实现规则：

- 使用 `load_experiment_config` 和 `load_block3_screening_config` 读配置。
- 使用 `build_screening_sample_view(config=experiment_config, ...)` 取样本视图。
- 使用 `compute_block3_screening_metrics` 获取指标。
- 使用 `apply_block3_screening_gate` 做判定。
- 使用 `Block3ScreeningWriter` 写产物。
- 不导入或实例化旧 `Evaluator`。
- 不把 runner 放进 `evaluate.py`。
- 不再提供公开 `block3-screen` 命令；日常主入口就是 `factor evaluate`。

- [ ] **Step 3: 写 CLI 帮助测试**

`factor evaluate --help` 必须包含：

```text
--config
--candidates
--dataset
--output-dir
--screening-gate-config
```

- [ ] **Step 4: 实现 CLI**

`cli.py` 中新的 `factor evaluate` 只导入并调用：

```python
from factor_autoresearch.block3_screening_runner import run_block3_screening
```

`factor evaluate` 内部不直接拼装样本、不直接算指标、不触碰旧 `Evaluator`。旧 `Evaluator` 只从 `factor diagnose` 调用。

- [ ] **Step 5: 验证并提交**

```powershell
uv run pytest tests/test_block3_screening_runner.py tests/test_cli.py::test_cli_exposes_factor_evaluate_screening_command tests/test_cli.py::test_cli_exposes_factor_diagnose_legacy_command -v
git add factor_autoresearch/block3_screening_runner.py factor_autoresearch/cli.py tests/test_block3_screening_runner.py tests/test_cli.py
git commit -m "feat: route factor evaluate to block3 screening"
```

---

### Task 8: 总体验证与收口

- [ ] **Step 1: 跑 Block3 定向测试**

```powershell
uv run pytest tests/test_block3_screening_config.py tests/test_candidates.py tests/test_screening_sample.py tests/test_compute_v1_screening.py tests/test_block3_screening_gate.py tests/test_block3_screening_artifacts.py tests/test_block3_screening_runner.py -v
```

- [ ] **Step 2: 跑相关既有测试**

```powershell
uv run pytest tests/test_gate_registry.py tests/test_compute_v1_metrics.py tests/test_cli.py tests/test_evaluate.py -v
```

- [ ] **Step 3: 跑 lint**

```powershell
uv run ruff check factor_autoresearch tests
```

- [ ] **Step 4: 跑 compute v1 护栏**

本计划会触碰 `factor_autoresearch/compute_v1/**`，必须运行：

```powershell
uv run python scripts/run_compute_v1_guardrails.py
```

## 总体验收

最终报告必须按分类说明结果：

| 分类 | 必须报告的内容 |
| --- | --- |
| 职责边界 | 区块2提供数据样本视图；compute engine v1提供全部 Gate 指标；Block3只调用、判定、写产物 |
| 指标输出边界 | Screening 只记录 Gate 判定字段；诊断字段不进入 screening artifacts |
| Gate0 基础质量 | `expression_depth <= 8`、`coverage_mean >= 0.70`、`effective_trade_days >= 120`、`median_valid_stock_count >= 100`、`finite_ratio >= 0.99`、`std > 1e-12`、`unique_ratio >= 0.01` |
| Gate1 预测力 | 固定 `admission_horizon = "5d"`；`directional_rankic_mean >= 0.04`；`directional_rankic_ir >= 0.50` |
| Gate2 去重 / replacement | `library_corr_threshold = 0.50`；replacement 要求新因子绝对质量 `>= 0.10` 且相对旧因子提升 `>= 1.30x` |
| Gate3 经济含义 | `directional_long_short_sharpe >= 1.00`、`long_short_effective_days >= 50`、`monotonicity_score >= 0.30`、`turnover_proxy <= 0.70` |
| 产物路径 | `evaluation_log.jsonl`、`research_factor_library.jsonl`、`replacement_queue.jsonl` |
| 验证结果 | 实际运行过的验证命令和 pass/fail 结果 |