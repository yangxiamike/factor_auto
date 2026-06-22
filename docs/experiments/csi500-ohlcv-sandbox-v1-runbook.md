# CSI 500 OHLCV Sandbox v1 Runbook

1. Read `docs/experiments/factor-autoresearch-sandbox-v1.md`.
2. Read `codex/memory.md` and `codex/research_notes.md`.
3. Append 30 new candidates to `candidate_factors/candidates.jsonl`.
4. Run `uv run fm factor validate --dataset datasets/sandbox_v1 --candidates candidate_factors/candidates.jsonl --verbose`.
5. Run `uv run fm factor evaluate --dataset datasets/sandbox_v1 --candidates candidate_factors/candidates.jsonl --run-id <run_id> --verbose`.
6. Read `runs/<run_id>/summary.md`.
7. If the run fails, read `runs/<run_id>/logs/evaluate.log`.
8. If you need a clean slate, run `uv run fm experiment clean --experiment-id csi500_ohlcv_sandbox_v1 --yes`.
9. Update `codex/research_notes.md`.
10. Update `codex/memory.md` only after repeated stable insight.
