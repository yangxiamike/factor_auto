# Program

## Agent Research Protocol v0

1. Read the current experiment spec, `codex/memory.md`, `codex/research_notes.md`, the latest run summary, diagnostics, and candidate registry before proposing a new batch.
2. Append new candidates to `candidate_factors/candidates.jsonl`. Do not rewrite existing candidate history.
3. Run `fm factor validate`.
4. Run `fm factor evaluate`.
5. Read `runs/{run_id}/summary.md`, `runs/{run_id}/results/diagnostics.parquet`, `runs/{run_id}/results/candidate_results.jsonl`, and `runs/{run_id}/logs/evaluate.log`.
6. Update `codex/research_notes.md` with the current batch template and explicit pass/fail attribution.
7. Fill the Memory Decision section in `codex/research_notes.md` with one of three decisions: `no_update`, `watch`, or `propose_memory_update`.
8. Propose a `codex/memory.md` update only when the conclusion passes the Memory Decision Rubric below.

## Allowed

- Read experiment spec, summary, diagnostics, and registry artifacts.
- Append candidates to `candidate_factors/candidates.jsonl`.
- Run validate and evaluate.
- Update `codex/research_notes.md`.
- Recommend a `codex/memory.md` update only after multi-run stability is clear.

## Forbidden

- Do not modify evaluator, gate, dataset, config, preprocess, or forward return definitions during research execution.
- Do not write directly to `candidate_factors/registry.jsonl`.
- Do not write one-run observations into `codex/memory.md`.

## Memory Decision Rubric v0

Use this rubric at the end of every batch. The default decision is `no_update`.

### no_update

Use `no_update` when any of these are true:

- The observation comes from only one run.
- The run changed gate, config, dataset, preprocess, forward return, or candidate construction too much to compare with earlier runs.
- The result is about one candidate only, not a reusable research direction.
- The evidence is mainly a score/rank table without a clear causal research hypothesis.
- Diagnostics show strong year or industry concentration that has not been retested.

### watch

Use `watch` when the signal is promising but not mature enough for memory:

- The same category, transform, horizon, or direction appears useful in at least two comparable runs, but one important check is still weak.
- A family repeatedly gets close to gate, but has not passed or is unstable across year or industry slices.
- Directional metrics improve after a methodological fix, but the research implication still needs another clean run.

The notes entry must state the exact follow-up test that would promote or reject the observation.

### propose_memory_update

Use `propose_memory_update` only when all conditions are met:

- At least three comparable runs support the same conclusion, or two comparable runs plus one diagnostics review show the same stable pattern.
- The conclusion is about a reusable search-space rule, not a single candidate.
- The evidence includes the relevant horizon, expected direction, and failure/pass pattern.
- Diagnostics do not show an unresolved one-year or one-industry dependency.
- The proposed memory text is short, actionable, and phrased as guidance for future candidate generation.

### Memory Update Format

When proposing a memory update, write this in `codex/research_notes.md` first:

```text
Decision: propose_memory_update
Evidence runs: run_a, run_b, run_c
Reusable insight:
Suggested memory entry:
Open caveat:
```

Only after review should the stable insight be added to `codex/memory.md`.
