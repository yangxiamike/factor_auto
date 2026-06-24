# Factor Autoresearch 数据与样本协议 v1 实施计划

日期：2026-06-24

## 1. 目标

本计划用于执行 `docs/framework/factor-autoresearch-data-sample-protocol-v1-spec.md`。

核心策略：

```text
先做不碰区块一热区的部分，再等区块一稳定后做运行链路集成。
```

区块一当前仍在继续优化计算引擎，因此区块二需要拆成两条线：

- A 线：现在可以并行做，主要是数据口径、质量检查、样本协议独立模块和文档。
- B 线：等区块一收口后再做，主要是 evaluate 集成、run manifest 合并、slice 级 metrics / diagnostics / gate 消费。

这样既能提前铺好数据地基，又不会和区块一的 `DatasetBundle`、`PanelStore`、`evaluate.py`、`config.py` 频繁冲突。

## 2. A 线：现在可以先做

### 2.1 Source Pipeline Review

目标：确认 zer0share 侧数据构造流程，形成可审计记录。

工作内容：

- 查看 zer0share 中交易日历来源。
- 查看 universe membership 的来源和 `source_universe_key` 口径。
- 查看 ST、退市整理、停牌、涨跌停、低流动性、低成交量等基础过滤在哪里做。
- 查看行业、市值、复权因子来自哪里。
- 标记 PIT（point-in-time，当时可见数据）已确认项和未确认风险。
- 不把 zer0share 的实现复制进本仓库。

交付物：

```text
docs/data/source-pipeline-review-zer0share-mining-v1.md
```

验收：

- 能说明当前 `sandbox_v1` 继承了哪些 zer0share 口径。
- 能列出 `mining_v1` 上线前必须确认的 PIT 风险。
- 能给 `manifest.json` 提供应记录的 source pipeline 字段。

### 2.2 Data Quality Report 设计与独立实现

目标：先做 frozen dataset 入库验收，不接 evaluate 主流程。

建议新增：

```text
factor_autoresearch/data_quality.py
tests/test_data_quality.py
```

第一版检查：

- 文件是否存在：`panel.parquet`、`forward_returns.parquet`、`manifest.json`。
- 必需字段是否齐全。
- `(trade_date, ts_code)` 是否重复。
- manifest 的 `dataset_id`、`experiment_id`、日期范围是否和数据一致。
- `source`、`source_universe_key`、`base_filters_inherited`、`forward_return_definition` 是否存在。
- 每日 universe 数量统计。
- OHLCV、industry、market_cap 缺失率。
- forward return 覆盖率。
- `market_cap <= 0` 比例。

建议 CLI：

```bash
uv run fm dataset check-quality \
  --dataset datasets/sandbox_v1 \
  --config configs/csi500_ohlcv_sandbox_v1.toml
```

输出：

```text
datasets/{dataset_id}/data_quality_report.json
datasets/{dataset_id}/data_quality_report.md
```

验收：

- `sandbox_v1` 能生成质量报告。
- 合同破坏类问题返回 fail。
- 统计异常类问题返回 warning。
- 不修改 dataset 原始 parquet。

### 2.3 Sample Protocol 独立模块

目标：先把样本切片规则独立做出来，不要求 metrics / gate 立即消费。

建议新增：

```text
factor_autoresearch/sample_protocol.py
tests/test_sample_protocol.py
```

第一版支持：

- `sandbox_v1`：完整样本，保持当前快速开发语义。
- `mining_v1`：固定 formation / validation / OOS / walk-forward slices。
- `sample_protocol_hash`：用 canonical JSON 生成稳定 sha256。

建议 CLI：

```bash
uv run fm dataset show-slices \
  --dataset datasets/sandbox_v1 \
  --sample-protocol sandbox_v1
```

验收：

- 同一 dataset + 同一 protocol 多次生成相同 slices。
- `sample_protocol_hash` 稳定。
- candidate 无法传入或覆盖 sample protocol。

### 2.4 文档与配置草案

目标：先把 `mining_v1` 的规则写清楚，避免后续接代码时再争口径。

工作内容：

- 在 spec 中持续维护 `sandbox_v1` 和 `mining_v1` 的差异。
- 新增 `mining_v1` sample protocol 配置草案。
- 明确 forward return 默认仍为 `next_open_to_open_v1`。
- 明确 OOS / walk-forward 的具体日期窗口必须固化在协议中。

验收：

- 另一个 agent 能只看 spec + plan 就知道先做哪些模块。
- 不需要改动区块一的计算引擎代码。

## 3. B 线：等区块一稳定后再做

### 3.1 Config 集成

触发条件：

- 区块一的 engine 配置、jobs 配置、`ExperimentConfig` 边界稳定。

工作内容：

- 在 experiment config 增加 sample protocol 字段。
- 保持 `sandbox_v1` 默认兼容现有配置。
- 为 `mining_v1` 新增专用 config。

验收：

- 老配置仍能跑。
- 新配置能读取 sample protocol。
- config hash 包含 sample protocol 关键字段。

### 3.2 Run Manifest 集成

触发条件：

- 区块一的 run manifest engine 字段稳定。

工作内容：

- run manifest 写入 data quality report 路径。
- run manifest 写入 sample protocol、slices、hash。
- run manifest 同时保留区块一的 engine / jobs / equivalence 信息。

验收：

- 每次 run 可以追溯 dataset、source universe key、base filters、forward return、sample protocol、sample slices。
- 不破坏现有 artifact 读取逻辑。

### 3.3 Metrics / Diagnostics 按 Slice 消费

触发条件：

- 区块一的新 metrics / diagnostics 输出结构稳定。

工作内容：

- metrics 支持按 sample slice 计算。
- diagnostics 支持按 sample slice 汇总。
- `sandbox_v1` 仍输出当前全样本结果。
- `mining_v1` 输出 formation / validation / OOS / walk-forward 证据。

验收：

- 当前 `candidate_results.jsonl`、`metrics.parquet`、`ic_series.parquet` 不被无计划破坏。
- 新 slice 级结果有清晰 schema。
- 区块三可以直接读取 slice 级结果做 gate。

### 3.4 Gate 接入留给区块三

区块二不实现最终验收 gate。

区块二只保证：

- OOS / walk-forward 切片可复现。
- slice 级 metrics / diagnostics 可生成。
- run manifest 可追溯。

区块三再实现：

- `oos_gate`
- `walk_forward_gate`
- `correlation_dedup_gate`
- `incremental_signal_gate`
- acceptance report

## 4. 推荐实施顺序

建议顺序：

1. 补 source pipeline review 文档模板。
2. 实现 `data_quality.py` 和 `fm dataset check-quality`。
3. 给 `sandbox_v1` 跑出第一份 data quality report。
4. 实现 `sample_protocol.py`，先支持 `sandbox_v1`。
5. 增加 `mining_v1` sample protocol 草案和切片 hash。
6. 等区块一稳定后，集成 config 和 run manifest。
7. 再接 metrics / diagnostics 的 slice 级输出。
8. 交给区块三消费 OOS / walk-forward 结果。

## 5. 冲突控制

### 5.1 Worktree 与合并策略

区块一当前在独立 worktree 中继续开发计算引擎。区块二也应使用独立 worktree，不建议直接在 `M` / main 工作区上开发。

推荐结构：

```text
worktree-1: 区块一
  继续开发 compute engine、engine config、evaluate 边界

worktree-2: 区块二 A 线
  只开发 source review、data quality、sample protocol 独立模块

M / main:
  保持作为合并基线，不直接承载区块二开发
```

推荐流程：

1. 从当前主线或规划分支新开区块二 worktree。
2. 区块二 worktree 先只做 A 线。
3. 区块一合并回主线后，区块二 worktree rebase 或 merge 到最新主线。
4. 再开始区块二 B 线，接 config、run manifest、metrics / diagnostics slice 输出。
5. 如果区块二 A 线必须碰 `config.py` 或 `cli.py`，先确认区块一是否正在改同一文件；冲突较大时延后 CLI / config 接入。

这样可以让区块二提前推进，同时避免和区块一在 `evaluate.py`、`config.py`、`DatasetBundle`、run manifest 上互相覆盖。

### 5.2 文件边界

区块二 A 线阶段应避免修改：

```text
factor_autoresearch/evaluate.py
factor_autoresearch/metrics.py
factor_autoresearch/diagnostics.py
factor_autoresearch/preprocess.py
```

除非只是增加只读辅助入口或测试夹具。

A 线阶段可以优先修改或新增：

```text
docs/**
factor_autoresearch/data_quality.py
factor_autoresearch/sample_protocol.py
tests/test_data_quality.py
tests/test_sample_protocol.py
```

`factor_autoresearch/config.py` 和 `factor_autoresearch/cli.py` 是轻度冲突点：

- 如果区块一正在改它们，区块二先只写模块和测试，不接 CLI。
- 如果区块一已稳定，再补 CLI 和 config。

## 6. 验收标准

A 线完成标准：

- 有 source pipeline review 文档。
- `sandbox_v1` 能生成 data quality report。
- `sandbox_v1` sample protocol 能稳定生成 full sample slice。
- `mining_v1` sample protocol 草案明确。
- 不影响区块一 compute engine 开发。

B 线完成标准：

- run manifest 记录 data quality report 和 sample protocol。
- metrics / diagnostics 能按 sample slices 输出证据。
- candidate 不能改变 universe、日期范围、forward return 或样本窗口。
- 区块三可以直接消费 OOS / walk-forward 结果。

## 7. 当前建议

当前区块一已经接近完成，并且仍在继续计算优化。

因此现在建议新开区块二独立 worktree，并启动区块二 A 线：

```text
source pipeline review
data quality report
sample protocol 独立模块
mining_v1 窗口草案
```

暂缓区块二 B 线：

```text
evaluate 深度集成
run manifest 最终合并
metrics / diagnostics slice 级输出
gate 消费 OOS / walk-forward
```

等区块一的 engine、config、evaluate 边界稳定并合并回主线后，区块二 worktree 先 rebase / merge 最新主线，再进入 B 线。
