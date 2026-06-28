# Factor Autoresearch Mining Agent 5a 雏形记录

## 1. 这份文档解决什么问题

这份文档先记录区块五的一个最小雏形：`Mining Agent 5a`。

它不是正式实现计划，也不是完整 Agent 挖掘闭环。它只把当前讨论中已经比较清楚的一件事固定下来：

```text
人给一个研究方向，
Mining Agent 围绕这个方向做 category mining，
通过轻量 evaluator 多轮迭代，
产出 Top K 候选，
再交给区块三的 acceptance gate。
```

这样后续真正做区块五时，不需要重新从概念开始讨论。

## 2. 当前定位

`Mining Agent 5a` 只做一件事：

- 围绕一个给定研究主题，组织并执行一个研究 batch。

它暂时不做：

- Manager Agent 自动选题。
- 多 batch 调度。
- Alpha101 / 论文因子批量导入。
- 因子库清理和 retired 管理。
- 自动改 gate 阈值。
- 自动改样本协议。

第一版先只支持一种 batch 类型：

```text
category_mining
```

## 3. 和区块三、区块四、区块五的关系

这件事横跨区块三、区块四、区块五，但第一版要拆小：

| 部分 | 最小职责 | 说明 |
|---|---|---|
| 区块三 3a | lightweight fitness + acceptance gate 合同 | 给候选打分快筛，并定义最终验收输出 |
| 区块四 4a | candidate pool + batch memory | 保存候选、评分、失败原因、Top K、batch 记录 |
| 区块五 5a | Mining Agent batch loop | 人给主题后，Agent 自主组织一轮 category mining |

推荐推进顺序：

```text
3a -> 4a -> 5a
```

但区块三不要做成孤立 gate 函数。它要服务后续 Mining Agent 的循环。

## 4. Baseline 流程

```text
人给研究主题
  -> Mining Agent 建 batch plan
  -> 读取已有记忆
  -> 生成候选
  -> lightweight evaluator 打分
  -> Agent 反思并改进
  -> 多轮迭代
  -> 产出 Top K
  -> acceptance gate
  -> 写入 candidate registry / watch / rejected
```

## 5. 输入是什么

第一版由人给一个大方向，例如：

```text
研究成交量冲击后的价格延迟反应。
```

Agent 拿到方向后，先把它整理成 batch plan，而不是直接生成公式。

batch plan 至少包括：

- `theme`：本轮研究主题。
- `hypothesis`：本轮核心研究假设。
- `sub_paths`：2 到 4 个子路径。
- `allowed_fields`：可用字段。
- `allowed_windows`：可用窗口。
- `avoid`：要避开的已知重复方向。
- `fitness_focus`：本轮更重视哪些评分项。
- `stop_rules`：本轮停止条件。

## 6. Mining Agent 在 batch 内做什么

每轮循环大致是：

1. 读取当前主题、上一轮反馈、已有候选和失败原因。
2. 提出若干候选公式。
3. 调用固定 evaluator 计算轻量 fitness。
4. 读取评分和失败原因。
5. 写一段结构化反思。
6. 决定下一轮是继续探索、收敛优化，还是停止。

Agent 的自由度在这里：

- 可以拆子路径。
- 可以生成公式。
- 可以根据失败原因调整下一轮。
- 可以选择继续探索或收敛。
- 可以提出下一批研究建议。

Agent 不能做：

- 改 gate 阈值。
- 改数据范围。
- 改样本切片。
- 跳过 evaluator。
- 直接写入 accepted registry。
- 看 final OOS 后回头改公式。

## 7. Lightweight fitness 的作用

轻量 fitness 是内循环筛选工具，不是正式入库判断。

第一版可以包含：

- coverage。
- RankIC。
- ICIR。
- 单调性。
- 复杂度惩罚。
- 粗相关去重。
- novelty，表示和已有候选是否足够不同。

它回答的问题是：

```text
这一批候选里，哪些值得进入深度验收？
```

它不回答：

```text
这个因子是否可以正式入库？
```

## 8. Acceptance gate 的作用

acceptance gate 只对 Top K 候选运行。

它负责更严格的问题：

- 是否有样本外证据。
- 是否滚动稳定。
- 是否只依赖某一年、某行业、某市值段。
- 是否和已有因子重复。
- 是否有增量信息。
- 是否具备基本交易可实现性。

第一版可以先保持轻量，但输出合同要预留这些字段。

## 9. 停止条件

第一版建议使用硬停止条件，不让 Agent 自己凭感觉停：

```text
max_rounds = 5
max_candidates = 100
no_improvement_rounds = 2
top_k = 10
```

后续可以扩展：

- 连续若干轮 Top score 没明显提升。
- 新候选重复率过高。
- 已经积累足够 acceptance queue。
- 失败原因反复集中在同一类。

## 10. Batch 产物

每个 batch 结束后，至少产出：

```text
batch_plan.md
round_logs.jsonl
all_candidates.jsonl
scored_candidates.jsonl
top_k.jsonl
failure_summary.md
acceptance_queue.jsonl
batch_summary.md
```

这些产物后续属于区块四的 candidate memory / research memory。

## 11. 反思记录要写什么

每轮反思要结构化，避免只有空泛总结。

至少记录：

- 哪些候选表现最好。
- 主要失败原因是什么。
- 哪些公式结构重复。
- 哪些字段或算子更有希望。
- 哪些方向下一轮不要再试。
- 下一轮应该探索还是收敛。

示例：

```text
本轮 volume shock 类候选覆盖率正常，但多数和已有 volume rank 家族高度相似。
下一轮应减少纯 volume rank，改为行业内 volume surprise + price delay 组合。
复杂度上限保持 12，不扩大窗口集合。
```

## 12. 第一版不做什么

为了避免第一版过重，暂时不做：

- `seed_import`。
- `variant_optimization`。
- `dedup_review`。
- Manager Agent。
- 自动主题调度。
- 多 Agent 并行挖掘。
- accepted / retired 因子全生命周期治理。

这些留给后续：

```text
5b / 4b / Manager Agent
```

## 13. 当前结论

`Mining Agent 5a` 的最小目标是：

```text
人给主题，
Agent 能围绕主题自主跑一个 category mining batch，
产出可复查 Top K，
并把结果交给 acceptance gate。
```

这件事跑通以后，系统才适合继续做 Manager Agent 和更复杂的因子资产库治理。
