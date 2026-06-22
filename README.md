# Factor Autoresearch

Deterministic sandbox tooling for the first CSI 500 daily OHLCV factor mining loop.

## Scope

- Build a fixed dataset from local `zer0share` data.
- Validate hand-written DSL candidates.
- Evaluate candidates with a reproducible pipeline.
- Write auditable run artifacts and append-only registry outputs.

## Main commands

```bash
uv run fm dataset prepare-fixed --config configs/csi500_ohlcv_sandbox_v1.toml --output datasets/sandbox_v1
uv run fm factor validate --dataset datasets/sandbox_v1 --candidates candidate_factors/candidates.jsonl --verbose
uv run fm factor evaluate --dataset datasets/sandbox_v1 --candidates candidate_factors/candidates.jsonl --run-id smoke_001 --verbose
uv run fm experiment clean --experiment-id csi500_ohlcv_sandbox_v1
```

## Layout

- `configs/`: experiment and gate config.
- `datasets/`: fixed read-only datasets for evaluation.
- `factor_autoresearch/`: package code.
- `candidate_factors/`: candidate input and registry output.
- `runs/`: per-run artifacts.
- `codex/`: orchestration notes for the research loop.
