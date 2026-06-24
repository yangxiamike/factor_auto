# Factor Autoresearch 数据与样本协议 v1 规格说明

日期：2026-06-24

## 1. 目标

本规格说明定义路线图区块二“数据与样本协议”的第一版工作。

目标不是把 zer0share 的数据工程逻辑搬进 `factor_autoresearch`，而是建立一层清楚、可复现、可审计的研究样本合同：

- zer0share 负责生产数据、维护 PIT（point-in-time，当时可见数据）口径、构造股票池和执行基础过滤。
- `factor_autoresearch` 负责验收冻结数据、记录来源和口径、定义样本切片，并让后续 metrics、diagnostics、gate 复用同一套样本协议。
- `sandbox_v1` 继续作为快速开发数据集。
- 新增 `mining_v1` 作为严肃挖因子的样本协议。
- OOS（out-of-sample，样本外检验）和 walk-forward（滚动前推验证）先作为样本切片协议落地，后续区块三再用这些切片做验收 gate。

最终要让系统能回答：

```text
这次因子评价用了哪份数据？
数据来自哪个 zer0share universe key？
继承了哪些基础过滤？
forward return 怎么定义？
样本内、验证、OOS、walk-forward 窗口怎么切？
这份数据有没有通过基础质量检查？
```

## 2. 非目标

本阶段不做这些事：

- 不把 zer0share 变成本仓库子模块。
- 不在 `factor_autoresearch` 里重写 ST、停牌、涨跌停、指数成分、低流动性等基础过滤。
- 不让 evaluate 阶段直接查询 zer0share 原始数据。
- 不允许 candidate 自带或修改 universe、日期范围、forward return、sample window。
- 不在 v1 第一版扩展到完整全 A 股票池。
- 不在区块二决定 OOS gate 或 walk-forward gate 的通过阈值；这些属于区块三。
- 不做实盘可交易性、组合构建、成本模型或券商执行接口。

## 3. 总体边界

### 3.1 zer0share 负责什么

zer0share 是数据源和基础口径工厂，负责回答：

```text
某个交易日、某只股票，在当时可见数据下，原始状态是什么？
```

区块二需要审查并记录 zer0share 中以下来源：

- 交易日历：当前 adapter 读取 `stock/trade_cal/exchange=*/data.parquet`。
- 股票池 membership：当前 adapter 读取 `stock/universe/name={source_universe_key}/date=*/data.parquet`。
- 日频行情：当前 adapter 读取 `stock/daily_kline/date=*/data.parquet`。
- 日频基础指标：当前 adapter 读取 `stock/daily_basic/date=*/data.parquet`。
- 复权因子：当前 adapter 读取 `stock/adj_factor/date=*/data.parquet`。
- 行业归属：当前 adapter 读取 `stock/industry/sw_member/data.parquet` 或 `stock/industry/ci_member/data.parquet`。
- 基础过滤：中证500 membership、ST、退市整理、停牌、低流动性、低成交量、涨停、跌停等过滤应由 zer0share 的受控流程完成，并通过 `in_universe` 和 manifest 声明传递给本仓库。

区块二要做 source pipeline review（源流水线审查），但审查结论沉淀为文档、manifest 字段和质量报告，不复制上游实现。

### 3.2 factor_autoresearch 负责什么

`factor_autoresearch` 负责回答：

```text
这次因子研究允许使用哪些股票、哪些日期、哪个 forward return、哪些样本窗口？
```

它负责：

- 读取固定 dataset：`panel.parquet`、`forward_returns.parquet`、`manifest.json`。
- 校验 dataset 合同：字段、主键、日期、来源、过滤声明、forward return 定义。
- 输出 data quality report（数据质量报告）。
- 定义 sample protocol（样本协议）和 sample slices（样本切片）。
- 在 run manifest 中记录 dataset、sample protocol、窗口切片和质量报告路径。
- 保证 metrics、diagnostics、gate 复用同一套样本切片。

## 4. 数据集合同

固定 dataset 目录继续使用：

```text
datasets/{dataset_id}/
  panel.parquet
  forward_returns.parquet
  manifest.json
  README.md
```

### 4.1 `panel.parquet`

必需字段：

```text
trade_date
ts_code
in_universe
industry
market_cap
open_hfq
high_hfq
low_hfq
close_hfq
volume
```

合同要求：

- 主键 `(trade_date, ts_code)` 必须唯一。
- `trade_date` 必须能解析为交易日日期。
- `in_universe` 是固定股票池 membership，不由 candidate 或 evaluate 阶段重新计算。
- `industry` 和 `market_cap` 只作为评价预处理中性化暴露，不进入默认 DSL 搜索字段。
- OHLC 字段使用后复权价格。
- 缺失值保留为缺失，不在 dataset 合同层填充。

### 4.2 `forward_returns.parquet`

必需字段：

```text
trade_date
ts_code
fwd_ret_1d
fwd_ret_5d
fwd_ret_20d
```

默认 forward return 定义继续使用：

```text
forward_return_definition = "next_open_to_open_v1"
fwd_ret_h = open_hfq[t + h + 1] / open_hfq[t + 1] - 1
```

含义：

- day `t` 收盘后得到因子信号。
- 下一交易日后复权开盘价进场。
- 持有 `h` 个交易日后，用后复权开盘价退出。
- 如果进场或退出开盘价缺失，该样本 forward return 记为缺失。

未来如果新增 close-to-close、vwap-to-vwap 或其他收益口径，必须新增 protocol 版本，不能覆盖 `next_open_to_open_v1`。

### 4.3 `manifest.json`

v1 manifest 必须至少记录：

```json
{
  "dataset_id": "sandbox_v1",
  "experiment_id": "csi500_ohlcv_sandbox_v1",
  "created_at": "2026-06-22",
  "source": "zer0share",
  "source_path": "C:/Users/hp/Documents/zer0share",
  "universe": "csi500",
  "source_universe_key": "univ_trade_zz500",
  "date_start": "2024-01-01",
  "date_end": "2025-12-31",
  "adjustment": "hfq",
  "features": ["open_hfq", "high_hfq", "low_hfq", "close_hfq", "volume"],
  "preprocess_exposures": ["industry", "market_cap"],
  "base_filters_inherited": ["csi_membership", "st", "delisting", "suspension", "low_liquidity", "low_volume", "limit_up", "limit_down"],
  "forward_returns": ["1d", "5d", "20d"],
  "forward_return_definition": "next_open_to_open_v1"
}
```

`mining_v1` 阶段建议扩展字段：

```json
{
  "source_pipeline": {
    "name": "zer0share_daily_equity_pipeline",
    "review_status": "reviewed",
    "reviewed_at": "2026-06-24",
    "code_reference": "zer0share data pipeline paths reviewed in source_pipeline_review.md",
    "pit_assumption": "universe and exposures are generated from point-in-time source tables"
  },
  "data_quality_report": "datasets/mining_v1/data_quality_report.json",
  "sample_protocol_id": "mining_v1"
}
```

如果暂时拿不到 zer0share commit hash，可以先记录 pipeline 名称、关键路径和 review 文档路径；拿到版本信息后再补 `source_commit` 或 `source_file_hashes`。

## 5. Source Pipeline Review

Source pipeline review 是区块二的第一项工作。

它的目的不是证明上游每一条数据都绝对正确，而是确认：

```text
factor_autoresearch 使用的 frozen dataset 是否有清楚、可审计、可复现的上游来源。
```

### 5.1 审查清单

审查负责人需要输出：

- zer0share 中交易日历来源、字段和日期过滤逻辑。
- zer0share 中 `source_universe_key` 的构造逻辑。
- `in_universe` 是否已经继承基础过滤。
- ST、退市整理、停牌、涨跌停、低流动性、低成交量等过滤在 zer0share 的位置和口径。
- 行业归属是否按生效日期处理，是否有 out date。
- 市值字段来自哪里，单位和缺失处理是什么。
- 复权因子来自哪里，后复权 OHLC 如何构造。
- PIT 假设：哪些字段按当时可见数据生成，哪些字段可能存在未来修订风险。
- forward return 当前是在 `factor_autoresearch` prepare 阶段构造，还是未来考虑上移到 zer0share。

### 5.2 交付物

建议新增或维护：

```text
docs/data/source-pipeline-review-zer0share-mining-v1.md
```

第一版可先作为人工审查笔记，包含：

- 上游路径。
- 上游字段。
- 已确认的过滤。
- 尚未确认的 PIT 风险。
- 对 `manifest.json` 的记录建议。

区块二 spec 不要求每次 evaluate 读取这份文档，但要求 manifest 或 data quality report 能链接到它。

## 6. Data Quality Report

Data quality report 是 frozen dataset 的入库验收报告。

第一版输出建议：

```text
datasets/{dataset_id}/data_quality_report.json
datasets/{dataset_id}/data_quality_report.md
```

JSON 供程序读取，Markdown 供人复核。

### 6.1 检查项

必须检查：

- `panel.parquet` 和 `forward_returns.parquet` 是否存在。
- 必需字段是否齐全。
- `(trade_date, ts_code)` 是否唯一。
- manifest 的 `dataset_id`、`experiment_id`、`date_start`、`date_end` 是否和实际数据一致。
- manifest 的 `source`、`source_universe_key`、`base_filters_inherited`、`forward_return_definition` 是否存在。
- 每日 `in_universe == true` 数量的最小值、最大值、均值和异常日期。
- `open_hfq`、`high_hfq`、`low_hfq`、`close_hfq`、`volume` 在 universe 内的缺失率。
- `industry` 和 `market_cap` 在 universe 内的缺失率。
- `fwd_ret_1d`、`fwd_ret_5d`、`fwd_ret_20d` 在 universe 内的覆盖率。
- `market_cap <= 0` 的样本占比。
- forward return 覆盖率在样本尾部自然下降时，应标注为 expected tail missing，不直接视为异常。

### 6.2 fail / warning 规则

第一版使用两级结果：

```text
fail       影响研究可复现或合同完整性，不能进入严肃评价
warning    统计上可疑，需要人工看，但不一定阻塞 sandbox
```

建议直接 fail：

- 缺少必需文件。
- 缺少必需字段。
- 主键重复。
- manifest 与 config 的 `dataset_id` 或 `experiment_id` 不一致。
- manifest 缺少 `source_universe_key` 或 `forward_return_definition`。
- 实际日期范围不覆盖 manifest 声明日期范围。

建议 warning：

- 某些日期 universe 数量显著低于中位数。
- 行业或市值缺失率偏高。
- forward return 覆盖率在非尾部日期大面积缺失。
- `in_universe == true` 但 OHLCV 大面积缺失。
- manifest 声明继承某类基础过滤，但 source pipeline review 尚未确认具体上游路径。

## 7. Sample Protocol

Sample protocol 定义样本怎么切。

区块二只定义切片，不定义通过阈值。

### 7.1 `sandbox_v1`

`sandbox_v1` 保持快速开发定位：

```text
sample_protocol_id = "sandbox_v1"
dataset_id = "sandbox_v1"
purpose = "快速开发和 smoke test"
split_policy = "single_full_sample"
```

规则：

- 使用完整 dataset 日期范围。
- 不做 OOS。
- 不做 walk-forward。
- 继续支持当前 evaluate / smoke run。

### 7.2 `mining_v1`

`mining_v1` 用于严肃挖因子。

第一版建议协议：

```text
sample_protocol_id = "mining_v1"
purpose = "严肃挖因子评价"
split_policy = "time_ordered_oos_and_walk_forward"
forward_return_definition = "next_open_to_open_v1"
```

必须固化：

- formation window：用于样本内观察和初筛。
- validation window：用于调试 gate 和稳定性判断。
- OOS window：用于最终样本外检验。
- walk-forward windows：多个固定滚动窗口，每个窗口包含 formation 和 validation 两段。

具体日期必须写进协议配置或 manifest，不能由 candidate 或单次 run 临时决定。

### 7.3 切片输出

样本切片建议输出为结构化对象：

```json
{
  "sample_protocol_id": "mining_v1",
  "slices": [
    {
      "slice_id": "formation",
      "role": "in_sample",
      "date_start": "YYYY-MM-DD",
      "date_end": "YYYY-MM-DD"
    },
    {
      "slice_id": "validation",
      "role": "validation",
      "date_start": "YYYY-MM-DD",
      "date_end": "YYYY-MM-DD"
    },
    {
      "slice_id": "oos",
      "role": "oos",
      "date_start": "YYYY-MM-DD",
      "date_end": "YYYY-MM-DD"
    },
    {
      "slice_id": "wf_001_formation",
      "role": "walk_forward_formation",
      "pair_id": "wf_001",
      "date_start": "YYYY-MM-DD",
      "date_end": "YYYY-MM-DD"
    },
    {
      "slice_id": "wf_001_validation",
      "role": "walk_forward_validation",
      "pair_id": "wf_001",
      "date_start": "YYYY-MM-DD",
      "date_end": "YYYY-MM-DD"
    }
  ]
}
```

### 7.4 hash 和可复现

sample protocol 必须有稳定 hash：

```text
sample_protocol_hash = sha256(canonical_json(sample_protocol))
```

hash 输入包含：

- `sample_protocol_id`
- dataset 日期范围
- forward return 定义
- universe 名称
- 所有 sample slices 的起止日期和 role

同一 dataset + 同一 sample protocol 多次运行，必须生成完全一致的切片和 hash。

## 8. Run Manifest Integration

每次 evaluate 的 `runs/{run_id}/manifest.json` 需要记录：

```json
{
  "run_id": "batch_001",
  "experiment_id": "csi500_ohlcv_sandbox_v1",
  "dataset_id": "sandbox_v1",
  "dataset_manifest": {},
  "data_quality_report": "datasets/sandbox_v1/data_quality_report.json",
  "sample_protocol": {
    "sample_protocol_id": "sandbox_v1",
    "sample_protocol_hash": "sha256:...",
    "slices": []
  },
  "preprocess": {
    "winsorize_mad_scale": 5.0,
    "size_exposure": "log_market_cap"
  }
}
```

`sandbox_v1` 在第一版可以记录空 slices 或单个 full_sample slice。

`mining_v1` 必须记录 formation、validation、OOS 和 walk-forward slices。

## 9. 下游消费规则

metrics、diagnostics、gate 的关系如下：

```text
DatasetBundle
  -> SampleProtocol
  -> SampleSlices
  -> Metrics / Diagnostics
  -> Acceptance Gate
```

规则：

- metrics 不再私自决定日期范围。
- diagnostics 不再私自决定日期范围。
- gate 不再私自切 OOS 或 walk-forward，只消费区块二产出的切片结果。
- candidate JSONL 不允许出现 `date_start`、`date_end`、`universe`、`forward_return_definition`、`sample_protocol_id`。
- registry 和 acceptance report 后续必须能追溯到 `sample_protocol_hash`。

## 10. 建议工程模块

后续实现时建议新增：

```text
factor_autoresearch/data_quality.py
factor_autoresearch/sample_protocol.py
```

### 10.1 `data_quality.py`

职责：

- 读取固定 dataset。
- 执行 data quality checks。
- 输出 JSON / Markdown 报告。
- 给 prepare 或单独 CLI 使用。

建议 CLI：

```bash
uv run fm dataset check-quality --dataset datasets/sandbox_v1 --config configs/csi500_ohlcv_sandbox_v1.toml
```

### 10.2 `sample_protocol.py`

职责：

- 从 config 或 manifest 加载 sample protocol。
- 根据 dataset 交易日生成 slices。
- 输出 `sample_protocol_hash`。
- 给 evaluate、diagnostics、future gate 复用。

建议 CLI：

```bash
uv run fm dataset show-slices --dataset datasets/mining_v1 --sample-protocol mining_v1
```

## 11. 分工

### 11.1 数据源审查负责人

负责：

- 查看 zer0share 构造流程。
- 输出 source pipeline review 文档。
- 标注 universe、PIT、基础过滤、行业、市值、复权、交易日历的上游路径。
- 标注尚未确认的 PIT 风险。

交付物：

```text
docs/data/source-pipeline-review-zer0share-mining-v1.md
```

### 11.2 协议负责人

负责：

- 维护本 spec。
- 定义 `sandbox_v1` 与 `mining_v1` 的边界。
- 固化 manifest 字段和 sample protocol 字段。
- 固化 OOS / walk-forward 日期切片规则。

交付物：

```text
docs/framework/factor-autoresearch-data-sample-protocol-v1-spec.md
```

### 11.3 数据质量负责人

负责：

- 设计 data quality report。
- 定义 fail / warning 规则。
- 第一版只做 frozen dataset 入库验收，不逐条复算 zer0share 原始过滤。

交付物：

```text
datasets/{dataset_id}/data_quality_report.json
datasets/{dataset_id}/data_quality_report.md
```

### 11.4 工程集成负责人

负责：

- 新增 sample protocol 模块。
- 扩展 config。
- 扩展 run manifest。
- 保证 evaluate 阶段仍只读 fixed dataset。
- 保证现有 `sandbox_v1` 流程兼容。

交付物：

```text
factor_autoresearch/sample_protocol.py
factor_autoresearch/data_quality.py
tests/test_sample_protocol.py
tests/test_data_quality.py
```

### 11.5 测试验收负责人

负责：

- 覆盖 manifest 合同测试。
- 覆盖数据质量异常测试。
- 覆盖样本切片可复现测试。
- 覆盖 run manifest 追溯测试。
- 覆盖现有 `sandbox_v1` smoke run 不破坏。

交付物：

```text
uv run pytest -v
uv run fm factor evaluate --dataset datasets/sandbox_v1 --candidates candidate_factors/candidates.jsonl --run-id sample_protocol_v1_smoke
```

## 12. 实施顺序

建议按 6 个 patch group 推进：

1. 文档和协议
   - 新增本 spec。
   - 新增 source pipeline review 模板。
   - 在 roadmap 第二区块链接本 spec。

2. 数据质量报告
   - 新增 `data_quality.py`。
   - 新增 `fm dataset check-quality`。
   - 对 `sandbox_v1` 生成报告。

3. sample protocol 模块
   - 新增 `sample_protocol.py`。
   - 支持 `sandbox_v1` full sample。
   - 支持 `mining_v1` 固定日期切片。

4. config 和 manifest 集成
   - config 增加 sample protocol 字段。
   - run manifest 记录 sample protocol、hash、slices、quality report。

5. 下游接入
   - metrics / diagnostics 支持按 slice 计算。
   - 当前 gate 保持 in-sample 行为。
   - 区块三再新增 OOS / walk-forward gate。

6. 回归和验收
   - 确认 `sandbox_v1` 旧流程不破坏。
   - 确认同一协议切片 hash 稳定。
   - 确认 candidate 不能改变样本协议。

详细实施拆分见：

- `docs/plans/factor-autoresearch-data-sample-protocol-v1-implementation-plan.md`

## 13. 验收标准

区块二 v1 完成时必须满足：

- spec 能清楚回答数据从哪里来、zer0share 做了什么、`factor_autoresearch` 验收什么、哪些口径被固定、哪些事情不在本仓库重做。
- `sandbox_v1` 保持当前快速开发定位。
- `mining_v1` 明确用于严肃挖因子，并有固定 sample protocol。
- 每次 run 都能追溯 dataset、source universe key、基础过滤声明、forward return 定义、sample protocol、窗口切片和质量报告。
- 同一 dataset + 同一 sample protocol 多次生成的 OOS / walk-forward 切片完全一致。
- candidate 不能改变日期范围、股票池、forward return 或样本窗口。
- 区块三的 `oos_gate` 和 `walk_forward_gate` 可以直接消费区块二输出的样本切片。

## 14. 风险

主要风险：

- zer0share 的 PIT 假设没有完整记录，导致后续因子有效性难以解释。
- manifest 只记录字段名称，不记录上游 pipeline 版本，导致数据来源无法复核。
- OOS / walk-forward 由 gate 临时切片，造成不同模块口径不一致。
- forward return 定义后续被覆盖而不是新建版本，破坏历史 run 可比性。
- 数据质量报告只看字段存在，不看覆盖率和异常日期，导致坏数据进入严肃评价。

缓解方式：

- source pipeline review 先行。
- manifest 记录 source pipeline 和 review 文档。
- sample protocol hash 写入 run manifest。
- forward return 口径版本化。
- data quality report 同时输出机器可读 JSON 和人工可读 Markdown。

## 15. 最终定义

数据与样本协议 v1 的成功标准不是“多生成一份 parquet”，而是：

```text
source boundary clear                       # 来源边界清楚
dataset contract explicit                   # 数据合同明确
quality checked                             # 质量检查可追溯
sample slices reproducible                  # 样本切片可复现
run manifest auditable                      # 运行记录可审计
downstream gates share one protocol         # 后续 gate 共用同一协议
```

只有这些条件满足后，区块三的 OOS、walk-forward、稳健性 gate 才有可靠地基。
