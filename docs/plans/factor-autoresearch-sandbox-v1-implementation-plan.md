# Factor Autoresearch Sandbox v1 实施计划

## 1. 这份文档要解决什么

这份 plan 是给 `Factor Autoresearch` 第一轮 sandbox 落地用的工程工单。它把两份上游文档转成可以实现、可以测试、可以验收的工作拆分：

- framework spec：`docs/framework/factor-autoresearch-framework-v1.md`
- sandbox experiment spec：`docs/experiments/factor-autoresearch-sandbox-v1.md`

这份 plan 不重新定义实验规则。framework spec 和 experiment spec 仍然是规则来源；本文件只回答：

- 仓库要长什么样。
- 选什么技术栈。
- 哪些模块负责什么事情。
- 关键类、函数、数据结构怎么分。
- 分哪些工程任务做。
- 每个任务怎么测试和验收。

## 2. 总体目标

实现一个确定性 Python 工具链，让第一轮中证500 OHLCV 日频因子实验可以完整跑通：

```text
Codex 追加候选 DSL
  -> Python 工具静态校验候选
  -> Python 工具读取固定 dataset 做评价
  -> run artifacts 落盘
  -> 通过 gate 的候选追加 registry
  -> Codex 阅读 summary 并维护 research notes / memory
```

v1 的重点不是挖出最强因子，而是把“候选提交、校验、评价、记录、复现”这条闭环搭起来。

## 3. 文档和目录分层

当前文档分三类放置：

```text
docs/
├── framework/
│   └── factor-autoresearch-framework-v1.md       # 长期稳定的框架合同
├── experiments/
│   └── factor-autoresearch-sandbox-v1.md         # 本轮中证500 sandbox 实验规格
└── plans/
    └── factor-autoresearch-sandbox-v1-implementation-plan.md
                                                       # 本实施计划
```

三层职责：

- `framework/`：Codex 和 Python tools 的长期分工、权限边界、artifact 合同。
- `experiments/`：某一次实验的 universe、数据字段、DSL 搜索空间、metrics、gate。
- `plans/`：怎么写代码、怎么测试、怎么验收。

## 4. 技术栈选择

| 类型 | 选择 | 用途 | 选择原因 |
| --- | --- | --- | --- |
| 语言 | Python 3.11+ | CLI、数据处理、评价器 | 数据生态成熟，类型和标准库足够稳定 |
| 项目管理 | uv | 依赖管理、虚拟环境、lockfile、命令执行 | 环境可复现，命令口径统一，安装和 CI 速度快 |
| 表格计算 | pandas | panel 数据、横截面/时间序列计算 | 日频因子研究最直接，便于调试 |
| 数值计算 | numpy | 安全除法、缺失值、数组运算 | 和 pandas 配合自然 |
| 文件格式 | parquet + pyarrow | 固定 dataset、因子值、metrics | 适合列式数据，读写快，可复现 |
| 本地分析查询 | DuckDB | 读取 parquet、检查 dataset、查询 run artifacts | 不引入服务端数据库，也能高效做列式查询和人工审计 |
| 配置 | TOML | experiment config、gate config | 人能读，Python 3.11 标准库可读 |
| 候选输入 | JSONL | `candidate_factors/candidates.jsonl` | 追加友好，每行一个候选，适合审计 |
| 表达式 DSL | 自定义受限 DSL + Python AST parser | 候选表达式解析、静态校验、复杂度计算 | 搜索空间小，安全边界清楚，v1 不需要完整量化框架 |
| CLI | Typer | `fm dataset ...`、`fm factor ...` | 参数声明清楚，测试方便 |
| 日志 | Python `logging` 标准库 + Typer/Rich 控制台输出 | run 级持久日志、CLI verbose 过程输出、错误追踪 | 标准库足够稳定，日志可落盘可测试；控制台输出适合人类实时观察 |
| 统计 | scipy / statsmodels | RankIC、OLS 中性化 | 避免手写统计细节 |
| 测试 | pytest | 单元测试和 smoke test | 简洁，适合模块化测试 |
| 代码质量 | ruff | lint 和基础格式检查 | 快，配置轻 |

本轮暂时不引入：

- 分布式计算框架。两年中证500日频数据规模不需要。
- 外部或状态型数据库。DuckDB 只作为嵌入式查询引擎读取 parquet 和 run artifacts，不保存 evaluator 状态。
- QLib。v1 只需要固定数据集读取、受限 DSL 解析、因子评价和 artifact 合同，不引入完整量化研究平台。
- 自动搜索引擎。v1 只支持 Codex 手写 DSL 候选。
- LLM API。Codex 作为人工协作 orchestrator，不嵌入工具内部。

## 5. 目标仓库结构

下面是实现完成后的预期目录。这里用树状结构展示，方便直接看系统边界：

```text
.
├── README.md
├── AGENTS.md
├── pyproject.toml
├── uv.lock
├── codex/
│   ├── program.md
│   ├── memory.md
│   └── research_notes.md
├── configs/
│   ├── csi500_ohlcv_sandbox_v1.toml
│   └── candidate_gate_v1.toml
├── datasets/
│   └── sandbox_v1/
│       ├── panel.parquet
│       ├── forward_returns.parquet
│       ├── manifest.json
│       └── README.md
├── factor_autoresearch/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── candidates.py
│   ├── calculator.py
│   ├── data_loader.py
│   ├── prepare.py
│   ├── preprocess.py
│   ├── metrics.py
│   ├── gate.py
│   ├── registry.py
│   ├── logging_config.py
│   ├── cleanup.py
│   └── evaluate.py
├── candidate_factors/
│   ├── candidates.jsonl
│   └── registry.jsonl
├── official_factors/
│   └── README.md
├── runs/
│   └── .gitkeep
├── docs/
│   ├── framework/
│   ├── experiments/
│   └── plans/
└── tests/
    ├── fixtures/
    │   └── sandbox_v1/
    ├── test_config.py
    ├── test_candidates.py
    ├── test_calculator.py
    ├── test_data_loader.py
    ├── test_preprocess_metrics.py
    ├── test_gate_registry.py
    ├── test_logging_config.py
    ├── test_cleanup.py
    ├── test_evaluate.py
    ├── test_cli.py
    └── test_smoke_run.py
```

目录语义：

- `README.md`：仓库入口说明，先放最小项目介绍和后续补充占位。
- `AGENTS.md`：Codex / agent 操作边界，必须留在仓库根目录，方便工具自动发现。
- `codex/`：Codex 维护的研究状态和过程记录，不被 evaluator 读取。
- `configs/`：实验和 gate 的参数，不在代码里硬编码。
- `datasets/`：固定数据集。评价阶段只读这里，不访问原始数据源。
- `factor_autoresearch/`：确定性 Python 工具层。
- `candidate_factors/candidates.jsonl`：Codex 只追加候选。
- `candidate_factors/registry.jsonl`：Python 工具只追加通过 gate 的候选。
- `runs/`：每次 evaluate 的可审计输出。
- `official_factors/`：v1 不晋升 official factor，只保留说明。

## 6. 数据流

```text
prepare-fixed
  输入：本地受控数据源 + configs/csi500_ohlcv_sandbox_v1.toml
  输出：datasets/sandbox_v1/**

validate
  输入：datasets/sandbox_v1/manifest.json + candidate_factors/candidates.jsonl + configs
  输出：静态校验结果

evaluate
  输入：fixed dataset + candidates + configs
  输出：runs/{run_id}/** + candidate_factors/registry.jsonl
```

评价阶段的核心原则：

- 不查询 zer0share。
- 不修改 dataset。
- 不修改 candidate 历史记录。
- 不让候选记录携带 universe、日期、gate、source data 等实验参数。
- 同一份 dataset、candidate JSONL、config、工具版本重复运行，结果应一致。

## 7. 关键模块设计

### 7.1 设计收敛

v1 只把三类长期行为做成核心类：

```text
DataLoader
FactorCalc
Evaluator
```

这三个类不是继承体系，也不是为了提前做复杂多态；它们只是把系统里最容易变重的三个执行边界收住：

- `DataLoader`：固定数据入口。
- `FactorCalc`：候选表达式到原始因子值。
- `Evaluator`：一次 run 的评价编排和 artifact 写出。

第 8 节的 7 个结构是核心数据结构关系。实现内部可以为了类型安全使用私有 dataclass 或 namedtuple，例如 loaded dataset bundle、calculation detail、gate decision，但这些都不进入核心结构图，也不作为长期落盘合同。

### 7.2 `DataLoader`

所在模块：`data_loader.py`

职责：只读取固定 dataset，并做最小结构校验。

核心 API：

```python
class DataLoader:
    def load(self, dataset_path: Path, config: ExperimentConfig):
        ...
```

`load()` 返回的是内存 dataset 对象，至少包含：

- `panel.parquet` 读出的 panel 数据。
- `forward_returns.parquet` 读出的 forward return。
- `manifest.json` 读出的 Dataset Manifest。

需要校验：

- `panel.parquet` 必须有 spec 要求字段。
- `forward_returns.parquet` 必须有 1d / 5d / 20d forward return。
- `(trade_date, ts_code)` 主键唯一。
- Dataset Manifest 中的 `dataset_id`、`experiment_id` 能和 Experiment Config 对齐。

人类审阅重点：

- `DataLoader` 只读固定 dataset。
- `Evaluator` 不允许绕过 `DataLoader` 去读原始数据源。
- 内存 dataset 对象只是实现细节，不是第 8 节的核心数据结构。

### 7.3 `FactorCalc`

所在模块：`calculator.py`

职责：把 `Candidate.expression` 安全地计算成原始因子值。v1 的计算能力完全来自受限 DSL，所以 `FactorCalc` 是 DSL parser、校验和执行的对外边界。

核心 API：

```python
class FactorCalc:
    def calculate(self, candidate: Candidate, dataset, config: ExperimentConfig) -> pd.Series:
        ...

    def complexity_score(self, candidate: Candidate, config: ExperimentConfig) -> int:
        ...
```

DSL 允许：

```text
字段：open_hfq, high_hfq, low_hfq, close_hfq, volume
运算：+ - * / unary -
函数：abs, log, delay, ts_mean, ts_std, ts_delta, ts_return, ts_rank, cs_rank, cs_zscore
窗口：1, 3, 5, 10, 20
```

实现说明：

- 可以用 Python `ast.parse(..., mode="eval")` 当 parser，但只能接受白名单节点。
- 禁止 attribute、subscript、lambda、comprehension、import、function definition、任意 Python 调用。
- `/` 是安全除法，除零变成缺失值。
- `log(x)` 在 `x <= 0` 时变成缺失值。
- `inf` / `-inf` 统一转缺失。
- 时间序列函数按 `ts_code` 分组、`trade_date` 排序。
- 横截面函数按 `trade_date`，只在 `in_universe == true` 样本内计算。

人类审阅重点：

- `FactorCalc` 只负责 raw factor values 和 complexity，不负责 metrics、gate 或 registry。
- 这是 DSL，不是 Python 表达式执行器。
- complexity score 要可复现，后面 gate 会用。

### 7.4 `Evaluator`

所在模块：`evaluate.py`

职责：串起完整评价流程并写出 run artifacts。

核心 API：

```python
class Evaluator:
    def evaluate_candidate(self, candidate: Candidate) -> dict:
        ...

    def evaluate_batch(self, candidates: list[Candidate]) -> None:
        ...
```

`Evaluator` 组合使用：

- `DataLoader`
- `FactorCalc`
- `preprocess.py`
- `metrics.py`
- `gate.py`
- `registry.py`

单个 candidate 的评价顺序：

```text
Candidate
  -> FactorCalc.calculate
  -> winsorize
  -> zscore
  -> industry + size neutralization
  -> metrics
  -> gate
  -> Candidate Result
  -> pass 时追加 Registry
```

一次 run 的输出：

```text
runs/{run_id}/
├── manifest.json                     # 记录本次 run 的复现上下文
├── summary.md                        # 给人和 Codex 看的结果摘要
├── factors/
│   └── {candidate_id}.parquet        # 单个候选的因子值明细
├── results/
│   ├── candidate_results.jsonl       # 每个候选的最终状态和结论
│   ├── metrics.parquet               # 每个候选各 horizon 的汇总指标
│   └── ic_series.parquet             # 每日 IC / RankIC 等时间序列
└── logs/
    └── evaluate.log                  # 本次 evaluate 的运行日志
```

人类审阅重点：

- 一个 candidate 出错不能让整批 run 直接丢失结果。
- `summary.md` 要适合 Codex 和人类一起阅读。
- `manifest.json` 要足够复现本次 run。
- `Evaluator` 是编排者，不把 DSL、metrics、gate 的细节写死在一个长函数里。

### 7.5 `config.py`

职责：读取 TOML 配置，并计算配置 hash。

关键结构：

```python
@dataclass(frozen=True)
class ExperimentConfig:
    experiment_id: str
    dataset_id: str
    universe: str
    date_start: str
    date_end: str
    allowed_fields: list[str]
    allowed_functions: list[str]
    allowed_windows: list[int]
    categories: list[str]
    horizons: list[str]
    gate: dict[str, Any]
    config_hash: str
```

说明：

- gate 阈值可以来自单独 TOML 文件，但在核心数据结构关系里仍归入 Experiment Config。
- 代码内部如果拆出 gate-specific typed object，只是实现细节，不进入第 8 节核心结构图。

人类审阅重点：

- 实验参数必须从 config 读，不要散落在 evaluator 代码里。
- `config_hash` 必须进入 Run Manifest。

### 7.6 `candidates.py`

职责：读取和校验候选 JSONL 的通用字段。

关键结构：

```python
@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    name: str
    expression: str
    expected_direction: str
    hypothesis: str
    category: str
    lookback_days: int
    created_at: str
    notes: str
```

需要拒绝：

- JSONL 解析失败。
- 必填字段缺失。
- `candidate_id` 重复。
- `expected_direction` 不是 `positive` / `negative`。
- `category` 不在 sandbox v1 枚举中。
- 候选记录携带 `universe`、`date_start`、`gate`、`data_source` 等 forbidden fields。

人类审阅重点：

- Candidate 是“研究想法”，不是“实验配置”。
- Codex 只能追加候选，不能改旧候选。

### 7.7 `prepare.py`

职责：维护者运行的 dataset 冻结入口。

命令：

```bash
uv run fm dataset prepare-fixed \
  --config configs/csi500_ohlcv_sandbox_v1.toml \
  --output datasets/sandbox_v1
```

输出：

```text
datasets/sandbox_v1/
├── panel.parquet
├── forward_returns.parquet
├── manifest.json
└── README.md
```

人类审阅重点：

- 这是唯一可以访问本地受控数据源的模块。
- 评价阶段不能调用 prepare。
- manifest 要记录 source path、source universe key、基础过滤口径和 forward return 定义。

### 7.8 辅助模块

这些模块先保持函数式，不做核心抽象类。等 v1 跑通后，如果确实需要替换实现，再从这里抽出独立策略对象。

#### `preprocess.py`

职责：把原始因子值变成用于评价的标准化残差。

处理顺序：

```text
raw factor values
  -> winsorize
  -> zscore
  -> industry + size neutralization
  -> metrics
```

中性化模型：

```text
factor_z ~ industry dummies + log(market_cap)
```

人类审阅重点：

- industry 和 market_cap 只是评价预处理暴露，不进入 DSL 搜索字段。
- 中性化在每日横截面内做，不跨日期。
- 不填充缺失值。

#### `metrics.py`

职责：计算每个候选、每个 horizon 的指标。

核心指标：

- `IC`
- `RankIC`
- `ICIR`
- `coverage`
- `quantile_returns`
- `long_short_return`
- `monotonicity`
- `complexity_score`

人类审阅重点：

- 每天横截面有效样本数至少 100 才计算当日 IC / RankIC。
- RankIC 和 monotonicity 是 gate 里的重要信号。
- 指标命名要带 horizon 后缀，例如 `rankic_mean_20d`。

#### `gate.py`

职责：把 metrics 转成 candidate pass / fail。

硬规则：

```text
validate passed
coverage_mean >= 0.70
effective_trade_days >= 60
complexity_score <= 12
best_horizon_score >= 1.0
```

人类审阅重点：

- 分数要按 `expected_direction` 调整方向。
- gate 是 candidate gate，不是 production official gate。
- 未通过 gate 的候选不能写 registry。

#### `registry.py`

职责：append-only 写入通过 gate 的候选。

registry 记录示意：

```json
{
  "candidate_id": "fa_0001_range_position",
  "status": "candidate_pass",
  "dataset_id": "sandbox_v1",
  "experiment_id": "csi500_ohlcv_sandbox_v1",
  "run_id": "smoke_001",
  "best_horizon": "20d",
  "best_horizon_score": 1.2
}
```

人类审阅重点：

- 只追加，不重写。
- 只写 candidate_pass。
- failed / invalid / error 只保存在 run artifacts。

### 7.9 `logging_config.py`

职责：统一配置 CLI 控制台日志和 run 级持久日志。

核心 API：

```python
def configure_logging(
    *,
    run_dir: Path | None,
    verbose: bool,
    quiet: bool = False,
) -> None:
    ...
```

日志输出分两层：

```text
console
  默认：只显示阶段级状态、最终摘要位置、错误提示
  --verbose：显示数据读取、候选处理、指标计算、gate 决策等过程信息
  --quiet：只显示错误和最终必要路径

runs/{run_id}/logs/evaluate.log
  始终记录完整过程
  包含 run_id、candidate_id、stage、duration、status、error class/message
  不受 --quiet 影响
```

日志级别约定：

- `INFO`：阶段开始/完成、候选通过/失败、artifact 写入路径。
- `DEBUG`：`--verbose` 时给人看的过程细节，例如候选数量、字段校验、单个 horizon 指标摘要。
- `WARNING`：可恢复但需要注意的问题，例如某个交易日有效样本不足被跳过。
- `ERROR`：单个 candidate 失败，写入 `candidate_results.jsonl` 后继续下一候选。
- `CRITICAL`：run 无法继续，例如 dataset 缺失或 config 无法读取。

人类审阅重点：

- 日志是运行证据，不是替代 `summary.md` 的人类结论。
- 控制台输出可以随 `--verbose` 变详细，但 `evaluate.log` 必须持续、完整、可追溯。
- 日志不能泄露原始数据路径之外的敏感凭据；异常 detail 要可排查，但不 dump 大型 DataFrame。

### 7.10 `cleanup.py`

职责：清空测试或试跑产生的实验输出，让 sandbox 可以从零开始重新跑。

核心 API：

```python
def clean_experiment_outputs(
    *,
    experiment_id: str,
    runs_dir: Path,
    registry_path: Path,
    yes: bool,
) -> CleanupReport:
    ...
```

默认清理范围：

- 删除 `runs/` 下 manifest 属于该 `experiment_id` 的 run 目录。
- 保留 `runs/.gitkeep`。
- 从 `candidate_factors/registry.jsonl` 中移除该 `experiment_id` 的记录；如果 v1 只有一个 experiment，则结果应为空文件。
- 未传 `yes=True` 时只返回 dry-run report，不执行文件修改。

禁止清理：

- `candidate_factors/candidates.jsonl`。
- `datasets/`。
- `configs/`。
- `codex/research_notes.md`。
- `codex/memory.md`。
- `official_factors/`。

安全要求：

- 所有删除目标必须 resolve 后仍在 repo 的 `runs/` 目录内。
- registry 只能通过临时文件 + 原子替换方式改写，避免半写状态。
- dry-run 输出要列出将删除的 run id、将移除的 registry 行数、不会触碰的输入文件。

### 7.11 `cli.py`

职责：暴露 `fm` 命令。

需要支持：

```bash
uv run fm dataset prepare-fixed \
  --config configs/csi500_ohlcv_sandbox_v1.toml \
  --output datasets/sandbox_v1

uv run fm factor validate \
  --dataset datasets/sandbox_v1 \
  --candidates candidate_factors/candidates.jsonl \
  --verbose

uv run fm factor evaluate \
  --dataset datasets/sandbox_v1 \
  --candidates candidate_factors/candidates.jsonl \
  --run-id smoke_001 \
  --verbose

uv run fm experiment clean \
  --experiment-id csi500_ohlcv_sandbox_v1

uv run fm experiment clean \
  --experiment-id csi500_ohlcv_sandbox_v1 \
  --yes
```

人类审阅重点：

- CLI 是人和 Codex 都会调用的接口。
- 参数名要和 spec 保持一致。
- validate 不计算指标；evaluate 才计算指标。
- `--verbose` 只影响控制台过程输出；run 级日志仍然持续写入 `runs/{run_id}/logs/evaluate.log`。
- `experiment clean` 默认 dry-run；只有传 `--yes` 才清空 run artifacts 和 registry 结果。

## 8. 关键数据结构

核心数据结构关系只包含下面 7 个结构。它们对应“会落盘、可追溯、可被人或工具引用”的协议对象；内部临时对象不放进这张关系图。

### 8.1 Candidate

只描述“因子是什么”，不携带实验环境。

每行一个候选：

```json
{
  "candidate_id": "fa_0001_range_position",
  "name": "range position",
  "expression": "cs_rank((close_hfq - low_hfq) / (high_hfq - low_hfq))",
  "expected_direction": "positive",
  "hypothesis": "收盘价越接近日内高点，可能代表更强的日内需求。",
  "category": "intraday",
  "lookback_days": 1,
  "created_at": "2026-06-22",
  "notes": "csi500_ohlcv_sandbox_v1 baseline candidate"
}
```

禁止字段：

- `universe`
- `date_start`
- `date_end`
- `forward_return_definition`
- `gate`
- `data_source`

### 8.2 Experiment Config

定义“这次实验怎么测”。

至少记录：

```json
{
  "experiment_id": "csi500_ohlcv_sandbox_v1",
  "dataset_id": "sandbox_v1",
  "universe": "csi500",
  "date_start": "2024-01-01",
  "date_end": "2025-12-31",
  "allowed_fields": ["open_hfq", "high_hfq", "low_hfq", "close_hfq", "volume"],
  "allowed_windows": [1, 3, 5, 10, 20],
  "horizons": ["1d", "5d", "20d"],
  "gate": {
    "version": "candidate_gate_v1"
  },
  "config_hash": "sha256:..."
}
```

### 8.3 Dataset Manifest

记录“实际用的是哪份数据”。

manifest 至少记录：

```json
{
  "dataset_id": "sandbox_v1",
  "experiment_id": "csi500_ohlcv_sandbox_v1",
  "source": "zer0share",
  "universe": "csi500",
  "source_universe_key": "csi500",
  "date_start": "2024-01-01",
  "date_end": "2025-12-31",
  "adjustment": "hfq",
  "forward_return_definition": "next_open_to_open_v1",
  "file_hashes": {
    "panel.parquet": "sha256:...",
    "forward_returns.parquet": "sha256:..."
  }
}
```

### 8.4 Run Manifest

记录“一次评价运行的上下文”。

manifest 至少记录：

```json
{
  "run_id": "smoke_001",
  "experiment_id": "csi500_ohlcv_sandbox_v1",
  "dataset_id": "sandbox_v1",
  "candidate_file_hash": "sha256:...",
  "config_hash": "sha256:...",
  "tool_version": "0.1.0",
  "log_file": "runs/smoke_001/logs/evaluate.log",
  "logging_level_file": "DEBUG",
  "logging_level_console": "INFO"
}
```

### 8.5 Candidate Result

run artifact 中每个候选都要有结果：

```json
{
  "run_id": "smoke_001",
  "candidate_id": "fa_0001_range_position",
  "status": "candidate_pass",
  "failure_bucket": null,
  "best_horizon": "20d",
  "best_horizon_score": 1.2,
  "details": {}
}
```

允许状态：

- `candidate_pass`
- `candidate_fail`
- `invalid`
- `error`

允许 failure bucket：

- `validate_failed`
- `gate_failed`
- `runtime_error`

### 8.6 Metrics / IC Series

保存“可复查的详细证据”。

metrics 至少包含：

```json
{
  "run_id": "smoke_001",
  "candidate_id": "fa_0001_range_position",
  "horizon": "20d",
  "ic_mean": 0.012,
  "rankic_mean": 0.018,
  "icir": 0.42,
  "coverage_mean": 0.91,
  "long_short_return": 0.006,
  "monotonicity": 0.8,
  "effective_trade_days": 210,
  "complexity_score": 7
}
```

IC series 至少以 `(run_id, candidate_id, horizon, trade_date)` 作为可追溯键，保存每日 `IC` / `RankIC` 等序列。

### 8.7 Registry

只记录“哪些因子在哪次实验通过”，不复制完整指标。

registry 记录示意：

```json
{
  "candidate_id": "fa_0001_range_position",
  "status": "candidate_pass",
  "dataset_id": "sandbox_v1",
  "experiment_id": "csi500_ohlcv_sandbox_v1",
  "run_id": "smoke_001",
  "best_horizon": "20d",
  "best_horizon_score": 1.2
}
```

## 9. 工程任务拆分

### Task 1：仓库骨架

目标：先让项目像一个可安装、可测试的 Python 包。

涉及文件：

```text
.
├── README.md
├── pyproject.toml
├── uv.lock
├── AGENTS.md
├── codex/
│   ├── program.md
│   ├── memory.md
│   └── research_notes.md
├── factor_autoresearch/
│   └── __init__.py
├── candidate_factors/
│   ├── candidates.jsonl
│   └── registry.jsonl
├── official_factors/
│   └── README.md
├── runs/
│   └── .gitkeep
└── tests/
    └── test_package_imports.py
```

实现要点：

- `README.md` 先放最小仓库说明和待补内容占位。
- `pyproject.toml` 声明包名、依赖、`fm` CLI entrypoint。
- 使用 `uv` 管理虚拟环境和 lockfile，提交 `uv.lock`。
- `AGENTS.md` 写清 Codex 权限边界。
- `codex/program.md`、`codex/memory.md`、`codex/research_notes.md` 先放初始内容。
- `registry.jsonl` 初始为空。

测试：

```bash
uv run pytest tests/test_package_imports.py -v
```

验收：

- `import factor_autoresearch` 成功。
- 项目目录和 framework spec 的最小目录合同一致。

### Task 2：配置系统

目标：把 experiment 和 gate 的参数从代码里拿出来，放进 TOML。

涉及文件：

```text
configs/
├── csi500_ohlcv_sandbox_v1.toml
└── candidate_gate_v1.toml

factor_autoresearch/
└── config.py

tests/
└── test_config.py
```

实现要点：

- `csi500_ohlcv_sandbox_v1.toml` 定义 universe、日期、字段、函数、窗口、category、horizon、预处理参数。
- `candidate_gate_v1.toml` 定义 gate 阈值和分数组件权重。
- `config.py` 读取 TOML，返回 typed dataclass。
- 对每份 config 计算 `sha256`，写入 run manifest。

审阅提示：

```python
config.allowed_fields
# 这里必须只有 open_hfq / high_hfq / low_hfq / close_hfq / volume。
# 如果 industry 或 market_cap 出现在这里，就破坏了 experiment spec。
```

测试：

```bash
uv run pytest tests/test_config.py -v
```

### Task 3：候选 JSONL 校验

目标：确保候选记录格式正确，且没有把实验参数塞进候选里。

涉及文件：

```text
factor_autoresearch/
└── candidates.py

tests/
└── test_candidates.py
```

实现要点：

- 逐行读取 JSONL。
- 校验必填字段。
- 校验 `candidate_id` 唯一。
- 校验 category 和 expected_direction。
- 拒绝 forbidden fields。

审阅提示：

```python
FORBIDDEN_FIELDS = {
    "universe",
    "date_start",
    "date_end",
    "forward_return_definition",
    "gate",
    "data_source",
}
# 候选只能表达研究想法，不能偷偷改变实验环境。
```

测试：

```bash
uv run pytest tests/test_candidates.py -v
```

### Task 4：FactorCalc 和受限 Expression DSL

目标：让候选表达式能安全解析和计算，但不能执行任意 Python 代码。

涉及文件：

```text
factor_autoresearch/
└── calculator.py

tests/
└── test_calculator.py
```

实现要点：

- 提供 `FactorCalc` 类作为候选因子计算入口。
- 解析表达式并生成受限 AST。
- 校验字段、函数、窗口。
- 计算 complexity score 和 lookback。
- 实现安全数值规则。
- 实现 `delay`、`ts_mean`、`ts_std`、`ts_delta`、`ts_return`、`ts_rank`、`cs_rank`、`cs_zscore`。

审阅提示：

```python
FactorCalc().calculate(candidate_with("cs_rank(close_hfq)"), dataset, config)
# 这是允许的，因为 cs_rank 在白名单里，close_hfq 是允许字段。

FactorCalc().calculate(candidate_with("__import__('os').system('rm -rf /')"), dataset, config)
# 必须拒绝。DSL 不是 Python 执行环境。
```

测试：

```bash
uv run pytest tests/test_calculator.py -v
```

### Task 5：固定 Dataset Loader

目标：评价阶段只从 `datasets/sandbox_v1/` 读取固定数据。

涉及文件：

```text
factor_autoresearch/
└── data_loader.py

tests/
└── test_data_loader.py
```

实现要点：

- 读取 `panel.parquet`。
- 读取 `forward_returns.parquet`。
- 读取 `manifest.json`。
- 校验字段和主键唯一性。

审阅提示：

```python
DataLoader().load(Path("datasets/sandbox_v1"), config)
# 评价器只能走这个入口，不能直接访问 zer0share。
```

测试：

```bash
uv run pytest tests/test_data_loader.py -v
```

### Task 6：Dataset Prepare 边界

目标：实现维护者使用的数据冻结入口。

涉及文件：

```text
factor_autoresearch/
└── prepare.py

tests/
└── test_prepare.py
```

实现要点：

- `prepare_fixed_dataset` 可以访问受控本地数据源。
- 输出固定的 panel、forward returns、manifest、README。
- forward return 按 open-to-open 定义生成。
- manifest 记录 source path 和 source universe key。

审阅提示：

- 这个模块可以接触源数据。
- `evaluate.py` 不应该 import 或调用这个模块。

测试：

```bash
uv run pytest tests/test_prepare.py -v
```

### Task 7：预处理

目标：实现固定评价预处理，让每个候选因子在同一口径下比较。

涉及文件：

```text
factor_autoresearch/
└── preprocess.py

tests/
└── test_preprocess_metrics.py
```

实现要点：

- 每日横截面 winsorize。
- 每日横截面 zscore。
- 每日横截面行业和市值中性化。
- 输出 residual factor。

审阅提示：

```text
raw factor
  -> winsorize
  -> zscore
  -> OLS neutralization
  -> residual
```

测试：

```bash
uv run pytest tests/test_preprocess_metrics.py -v
```

### Task 8：Metrics

目标：实现候选评价指标。

涉及文件：

```text
factor_autoresearch/
└── metrics.py

tests/
└── test_preprocess_metrics.py
```

实现要点：

- 按 `(trade_date, ts_code)` join factor 和 forward returns。
- 对 1d / 5d / 20d 分别计算 IC、RankIC、ICIR、coverage、分层收益、多空收益、monotonicity。
- 记录 `effective_trade_days`。
- 每日有效横截面样本数不足 100 时跳过当日 IC / RankIC。

审阅提示：

```python
rankic_mean_20d
# 这个值是 gate 重点使用的指标之一，命名必须稳定。
```

测试：

```bash
uv run pytest tests/test_preprocess_metrics.py -v
```

### Task 9：Candidate Gate 和 Registry

目标：把 metrics 转成 pass / fail，并只把 pass 写入 registry。

涉及文件：

```text
factor_autoresearch/
├── gate.py
└── registry.py

tests/
└── test_gate_registry.py
```

实现要点：

- 按 `expected_direction` 调整 IC、RankIC、monotonicity 方向。
- 计算每个 horizon 的 score。
- 取 best horizon。
- 应用硬规则。
- append-only 写 registry。

审阅提示：

```python
direction_sign = 1 if expected_direction == "positive" else -1
# 候选方向来自研究先验。方向不对的候选应该 fail，而不是自动翻转。
```

测试：

```bash
uv run pytest tests/test_gate_registry.py -v
```

### Task 10：Logging 基础设施

目标：让所有 CLI 命令都有统一日志口径，尤其是 evaluate 的持续过程记录。

涉及文件：

```text
factor_autoresearch/
└── logging_config.py

tests/
└── test_logging_config.py
```

实现要点：

- 提供 `configure_logging(run_dir, verbose, quiet=False)`。
- console handler 写 stderr，默认短输出，`--verbose` 输出过程细节。
- file handler 写 `runs/{run_id}/logs/evaluate.log`，固定记录 DEBUG 及以上完整过程。
- 日志格式至少包含 timestamp、level、module、run_id、candidate_id、stage、message。
- 重复调用配置函数不能重复添加 handler，避免同一条日志打印多次。
- 单个 candidate 的异常要记录 stack trace，但不能阻断 batch。

审阅提示：

```text
--verbose
  -> 让人看到更多过程
  -> 不改变 evaluate 的结果
  -> 不改变 evaluate.log 的完整程度
```

测试：

```bash
uv run pytest tests/test_logging_config.py -v
```

### Task 11：Evaluate Orchestration

目标：串起完整评价流程并写出 artifacts。

涉及文件：

```text
factor_autoresearch/
├── evaluate.py
└── logging_config.py

runs/
└── {run_id}/

tests/
├── test_evaluate.py
└── test_logging_config.py
```

实现要点：

- 创建 run 目录。
- 初始化 run 级 file logger。
- 写 run manifest。
- 对每个 candidate 执行 parse、evaluate expression、preprocess、metrics、gate。
- 单候选失败时记录 error 和 stack trace，不中断整批。
- 写 `summary.md`、`candidate_results.jsonl`、`metrics.parquet`、`ic_series.parquet`、`evaluate.log`。
- candidate_pass 追加 registry。

审阅提示：

```text
candidate invalid/error
  -> 写入 runs/{run_id}/results/candidate_results.jsonl
  -> 不写 registry
  -> 继续处理下一个 candidate
```

测试：

```bash
uv run pytest tests/test_evaluate.py -v
```

### Task 12：CLI

目标：给人和 Codex 一个稳定命令入口。

涉及文件：

```text
factor_autoresearch/
└── cli.py

tests/
└── test_cli.py
```

实现命令：

```bash
uv run fm dataset prepare-fixed --config configs/csi500_ohlcv_sandbox_v1.toml --output datasets/sandbox_v1
uv run fm factor validate --dataset datasets/sandbox_v1 --candidates candidate_factors/candidates.jsonl --verbose
uv run fm factor evaluate --dataset datasets/sandbox_v1 --candidates candidate_factors/candidates.jsonl --run-id smoke_001 --verbose
uv run fm experiment clean --experiment-id csi500_ohlcv_sandbox_v1
uv run fm experiment clean --experiment-id csi500_ohlcv_sandbox_v1 --yes
```

审阅提示：

- `validate` 只做静态校验。
- `evaluate` 才计算 factor values 和 metrics。
- CLI 默认输出要短，但要告诉用户 summary 和 evaluate log 写到哪里。
- `--verbose` 展示持续过程；适合人工盯运行，也适合 Codex 排查失败。
- `experiment clean` 未传 `--yes` 时只展示 dry-run 清单，避免误删。

测试：

```bash
uv run pytest tests/test_cli.py -v
```

### Task 13：实验输出清理

目标：支持测试后清空 run artifacts 和 registry 结果，从干净状态重新开始。

涉及文件：

```text
factor_autoresearch/
├── cleanup.py
└── cli.py

tests/
└── test_cleanup.py
```

实现要点：

- `fm experiment clean --experiment-id csi500_ohlcv_sandbox_v1` 默认 dry-run。
- `fm experiment clean --experiment-id csi500_ohlcv_sandbox_v1 --yes` 才执行清理。
- 清理 `runs/` 中属于该 experiment 的 run 目录。
- 清空或过滤 `candidate_factors/registry.jsonl` 中属于该 experiment 的记录。
- 保留 `candidate_factors/candidates.jsonl`、`datasets/`、`configs/`、`codex/research_notes.md`、`codex/memory.md`。
- 输出清理摘要：删除 run 数、移除 registry 行数、保留的输入文件。

审阅提示：

```text
clean outputs
  -> 删除 evaluate 产生的输出
  -> 清空 registry 结果
  -> 不删除候选输入、固定数据集、配置和研究笔记
```

测试：

```bash
uv run pytest tests/test_cleanup.py -v
```

### Task 14：Runbook 和 Smoke Test

目标：提供第一轮 sandbox 实验怎么跑的说明，以及一个最小可跑 fixture。

涉及文件：

```text
docs/
└── experiments/
    └── csi500-ohlcv-sandbox-v1-runbook.md

tests/
├── fixtures/
│   └── sandbox_v1/
└── test_smoke_run.py
```

runbook 内容：

```text
1. 阅读 sandbox spec。
2. 阅读 `codex/memory.md` 和 `codex/research_notes.md`。
3. 追加 30 个 JSONL candidates。
4. 运行 `uv run fm factor validate --verbose`。
5. 运行 `uv run fm factor evaluate --verbose`。
6. 阅读 runs/{run_id}/summary.md。
7. 出错时先阅读 runs/{run_id}/logs/evaluate.log。
8. 测试或试跑结束后，如需从零开始，运行 `uv run fm experiment clean --experiment-id csi500_ohlcv_sandbox_v1 --yes`。
9. 更新 `codex/research_notes.md`。
10. 只有多轮稳定 insight 才更新 `codex/memory.md`。
```

测试：

```bash
uv run pytest tests/test_smoke_run.py -v
```

### Task 15：最终验证

目标：确认整条链路能工作。

命令：

```bash
uv run pytest -v
uv run ruff check .
uv run fm --help
uv run fm factor validate --dataset datasets/sandbox_v1 --candidates candidate_factors/candidates.jsonl --verbose
uv run fm factor evaluate --dataset datasets/sandbox_v1 --candidates candidate_factors/candidates.jsonl --run-id smoke_001 --verbose
uv run fm experiment clean --experiment-id csi500_ohlcv_sandbox_v1
```

验收：

- 全部测试通过。
- lint 通过。
- CLI help 正常。
- `--verbose` 能输出过程日志，且不改变评价结果。
- validate 对 seed batch 返回 0 invalid。
- evaluate 写出 `runs/smoke_001/summary.md`。
- evaluate 写出 `runs/smoke_001/logs/evaluate.log`。
- 每个 candidate 都有最终状态。
- 通过 gate 的 candidate 才进入 registry。
- clean dry-run 能列出将清理的 run artifacts 和 registry 行数，但不修改文件。

## 10. 第一轮候选和实验运行限制

每轮候选数量：

```text
30
```

Codex 第一阶段只能维护：

```text
candidate_factors/candidates.jsonl
codex/memory.md
codex/research_notes.md
```

Codex 不能修改：

```text
README.md
AGENTS.md
codex/program.md
configs/**
datasets/**
factor_autoresearch/**
official_factors/**
candidate_factors/registry.jsonl
pyproject.toml
uv.lock
tests/**
```

注意：上面是研究循环阶段的权限边界。工程实现阶段当然需要创建和修改 `README.md`、`codex/`、`factor_autoresearch/`、`tests/`、`configs/` 等文件。

## 11. 风险和设计取舍

### 11.1 DSL 用 Python AST 解析的风险

风险：如果白名单不严格，可能意外允许 Python 能力。

取舍：Python AST 可以快速实现表达式 parser，但必须逐节点校验，只允许明确支持的节点和函数。

验收重点：

- unknown field 必须 fail。
- unknown function 必须 fail。
- attribute / subscript / lambda / comprehension 必须 fail。

### 11.2 pandas 和 DuckDB 边界

风险：如果同一段评价逻辑同时存在 pandas 和 DuckDB 两套实现，容易出现结果不一致。

取舍：v1 的 canonical evaluator 用 pandas 实现，所有 gate 结果以 pandas 路径为准。DuckDB 只用于读取 parquet、检查固定 dataset、查询 run artifacts 和辅助人工审计，不实现另一套因子评价语义。

验收重点：

- `evaluate.py` 不依赖 DuckDB 计算 gate 指标。
- DuckDB 查询不能修改 dataset、candidate JSONL 或 registry。

### 11.3 不引入 QLib

风险：QLib 提供完整量化研究平台能力，但会同时引入数据 handler、feature expression、model workflow 和 recorder 等概念，容易让 v1 的边界变重。

取舍：v1 不引入 QLib。候选表达式使用本项目自定义受限 DSL，数据读取使用固定 dataset loader，评价和 artifact 合同由本项目工具层直接实现。

验收重点：

- `factor_autoresearch/` 不依赖 QLib。
- candidate DSL 的字段、函数和窗口只来自 experiment config。
- evaluator 的输入输出合同不绑定 QLib recorder 或 workflow。

### 11.4 中性化实现

风险：行业 dummy、缺失市值、样本不足可能导致 OLS 不稳定。

取舍：v1 先用每日横截面 OLS，缺失值不填充，样本不足时该日残差缺失。

验收重点：

- `market_cap <= 0` 按市值暴露缺失处理。
- industry 和 size 在同一个横截面模型中同时中性化。

### 11.5 Registry append-only

风险：重复 evaluate 同一个 run 可能重复写 registry。

取舍：v1 先保持 append-only 审计语义；可以在 registry writer 中拒绝重复 `(candidate_id, dataset_id, run_id)`。

验收重点：

- 不重写历史 registry。
- 不写 failed / invalid / error。

### 11.6 Logging 口径膨胀

风险：如果每个模块自己配置 logger，CLI 会出现重复日志、格式不一致、verbose 行为不一致，甚至让日志反过来影响评价结果。

取舍：v1 只允许 `logging_config.py` 统一配置 handler 和 level。业务模块只拿 `logging.getLogger(__name__)` 记录事件，不自己添加 handler。

验收重点：

- 默认 CLI 输出短，`--verbose` 输出过程细节。
- `evaluate.log` 始终完整记录 DEBUG 及以上运行过程。
- 重复调用 CLI 或测试中的 logging 配置，不应让同一条日志重复输出。
- logging 不能改变任何 metrics、gate 或 registry 结果。

### 11.7 清理命令误删输入

风险：为了测试方便加入 clean/reset 后，如果边界不清，可能误删 candidates、dataset、config 或研究笔记，导致实验不可复现。

取舍：v1 只提供 outputs clean，不提供全仓库 reset。默认 dry-run，执行必须显式传 `--yes`。

验收重点：

- 清理只影响 `runs/` 和 `candidate_factors/registry.jsonl`。
- `candidate_factors/candidates.jsonl`、`datasets/`、`configs/`、`codex/research_notes.md`、`codex/memory.md` 保持不变。
- 清理前后可以重新运行同一个 smoke evaluate。

## 12. 验收标准

工程验收通过条件：

1. 仓库目录符合第 5 节结构。
2. `fm dataset prepare-fixed` 能生成 `datasets/sandbox_v1`。
3. `fm factor validate` 能静态校验候选 JSONL 和 DSL。
4. `fm factor validate` 不计算指标、不读取因子值。
5. `fm factor evaluate` 只读取固定 dataset、候选 JSONL 和 configs。
6. 表达式 DSL 拒绝未知字段、未知函数、非法窗口和任意 Python 代码。
7. 评价预处理顺序是 winsorize、zscore、行业 + 市值中性化、metrics。
8. 每个候选在 run result 中得到 `candidate_pass`、`candidate_fail`、`invalid` 或 `error`。
9. 每个失败或无效候选都有 `failure_bucket` 和 `details`。
10. 每次 evaluate 都写出 `runs/{run_id}/summary.md`。
11. 每次 evaluate 都写出 `runs/{run_id}/logs/evaluate.log`。
12. CLI 支持 `--verbose`，能展示持续过程日志。
13. `--verbose` 和默认模式的 metrics、gate、registry 结果一致。
14. 通过 gate 的候选追加到 `candidate_factors/registry.jsonl`。
15. 未通过 gate、无效、运行错误的候选不写 registry。
16. `fm experiment clean --experiment-id csi500_ohlcv_sandbox_v1` 默认 dry-run，不修改文件。
17. `fm experiment clean --experiment-id csi500_ohlcv_sandbox_v1 --yes` 可以清空 run artifacts 和该 experiment 的 registry 结果。
18. 清理命令不能删除 candidates、dataset、configs、research notes 或 memory。
19. 同一个 dataset、candidate JSONL、config 和 tool version 重复运行，应产生相同 summary 和 registry-eligible 结果。

## 13. 后续不在 v1 做的事情

v1 不做：

- OOS / walk-forward。
- 交易成本建模。
- registry 相关性检查。
- official factor 晋升。
- 财务、分钟级、盘口特征。
- 自动模板搜索。
- 自动表达式树搜索。
- LLM API 内嵌调用。

这些可以在 sandbox v1 跑稳定以后，进入 v1.5 或 v2。

## 14. 当前实现回填（2026-06-22）

本节用于回填本实施计划在当前仓库中的实际落地状态，帮助后续维护者快速区分“计划要求”和“当前已交付结果”。

### 14.1 当前实现状态

截至 `2026-06-22`，sandbox v1 的核心闭环已经在仓库中落地并跑通：

- 已实现 `fm dataset prepare-fixed`，可从本地 `zer0share` 数据生成 `datasets/sandbox_v1/` 固定数据集。
- 已实现 `fm factor validate`，可对 `candidate_factors/candidates.jsonl` 做 JSONL、字段、category、方向、DSL、窗口、lookback、complexity 的静态校验。
- 已实现 `fm factor evaluate`，可读取固定 dataset、执行候选表达式、做预处理、计算 metrics、执行 gate，并写出 run artifacts。
- 已实现 `candidate_factors/registry.jsonl` append-only 写入逻辑，只记录 `candidate_pass`。
- 已实现统一日志配置，控制台支持 `--verbose`，并持续写出 `runs/{run_id}/logs/evaluate.log`。
- 已实现 `fm experiment clean`，默认 dry-run，传 `--yes` 后清理当前 experiment 的 run 输出和 registry 结果。
- 已补齐 pytest 测试与 smoke test，并已通过 `ruff check .`。

当前主要实现文件包括：

- `factor_autoresearch/config.py`
- `factor_autoresearch/candidates.py`
- `factor_autoresearch/calculator.py`
- `factor_autoresearch/data_loader.py`
- `factor_autoresearch/prepare.py`
- `factor_autoresearch/preprocess.py`
- `factor_autoresearch/metrics.py`
- `factor_autoresearch/gate.py`
- `factor_autoresearch/registry.py`
- `factor_autoresearch/logging_config.py`
- `factor_autoresearch/cleanup.py`
- `factor_autoresearch/evaluate.py`
- `factor_autoresearch/cli.py`

### 14.2 当前数据准备状态

`zer0share` 当前本地数据状态已满足本轮 sandbox v1 的固定 dataset 生成要求：

- 已同步：`basic`、`trade_cal`、`daily_kline`、`adj_factor`、`daily_basic`、`stock_st`、`suspend_d`、`stk_limit`、`index_weight`
- 已构建股票池：`univ_trade_zz500` 等 universe 分区
- 已有行业映射：`sw_member`
- 当前固定 dataset 已生成：`datasets/sandbox_v1/`

### 14.3 当前实现偏差

当前实现存在一项已知、且是有意接受的偏差：

- 原实验规格和数据准备设想中，行业暴露优先希望使用 `ci_member`。
- 实际执行时，当前 Tushare token 不具备 `ci_index_member` 接口权限，无法完成 `zer0share` 的 `ci_member` 同步。
- 因此当前 `prepare-fixed` 实现改为使用本地已同步的 `sw_member` 一级行业映射作为 `industry` 暴露来源。
- 这一偏差不影响 sandbox v1 的“固定 dataset -> validate -> evaluate -> registry -> notes”闭环，但会影响行业暴露口径。

当前配置中的落地口径为：

```toml
industry_source = "sw_l1_name"
```

如果未来 token 权限补齐，可以将行业源切回 CI 口径，并重新生成固定 dataset。

### 14.4 第一轮实际运行结果

当前仓库已经完成第一轮真实候选挖掘，运行信息如下：

- run id：`batch_001`
- summary：`runs/batch_001/summary.md`
- log：`runs/batch_001/logs/evaluate.log`
- registry 输出：`candidate_factors/registry.jsonl`

本轮 batch 的结果为：

- 候选数：30
- `candidate_pass`：8
- `candidate_fail`：22
- `invalid`：0
- `error`：0

本轮通过 gate 的候选包括：

- `fa_0005_daily_range`
- `fa_0010_volume_volatility`
- `fa_0019_reversal_3d`
- `fa_0020_reversal_5d`
- `fa_0021_daily_vol_5d`
- `fa_0022_daily_vol_10d`
- `fa_0023_range_vol_5d`
- `fa_0024_range_mean_5d`

从当前结果看，第一轮更强的方向集中在：

- 负向 `volatility`
- 负向 `reversal`

### 14.5 当前验收结论

按照本计划第 12 节验收标准，当前状态可以判定为：

- 工程闭环已完成
- 固定 dataset 已生成
- validate / evaluate / registry / summary / evaluate.log 均已真实产出
- 测试与 lint 已通过
- 首轮 30 候选真实挖掘已完成

因此，sandbox v1 当前可以视为“已完成首次可运行实现，并已完成第一轮真实因子挖掘”。
