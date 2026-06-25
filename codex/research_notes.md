# Research Notes

Use the template below for each evaluated batch.

## Batch {run_id}

### 1. 本轮目标
- 说明这轮要验证的研究方向和想回答的问题。

### 2. 候选来源
- 上一轮延伸
- 人工假设
- 经典因子改写
- 失败候选修正

### 3. 结果总览
- evaluated:
- passed:
- failed:
- invalid:
- error:

### 4. 通过共性
- 通过候选集中在哪些 category / horizon / direction / complexity 区间。

### 5. 失败归因
- 按 `failed_rules` 汇总主要失败原因。

### 6. 体检观察
- 结合 diagnostics 记录 year / industry / horizon 上的稳定和不稳定现象。

### 7. 下一轮路径
- 继续扩什么
- 停止什么
- 变异什么

### 8. Memory 判断
- Decision: `no_update` / `watch` / `propose_memory_update`
- Evidence runs:
- Reusable insight:
- Why this is not just a one-run observation:
- Diagnostics caveat:
- Next confirmation test:
- Suggested memory entry:

判断口径：
- `no_update`: 单轮观察、单候选结果、配置/数据/gate 变化导致不可比、或 diagnostics 仍显示明显 year / industry 依赖。
- `watch`: 至少两轮出现相近信号，但还缺一次 clean run、稳定性体检或可复用假设验证。
- `propose_memory_update`: 至少三轮可比结果支持同一结论，或两轮可比结果加一次 diagnostics 复核支持同一稳定模式；结论必须能指导未来候选生成，而不是记录流水账。
