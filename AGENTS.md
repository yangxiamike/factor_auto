# Compute v1 Guardrails

当改动涉及 `factor_autoresearch/compute_v1/**`、`factor_autoresearch/evaluate.py`、相关测试、文档、脚本或 CI 时，提交前先跑：

```bash
uv run python scripts/run_compute_v1_guardrails.py
```

规则：

- 只改测试、benchmark、diagnostics、runtime estimate、文档时：跑 guardrails。
- 改到 compute_v1 核心模块时：再跑 compute_v1 suite。
- 合并前或大改后：再跑 `uv run pytest -q`。

注意：

- 不要借机修改 IC、RankIC、gate、candidate DSL、forward return、universe 语义，也不要引入新 engine。
- guardrail 失败时，先判断是 schema、数值口径、benchmark 退化，还是环境波动；不要直接放宽测试。
