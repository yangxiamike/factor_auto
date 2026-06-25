# Compute V1 Guardrails Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 Compute Engine v1 增加轻量护栏，防止后续 OOS（out-of-sample，样本外检验）和 walk-forward（滚动前推验证）改造时出现性能退化、诊断口径跑偏或成本不可控。

**Architecture:** 不改 `compute_v1` 核心计算语义，不引入 Polars / DuckDB / 新引擎。只在现有 benchmark、diagnostics、测试和文档层增加外层护栏；普通 `fm factor evaluate` 主链路保持现在结构。

**Tech Stack:** Python, pandas, NumPy, pytest, Parquet artifacts, existing `factor_autoresearch.compute_v1` modules.

---

## 文件结构

- Modify: `tests/test_compute_v1_benchmark.py`
  - 增加 benchmark report 字段和 classification 的回归测试。
  - 不跑完整主板压力测试，只用已有小 fixture，避免测试变慢。
- Modify: `tests/test_compute_v1_equivalence.py`
  - 增加 diagnostics 等价的非空表用例，防止 schema 和数值口径未来跑偏。
- Create: `factor_autoresearch/compute_v1/runtime_estimator.py`
  - 提供 OOS / walk-forward 成本估算的纯函数。
  - 不参与正式 evaluate，只用于报告和测试。
- Create: `tests/test_compute_v1_runtime_estimator.py`
  - 覆盖 20-30 candidates、OOS multiplier、walk-forward windows 的成本估算。
- Create: `docs/plans/factor-autoresearch-compute-v1-guardrails.md`
  - 中文说明护栏边界、复杂度红线和后续执行策略。

## Task 1: Benchmark Regression Guard

**Files:**
- Modify: `tests/test_compute_v1_benchmark.py`

- [ ] **Step 1: Read current benchmark tests**

Run:

```bash
python -m pytest tests/test_compute_v1_benchmark.py -q
```

Expected: current benchmark tests pass.

- [ ] **Step 2: Add classification guard test**

Append this test to `tests/test_compute_v1_benchmark.py`:

```python
def test_benchmark_report_keeps_compute_v1_green_classification(sample_dataset_dir, test_config, tmp_path) -> None:
    from factor_autoresearch.candidates import Candidate
    from factor_autoresearch.context import EvaluationContext
    from factor_autoresearch.evaluate import Evaluator

    candidates_path = tmp_path / "candidates.jsonl"
    candidate = Candidate(
        candidate_id="fa_benchmark_guard",
        name="benchmark guard",
        expression="cs_rank((close_hfq - open_hfq) / open_hfq)",
        expected_direction="positive",
        hypothesis="benchmark guard",
        category="intraday",
        lookback_days=1,
        created_at="2026-06-25",
        notes="benchmark guard",
    )
    candidates_path.write_text(
        __import__("json").dumps(candidate.as_dict(), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    context = EvaluationContext(
        config=test_config,
        dataset_path=sample_dataset_dir,
        candidates_path=candidates_path,
        run_id="benchmark_guard",
        output_root=tmp_path / "runs",
        registry_path=tmp_path / "registry.jsonl",
        engine="v1",
        jobs="1",
    )
    Evaluator(context).evaluate_batch()
    report = __import__("json").loads((context.run_dir / "benchmark.json").read_text(encoding="utf-8"))

    assert report["engine"] == "v1"
    assert report["jobs"] == "1"
    assert report["candidate_count"] == 1
    assert report["total_seconds"] >= 0.0
    assert report["calculate_seconds"] >= 0.0
    assert report["preprocess_seconds"] >= 0.0
    assert report["metrics_seconds"] >= 0.0
    assert report["artifact_seconds"] >= 0.0
    assert report["projected_seconds_10y_30c"] >= 0.0
    assert report["classification"] in {"strong_green", "green", "yellow", "red"}
    assert report["classification"] in {"strong_green", "green"}
```

- [ ] **Step 3: Run focused test**

Run:

```bash
python -m pytest tests/test_compute_v1_benchmark.py -q
```

Expected: all tests in `test_compute_v1_benchmark.py` pass.

- [ ] **Step 4: Check runtime cost**

Run:

```bash
python -m pytest tests/test_compute_v1_benchmark.py --durations=5 -q
```

Expected: no single benchmark guard test takes more than a few seconds on the fixture dataset.

## Task 2: Diagnostics Equivalence Guard

**Files:**
- Modify: `tests/test_compute_v1_equivalence.py`

- [ ] **Step 1: Add non-empty diagnostics equivalence test**

Append this test to `tests/test_compute_v1_equivalence.py`:

```python
def test_compare_equivalence_checks_non_empty_diagnostics_values() -> None:
    results = _results()
    metrics, ic_series = _frames()
    legacy_diagnostics = pd.DataFrame(
        [
            {
                "table_name": "daily_summary_table",
                "candidate_id": "fa_1",
                "horizon": "1d",
                "coverage_mean": 0.91,
                "ic_mean": 0.031,
                "rankic_mean": 0.042,
            }
        ]
    )
    v1_diagnostics = legacy_diagnostics.copy()
    v1_diagnostics.loc[0, "rankic_mean"] = 0.0424

    report = compare_equivalence(
        legacy_results=results,
        v1_results=results,
        legacy_metrics=metrics,
        v1_metrics=metrics.copy(),
        legacy_ic_series=ic_series,
        v1_ic_series=ic_series.copy(),
        legacy_diagnostics=legacy_diagnostics,
        v1_diagnostics=v1_diagnostics,
        float_tolerance=0.001,
    )

    assert report.matches is True
    assert report.diagnostics.matches is True


def test_compare_equivalence_fails_non_empty_diagnostics_outside_tolerance() -> None:
    results = _results()
    metrics, ic_series = _frames()
    legacy_diagnostics = pd.DataFrame(
        [
            {
                "table_name": "daily_summary_table",
                "candidate_id": "fa_1",
                "horizon": "1d",
                "coverage_mean": 0.91,
                "ic_mean": 0.031,
                "rankic_mean": 0.042,
            }
        ]
    )
    v1_diagnostics = legacy_diagnostics.copy()
    v1_diagnostics.loc[0, "rankic_mean"] = 0.052

    report = compare_equivalence(
        legacy_results=results,
        v1_results=results,
        legacy_metrics=metrics,
        v1_metrics=metrics.copy(),
        legacy_ic_series=ic_series,
        v1_ic_series=ic_series.copy(),
        legacy_diagnostics=legacy_diagnostics,
        v1_diagnostics=v1_diagnostics,
        float_tolerance=0.001,
    )

    assert report.matches is False
    assert report.diagnostics.matches is False
    assert report.diagnostics.diffs[0].column == "rankic_mean"
```

- [ ] **Step 2: Run focused test**

Run:

```bash
python -m pytest tests/test_compute_v1_equivalence.py -q
```

Expected: diagnostics equivalence tests pass and fail in the intended places.

## Task 3: Runtime Estimator

**Files:**
- Create: `factor_autoresearch/compute_v1/runtime_estimator.py`
- Create: `tests/test_compute_v1_runtime_estimator.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_compute_v1_runtime_estimator.py`:

```python
from factor_autoresearch.compute_v1.runtime_estimator import (
    RuntimeEstimate,
    estimate_mining_runtime,
)


def test_estimate_mining_runtime_scales_candidate_and_year_count() -> None:
    estimate = estimate_mining_runtime(
        baseline_seconds=54.654126,
        baseline_trade_days=485,
        baseline_candidates=30,
        target_years=10,
        target_candidates=30,
    )

    assert isinstance(estimate, RuntimeEstimate)
    assert estimate.projected_seconds == 283.976079
    assert estimate.projected_minutes == 4.733
    assert estimate.classification == "strong_green"
    assert estimate.should_trigger_optimization_loop is False


def test_estimate_mining_runtime_accounts_for_oos_and_walk_forward() -> None:
    estimate = estimate_mining_runtime(
        baseline_seconds=54.654126,
        baseline_trade_days=485,
        baseline_candidates=30,
        target_years=10,
        target_candidates=30,
        oos_multiplier=1.3,
        walk_forward_windows=3,
    )

    assert estimate.projected_seconds == 1107.506708
    assert estimate.projected_minutes == 18.458
    assert estimate.classification == "yellow"
    assert estimate.should_trigger_optimization_loop is True


def test_estimate_mining_runtime_rejects_invalid_inputs() -> None:
    for kwargs in (
        {"baseline_seconds": 0},
        {"baseline_trade_days": 0},
        {"baseline_candidates": 0},
        {"target_years": 0},
        {"target_candidates": 0},
        {"oos_multiplier": 0},
        {"walk_forward_windows": 0},
    ):
        base = {
            "baseline_seconds": 54.654126,
            "baseline_trade_days": 485,
            "baseline_candidates": 30,
            "target_years": 10,
            "target_candidates": 30,
        }
        base.update(kwargs)
        try:
            estimate_mining_runtime(**base)
        except ValueError as exc:
            assert "must be positive" in str(exc)
        else:
            raise AssertionError("expected ValueError")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_compute_v1_runtime_estimator.py -q
```

Expected: FAIL because `factor_autoresearch.compute_v1.runtime_estimator` does not exist.

- [ ] **Step 3: Implement estimator**

Create `factor_autoresearch/compute_v1/runtime_estimator.py`:

```python
"""Runtime cost estimates for compute_v1 mining workflows."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeEstimate:
    """Projected runtime summary for a target mining workload."""

    projected_seconds: float
    projected_minutes: float
    classification: str
    should_trigger_optimization_loop: bool


def estimate_mining_runtime(
    *,
    baseline_seconds: float,
    baseline_trade_days: int,
    baseline_candidates: int,
    target_years: int,
    target_candidates: int,
    trading_days_per_year: int = 252,
    oos_multiplier: float = 1.0,
    walk_forward_windows: int = 1,
) -> RuntimeEstimate:
    """Estimate full evaluation cost from a measured benchmark."""

    numeric_inputs = {
        "baseline_seconds": baseline_seconds,
        "baseline_trade_days": baseline_trade_days,
        "baseline_candidates": baseline_candidates,
        "target_years": target_years,
        "target_candidates": target_candidates,
        "trading_days_per_year": trading_days_per_year,
        "oos_multiplier": oos_multiplier,
        "walk_forward_windows": walk_forward_windows,
    }
    for name, value in numeric_inputs.items():
        if value <= 0:
            raise ValueError(f"{name} must be positive")

    seconds_per_candidate_day = baseline_seconds / (baseline_trade_days * baseline_candidates)
    projected_seconds = (
        seconds_per_candidate_day
        * trading_days_per_year
        * target_years
        * target_candidates
        * oos_multiplier
        * walk_forward_windows
    )
    rounded_seconds = round(projected_seconds, 6)
    classification = _classify_runtime(rounded_seconds)
    return RuntimeEstimate(
        projected_seconds=rounded_seconds,
        projected_minutes=round(rounded_seconds / 60.0, 3),
        classification=classification,
        should_trigger_optimization_loop=classification not in {"strong_green", "green"},
    )


def _classify_runtime(projected_seconds: float) -> str:
    if projected_seconds <= 300.0:
        return "strong_green"
    if projected_seconds <= 600.0:
        return "green"
    if projected_seconds <= 1200.0:
        return "yellow"
    return "red"
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
python -m pytest tests/test_compute_v1_runtime_estimator.py -q
```

Expected: all estimator tests pass.

## Task 4: Guardrail Documentation

**Files:**
- Create: `docs/plans/factor-autoresearch-compute-v1-guardrails.md`

- [ ] **Step 1: Create Chinese guardrail note**

Create `docs/plans/factor-autoresearch-compute-v1-guardrails.md`:

```markdown
# Compute Engine v1 护栏计划

## 📌 结论

当前每轮 20-30 个 candidates 的规模下，不继续做性能大改。

本阶段只补三类护栏：

- benchmark regression（性能回归检查）
- diagnostics equivalence（诊断口径等价）
- OOS / walk-forward runtime estimate（样本外和滚动验证成本估算）

## 🧩 边界

不做：

- 不引入 Polars / DuckDB 作为计算主路径
- 不新增 engine
- 不修改 IC / RankIC / gate / forward return / universe 语义
- 不把 OOS / walk-forward 混入 compute_v1 核心

## 📊 当前基线

主板压力测试基线：

- baseline_seconds: 54.654126
- baseline_trade_days: 485
- baseline_candidates: 30
- projected 10年 x 30 candidates: 283.976079 秒
- classification: strong_green

## 🔧 后续策略

OOS 和 walk-forward 作为评价外层处理：

```text
factor values
 -> full sample metrics/gate
 -> OOS metrics/gate
 -> walk-forward slice metrics/gate
```

因子原始值尽量复用，slice 级 metrics 和 gate 单独计算。

## ⚠️ 复杂度红线

如果某个方案需要：

- 新增一套 engine
- 修改 candidate DSL
- 修改指标定义
- 让普通 evaluate 命令增加大量参数
- 让 summary 无法扫读

则视为过度复杂，先不做。
```

- [ ] **Step 2: Verify docs are readable**

Run:

```bash
python -m pytest tests/test_compute_v1_benchmark.py tests/test_compute_v1_equivalence.py tests/test_compute_v1_runtime_estimator.py -q
```

Expected: tests pass.

## Task 5: Final Verification

**Files:**
- No new files beyond tasks above.

- [ ] **Step 1: Run focused guardrail tests**

Run:

```bash
python -m pytest tests/test_compute_v1_benchmark.py tests/test_compute_v1_equivalence.py tests/test_compute_v1_runtime_estimator.py -q
```

Expected: all focused guardrail tests pass.

- [ ] **Step 2: Run compute_v1 suite**

Run:

```bash
python -m pytest tests/test_compute_v1_calculator.py tests/test_compute_v1_preprocess.py tests/test_compute_v1_metrics.py tests/test_compute_v1_metrics_backends.py tests/test_compute_v1_parallel.py tests/test_compute_v1_panel.py tests/test_compute_v1_kernels.py tests/test_compute_v1_equivalence.py tests/test_compute_v1_benchmark.py tests/test_compute_v1_runtime_estimator.py -q
```

Expected: compute_v1 tests pass.

- [ ] **Step 3: Run full test suite**

Run:

```bash
python -m pytest -q
```

Expected: full test suite passes.

- [ ] **Step 4: Commit implementation**

Run:

```bash
git status --short
git add factor_autoresearch/compute_v1/runtime_estimator.py tests/test_compute_v1_benchmark.py tests/test_compute_v1_equivalence.py tests/test_compute_v1_runtime_estimator.py docs/plans/factor-autoresearch-compute-v1-guardrails.md
git commit -m "test: add compute v1 guardrails"
```

Expected: commit succeeds with only guardrail code, tests, and docs.

## 自检

- ✅ 覆盖 benchmark 门槛、diagnostics 等价、OOS / walk-forward 成本估算。
- ✅ 不引入 Polars / DuckDB / 新 engine。
- ✅ 不改 IC、RankIC、gate、DSL、forward return、universe。
- ✅ 每个任务都有明确文件、测试命令和验收结果。
