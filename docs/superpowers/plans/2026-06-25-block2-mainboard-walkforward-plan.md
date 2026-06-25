# 区块2主板 Walk-Forward 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把区块2从当前 `csi500 / 2024-2025` 小样本协议，推进到第一版正式挖因子使用的沪深主板 walk-forward 数据协议，并从 zer0share 准备出可用于挖因子的冻结 dataset。

**Architecture:** 样本协议配置负责切片规则，实验配置负责从 zer0share 读数和 prepare dataset；治理文档解释人类规则；source pipeline review 记录 zer0share 主板 universe 的来源、覆盖和风险；prepare 产物的 manifest 记录协议、质量报告和数据来源，保证后续因子结果可追溯。区块2不重写 zer0share 的股票池逻辑，只引用 zer0share 已存在的主板 universe。

**Tech Stack:** Python、TOML、Typer CLI、pytest、ruff、pandas/parquet、项目现有 dataset manifest 与 sample protocol 模块。

---

## 已确认口径

- `sample_protocol_id`：`mining_v1_mainboard_walkforward`
- 总样本定位：第一版正式挖因子的总历史窗口
- 正式评分窗口：`2014-01-01` 到 `2026-05-31`
- 预热窗口：`2013-01-01` 起，只用于长窗口因子计算，不进入评分
- 股票范围：沪深主板
- 股票池来源：zer0share 已存在主板 universe，区块2只引用，不自行构造
- 当前限制：zer0share 主板 universe 已有，但历史长度还不够，需要 source review 里显式记录
- 主评估方式：walk-forward
- 每折结构：5 年 formation + 20 个交易日 embargo gap + 1 年 test
- 2026-01-01 到 2026-05-31：final OOS，只报告，不用于调参
- TOML 字段保留英文，右侧加中文注释；管理性口号不写进 TOML 字段

## 文件结构

- Create: `configs/mining_v1_mainboard_walkforward.toml`
  - 第一版正式挖因子的样本协议配置，机器读取，右侧中文注释辅助人看懂。
- Create: `configs/mainboard_mining_v1.toml`
  - 第一版正式挖因子的 dataset prepare 配置，指向 zer0share 主板 universe。
- Modify: `docs/governance/block2-data-sample-protocol-governance.md`
  - 增加 `mining_v1_mainboard_walkforward` 的定位、使用规则和 final OOS 约束。
- Create: `docs/data/source-pipeline-review-mainboard-mining-v1.md`
  - 主板正式版 source pipeline review，不混入现有 csi500/sandbox 审查材料。
- Modify: `factor_autoresearch/config.py`
  - 支持实验配置记录 `warmup_start`、`sample_protocol_id` 和 `sample_protocol_config`。
- Modify: `factor_autoresearch/prepare.py`
  - 从 `warmup_start` 开始读取 zer0share 数据，manifest 写入样本协议和质量追溯字段。
- Modify: `factor_autoresearch/sample_protocol.py`
  - 支持从新的 TOML 生成 walk-forward slices、final OOS slice 和稳定 hash。
- Modify: `factor_autoresearch/cli.py`
  - 确认 `dataset show-slices --sample-protocol mining_v1_mainboard_walkforward` 可用。
- Modify: `tests/test_config.py`
  - 覆盖正式主板实验配置可加载。
- Modify: `tests/test_prepare.py`
  - 覆盖 warmup、sample protocol 和 manifest 追溯字段。
- Modify: `tests/test_sample_protocol.py`
  - 覆盖新协议切片、gap、final OOS 和 hash 稳定性。
- Modify: `tests/test_cli.py`
  - 覆盖 CLI 能展示新协议。

---

### Task 1: 新增主板 Walk-Forward 协议配置

**Files:**
- Create: `configs/mining_v1_mainboard_walkforward.toml`

- [ ] **Step 1: 新建协议配置**

写入以下内容。`source_universe_key` 先填 zer0share 里的真实主板 universe key；如果执行时还没拿到真实 key，先不要编造，停下确认。

```toml
sample_protocol_id = "mining_v1_mainboard_walkforward" # 样本协议名称，用来标识这套切片规则
purpose = "第一版正式挖因子"                            # 协议用途

date_start = "2014-01-01"                              # 正式评分开始日期
date_end = "2026-05-31"                                # 正式评分结束日期
warmup_start = "2013-01-01"                            # 预热期开始日期，只用于长窗口因子计算

universe = "mainboard"                                 # 股票池名称：沪深主板
source_universe_key = "<ZEROSHARE_MAINBOARD_KEY>"      # zer0share 里的主板股票池键名

formation_years = 5                                    # 每折用 5 年做形成期
test_years = 1                                         # 每折用 1 年做测试期
embargo_trading_days = 20                              # 形成期和测试期之间空 20 个交易日，防止未来收益泄漏
max_forward_horizon_days = 20                          # 当前最长未来收益周期是 20 日

final_oos_start = "2026-01-01"                         # 最终样本外开始日期，只报告
final_oos_end = "2026-05-31"                           # 最终样本外结束日期，只报告

tail_missing_policy = "expected_for_forward_returns"   # 尾部未来收益缺失属于预期现象
```

- [ ] **Step 2: 读取配置确认 TOML 可解析**

Run:

```bash
python - <<'PY'
from pathlib import Path
import tomllib

path = Path("configs/mining_v1_mainboard_walkforward.toml")
with path.open("rb") as handle:
    payload = tomllib.load(handle)
print(payload["sample_protocol_id"])
print(payload["date_start"], payload["date_end"])
PY
```

Expected:

```text
mining_v1_mainboard_walkforward
2014-01-01 2026-05-31
```

- [ ] **Step 3: 如果真实 `source_universe_key` 不确定，暂停**

不要把 `<ZEROSHARE_MAINBOARD_KEY>` 留进可运行配置。执行前必须替换成真实 key，或把配置标记为草案并避免代码默认读取。

---

### Task 2: 更新区块2治理文档

**Files:**
- Modify: `docs/governance/block2-data-sample-protocol-governance.md`

- [ ] **Step 1: 增加正式协议定位**

在 “sample protocol” 相关段落后补充：

```markdown
#### `mining_v1_mainboard_walkforward`

这是第一版正式挖因子的主样本协议。

- 正式评分窗口：`2014-01-01` 到 `2026-05-31`
- 预热期：从 `2013-01-01` 开始，只用于长窗口因子计算
- 股票范围：沪深主板
- 股票池来源：zer0share 已存在的主板 universe
- 评估方式：5 年 formation + 20 个交易日 embargo + 1 年 test 的 walk-forward
- final OOS：`2026-01-01` 到 `2026-05-31`，只报告，不用于调参

本仓不在区块2里重新实现主板 universe。主板股票池口径由 zer0share 负责，区块2只记录引用关系、样本切片和质量检查结果。
```

- [ ] **Step 2: 增加字段解释表**

在 manifest 或追溯相关段落补充：

```markdown
| 字段 | 中文解释 |
| --- | --- |
| `dataset_id` | 数据集名称，用来区分不同冻结数据 |
| `source_universe_key` | zer0share 里的股票池键名 |
| `sample_protocol_id` | 样本协议名称 |
| `sample_protocol_hash` | 样本协议指纹，用来确认切片规则没有变化 |
| `date_start` / `date_end` | 正式评分时间范围 |
| `warmup_start` | 预热期起点，只用于长窗口因子计算 |
| `forward_return_definition` | 未来收益定义 |
| `data_quality_report` | 数据质量报告路径或编号 |
```

- [ ] **Step 3: 检查文档不把管理口号写成机器字段**

确认文档说明 `final OOS 只报告`，但 TOML 不新增 `final_oos_policy` 这类字段。

---

### Task 3: 新建主板 Source Pipeline Review

**Files:**
- Create: `docs/data/source-pipeline-review-mainboard-mining-v1.md`

- [ ] **Step 1: 新建审查文档骨架**

写入：

```markdown
# Mainboard Mining v1 Source Pipeline Review

日期：2026-06-25

## 📌 结论

- `mining_v1_mainboard_walkforward` 面向第一版正式挖因子。
- 股票范围为沪深主板，股票池由 zer0share 已存在的主板 universe 提供。
- 本仓不重新构造主板 universe，只读取 zer0share 冻结后的结果。
- 当前已知限制：主板 universe 已存在，但历史长度还不够覆盖 `2013-01-01` 预热期到 `2026-05-31` 正式终点。
- 在覆盖长度补齐前，本协议可以先完成配置、文档和代码支持，但不能声明正式数据集已经封版。

## 🧩 本次审查范围

- `configs/mining_v1_mainboard_walkforward.toml`
- zer0share 主板 universe 的实际 key、路径和覆盖日期
- 本仓 dataset prepare / manifest / sample protocol / data quality 相关逻辑

## ✅ 已确认事项

- zer0share 已存在主板 universe。
- 区块2只引用主板 universe，不在本仓重写股票池构造。

## ⚠️ 待确认事项

1. zer0share 主板 universe 的真实 `source_universe_key`
2. 主板 universe 当前最早覆盖日期
3. 主板 universe 当前最新覆盖日期
4. 主板 universe 是否完整排除创业板、科创板、北交所
5. 主板 universe 的 ST、停牌、上市天数、流动性、市值等过滤是否已经在 zer0share 上游完成

## 👀 对 manifest 的建议

第一版正式数据集至少记录：

- `dataset_id`
- `source_universe_key`
- `sample_protocol_id`
- `sample_protocol_hash`
- `date_start`
- `date_end`
- `warmup_start`
- `forward_return_definition`
- `data_quality_report`

## 📌 当前 review 状态

```text
reviewed_with_open_risks
```

状态原因：主板 universe 已存在，但历史覆盖长度与具体 key 仍需要补齐和记录。
```

- [ ] **Step 2: 补真实证据路径**

执行时读取 zer0share 实际路径后，把真实 key、路径和日期覆盖写入文档。不要用猜测值。

---

### Task 4: 新增正式主板 Dataset Prepare 配置

**Files:**
- Create: `configs/mainboard_mining_v1.toml`
- Modify: `tests/test_config.py`

- [ ] **Step 1: 写配置加载测试**

在 `tests/test_config.py` 新增：

```python
def test_load_mainboard_mining_v1_config() -> None:
    config = load_experiment_config("configs/mainboard_mining_v1.toml")

    assert config.experiment_id == "mainboard_mining_v1"
    assert config.dataset_id == "mainboard_mining_v1"
    assert config.universe == "mainboard"
    assert config.date_start == "2014-01-01"
    assert config.date_end == "2026-05-31"
    assert config.warmup_start == "2013-01-01"
    assert config.sample_protocol_id == "mining_v1_mainboard_walkforward"
    assert config.sample_protocol_config == "configs/mining_v1_mainboard_walkforward.toml"
```

Run:

```bash
python -m pytest tests/test_config.py::test_load_mainboard_mining_v1_config -v
```

Expected: FAIL，因为配置和字段还不存在。

- [ ] **Step 2: 新建正式主板实验配置**

写入 `configs/mainboard_mining_v1.toml`。`source_universe_key` 必须替换成 zer0share 里的真实主板 key，不要保留占位符。

```toml
experiment_id = "mainboard_mining_v1"                  # 实验名称：第一版正式挖因子
dataset_id = "mainboard_mining_v1"                     # 冻结数据集名称
universe = "mainboard"                                 # 股票池名称：沪深主板
date_start = "2014-01-01"                              # 正式评分开始日期
date_end = "2026-05-31"                                # 正式评分结束日期
warmup_start = "2013-01-01"                            # 预热期开始日期，只用于长窗口因子计算
adjustment = "hfq"                                     # 后复权价格
forward_return_definition = "next_open_to_open_v1"     # 未来收益定义：下期开盘到未来开盘
sample_protocol_id = "mining_v1_mainboard_walkforward" # 样本协议名称
sample_protocol_config = "configs/mining_v1_mainboard_walkforward.toml" # 样本协议配置路径

allowed_fields = ["open_hfq", "high_hfq", "low_hfq", "close_hfq", "volume"]
allowed_functions = [
    "abs",
    "log",
    "delay",
    "ts_mean",
    "ts_std",
    "ts_delta",
    "ts_return",
    "ts_rank",
    "cs_rank",
    "cs_zscore",
]
allowed_windows = [1, 3, 5, 10, 20]
categories = ["momentum", "reversal", "volatility", "liquidity", "volume", "intraday", "gap"]
horizons = ["1d", "5d", "20d"]
features = ["open_hfq", "high_hfq", "low_hfq", "close_hfq", "volume"]
preprocess_exposures = ["industry", "market_cap"]

source = "zer0share"                                   # 数据来源
source_path = "C:/Users/hp/Documents/zer0share"        # zer0share 本地数据目录
source_universe_key = "<ZEROSHARE_MAINBOARD_KEY>"      # zer0share 里的主板股票池键名
industry_source = "sw_l1_name"                         # 行业口径：申万一级
base_filters_inherited = [
    "mainboard_membership",
    "st",
    "delisting",
    "suspension",
    "low_liquidity",
    "low_volume",
    "limit_up",
    "limit_down",
]
gate_config = "configs/candidate_gate_baseline_v0.toml"

[prepare]
price_start_buffer_days = 30
use_incremental_universe = true

[preprocess]
winsorize_mad_scale = 5.0
size_exposure = "log_market_cap"
```

- [ ] **Step 3: 扩展配置模型**

在 `factor_autoresearch/config.py` 的 `ExperimentConfig` 中新增字段：

```python
warmup_start: str | None
sample_protocol_id: str | None
sample_protocol_config: str | None
```

在 `load_experiment_config` 中读取：

```python
warmup_start=raw.get("warmup_start"),
sample_protocol_id=raw.get("sample_protocol_id"),
sample_protocol_config=raw.get("sample_protocol_config"),
```

旧配置没有这些字段时必须继续通过测试。

- [ ] **Step 4: 运行配置测试**

Run:

```bash
python -m pytest tests/test_config.py -v
```

Expected: PASS。

---

### Task 5: 让 Prepare 真正使用 Warmup 并写入追溯字段

**Files:**
- Modify: `factor_autoresearch/prepare.py`
- Modify: `tests/test_prepare.py`

- [ ] **Step 1: 写 manifest 追溯测试**

在 `tests/test_prepare.py` 新增或扩展现有 fake zer0share 测试，构造带新字段的配置后断言：

```python
assert prepared.manifest["date_start"] == "2014-01-01"
assert prepared.manifest["date_end"] == "2026-05-31"
assert prepared.manifest["warmup_start"] == "2013-01-01"
assert prepared.manifest["sample_protocol_id"] == "mining_v1_mainboard_walkforward"
assert prepared.manifest["sample_protocol_config"] == "configs/mining_v1_mainboard_walkforward.toml"
assert "sample_protocol_hash" in prepared.manifest
assert prepared.manifest["data_quality_report"] == "data_quality_report.json"
```

如果 fake dataset 不方便覆盖 2013-2026 的真实日期，可以用短日期 fixture，但字段语义必须保持一致。

Run:

```bash
python -m pytest tests/test_prepare.py -v
```

Expected: FAIL，直到 prepare 写入新字段。

- [ ] **Step 2: 从 warmup 起点读取 zer0share 数据**

在 `prepare_fixed_dataset` 中把读取起点改为：

```python
read_start = config.warmup_start or config.date_start
start_date = _yyyymmdd(read_start)
end_date = _yyyymmdd(config.date_end)
```

manifest 中保留：

```python
"date_start": config.date_start,
"date_end": config.date_end,
"warmup_start": config.warmup_start,
```

这样 panel 可以包含 warmup 行，但正式评分窗口仍从 `date_start` 开始。

- [ ] **Step 3: 写入 sample protocol 追溯字段**

在 prepare 产出的 manifest 中加入：

```python
"sample_protocol_id": config.sample_protocol_id,
"sample_protocol_config": config.sample_protocol_config,
"sample_protocol_hash": protocol.sample_protocol_hash,
"data_quality_report": "data_quality_report.json",
```

实现时可以在 prepare 内调用 `build_sample_protocol`，也可以先在准备完成后由专门函数写入；但最终 manifest 必须能追溯到协议 hash。

- [ ] **Step 4: 更新 README 输出**

在 dataset `README.md` 中增加：

```text
- warmup_start: 2013-01-01
- sample_protocol_id: mining_v1_mainboard_walkforward
- sample_protocol_hash: sha256:实际协议指纹
- data_quality_report: data_quality_report.json
```

- [ ] **Step 5: 运行 prepare 测试**

Run:

```bash
python -m pytest tests/test_prepare.py -v
```

Expected: PASS。

---

### Task 6: 执行 zer0share 到正式主板 Dataset 的准备链路

**Files:**
- Runtime output: `datasets/mainboard_mining_v1/`
- Modify if needed: `docs/data/source-pipeline-review-mainboard-mining-v1.md`

- [ ] **Step 1: 检查 zer0share 主板 universe 覆盖范围**

用真实 `source_universe_key` 检查：

```bash
python - <<'PY'
from pathlib import Path

source = Path("C:/Users/hp/Documents/zer0share/data/stock/universe/name=<ZEROSHARE_MAINBOARD_KEY>")
parts = sorted(source.glob("date=*/data.parquet"))
print("partitions", len(parts))
if parts:
    dates = [p.parent.name.removeprefix("date=") for p in parts]
    print("first", min(dates))
    print("last", max(dates))
PY
```

Expected: 覆盖至少到 `2013-01-01` 之后的 warmup 起点，并尽量覆盖到 `2026-05-31`。如果长度不够，停止并把 blocker 写进 source review。

- [ ] **Step 2: 运行 prepare**

Run:

```bash
python -m factor_autoresearch.cli dataset prepare-fixed configs/mainboard_mining_v1.toml datasets/mainboard_mining_v1
```

Expected:

```text
dataset_id: mainboard_mining_v1
```

并生成：

```text
datasets/mainboard_mining_v1/panel.parquet
datasets/mainboard_mining_v1/forward_returns.parquet
datasets/mainboard_mining_v1/manifest.json
datasets/mainboard_mining_v1/README.md
```

- [ ] **Step 3: 运行 data quality**

Run:

```bash
python -m factor_autoresearch.cli dataset check-quality datasets/mainboard_mining_v1 --config configs/mainboard_mining_v1.toml
```

Expected:

```text
overall_outcome 不是 fail
```

生成：

```text
datasets/mainboard_mining_v1/data_quality_report.json
datasets/mainboard_mining_v1/data_quality_report.md
```

- [ ] **Step 4: 展示样本切片**

Run:

```bash
python -m factor_autoresearch.cli dataset show-slices datasets/mainboard_mining_v1 --sample-protocol mining_v1_mainboard_walkforward
```

Expected:

```text
包含 walk-forward slices 和 final_oos
```

- [ ] **Step 5: 更新 source review 状态**

把真实执行结果写进 `docs/data/source-pipeline-review-mainboard-mining-v1.md`：

- zer0share 主板 universe key
- universe 覆盖起止日期
- prepare 输出 dataset 路径
- data quality 总结
- 是否还有 open risk

---
### Task 7: 扩展 Sample Protocol 代码支持

**Files:**
- Modify: `factor_autoresearch/sample_protocol.py`
- Test: `tests/test_sample_protocol.py`

- [ ] **Step 1: 写失败测试，覆盖新协议**

在 `tests/test_sample_protocol.py` 新增测试：

```python
def test_build_sample_protocol_builds_mainboard_walkforward_slices(sample_dataset_dir) -> None:
    protocol = build_sample_protocol_from_dataset(
        sample_dataset_dir,
        sample_protocol_id="mining_v1_mainboard_walkforward",
    )

    assert protocol.sample_protocol_id == "mining_v1_mainboard_walkforward"
    assert protocol.dataset_date_range == {
        "date_start": "2014-01-01",
        "date_end": "2026-05-31",
    }
    assert protocol.rules["warmup_start"] == "2013-01-01"
    assert protocol.rules["formation_years"] == 5
    assert protocol.rules["test_years"] == 1
    assert protocol.rules["embargo_trading_days"] == 20
    assert protocol.rules["max_forward_horizon_days"] == 20

    slice_ids = [sample_slice.slice_id for sample_slice in protocol.slices]
    assert "wf_2020_formation" in slice_ids
    assert "wf_2020_test" in slice_ids
    assert "final_oos" in slice_ids
```

Run:

```bash
python -m pytest tests/test_sample_protocol.py::test_build_sample_protocol_builds_mainboard_walkforward_slices -v
```

Expected: FAIL，因为代码还不支持新协议。

- [ ] **Step 2: 增加协议常量和配置路径**

在 `factor_autoresearch/sample_protocol.py` 中扩展：

```python
SUPPORTED_SAMPLE_PROTOCOLS = {
    "sandbox_v1",
    "mining_v1",
    "mining_v1_mainboard_walkforward",
}

MAINBOARD_WALKFORWARD_PATH = (
    Path(__file__).resolve().parent.parent / "configs" / "mining_v1_mainboard_walkforward.toml"
)
```

- [ ] **Step 3: 在分发逻辑中接入新协议**

在 `build_sample_protocol` 中加入：

```python
if protocol_id == "mining_v1_mainboard_walkforward":
    return _build_mainboard_walkforward_protocol(manifest, normalized_dates)
```

- [ ] **Step 4: 实现配置读取和切片生成**

新增私有函数：

```python
def _build_mainboard_walkforward_protocol(
    manifest: Mapping[str, Any],
    trade_dates: list[str],
) -> SampleProtocol:
    draft = _load_toml_config(MAINBOARD_WALKFORWARD_PATH)
    # 读取 date_start/date_end/warmup_start/formation_years/test_years/embargo_trading_days/final_oos_start/final_oos_end
    # 用交易日序列定位每折 formation/test 边界
    # formation 结束日需要扣掉 embargo_trading_days
    # final_oos 单独生成 role="final_oos" 的 slice
    # 最后调用 _finalize_protocol 生成稳定 hash
```

实现时不要硬编码自然日切片后直接跳过交易日，必须用 `trade_dates` 中真实存在的交易日确定边界。

- [ ] **Step 5: 跑定向测试**

Run:

```bash
python -m pytest tests/test_sample_protocol.py -v
```

Expected: PASS。

---

### Task 8: 扩展 CLI 覆盖

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `factor_autoresearch/cli.py` if needed

- [ ] **Step 1: 写 CLI 测试**

在 `tests/test_cli.py` 新增：

```python
def test_cli_dataset_show_slices_outputs_mainboard_walkforward(sample_dataset_dir) -> None:
    result = runner.invoke(
        app,
        [
            "dataset",
            "show-slices",
            str(sample_dataset_dir),
            "--sample-protocol",
            "mining_v1_mainboard_walkforward",
        ],
    )

    assert result.exit_code == 0
    assert "mining_v1_mainboard_walkforward" in result.stdout
    assert "final_oos" in result.stdout
```

Run:

```bash
python -m pytest tests/test_cli.py::test_cli_dataset_show_slices_outputs_mainboard_walkforward -v
```

Expected: FAIL until Task 4 implementation is complete.

- [ ] **Step 2: 如 CLI 已透传 sample protocol，无需改代码**

当前 `dataset show-slices --sample-protocol` 已透传到 `build_sample_protocol_from_dataset`。如果测试通过，不要额外改 CLI。

- [ ] **Step 3: 跑 CLI 测试**

Run:

```bash
python -m pytest tests/test_cli.py -v
```

Expected: PASS。

---

### Task 9: Data Quality 和 Manifest 追溯规则

**Files:**
- Modify: `docs/governance/block2-data-sample-protocol-governance.md`
- Modify later: dataset manifest generation path, likely `factor_autoresearch/prepare.py`
- Test later: `tests/test_prepare.py` or dedicated manifest test

- [ ] **Step 1: 先文档化 manifest 字段**

在治理文档中明确第一版正式数据集至少要记录：

```text
dataset_id
source_universe_key
sample_protocol_id
sample_protocol_hash
date_start
date_end
warmup_start
forward_return_definition
data_quality_report
```

- [ ] **Step 2: 后续实现时写 manifest 测试**

当进入 prepare / manifest 代码改动时，新增测试断言：

```python
assert manifest["sample_protocol_id"] == "mining_v1_mainboard_walkforward"
assert manifest["warmup_start"] == "2013-01-01"
assert manifest["source_universe_key"] == expected_source_universe_key
assert manifest["data_quality_report"].endswith("data_quality_report.json")
```

- [ ] **Step 3: 明确尾部缺失规则**

在 data quality 文档或后续代码中确认：由于 `fwd_ret_20d` 需要未来 20 个交易日，样本末尾 forward return 缺失属于 expected missing，不应直接判 fail。

---

### Task 10: 验证和收口

**Files:**
- All changed files

- [ ] **Step 1: 运行区块2相关测试**

Run:

```bash
python -m pytest tests/test_sample_protocol.py tests/test_data_quality.py tests/test_cli.py -v
```

Expected: PASS。

- [ ] **Step 2: 运行 ruff**

Run:

```bash
ruff check factor_autoresearch/sample_protocol.py factor_autoresearch/data_quality.py factor_autoresearch/cli.py tests/test_sample_protocol.py tests/test_data_quality.py tests/test_cli.py
```

Expected: PASS。

- [ ] **Step 3: 如果改到 compute v1 或 evaluate，再跑 guardrails**

只有当实现碰到 `factor_autoresearch/compute_v1/**`、`factor_autoresearch/evaluate.py` 或 compute v1 测试时，运行：

```bash
python scripts/run_compute_v1_guardrails.py
```

Expected: PASS。

- [ ] **Step 4: 检查 git diff**

Run:

```bash
git status --short
git diff --stat
```

Expected: 只包含区块2主板 walk-forward 协议相关文件。

---

## 自检

- Spec coverage：计划覆盖样本协议配置、正式主板 prepare 配置、治理文档、source review、sample protocol 代码、prepare 数据生成、CLI、data quality/manifest 追溯和验证。
- Placeholder scan：唯一允许的占位符是 `<ZEROSHARE_MAINBOARD_KEY>`，且计划要求执行时必须替换或暂停确认；正式可运行配置不得保留该占位符。
- Type consistency：协议名统一为 `mining_v1_mainboard_walkforward`；日期统一为 `2014-01-01` 到 `2026-05-31`，预热期统一为 `2013-01-01`。
- Scope check：本计划不实现 zer0share 主板 universe，只引用并审查其覆盖；不把 `final_oos_policy` / `universe_policy` 这类管理口号写进 TOML 机器字段。


