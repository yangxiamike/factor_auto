# Repository Agent Rules

## 📌 Compute v1 Guardrails

当改动涉及下面任一范围时，提交前至少先跑一次 compute_v1 guardrails：

- `factor_autoresearch/compute_v1/**`
- `factor_autoresearch/evaluate.py`
- `tests/test_compute_v1_benchmark.py`
- `tests/test_compute_v1_equivalence.py`
- `tests/test_compute_v1_runtime_estimator.py`
- `docs/plans/factor-autoresearch-compute-v1-guardrails.md`
- `scripts/run_compute_v1_guardrails.py`
- compute_v1 相关 CI / 文档 / agent 规则

统一命令：

```bash
uv run python scripts/run_compute_v1_guardrails.py
```

## 🧩 默认执行规则

- 只改 compute_v1 相关测试、benchmark、diagnostics、runtime estimate、文档时：先跑 guardrails。
- 改到 compute_v1 核心模块时：在 guardrails 之外，再跑 compute_v1 suite。
- 准备合并大改或发版前：再跑一次 `uv run pytest -q`。

## ⚠️ 边界提醒

compute_v1 guardrails 只做护栏，不代表可以顺手改语义。

没有明确计划时，不要借机修改：

- IC / RankIC 定义
- gate 语义
- candidate DSL
- forward return 口径
- universe 语义
- 新 engine 引入

如果 guardrail 失败，先判断是：

- 报告字段 / schema 漂移
- diagnostics 数值口径漂移
- benchmark 分类退化
- 环境波动导致的偶发变化

不要第一反应就放宽测试或修改核心语义。
