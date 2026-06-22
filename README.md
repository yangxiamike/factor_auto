# Factor Autoresearch

Factor Autoresearch 是一个面向 A 股日频因子研究的确定性 sandbox 工具链。

它的第一轮实验是 **中证500 OHLCV Sandbox v1**：用固定的中证500方向日频数据集，评价一批手写 DSL 候选因子，并把每次运行的结果完整落盘，方便复现、审计和继续研究。

## 1. 项目背景

传统因子研究里，最容易混在一起的是三件事：

- 研究假设：想测试什么因子。
- 实验环境：用什么股票池、什么日期、什么字段、什么评价指标。
- 运行结果：每个候选因子到底是通过、失败、无效，还是运行出错。

这个项目把它们拆开：

- Codex / 研究者负责提出候选因子和总结研究观察。
- Python 工具负责固定数据读取、候选校验、因子计算、指标评价和结果落盘。
- 文档和配置负责锁定实验规则，避免为了某个结果临时改口径。

v1 的目标不是立刻挖出最强因子，而是先把“候选提交 -> 校验 -> 评价 -> 记录 -> 复现”这条闭环搭起来。

## 2. 当前 Sandbox

第一轮 sandbox 固定规则：

- universe：中证500方向股票池。
- 数据区间：`2024-01-01` 到 `2025-12-31`。
- 数据频率：日频。
- 可搜索字段：后复权 OHLCV 和成交量。
- forward return：`1d`、`5d`、`20d`。
- 预处理：winsorize、zscore、行业中性化、市值中性化。
- 候选来源：追加到 `candidate_factors/candidates.jsonl` 的手写 DSL。
- 结果归档：每次 evaluate 写入 `runs/{run_id}/`。
- 通过 gate 的候选写入 `candidate_factors/registry.jsonl`。

面向人的业务名称是“中证500”；配置和 artifact 里的稳定 profile 标识仍使用 `csi500`，例如 `csi500_ohlcv_sandbox_v1`。

## 3. 重要目录

```text
configs/
  csi500_ohlcv_sandbox_v1.toml    # sandbox 实验配置
  candidate_gate_v1.toml          # candidate gate 配置

datasets/sandbox_v1/
  panel.parquet                   # 固定 panel 数据
  forward_returns.parquet         # 固定 forward return
  manifest.json                   # 数据集口径和来源记录

candidate_factors/
  candidates.jsonl                # 候选因子输入，只追加
  registry.jsonl                  # 通过 gate 的候选输出

runs/
  {run_id}/                       # 每次评价的完整输出

codex/
  research_notes.md               # 当前研究过程笔记
  memory.md                       # 多轮稳定 insight

factor_autoresearch/
  *.py                            # 确定性 Python 工具层

docs/
  framework/                      # 长期框架合同
  experiments/                    # sandbox 实验规格
  plans/                          # 实施计划和任务拆分
```

## 4. 快速开始

### 4.1 安装依赖

本项目使用 `uv` 管理环境和命令执行。

```bash
uv sync --all-groups
```

### 4.2 校验候选

```bash
uv run fm factor validate \
  --dataset datasets/sandbox_v1 \
  --candidates candidate_factors/candidates.jsonl \
  --verbose
```

这个命令只做静态校验，不计算因子值，也不写 registry。

### 4.3 运行评价

```bash
uv run fm factor evaluate \
  --dataset datasets/sandbox_v1 \
  --candidates candidate_factors/candidates.jsonl \
  --run-id batch_001 \
  --verbose
```

评价完成后重点看：

- `runs/batch_001/summary.md`
- `runs/batch_001/results/candidate_results.jsonl`
- `runs/batch_001/results/metrics.parquet`
- `runs/batch_001/logs/evaluate.log`
- `candidate_factors/registry.jsonl`

### 4.4 清空测试输出

如果只是想看会清理什么，先跑 dry-run：

```bash
uv run fm experiment clean \
  --experiment-id csi500_ohlcv_sandbox_v1
```

确认后再真正清理：

```bash
uv run fm experiment clean \
  --experiment-id csi500_ohlcv_sandbox_v1 \
  --yes
```

清理命令只清实验输出：

- 会清理：`runs/` 下属于该 experiment 的 run artifacts。
- 会清理：`candidate_factors/registry.jsonl` 里属于该 experiment 的记录。
- 不会清理：`candidate_factors/candidates.jsonl`。
- 不会清理：`datasets/`、`configs/`、`codex/research_notes.md`、`codex/memory.md`。

### 4.5 重新准备固定数据集

这个命令只给维护者使用。它会从本地受控数据源生成固定 sandbox 数据集。

```bash
uv run fm dataset prepare-fixed \
  --config configs/csi500_ohlcv_sandbox_v1.toml \
  --output datasets/sandbox_v1
```

普通实验评价阶段不应该直接访问原始数据源，只读 `datasets/sandbox_v1/`。

## 5. 候选因子怎么写

候选因子写在：

```text
candidate_factors/candidates.jsonl
```

每行是一个 JSON 对象。示例：

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
  "notes": "baseline candidate"
}
```

候选里不能偷偷改变实验环境。不要放这些字段：

- `universe`
- `date_start`
- `date_end`
- `forward_return_definition`
- `gate`
- `data_source`

## 6. 一轮研究怎么走

推荐流程：

1. 阅读 `docs/experiments/factor-autoresearch-sandbox-v1.md`。
2. 阅读 `codex/memory.md` 和 `codex/research_notes.md`。
3. 在 `candidate_factors/candidates.jsonl` 末尾追加候选。
4. 运行 `fm factor validate`。
5. 运行 `fm factor evaluate`。
6. 阅读 `runs/{run_id}/summary.md`。
7. 出错时先看 `runs/{run_id}/logs/evaluate.log`。
8. 把本轮观察写入 `codex/research_notes.md`。
9. 只有多轮反复稳定的结论，才写入 `codex/memory.md`。

## 7. 测试和质量检查

运行全部测试：

```bash
uv run pytest -v
```

运行代码检查：

```bash
uv run ruff check .
```

常见的单项测试：

```bash
uv run pytest tests/test_candidates.py -v
uv run pytest tests/test_calculator.py -v
uv run pytest tests/test_evaluate.py -v
uv run pytest tests/test_cleanup.py -v
uv run pytest tests/test_smoke_run.py -v
```

## 8. 边界和注意事项

- `datasets/sandbox_v1/` 是固定实验输入，evaluate 阶段只读它。
- `configs/` 定义实验规则，不应该为了某个候选结果临时修改。
- `candidate_factors/candidates.jsonl` 是候选输入和审计记录，默认只追加。
- `candidate_factors/registry.jsonl` 是工具输出，只有通过 gate 的候选会进入。
- `runs/{run_id}/` 是一次运行的完整证据，包含 summary、metrics、candidate results、因子值和日志。
- `official_factors/` 在 v1 不做晋升，只保留说明。

## 9. 文档入口

建议按这个顺序读：

1. `README.md`：项目入口和常用操作。
2. `docs/framework/factor-autoresearch-framework-v1.md`：长期框架合同。
3. `docs/experiments/factor-autoresearch-sandbox-v1.md`：第一轮中证500 sandbox 规则。
4. `docs/experiments/csi500-ohlcv-sandbox-v1-runbook.md`：每轮实验操作步骤。
5. `docs/plans/factor-autoresearch-sandbox-v1-implementation-plan.md`：实现任务、测试和验收拆分。

## 10. 当前定位

这个仓库现在是研究 sandbox，不是生产交易系统。

它关心的是：

- 实验口径固定。
- 候选输入可审计。
- 评价流程可复现。
- 输出结果可追踪。
- 多轮研究可以沉淀经验。

它暂时不处理：

- 实盘交易。
- 交易成本模型。
- 自动搜索引擎。
- 全 A 股票池。
- official factor 晋升。
